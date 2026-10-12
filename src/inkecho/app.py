"""Qt/asyncio orchestration; all text delivery passes through TaskController."""

import asyncio
import time
from collections.abc import Awaitable

from PySide6.QtCore import QObject, QTimer, Signal

from inkecho.audio import Recorder
from inkecho.config import ConfigStore
from inkecho.core import Failure, State, TaskController
from inkecho.platform.accessibility import AccessibilityInput, InputUnavailable
from inkecho.providers import ProviderClient, ProviderError
from inkecho.security import CredentialError, SecretStore

STATE_LABELS = {
    State.IDLE: "准备就绪",
    State.RECORDING: "正在聆听",
    State.TRANSCRIBING: "正在转写",
    State.POLISHING: "正在润色",
    State.INJECTING: "正在输入",
    State.SUCCEEDED: "已输入到目标",
    State.FAILED: "本次任务失败",
    State.CANCELLED: "已取消",
}
ERROR_LABELS = {
    Failure.TARGET: "未找到可安全输入的目标。请先聚焦可编辑文本框。",
    Failure.FOCUS: "目标焦点或光标已变化，本次输入已取消。",
    Failure.TIMEOUT: "任务超时，请缩短录音后重试。",
    Failure.AUDIO: "录音失败，请检查麦克风及音频设置。",
    Failure.TRANSCRIPTION: "转写失败，请检查服务配置、网络和账户权限。",
    Failure.POLISHING: "润色失败，当前已关闭原文回退。",
    Failure.EMPTY: "服务没有返回有效文字。",
    Failure.INJECTION: "目标无法安全接收文字，未使用剪贴板回退。",
}
PROVIDER_LABELS = {
    "configuration": "服务配置或请求参数不正确。",
    "credentials": "请保存有效 API 密钥。",
    "authentication": "服务拒绝了密钥或账户权限。",
    "rate_limit": "服务限流或额度不足。",
    "model": "当前模型不支持此请求，请检查模型 ID 与能力。",
    "unavailable": "云端服务暂时不可用。",
    "network": "无法连接云端服务，请检查网络。",
    "timeout": "云端服务响应超时。",
    "response": "云端返回了无法解析的结果。",
    "empty": "云端没有返回有效文字。",
    "audio": "录音格式或大小不符合服务要求。",
}


def current_task():
    try:
        return asyncio.current_task()
    except RuntimeError:
        return None


