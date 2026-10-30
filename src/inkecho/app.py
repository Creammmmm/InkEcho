"""Qt/asyncio orchestration; all text delivery passes through TaskController."""

import asyncio
import time
from collections.abc import Awaitable

from PySide6.QtCore import QObject, QTimer, Signal

from inkecho.audio import Recorder
from inkecho.config import ConfigStore
from inkecho.core import Failure, State, TaskController
from inkecho.performance import TaskTiming
from inkecho.platform.ibus_owned_default import DefaultAutoOutputRouter as OutputRouter
from inkecho.platform.keyboard import KeyboardError
from inkecho.platform.wayland_keyboard import keyboard_for_desktop
from inkecho.providers import ProviderClient, ProviderError, validate_provider_protocol
from inkecho.realtime import (
    MAX_FEED_BYTES,
    QwenRealtimeSession,
)
from inkecho.security import CredentialError, FileCredentialStore
from inkecho.streaming_output import StreamingOutput, TextDelta
from inkecho.text_units import UNSENT_NEIGHBOR_ROUTE

STATE_LABELS = {
    State.IDLE: "准备就绪",
    State.RECORDING: "正在聆听",
    State.TRANSCRIBING: "正在转写",
    State.POLISHING: "正在润色",
    State.INJECTING: "正在输入",
    State.SUCCEEDED: "已尝试发送文字",
    State.UNCONFIRMED: (
        "已尝试发送全部文字，接收结果无法确认；请检查光标位置，未自动重试。"
    ),
    State.FAILED: "本次任务失败",
    State.CANCELLED: "已取消",
}
ERROR_LABELS = {
    Failure.TIMEOUT: "任务超时，请缩短录音后重试。",
    Failure.AUDIO: "录音失败，请检查麦克风及音频设置。",
    Failure.TRANSCRIPTION: "转写失败，请检查服务配置、网络和账户权限。",
    Failure.POLISHING: "润色未完成；未继续输入或重放原文。",
    Failure.EMPTY: "服务没有返回有效文字。",
    Failure.INJECTION: "键盘输入未完成，未使用剪贴板回退。",
}
PROVIDER_LABELS = {
    "protocol": (
        "当前连接方式与模型能力或协议不匹配。"
        "请选择所选供应商支持的语音识别模型与对应转写方式。"
        "文件任务协议尚未实现。"
    ),
    "configuration": "服务配置或请求参数不正确。",
    "credentials": "请保存有效 API 密钥。",
    "authentication": "服务拒绝了密钥或账户权限。",
    "rate_limit": "服务限流或额度不足。",
    "model": "当前模型不支持此请求，请检查模型 ID 与能力。",
    "unavailable": "云端服务暂时不可用，请稍后重试；若持续失败，请检查模型与服务地址。",
    "network": "无法连接云端服务，请检查网络。",
    "timeout": "云端服务响应超时。",
    "response": "云端返回了无法解析的结果。",
    "empty": "云端没有返回有效文字。",
    "audio": "录音格式或大小不符合服务要求。",
}
KEYBOARD_LABELS = {
    "unsupported_compositor": (
        "当前 GNOME Wayland 缺少 Unicode 键盘映射接口。Ubuntu 24.04 / GNOME 46 "
        "请在登录界面选择「Ubuntu on Xorg」；程序不会自动更改系统会话。"
    ),
    "display_unavailable": "无法连接桌面的键盘输入服务。请检查桌面会话。",
    "unsupported_target": (
        "当前窗口或桌面环境暂不支持此键盘输入方式。"
        "请尝试兼容的 X11 / XWayland 应用，或检查输入方式设置。"
    ),
    "mapping_changed": "输入期间键盘布局发生变化，已停止剩余输入；未自动重试。",
    "permission_required": "请先在「输入与兼容性」中启用键盘输入。",
    "permission_denied": "系统未允许键盘输入。请重新启用并在系统提示中允许。",
    "portal_unavailable": "当前桌面没有可用的键盘输入服务。请检查桌面环境支持。",
    "session_closed": "键盘输入连接已断开。请重新启用键盘输入。",
    "injection_failed": "键盘输入未完成，未使用剪贴板回退。",
    "partial_input_failed": "部分文字已尝试输入，剩余内容未能完成，请检查目标位置。",
    "input_capability_unknown": (
        "无法确认当前输入目标或输入法状态，已停止输入，未自动切换或重试。"
    ),
    "input_cancelled": "输入已停止，不会继续发送剩余文字。",
    "unsupported_text": "结果含有当前键盘输入方式不支持的字符。",
    "busy": "键盘输入服务正在处理其他操作，请稍后重试。",
    "keys_held": "请松开键盘上按住的键，再重新尝试输入。",
    "caps_lock": "请关闭大写锁定，再重新尝试输入。",
    "cleanup_pending": "键盘布局尚未恢复，输入已暂停。请先松开所有按键并稍候。",
    "unsupported_layout": "当前键盘布局没有可用的兼容键位，暂时无法使用此输入方式。",
    "fcitx_unavailable": "Fcitx5 输入桥未安装或未运行，无法使用所选输入方式。",
    "ibus_target_unavailable": (
        "新版 GNOME IBus 方式只适用于兼容的原生 Wayland 控件。"
        "当前目标不可用或已变化，已停止；未切换其他方式，也不会重放已尝试的文字。"
    ),
    "ibus_unavailable": "IBus 实验性扩展未启用或不可用，请选择键盘输入。",
    "ibus_upgrade_required": (
        "IBus 扩展仍在运行旧协议。请停用并卸载旧扩展，安装匹配版本后重新登录桌面加载；"
        "本次未自动重试。"
    ),
    "ibus_authorization_failed": "IBus 扩展未接受本次输入任务，请检查扩展状态后重试。",
    "ibus_permission_denied": "IBus 无法创建任务凭证，请检查用户运行目录权限。",
    "ibus_untrusted_owner": "IBus 扩展服务的身份无法确认，已停止输入。",
    "fcitx_authorization_failed": "Fcitx5 输入桥未接受任务，请检查状态和权限。",
    "fcitx_permission_denied": "Fcitx5 输入桥缺少当前任务所需权限。",
    "fcitx_untrusted_owner": "Fcitx5 输入桥服务的身份无法确认，已停止输入。",
    "fcitx_owner_changed": "Fcitx5 服务发生变化，已停止输入，未自动重试。",
    "ibus_delivery_unknown": (
        "IBus 已尝试输入，但无法确认目标是否收到；请检查光标位置，未自动重试。"
    ),
    "ibus_cancelled": "输入已停止，不会继续发送剩余文字。",
    "ibus_unsupported_text": "IBus 实验性输入暂不支持结果中的控制字符。",
    "fcitx_ambiguous_target": "输入法报告了多个焦点，无法确定接收位置；已停止输入。",
    "fcitx_composition_guard_unavailable": (
        "当前 Fcitx5 输入桥版本过旧，缺少组词保护；请更新输入桥并重新启动输入法。"
    ),
    "fcitx_composition_active": (
        "输入法仍在组词或处理输入，已停止发送；请先完成当前输入。"
    ),
    "fcitx_linefeed_protocol_unavailable": (
        "当前运行的 Fcitx5 输入桥不支持安全换行批次，请启用新版输入桥。"
        "已停止输入，未自动重试。"
    ),
    "fcitx_unsupported_text": "Fcitx5 无法安全提交这段文字，已停止输入，未自动补发。",
    "fcitx_no_target": "当前没有可确定的输入目标，已停止输入，未自动重试。",
    "fcitx_delivery_unknown": "输入结果无法确认，已停止输入，未自动重试。",
    "fcitx_cancelled": "输入已停止，不会继续发送剩余文字。",
    "fcitx_expired": "输入任务已超时，剩余文字不会继续发送。",
}