class Session(QObject):
    status = Signal(str)
    state_changed = Signal(str)
    level = Signal(float)
    finished = Signal(dict)
    diagnostic = Signal(str)
    problem = Signal(str)

    def __init__(
        self, store=None, *, inputs=None, recorder=None, client=None, secrets=None
    ):
        super().__init__()
        self.store = store or ConfigStore()
        self.inputs = inputs or AccessibilityInput(self._focus_lost)
        self.inputs.on_focus_lost = self._focus_lost
        self.recorder = recorder or Recorder(self)
        self.client = client or ProviderClient()
        self.secrets = secrets
        self.controller = TaskController(self, on_state=self._state)
        self.pending: set[asyncio.Task] = set()
        self.ui_tasks: set[asyncio.Task] = set()
        self.epoch = 0
        self.preparing = False
        self.captured_preparation = False
        self.testing = False
        self.connected = False
        self.last_toggle = 0.0
        self.metrics = {}
        self.keys = {}
        self.task_context = None
        self.settings = self.store.load_settings()
        self.recorder.level.connect(self.level)
        self.recorder.finished.connect(self._recorded)
        self.recorder.failed.connect(self._audio_failed)
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.controller.tick)
        self.timer.start()

    def spawn(self, operation: Awaitable) -> asyncio.Task:
        task = asyncio.create_task(operation)
        self.pending.add(task)
        task.add_done_callback(self.pending.discard)
        return task

    def spawn_ui(self, operation: Awaitable) -> asyncio.Task:
        task = asyncio.create_task(operation)
        self.ui_tasks.add(task)
        task.add_done_callback(self.ui_tasks.discard)
        return task

    async def initialize(self):
        try:
            await self.inputs.connect()
            self.connected = True
        except InputUnavailable:
            self.diagnostic.emit("desktop_unavailable")
            self.report_problem("系统输入服务暂不可用，设置与麦克风测试仍可使用。")

    def report_problem(self, message: str) -> None:
        self.status.emit(message)
        self.problem.emit(message)

    def active(self, task_id: str) -> bool:
        return bool(self.controller.task and self.controller.task.id == task_id)

    def provider_client(self, role: str, settings=None):
        if type(self.client) is ProviderClient:
            settings = settings or self.store.load_settings()
            return ProviderClient(
                timeout_seconds=getattr(settings, role + "_timeout_seconds"),
                http=self.client.http,
            )
        return self.client

    async def key(self, reference: str) -> str:
        def read():
            if self.secrets is None:
                self.secrets = SecretStore()
            return self.secrets.get(reference)

        value = await asyncio.to_thread(read)
        if not value:
            raise CredentialError("请先在服务设置中保存 API 密钥。")
        return value

    async def save_key(self, reference: str, value: str | None) -> None:
        def save():
            if self.secrets is None:
                self.secrets = SecretStore()
            if value is None:
                self.secrets.delete(reference)
            else:
                self.secrets.set(reference, value)

        await asyncio.to_thread(save)

    def target_is_current(self, target) -> bool:
        return self.inputs.target_is_current(target)

    def inject(self, task_id, target, text, can_continue) -> None:
        async def deliver():
            try:
                await self.inputs.inject(target, text, can_continue)
                if can_continue():
                    self.metrics["characters"] = len(text)
                    self.controller.injection_finished(task_id)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.controller.injection_failed(task_id)

        self.spawn(deliver())

    def _state(self, state: State) -> None:
        self.state_changed.emit(state.value)
        if state == State.IDLE:
            return
        message = ERROR_LABELS.get(self.controller.failure, STATE_LABELS[state])
        if state == State.FAILED:
            self.diagnostic.emit(self.controller.failure.value)
            self.report_problem(message)
        else:
            self.status.emit(message)
        if state in {State.SUCCEEDED, State.FAILED, State.CANCELLED}:
            self.epoch += 1
            self.preparing = False
            self.recorder.cancel()
            current = current_task()
            for task in list(self.pending):
                if task is not current:
                    task.cancel()
            self.keys.clear()
            self.task_context = None
            self.finished.emit({"outcome": state.value, **self.metrics})
            self.metrics = {}

    def _focus_lost(self):
        if self.preparing and self.captured_preparation:
            self.cancel()
        self.controller.focus_changed()

    def cancel(self):
        self.epoch += 1
        self.preparing = False
        self.captured_preparation = False
        self.recorder.cancel()
        self.controller.cancel()
        current = current_task()
        for task in list(self.pending):
            if task is not current:
                task.cancel()
        self.keys.clear()
        self.task_context = None
        self.status.emit("已取消，迟到结果不会继续输入。")

    async def toggle(self, *, delay: float = 0) -> None:
        now = time.monotonic()
        if now - self.last_toggle < 0.35:
            return
        self.last_toggle = now
        if self.controller.state == State.RECORDING:
            self.recorder.stop()
            return
        if self.controller.task or self.preparing or self.testing:
            self.status.emit("当前任务正在处理，请等待或取消。")
            return
        self.preparing = True
        self.captured_preparation = False
        self.epoch += 1
        epoch = self.epoch
        try:
            self.settings = self.store.load_settings()
            transcription = self.store.load_provider(
                self.settings.transcription_provider
            )
            polishing = None
            prompt = None
            if self.settings.polishing_enabled:
                polishing = self.store.load_provider(self.settings.polishing_provider)
                prompt = self.store.load_prompt(self.settings.prompt)
            context = {
                "transcription": transcription,
                "polishing": polishing,
                "prompt": prompt,
                "transcription_client": self.provider_client(
                    "transcription", self.settings
                ),
                "polishing_client": self.provider_client("polishing", self.settings),
            }
            if not transcription.model:
                raise CredentialError("请先选择转写模型并保存 API 密钥。")
            if delay:
                self.status.emit("请切换到要输入的文本框，即将开始录音。")
                await asyncio.sleep(delay)
            if epoch != self.epoch:
                return
            if not self.connected:
                await self.initialize()
                if epoch != self.epoch:
                    return
                if not self.connected:
                    return
            target = await self.inputs.capture_target()
            if epoch != self.epoch:
                return
            self.captured_preparation = True
            key = await self.key(transcription.key_ref)
            if epoch != self.epoch:
                return
            self.keys = {"transcription": key}
            if self.settings.polishing_enabled:
                try:
                    polish_key = await self.key(polishing.key_ref)
                    if epoch != self.epoch:
                        return
                    self.keys["polishing"] = polish_key
                except CredentialError:
                    if epoch != self.epoch:
                        return
                    if not self.settings.polishing_fallback:
                        raise
            if epoch != self.epoch:
                return
            self.controller.polish = self.settings.polishing_enabled
            self.controller.fallback = self.settings.polishing_fallback
            self.controller.timeout_seconds = (
                self.settings.recording_limit_seconds
                + self.settings.transcription_timeout_seconds
                + self.settings.polishing_timeout_seconds
                + 15
            )
            task_id = self.controller.begin(target)
            if task_id:
                self.task_context = context
                self.metrics = {"audio_seconds": 0.0, "characters": 0}
                device = (
                    bytes.fromhex(self.settings.microphone)
                    if self.settings.microphone
                    else None
                )
                if not self.recorder.start(
                    device,
                    sample_rate=self.settings.sample_rate,
                    max_seconds=self.settings.recording_limit_seconds,
                ):
                    self.controller.fail(task_id, Failure.AUDIO)
        except asyncio.CancelledError:
            raise
        except InputUnavailable:
            if epoch != self.epoch:
                return
            self.diagnostic.emit("desktop_unavailable")
            self.report_problem(
                "未找到可安全输入的文本框。请先点击文本编辑器的正文区域，"
                "再按快捷键；当前控件也可能缺少可编辑辅助功能接口。"
                "Wayland 逐目标输入仍属实验性支持；浏览器和终端可能无法使用。"
            )
        except CredentialError as error:
            if epoch != self.epoch:
                return
            self.diagnostic.emit("credentials_unavailable")
            self.report_problem(str(error))
        except Exception:
            if epoch != self.epoch:
                return
            if self.controller.task:
                self.controller.fail(self.controller.task.id, Failure.AUDIO)
            self.diagnostic.emit("configuration_invalid")
            self.report_problem("无法开始录音，请检查配置与系统服务。")
        finally:
            if epoch == self.epoch:
                self.preparing = False
                self.captured_preparation = False
                if not self.controller.task:
                    self.keys.clear()

    def _audio_failed(self, _reason):
        if self.controller.task:
            self.controller.fail(self.controller.task.id, Failure.AUDIO)

    def _recorded(self, audio: bytes, duration: float):
        task = self.controller.task
        if task and self.controller.recording_stopped(task.id):
            self.metrics["audio_seconds"] = duration
            self.spawn(self._process(task.id, audio))

    async def _process(self, task_id: str, audio: bytes):
        if not self.active(task_id):
            return
        context = self.task_context
        started = time.monotonic()
        self.metrics["transcription_calls"] = 1
        try:
            result = await context["transcription_client"].transcribe(
                context["transcription"], self.keys["transcription"], audio
            )
            if not self.active(task_id):
                return
            self.metrics["transcription_seconds"] = time.monotonic() - started
            self.controller.transcribed(task_id, result.text)
            if self.controller.task is None or self.controller.task.id != task_id:
                return
            if self.controller.state != State.POLISHING:
                return
            started = time.monotonic()
            try:
                key = self.keys.get("polishing")
                if not key:
                    raise CredentialError("No polishing credential")
                self.metrics["polishing_calls"] = 1
                polished = await context["polishing_client"].polish(
                    context["polishing"], key, result.text, context["prompt"].body
                )
                if not self.active(task_id):
                    return
                self.metrics["polishing_seconds"] = time.monotonic() - started
                self.metrics["usage"] = polished.usage
                self.controller.polished(task_id, polished.text)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                if not self.active(task_id):
                    return
                self.metrics["polishing_seconds"] = time.monotonic() - started
                self.controller.polishing_failed(task_id)
                if isinstance(error, ProviderError):
                    self.diagnostic.emit(error.code)
                    self.status.emit(
                        PROVIDER_LABELS[error.code]
                        + (
                            " 已按设置使用原文。"
                            if self.settings.polishing_fallback
                            else ""
                        )
                    )
        except asyncio.CancelledError:
            raise
        except Exception as error:
            if not self.active(task_id):
                return
            self.metrics["transcription_seconds"] = time.monotonic() - started
            self.controller.fail(task_id, Failure.TRANSCRIPTION)
            if isinstance(error, ProviderError):
                self.diagnostic.emit(error.code)
                self.report_problem(PROVIDER_LABELS[error.code])

    async def sample_audio(self, seconds: float = 3) -> bytes:
        if self.testing or self.preparing or self.controller.task:
            raise RuntimeError("请先结束当前录音任务。")
        self.testing = True
        recorder = Recorder(self)
        recorder.level.connect(self.level)
        future = asyncio.get_running_loop().create_future()
        recorder.finished.connect(
            lambda data, _seconds: not future.done() and future.set_result(data)
        )
        recorder.failed.connect(
            lambda _reason: (
                not future.done()
                and future.set_exception(RuntimeError("麦克风测试失败。"))
            )
        )
        try:
            settings = self.store.load_settings()
            device = bytes.fromhex(settings.microphone) if settings.microphone else None
            if not recorder.start(
                device, sample_rate=settings.sample_rate, max_seconds=seconds + 2
            ):
                raise RuntimeError("麦克风不可用或不支持当前采样率。")
            await asyncio.sleep(seconds)
            recorder.stop()
            return await asyncio.wait_for(future, 2)
        finally:
            recorder.cancel()
            recorder.deleteLater()
            self.testing = False

    async def close(self):
        self.cancel()
        current = current_task()
        for task in list(self.ui_tasks):
            if task is not current:
                task.cancel()
        await asyncio.gather(
            *(t for t in self.pending | self.ui_tasks if t is not current),
            return_exceptions=True,
        )
        self.timer.stop()
        self.inputs.close()