AUDIO_LABELS = {
    "microphone_unavailable": "所选麦克风当前不可用，请刷新设备并重新选择。",
    "audio_format_unsupported": "麦克风不支持当前采样率，请在录音设置中调整。",
    "microphone_start_failed": "无法启动麦克风，请检查系统音频服务与设备权限。",
    "microphone_interrupted": "麦克风录音已中断，请检查设备连接后重试。",
    "empty_recording": "未收到有效录音数据，请检查麦克风输入后重试。",
    "recording_timed_out": "录音已达到最长时限，本次录音已丢弃；请缩短录音后重试。",
    "audio_failed": ERROR_LABELS[Failure.AUDIO],
}


class AudioError(RuntimeError):
    """Only fixed recorder codes and safe, actionable messages cross the UI boundary."""

    def __init__(self, reason):
        self.code = (
            reason
            if isinstance(reason, str) and reason in AUDIO_LABELS
            else "audio_failed"
        )
        super().__init__(AUDIO_LABELS[self.code])


def current_task():
    try:
        return asyncio.current_task()
    except RuntimeError:
        return None


class InputMaintenanceBusy(RuntimeError):
    """An input integration change cannot run during another task."""


class Session(QObject):
    status = Signal(str)
    state_changed = Signal(str)
    preview = Signal(str)
    level = Signal(float)
    capture_ready = Signal(bool)
    finished = Signal(dict)
    performance = Signal(dict)
    diagnostic = Signal(str)
    problem = Signal(str)

    def __init__(
        self,
        store=None,
        *,
        inputs=None,
        recorder=None,
        client=None,
        secrets=None,
        realtime_factory=QwenRealtimeSession,
    ):
        super().__init__()
        self.store = store or ConfigStore()
        self.inputs = (
            inputs if inputs is not None else OutputRouter(keyboard_for_desktop())
        )
        configure_diagnostics = getattr(self.inputs, "set_diagnostic_handler", None)
        if callable(configure_diagnostics):
            configure_diagnostics(self.diagnostic.emit)
        configure_mapping_wait = getattr(self.inputs, "set_mapping_wait_reader", None)
        if callable(configure_mapping_wait):
            configure_mapping_wait(lambda: self.settings.x11_mapping_wait_ms / 1000)
        configure_feedback_timeout = getattr(
            self.inputs, "set_feedback_timeout_reader", None
        )
        if callable(configure_feedback_timeout):
            configure_feedback_timeout(
                lambda: self.settings.x11_feedback_timeout_ms / 1000
            )
        configure_receiver_wait = getattr(
            self.inputs, "set_receiver_feedback_wait_reader", None
        )
        if callable(configure_receiver_wait):
            configure_receiver_wait(
                lambda: self.settings.receiver_feedback_wait_ms / 1000
            )
        self.input_maintenance_lock = asyncio.Lock()
        self.input_maintenance_active = False
        self.input_maintenance_tasks: set[asyncio.Task] = set()
        self.authorization_lock = asyncio.Lock()
        self.authorization_task = None
        self.recorder = recorder or Recorder(self)
        self.client = client or ProviderClient()
        self.realtime_factory = realtime_factory
        self.secrets = (
            secrets if secrets is not None else FileCredentialStore(self.store.root)
        )
        self.controller = TaskController(self, on_state=self._state)
        self.pending: set[asyncio.Task] = set()
        self.cleanup_tasks: set[asyncio.Task] = set()
        self.ui_tasks: set[asyncio.Task] = set()
        self.epoch = 0
        self.preparing = False
        self.testing = False
        self.connected = False
        self.last_toggle = 0.0
        self.metrics = {}
        self.output_metrics_task_id = None
        self._fallback_reprepare_task_id = None
        self.task_timing = None
        self.timing_task_id = None
        self.last_performance = None
        self.keys = {}
        self.task_context = None
        self.audio_failure = None
        self.input_failure = None
        self.settings = self.store.load_settings()
        self.recorder.level.connect(self.level)
        if hasattr(self.recorder, "capturing"):
            self.recorder.capturing.connect(self._capture_ready)
        self.recorder.finished.connect(self._recorded)
        self.recorder.failed.connect(self._audio_failed)
        if hasattr(self.recorder, "pcm_ready"):
            self.recorder.pcm_ready.connect(self._pcm_ready)
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.controller.tick)
        self.timer.start()

    @property
    def connected(self):
        return bool(getattr(self.inputs, "connected", self._connected))

    @connected.setter
    def connected(self, value):
        self._connected = value

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

    async def run_input_maintenance(self, operation):
        """Serialize changes; a worker survives caller cancellation."""
        state = {"started": False}

        async def run():
            async with self.input_maintenance_lock:
                if (
                    self.controller.task
                    or self.preparing
                    or self.testing
                    or self.authorization_lock.locked()
                ):
                    raise InputMaintenanceBusy()
                state["started"] = True
                self.input_maintenance_active = True
                try:
                    return await asyncio.to_thread(operation)
                finally:
                    self.input_maintenance_active = False

        task = asyncio.create_task(run())
        self.input_maintenance_tasks.add(task)

        def completed(done):
            self.input_maintenance_tasks.discard(done)
            if not done.cancelled():
                done.exception()

        task.add_done_callback(completed)
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            if not state["started"]:
                task.cancel()
            raise

    def _close_realtime(self, context) -> None:
        if not context or context.get("realtime_closing"):
            return
        completed = context.get("asr_completed_result")
        if completed is not None and not completed.done():
            completed.cancel()
        connection = context.get("realtime")
        if connection is not None:
            context["realtime_closing"] = True
            task = self.spawn(connection.aclose())
            self.cleanup_tasks.add(task)
            task.add_done_callback(self.cleanup_tasks.discard)

    async def initialize(self):
        try:
            await self.inputs.connect()
            self.connected = True
        except KeyboardError as error:
            self.input_problem(error)

    def report_problem(self, message: str) -> None:
        self.status.emit(message)
        self.problem.emit(message)

    def active(self, task_id: str) -> bool:
        return bool(self.controller.task and self.controller.task.id == task_id)

    def provider_client(self, role: str, settings=None):
        if type(self.client) is ProviderClient:
            settings = settings or self.store.load_settings()
            return self.client.with_timeout(
                getattr(settings, role + "_timeout_seconds")
            )
        return self.client

    async def key(self, reference: str) -> str:
        def read():
            return self.secrets.get(reference)

        value = await asyncio.to_thread(read)
        if not value:
            raise CredentialError(
                "当前配置目录未保存此供应商凭据。请重新填写并保存；旧版凭据不会自动迁移。"
            )
        return value

    async def save_key(self, reference: str, value: str | None) -> None:
        def save():
            if value is None:
                self.secrets.delete(reference)
            else:
                self.secrets.set(reference, value)

        await asyncio.to_thread(save)

    def input_problem(self, error: KeyboardError) -> None:
        code = error.code if error.code in KEYBOARD_LABELS else "injection_failed"
        self.diagnostic.emit(code)
        self.report_problem(KEYBOARD_LABELS[code])

    async def authorize_input(self, output_method=None) -> bool:
        """Only explicit recording or the enable action may request OS consent."""
        if self.input_maintenance_active:
            return False
        epoch = self.epoch
        async with self.authorization_lock:
            if epoch != self.epoch:
                return False
            self.authorization_task = current_task()
            try:
                prepare = getattr(self.inputs, "prepare_task", None)
                if callable(prepare):
                    if self.cleanup_tasks:
                        await asyncio.gather(
                            *tuple(self.cleanup_tasks), return_exceptions=True
                        )
                    if epoch != self.epoch:
                        return False

                    def notify_keyboard_authorization():
                        self.status.emit(
                            "录音已开始，正在启用键盘输入；请允许系统授权提示。"
                            if self.controller.state == State.RECORDING
                            else "正在启用键盘输入；如出现系统授权提示，请允许。"
                        )

                    selected_mode = (
                        output_method or self.store.load_settings().output_method
                    )
                    # The explicit enable action prepares the keyboard fallback.
                    # Recording tasks still defer auto selection until output.
                    prepare_mode = (
                        "keyboard"
                        if output_method is None and selected_mode == "auto"
                        else selected_mode
                    )
                    await prepare(
                        prepare_mode,
                        on_keyboard_authorization=notify_keyboard_authorization,
                    )
                    if epoch != self.epoch:
                        await self.inputs.discard_task()
                        return False
                    if output_method is None:
                        await self.inputs.discard_task()
                    return True
                if not self.connected:
                    await self.initialize()
                if not self.connected or epoch != self.epoch:
                    return False
                if not self.inputs.authorized:
                    self.status.emit(
                        "录音已开始，正在启用键盘输入；请允许系统授权提示。"
                        if self.controller.state == State.RECORDING
                        else "正在启用键盘输入；如出现系统授权提示，请允许。"
                    )
                    await self.inputs.authorize()
                return self.inputs.authorized and epoch == self.epoch
            except asyncio.CancelledError:
                if epoch != self.epoch:
                    return False
                raise
            except KeyboardError as error:
                if epoch == self.epoch:
                    self.input_problem(error)
                return False
            finally:
                self.authorization_task = None

    def mark_timing(self, task_id: str, event: str, *, at: float | None = None) -> None:
        """Ignore callbacks from finished/replaced tasks without retaining text."""
        if (
            self.active(task_id)
            and self.timing_task_id == task_id
            and self.task_timing is not None
        ):
            try:
                self.task_timing.mark(event, at=at)
            except ValueError:
                # Invalid observer metadata must not change delivery or its result.
                return

    def _record_acknowledged_attempts(self, error):
        # The input bridge acknowledges an attempt; this does not prove the
        # target received or displayed the characters. An uncertain
        # in-flight character is deliberately excluded.
        count = getattr(error, "acknowledged_attempts", 0)
        if type(count) is int and count >= 0:
            self.metrics["characters"] = max(self.metrics.get("characters", 0), count)

    def _snapshot_acknowledged_attempts(self):
        if (
            self.output_metrics_task_id != self.timing_task_id
            or not self.timing_task_id
        ):
            return
        count = getattr(self.inputs, "acknowledged_attempts", 0)
        if type(count) is int and count >= 0:
            self.metrics["characters"] = max(self.metrics.get("characters", 0), count)

    def inject(self, task_id, text, can_continue) -> None:
        async def deliver():
            try:
                task = self.controller.task
                if task is None or task.id != task_id:
                    return
                if self._fallback_reprepare_task_id == task_id:
                    self._fallback_reprepare_task_id = None
                    if not can_continue():
                        raise asyncio.CancelledError
                    prepare = getattr(self.inputs, "prepare_task", None)
                    if callable(prepare):
                        await prepare(self.settings.output_method)
                    if not can_continue():
                        raise asyncio.CancelledError
                options = {"deadline": task.deadline}
                if getattr(self.inputs, "supports_first_sent_callback", False):
                    options["on_first_sent"] = lambda sent_at=None: self.mark_timing(
                        task_id, "first_character_sent", at=sent_at
                    )
                self.output_metrics_task_id = task_id
                sent_characters = await self.inputs.insert(
                    text, can_continue, **options
                )
                if can_continue():
                    self.mark_timing(task_id, "output_completed")
                    self.metrics["characters"] = sent_characters
                    self.controller.injection_finished(task_id)
            except asyncio.CancelledError:
                raise
            except KeyboardError as error:
                if self.active(task_id):
                    self._record_acknowledged_attempts(error)
                    self.input_failure = error
                    if error.code == "ibus_delivery_unknown" and getattr(
                        error, "dispatch_complete", False
                    ):
                        self.mark_timing(task_id, "output_completed")
                        self.controller.injection_unconfirmed(task_id)
                    else:
                        self.controller.injection_failed(task_id)
            except Exception as error:
                if self.active(task_id):
                    self._record_acknowledged_attempts(error)
                self.controller.injection_failed(task_id)

        self.spawn(deliver())

    def _state(self, state: State) -> None:
        if state in {
            State.IDLE,
            State.RECORDING,
            State.SUCCEEDED,
            State.UNCONFIRMED,
            State.FAILED,
            State.CANCELLED,
        }:
            self.preview.emit("")
        empty = state == State.FAILED and self.controller.failure == Failure.EMPTY
        # No speech is a quiet completion, not a desktop error notification.
        self.state_changed.emit(State.IDLE.value if empty else state.value)
        if state == State.IDLE:
            return
        message = ERROR_LABELS.get(self.controller.failure, STATE_LABELS[state])
        if state == State.RECORDING and hasattr(self.recorder, "capturing"):
            message = "麦克风正在启动，请稍候。"
        if empty:
            self.status.emit("未识别到内容，本次已结束。")
        elif state == State.UNCONFIRMED:
            self.diagnostic.emit("ibus_delivery_unknown")
            self.status.emit(STATE_LABELS[state])
        elif state == State.FAILED:
            code = self.controller.failure.value
            credential_error = (self.task_context or {}).get("credential_error")
            if self.controller.failure == Failure.TRANSCRIPTION and credential_error:
                code, message = "credentials_unavailable", credential_error
            elif self.controller.failure == Failure.AUDIO and self.audio_failure:
                code, message = self.audio_failure.code, str(self.audio_failure)
            elif self.controller.failure == Failure.INJECTION and self.input_failure:
                code = (
                    self.input_failure.code
                    if self.input_failure.code in KEYBOARD_LABELS
                    else "injection_failed"
                )
                message = KEYBOARD_LABELS[code]
            self.diagnostic.emit(code)
            self.report_problem(message)
        else:
            self.status.emit(message)
        if state in {State.SUCCEEDED, State.UNCONFIRMED, State.FAILED, State.CANCELLED}:
            self.capture_ready.emit(False)
            self._snapshot_acknowledged_attempts()
            self.output_metrics_task_id = None
            if self.task_context and "asr_started" in self.task_context:
                self.metrics.setdefault(
                    "transcription_seconds",
                    time.monotonic() - self.task_context["asr_started"],
                )
            if self.task_timing is not None:
                self.last_performance = self.task_timing.finish(state.value)
                self.task_timing = None
                self.timing_task_id = None
                self.performance.emit(self.last_performance)
            self.epoch += 1
            self.preparing = False
            self.recorder.cancel()
            current = current_task()
            for task in list(self.pending):
                if task is not current and task not in self.cleanup_tasks:
                    task.cancel()
            abort = getattr(self.inputs, "abort_task", None)
            if callable(abort):
                try:
                    asyncio.get_running_loop()
                except RuntimeError:
                    pass
                else:
                    task = self.spawn(abort())
                    self.cleanup_tasks.add(task)
                    task.add_done_callback(self.cleanup_tasks.discard)
            self._close_realtime(self.task_context)
            self.keys.clear()
            self.task_context = None
            self.audio_failure = None
            self.input_failure = None
            self.finished.emit({"outcome": state.value, **self.metrics})
            self.metrics = {}

    def cancel(self):
        self._fallback_reprepare_task_id = None
        self.capture_ready.emit(False)
        self.preview.emit("")
        self.epoch += 1
        self.preparing = False
        self.recorder.cancel()
        self.controller.cancel()
        current = current_task()
        if (
            self.authorization_task is not None
            and self.authorization_task is not current
        ):
            self.authorization_task.cancel()
        for task in list(self.pending):
            if task is not current and task not in self.cleanup_tasks:
                task.cancel()
        self.keys.clear()
        self.task_context = None
        self.status.emit("已取消，迟到结果不会继续输入。")

    def stop_recording(self) -> None:
        if self.controller.state == State.RECORDING and self.controller.task:
            self.mark_timing(self.controller.task.id, "recording_stop_requested")
            self.recorder.stop()

    async def toggle(self, *, delay: float = 0) -> None:
        now = time.monotonic()
        if now - self.last_toggle < 0.35:
            return
        self.last_toggle = now
        if self.controller.state == State.RECORDING:
            self.stop_recording()
            return
        if self.input_maintenance_active or self.authorization_lock.locked():
            self.status.emit("输入服务正在调整，请完成后再开始录音。")
            return
        if self.controller.task or self.preparing or self.testing:
            self.status.emit("当前任务正在处理，请等待或取消。")
            return
        self.preparing = True
        self.capture_ready.emit(False)
        self.status.emit("正在准备录音，请稍候。")
        self.epoch += 1
        epoch = self.epoch
        context = None
        try:
            self.settings = self.store.load_settings()
            if not self.settings.transcription_provider:
                raise CredentialError("请先在模型配置中保存语音模型。")
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
                "polishing_streaming": self.settings.polishing_streaming,
            }
            if not transcription.model:
                raise CredentialError("请先选择转写模型并保存 API 密钥。")
            validate_provider_protocol(transcription)
            realtime_config = None
            if transcription.parameters.get("asr_protocol") is not None:
                from inkecho.asr_streaming import streaming_config

                realtime_config = streaming_config(
                    transcription, sample_rate=self.settings.sample_rate
                )
                if not hasattr(self.recorder, "pcm_ready"):
                    raise ProviderError("configuration")
            context["realtime_config"] = realtime_config
            if delay:
                self.status.emit(
                    "即将开始录音。文字会在识别完成后输入到当时的光标位置。"
                )
                await asyncio.sleep(delay)
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
            task_id = self.controller.begin()
            if task_id:
                self.task_timing = TaskTiming()
                self.timing_task_id = task_id
                self.mark_timing(task_id, "recording_started")
                self.task_context = context
                self.metrics = {"audio_seconds": 0.0, "characters": 0}
                context["startup_ready"] = asyncio.get_running_loop().create_future()
                context["onset_pcm"] = bytearray()
                device = (
                    bytes.fromhex(self.settings.microphone)
                    if self.settings.microphone
                    else None
                )
                options = {
                    "sample_rate": self.settings.sample_rate,
                    "max_seconds": self.settings.recording_limit_seconds,
                }
                if realtime_config is not None:
                    options["streaming"] = True
                # Input consent must not delay capturing the beginning of speech.
                # The same owned task is a hard gate before any text delivery.
                context["input_authorization"] = self.spawn(
                    self.authorize_input(self.settings.output_method)
                )
                if not self.recorder.start(device, **options):
                    self.controller.fail(task_id, Failure.AUDIO)
                    return
                key = await self.key(transcription.key_ref)
                if epoch != self.epoch:
                    return
                self.keys = {"transcription": key}
                if realtime_config is not None:
                    task = self.controller.task
                    from inkecho.asr_streaming import create_streaming_session

                    context["realtime"] = create_streaming_session(
                        transcription,
                        realtime_config,
                        key,
                        qwen_factory=self.realtime_factory,
                        timeout_seconds=self.settings.transcription_timeout_seconds,
                        deadline=task.deadline,
                        active=lambda: self.active(task_id),
                    )
                    preview = getattr(context["realtime"], "set_preview_callback", None)
                    if transcription.adapter == "qwen" and callable(preview):

                        def on_preview(text):
                            self.controller.tick()
                            if (
                                epoch == self.epoch
                                and self.active(task_id)
                                and self.controller.task is task
                                and self.task_context is context
                                and self.controller.state
                                in {
                                    State.RECORDING,
                                    State.TRANSCRIBING,
                                }
                                and isinstance(text, str)
                                and len(text) <= 100000
                            ):
                                self.preview.emit(text)

                        preview(on_preview)
                    observe = getattr(
                        context["realtime"], "set_completed_callback", None
                    )
                    if callable(observe):
                        completed = asyncio.get_running_loop().create_future()
                        context["asr_completed_result"] = completed

                        def on_completed(result):
                            self.controller.tick()
                            if (
                                self.active(task_id)
                                and self.task_context is context
                                and not completed.done()
                            ):
                                completed.set_result(result)

                        observe(on_completed)
                    context["asr_started"] = time.monotonic()
                    self.mark_timing(task_id, "asr_started")
                    self.metrics["transcription_calls"] = 1
                    context["realtime_start"] = self.spawn(
                        self._start_realtime(task_id, context)
                    )
                if not self.active(task_id):
                    return
                onset = context.pop("onset_pcm")
                if realtime_config is not None:
                    for offset in range(0, len(onset), MAX_FEED_BYTES):
                        context["realtime"].feed_nowait(
                            bytes(onset[offset : offset + MAX_FEED_BYTES])
                        )
                onset.clear()
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
                ready = context["startup_ready"]
                if ready.done():
                    return
                ready.set_result(True)
                if not await context["input_authorization"]:
                    if epoch == self.epoch and self.active(task_id):
                        self.cancel()
                    return
                if epoch != self.epoch or not self.active(task_id):
                    return
        except asyncio.CancelledError:
            raise
        except KeyboardError as error:
            if epoch != self.epoch:
                return
            self.input_problem(error)
        except CredentialError as error:
            if epoch != self.epoch:
                return
            if self.controller.task:
                context["credential_error"] = str(error)
                self.controller.fail(self.controller.task.id, Failure.TRANSCRIPTION)
            else:
                self.diagnostic.emit("credentials_unavailable")
                self.report_problem(str(error))
        except ProviderError as error:
            if epoch != self.epoch:
                return
            if self.controller.task:
                self.controller.fail(self.controller.task.id, Failure.TRANSCRIPTION)
            self.diagnostic.emit(error.code)
            self.report_problem(PROVIDER_LABELS[error.code])
        except Exception:
            if epoch != self.epoch:
                return
            if self.controller.task:
                self.controller.fail(self.controller.task.id, Failure.AUDIO)
            self.diagnostic.emit("configuration_invalid")
            self.report_problem("无法开始录音，请检查配置与系统服务。")
        finally:
            if context is not None:
                ready = context.get("startup_ready")
                if ready is not None and not ready.done():
                    ready.set_result(False)
                context.get("onset_pcm", bytearray()).clear()
            if epoch == self.epoch:
                self.preparing = False
                if not self.controller.task:
                    self.keys.clear()

    def _capture_ready(self) -> None:
        if self.controller.task and self.controller.state == State.RECORDING:
            self.capture_ready.emit(True)
            self.status.emit("正在聆听，可以开始说话。")

    def _audio_failed(self, reason):
        if self.controller.task:
            if reason == "empty_recording":
                self.controller.fail(self.controller.task.id, Failure.EMPTY)
                return
            self.audio_failure = AudioError(reason)
            self.controller.fail(self.controller.task.id, Failure.AUDIO)

    def _transcription_failed(self, task_id: str, error: Exception) -> None:
        if not self.active(task_id):
            return
        context = self.task_context
        if context and "asr_started" in context:
            self.metrics["transcription_seconds"] = (
                time.monotonic() - context["asr_started"]
            )
        if isinstance(error, ProviderError) and error.code == "empty":
            self.controller.fail(task_id, Failure.EMPTY)
            return
        self.controller.fail(task_id, Failure.TRANSCRIPTION)
        if isinstance(error, ProviderError):
            self.diagnostic.emit(error.code)
            self.report_problem(PROVIDER_LABELS[error.code])

    async def _start_realtime(self, task_id: str, context: dict) -> None:
        try:
            await context["realtime"].start()
            if self.active(task_id):
                self.spawn(self._watch_realtime(task_id, context["realtime"]))
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self._transcription_failed(task_id, error)

    async def _watch_realtime(self, task_id: str, connection) -> None:
        try:
            await connection.wait_failure()
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self._transcription_failed(task_id, error)

    def _pcm_ready(self, pcm: bytes) -> None:
        task = self.controller.task
        context = self.task_context
        if (
            task is None
            or context is None
            or self.controller.state != State.RECORDING
            or context.get("realtime_config") is None
        ):
            return
        task_id = task.id
        self.controller.tick()
        if not self.active(task_id):
            return
        try:
            if "realtime" not in context:
                onset = context["onset_pcm"]
                # Preserve the beginning while credentials load, without an
                # unbounded recording buffer or silently dropping old samples.
                if len(onset) + len(pcm) > self.settings.sample_rate * 4:
                    raise ProviderError("audio")
                onset.extend(pcm)
                return
            for offset in range(0, len(pcm), MAX_FEED_BYTES):
                context["realtime"].feed_nowait(pcm[offset : offset + MAX_FEED_BYTES])
        except asyncio.CancelledError:
            return
        except Exception as error:
            self._transcription_failed(task_id, error)

    def _recorded(self, audio: bytes, duration: float):
        task = self.controller.task
        if task and self.controller.recording_stopped(task.id):
            self.mark_timing(task.id, "recording_stopped")
            self.metrics["audio_seconds"] = duration
            self.spawn(self._process(task.id, audio))

    async def _process(self, task_id: str, audio: bytes):
        if not self.active(task_id):
            return
        context = self.task_context
        started = context.get("asr_started", time.monotonic())
        asr_finish = None
        try:
            ready = context.get("startup_ready")
            if ready is not None:
                if not await asyncio.shield(ready) or not self.active(task_id):
                    return
            if "realtime" in context:
                await context["realtime_start"]
                if not self.active(task_id):
                    return
                completed = context.get("asr_completed_result")
                if (
                    completed is not None
                    and self.controller.polish
                    and context["polishing_streaming"]
                    and callable(
                        getattr(context["polishing_client"], "polish_stream", None)
                    )
                ):
                    asr_finish = self.spawn(context["realtime"].finish())
                    done, _ = await asyncio.wait(
                        {asr_finish, completed}, return_when=asyncio.FIRST_COMPLETED
                    )
                    result = (
                        asr_finish.result()
                        if asr_finish in done
                        else completed.result()
                    )
                else:
                    result = await context["realtime"].finish()
            else:
                self.metrics["transcription_calls"] = 1
                self.mark_timing(task_id, "asr_started")
                result = await context["transcription_client"].transcribe(
                    context["transcription"], self.keys["transcription"], audio
                )
            if not self.active(task_id):
                return
            self.metrics["transcription_seconds"] = time.monotonic() - started
            self.mark_timing(task_id, "asr_completed")
            if not result.text.strip():
                self.controller.transcribed(task_id, result.text)
                return
            authorized = await context["input_authorization"]
            if not authorized or not self.active(task_id):
                return
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
                self.mark_timing(task_id, "polishing_started")
                client = context["polishing_client"]
                if context["polishing_streaming"] and hasattr(client, "polish_stream"):
                    await self._stream_polish(
                        task_id, context, key, result.text, asr_finish=asr_finish
                    )
                    return
                polished = await context["polishing_client"].polish(
                    context["polishing"], key, result.text, context["prompt"].body
                )
                if not self.active(task_id):
                    return
                self.metrics["polishing_seconds"] = time.monotonic() - started
                if polished.text:
                    self.mark_timing(task_id, "polishing_first_segment")
                self.mark_timing(task_id, "polishing_completed")
                self.metrics["usage"] = polished.usage
                self.controller.polished(task_id, polished.text)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                if not self.active(task_id):
                    return
                self.metrics["polishing_seconds"] = time.monotonic() - started
                # Even an error before streaming starts cannot release the
                # original-text fallback until the same ASR finish is valid.
                if asr_finish is not None:
                    try:
                        confirmed = await asr_finish
                        if confirmed.text != result.text:
                            raise ProviderError("response")
                    except asyncio.CancelledError:
                        raise
                    except Exception as asr_error:
                        self._transcription_failed(task_id, asr_error)
                        return
                    if not self.active(task_id):
                        return
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
            if self.active(task_id):
                self.metrics["transcription_seconds"] = time.monotonic() - started
            self._transcription_failed(task_id, error)

        finally:
            if asr_finish is not None:
                if not asr_finish.done():
                    asr_finish.cancel()
                await asyncio.gather(asr_finish, return_exceptions=True)

    async def _stream_polish(
        self, task_id, context, key, original, *, asr_finish=None
    ) -> None:
        started = time.monotonic()

        def active():
            self.controller.tick()
            return self.active(task_id) and self.controller.state in {
                State.POLISHING,
                State.INJECTING,
            }

        async def send(text):
            if not active():
                raise asyncio.CancelledError
            prepared_original = None
            if self.controller.state == State.POLISHING:
                prepared_original = self.controller.task.original
                if not self.controller.begin_streaming_output(task_id):
                    raise asyncio.CancelledError
            task = self.controller.task
            options = {"deadline": task.deadline}
            if getattr(self.inputs, "supports_first_sent_callback", False):
                options["on_first_sent"] = lambda sent_at=None: self.mark_timing(
                    task_id, "first_character_sent", at=sent_at
                )
            self.output_metrics_task_id = task_id
            count = await self.inputs.insert(text, active, **options)
            if not active():
                raise asyncio.CancelledError
            if count is UNSENT_NEIGHBOR_ROUTE:
                if (
                    prepared_original is None
                    or self.metrics.get("characters", 0)
                    or getattr(self.inputs, "acknowledged_attempts", None) != 0
                ):
                    raise KeyboardError("injection_failed")
                if not self.controller.resume_unsent_streaming_preparation(
                    task_id, prepared_original
                ):
                    raise asyncio.CancelledError
                return count
            if type(count) is int and count == len(text):
                self.metrics["characters"] += count
            return count

        prepare_stream = getattr(self.inputs, "prepare_stream", None)

        async def prepare_output():
            if not active():
                raise asyncio.CancelledError
            task = self.controller.task
            if task is None:
                raise asyncio.CancelledError
            return await prepare_stream(active, deadline=task.deadline)

        output = StreamingOutput(
            send,
            active,
            prepare=prepare_output if callable(prepare_stream) else None,
            batch_enabled=lambda: bool(
                getattr(self.inputs, "neighbor_batches_enabled", False)
            ),
        )
        offset = 0

        async def on_delta(text):
            nonlocal offset
            if not active():
                raise asyncio.CancelledError
            if text:
                self.mark_timing(task_id, "polishing_first_segment")
            await output.append(TextDelta(offset, text))
            offset += len(text)

        async def produce():
            result = await context["polishing_client"].polish_stream(
                context["polishing"], key, original, context["prompt"].body, on_delta
            )
            if not active():
                raise asyncio.CancelledError
            self.metrics["polishing_seconds"] = time.monotonic() - started
            self.metrics["usage"] = result.usage
            self.mark_timing(task_id, "polishing_completed")
            await output.finish(result.text)

        async def consume():
            output_session = getattr(self.inputs, "output_session", None)
            if not callable(output_session):
                return await output.run()
            async with output_session():
                return await output.run()

        producer = self.spawn(produce())
        consumer = self.spawn(consume())

        async def confirm_asr():
            result = await asr_finish
            if result.text != original:
                raise ProviderError("response")

        confirmation = self.spawn(confirm_asr()) if asr_finish is not None else None

        async def stop_operations(*, keep_confirmation=False):
            output.close()
            operations = [producer, consumer]
            if confirmation is not None and not keep_confirmation:
                operations.append(confirmation)
            for operation in operations:
                if not operation.done():
                    operation.cancel()
            try:
                await asyncio.gather(*operations, return_exceptions=True)
            finally:
                output.close()

        try:
            pending = {producer, consumer}
            if confirmation is not None:
                pending.add(confirmation)
            while pending:
                done, pending = await asyncio.wait(
                    pending, return_when=asyncio.FIRST_COMPLETED
                )
                # Closure errors retain transcription classification and cannot
                # be mistaken for a polishing fallback opportunity.
                if confirmation in done:
                    try:
                        confirmation.result()
                    except Exception as error:
                        self._transcription_failed(task_id, error)
                        raise
                for operation in done:
                    operation.result()
            count = consumer.result()
            if active():
                self.metrics["characters"] = count
                self.mark_timing(task_id, "output_completed")
                self.controller.injection_finished(task_id)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            fallback_possible = not output.attempted and not isinstance(
                error, KeyboardError
            )
            if self.active(task_id):
                self._snapshot_acknowledged_attempts()
                self._record_acknowledged_attempts(error)
            await stop_operations(keep_confirmation=fallback_possible)
            if fallback_possible and confirmation is not None:
                try:
                    await confirmation
                except asyncio.CancelledError:
                    raise
                except Exception as asr_error:
                    self._transcription_failed(task_id, asr_error)
                    return
            if not active():
                return
            self.metrics["characters"] = max(
                self.metrics.get("characters", 0), output.sent_characters
            )
            self.metrics["polishing_seconds"] = time.monotonic() - started
            if isinstance(error, KeyboardError):
                self._record_acknowledged_attempts(error)
                self.input_failure = error
                if error.code == "ibus_delivery_unknown" and getattr(
                    error, "dispatch_complete", False
                ):
                    self.mark_timing(task_id, "output_completed")
                    self.controller.injection_unconfirmed(task_id)
                else:
                    self.controller.fail(task_id, Failure.INJECTION)
            elif output.attempted:
                self.controller.fail(task_id, Failure.POLISHING)
            else:
                # This branch is reachable only before any dispatch attempt.
                # The consumer scope has already discarded its prepared route.
                # Authorize one task-scoped reprepare for original-text fallback;
                # partial/uncertain output never receives this permission.
                if self.controller.fallback:
                    self._fallback_reprepare_task_id = task_id
                self.controller.polishing_failed(task_id)
                if isinstance(error, ProviderError):
                    self.diagnostic.emit(error.code)
                    self.status.emit(
                        PROVIDER_LABELS[error.code]
                        + (" 已按设置使用原文。" if self.controller.fallback else "")
                    )
        finally:
            await stop_operations()

    async def sample_audio(self, seconds: float = 3) -> bytes:
        if (
            self.input_maintenance_active
            or self.testing
            or self.preparing
            or self.controller.task
        ):
            raise RuntimeError("请先结束当前录音任务。")
        self.testing = True
        recorder = Recorder(self)
        recorder.level.connect(self.level)
        future = asyncio.get_running_loop().create_future()
        recorder.finished.connect(
            lambda data, _seconds: not future.done() and future.set_result(data)
        )
        recorder.failed.connect(
            lambda reason: (
                not future.done() and future.set_exception(AudioError(reason))
            )
        )
        try:
            settings = self.store.load_settings()
            device = bytes.fromhex(settings.microphone) if settings.microphone else None
            if not recorder.start(
                device, sample_rate=settings.sample_rate, max_seconds=seconds + 2
            ):
                if future.done():
                    return await future
                raise AudioError("microphone_start_failed")
            await asyncio.sleep(seconds)
            recorder.stop()
            return await asyncio.wait_for(future, 2)
        except AudioError as error:
            self.diagnostic.emit(error.code)
            raise
        finally:
            if future.done() and not future.cancelled():
                future.exception()
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
        if self.input_maintenance_tasks:
            await asyncio.gather(
                *tuple(self.input_maintenance_tasks), return_exceptions=True
            )
        self.timer.stop()
        try:
            await self.inputs.aclose()
        except KeyboardError as error:
            self.diagnostic.emit(error.code)
        finally:
            close_client = getattr(self.client, "aclose", None)
            if close_client is not None:
                await close_client()
