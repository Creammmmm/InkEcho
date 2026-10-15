"""Qt widget interactions, isolated persistence and asynchronous form ownership."""

import asyncio
import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QPushButton

from inkecho.app import AudioError, Session
from inkecho.config import BUILTIN_PROMPT, ConfigStore
from inkecho.core import Failure, State
from inkecho.integration import DesktopIntegration
from inkecho.logging import DiagnosticLog
from inkecho.platform.hotkeys import ShortcutError
from inkecho.providers import ProviderError, Result, Usage
from inkecho.realtime import PROTOCOL, RealtimeConfig
from inkecho.statistics import Statistics
from inkecho.ui.settings import AppearancePage
from inkecho.ui.window import MainWindow


@pytest.fixture
def window(tmp_path, qt_app, monkeypatch):
    monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
    monkeypatch.setattr("inkecho.audio.Recorder.devices", lambda: [])
    store = ConfigStore(tmp_path / "config")
    store.initialize()
    session = Session(store)
    log = DiagnosticLog(tmp_path / "data")
    integration = DesktopIntegration(
        Path(sys.executable),
        data_home=tmp_path / "desktop",
        config_home=tmp_path / "autostart",
    )
    widget = MainWindow(
        session,
        Statistics(tmp_path / "statistics.json"),
        log,
        integration,
        [sys.executable, "-m", "inkecho", "--toggle"],
    )
    widget.tray.hide()
    widget.show()
    qt_app.processEvents()
    yield widget
    session.timer.stop()
    asyncio.run(session.inputs.aclose())
    widget.dispose()
    log.close()
    qt_app.processEvents()


def click(widget, text):
    matches = [item for item in widget.findChildren(QPushButton) if item.text() == text]
    assert len(matches) == 1
    QTest.mouseClick(matches[0], Qt.MouseButton.LeftButton)


def test_appearance_save_reload_and_builtin_prompt_copy(window, qt_app):
    page = window.pages[6]
    window.navigation.setCurrentRow(6)
    page.style.setCurrentIndex(page.style.findData("pulse"))
    page.position.setCurrentIndex(page.position.findData("top-center"))
    click(page, "保存外观")
    reloaded = AppearancePage(window.session, lambda: None)
    assert reloaded.style.currentData() == "pulse"
    assert reloaded.position.currentData() == "top-center"
    reloaded.close()
    prompts = window.pages[4]
    window.navigation.setCurrentRow(4)
    prompts.text.setPlainText("保留用户措辞，只修改标点。")
    click(prompts, "保存模板")
    assert prompts.identifier != BUILTIN_PROMPT.id
    assert window.session.store.load_prompt(BUILTIN_PROMPT.id) == BUILTIN_PROMPT
    assert (
        window.session.store.load_prompt(prompts.identifier).body
        == "保留用户措辞，只修改标点。"
    )


def test_navigation_scroll_and_icon(window, qt_app):
    assert not window.icon.isNull()
    for index in range(len(window.pages)):
        window.navigation.setCurrentRow(index)
        qt_app.processEvents()
        scroll = window.stack.widget(index)
        assert scroll.verticalScrollBar().value() == 0
        bar = scroll.verticalScrollBar()
        bar.setValue(bar.maximum())
        qt_app.processEvents()
        assert bar.value() == bar.maximum()


def test_app_local_active_window_does_not_block_authoritative_backend(window, qt_app):
    async def scenario():
        calls = []

        async def toggle():
            calls.append("backend")

        window.session.toggle = toggle
        window.activateWindow()
        window.problem_notice.present("Old failure")
        qt_app.processEvents()
        window.handle_command("toggle")
        await asyncio.gather(*window.session.pending)
        assert calls == ["backend"]
        assert not window.problem_notice.isVisible()

    asyncio.run(scenario())


def test_hidden_start_failure_is_visible_without_activating_settings(window, qt_app):
    window.hide()
    message = "目标不支持安全直接输入，请使用支持的文本编辑器。"
    window.session.problem.emit(message)
    qt_app.processEvents()
    assert not window.isVisible()
    assert window.problem_notice.isVisible()
    assert message in window.problem_notice.message.text()
    assert window.problem_notice.windowFlags() & Qt.WindowType.WindowDoesNotAcceptFocus
    assert window.problem_notice.testAttribute(
        Qt.WidgetAttribute.WA_ShowWithoutActivating
    )
    # Offscreen has no compositor and ignores the native activation prohibition.
    # Wayland never maps this auxiliary window during the voice workflow.


def test_wayland_status_never_maps_auxiliary_or_delayed_main_window(window, qt_app):
    window.wayland = True
    window.hide()
    notices = []
    window.notify = lambda message, **flags: notices.append((message, flags))
    window.show_problem("Visible desktop notification")
    for state in ("recording", "transcribing", "failed", "idle"):
        window.update_state(state)
    QTest.qWait(600)
    assert notices
    assert any(flags.get("recording") for _, flags in notices)
    assert not window.isVisible()
    assert not window.problem_notice.isVisible()
    assert not window.overlay.isVisible()
    assert not window.controls.isVisible()


def test_keyboard_failure_notifies_specific_reason_and_records_safe_code(window):
    from inkecho.platform.keyboard import KeyboardError

    window.wayland = True
    window.hide()
    notices = []
    window.notify = lambda message, **flags: notices.append(message)
    window.session.input_failure = KeyboardError("session_closed")
    window.session.controller.failure = Failure.INJECTION
    window.session._state(State.FAILED)
    window.session._state(State.IDLE)
    assert len(notices) == 1
    assert "键盘输入连接已断开" in notices[0]
    assert "重新启用" in window.home.description.text()
    assert "ERROR error session_closed" in window.log.recent()
    assert not window.problem_notice.isVisible()
    assert not window.controls.isVisible()
    assert not window.overlay.isVisible()


def test_notification_actions_cannot_control_a_different_task(window):
    actions = []
    window.session.active = lambda task_id: task_id == "current"
    window.session.cancel = lambda: actions.append("cancel")
    window.notification_action("cancel", "old")
    assert actions == []
    window.notification_action("cancel", "current")
    assert actions == ["cancel"]


def test_notification_service_failure_keeps_original_error_in_overview(window):
    async def scenario():
        async def unavailable(*args, **kwargs):
            return False

        window.wayland = True
        window.notifications.show = unavailable
        window.hide()
        message = "当前文本控件不支持安全输入。"
        window.show_problem(message)
        await asyncio.gather(*window.session.ui_tasks)
        assert message in window.home.description.text()
        assert "系统通知不可用" in window.home.description.text()
        assert not window.isVisible()
        assert not window.problem_notice.isVisible()

    asyncio.run(scenario())


@pytest.mark.parametrize("failed", [False, True])
def test_stale_shortcut_health_cannot_replace_enable_result(
    window, monkeypatch, failed
):
    async def scenario():
        page = window.pages[1]
        waiting, release = asyncio.Event(), asyncio.Event()

        async def operation(function, *args):
            if function.__name__ == "status":
                waiting.set()
                await release.wait()
                return "stale disabled result"
            assert function.__name__ == "enable"
            if failed:
                raise ShortcutError("conflict")

        monkeypatch.setattr("inkecho.ui.settings.asyncio.to_thread", operation)
        pending = asyncio.create_task(page.check_shortcut())
        await waiting.wait()
        enable = asyncio.create_task(page.enable())
        await asyncio.sleep(0)
        release.set()
        await pending
        await enable
        result = page.message.text()
        assert ("未启用" if failed else "已配置") in result
        assert page.message.text() == result

    asyncio.run(scenario())


def test_shortcut_mutations_are_serialized_in_user_action_order(window, monkeypatch):
    async def scenario():
        page = window.pages[1]
        entered, release = asyncio.Event(), asyncio.Event()
        calls = []

        async def operation(function, *args):
            calls.append(function.__name__)
            if function.__name__ == "enable":
                entered.set()
                await release.wait()

        monkeypatch.setattr("inkecho.ui.settings.asyncio.to_thread", operation)
        enable = asyncio.create_task(page.enable())
        await entered.wait()
        disable = asyncio.create_task(page.disable())
        await asyncio.sleep(0)
        assert calls == ["enable"]
        release.set()
        await asyncio.gather(enable, disable)
        assert calls == ["enable", "disable"]
        assert "已停用" in page.message.text()

    asyncio.run(scenario())


def test_no_tray_processing_retains_cancel_entry(window):
    window.hide()
    window.update_state("transcribing")
    assert window.controls.isVisible()
    assert not window.controls.stop.isEnabled()
    click(window.controls, "取消")
    assert "已取消" in window.home.description.text()


def test_preparation_cancel_restores_window(window):
    async def scenario():
        waiting = asyncio.Event()

        async def slow(**_kwargs):
            waiting.set()
            await asyncio.Event().wait()

        window.session.toggle = slow
        window.start_from_window()
        await waiting.wait()
        assert not window.isVisible()
        window.session.cancel()
        await asyncio.gather(*window.session.pending, return_exceptions=True)
        assert window.isVisible()

    asyncio.run(scenario())


def test_model_discovery_does_not_overwrite_another_form(window):
    async def scenario():
        page = window.pages[2]
        waiting, release = asyncio.Event(), asyncio.Event()

        async def key(_reference):
            return "test-key"

        class Client:
            async def models(self, *_args):
                waiting.set()
                await release.wait()
                return ["old-provider-model"]

        window.session.key = key
        window.session.provider_client = lambda _role: Client()
        request = asyncio.create_task(page.discover())
        await waiting.wait()
        page.new()
        page.model.setCurrentText("new-provider-model")
        release.set()
        await request
        assert page.model.currentText() == "new-provider-model"
        assert page.model.findText("old-provider-model") == -1

    asyncio.run(scenario())


def test_realtime_capability_rejected_before_key_recording_or_network(window):
    async def scenario():
        page = window.pages[2]
        page.model.setCurrentText("qwen3-asr-flash-realtime")

        async def forbidden(*args, **kwargs):
            raise AssertionError("Protocol preflight must precede external access")

        window.session.key = forbidden
        window.session.sample_audio = forbidden
        window.session.provider_client = forbidden
        await page.run(page.capability())
        assert "当前连接方式与模型协议不匹配" in page.message.text()
        assert "Qwen 实时 WebSocket" in page.message.text()
        assert "当前连接方式与模型协议不匹配" in page.model_hint.text()

    asyncio.run(scenario())


def test_provider_failure_is_actionable_chinese(window):
    async def scenario():
        page = window.pages[2]

        async def failed():
            raise ProviderError("unavailable")

        await page.run(failed())
        assert "云端服务暂时不可用" in page.message.text()
        assert "稍后重试" in page.message.text()
        assert "unavailable" not in page.message.text()

    asyncio.run(scenario())


def test_microphone_test_page_keeps_specific_failure(window):
    async def scenario():
        page = window.pages[1]

        async def failed():
            raise AudioError("audio_format_unsupported")

        window.session.sample_audio = failed
        await page.run(page.test_audio())
        assert "麦克风不支持当前采样率" in page.message.text()
        assert "录音设置中调整" in page.message.text()
        assert "操作未完成" not in page.message.text()

    asyncio.run(scenario())


def test_late_provider_failure_does_not_overwrite_new_form(window):
    async def scenario():
        page = window.pages[2]
        entered, release = asyncio.Event(), asyncio.Event()

        async def failed():
            entered.set()
            await release.wait()
            raise ProviderError("unavailable")

        pending = page.run(failed())
        await entered.wait()
        page.new()
        page.message.setText("new form")
        release.set()
        await pending
        assert page.message.text() == "new form"

    asyncio.run(scenario())


def test_discovery_marks_incompatible_protocols_without_switching_model(window):
    async def scenario():
        page = window.pages[2]
        page.model.setCurrentText("qwen3-asr-flash-realtime")

        async def key(*args):
            return "test-only"

        class Client:
            async def models(self, *args):
                return [
                    "qwen3-asr-flash",
                    "qwen3-asr-flash-realtime",
                    "qwen3-asr-flash-filetrans",
                ]

        window.session.key = key
        window.session.provider_client = lambda role: Client()
        await page.discover()
        assert page.provider().model == "qwen3-asr-flash-realtime"
        assert page.model.itemData(1, Qt.ItemDataRole.ToolTipRole)
        assert page.model.itemData(2, Qt.ItemDataRole.ToolTipRole)
        assert page.model.itemData(0, Qt.ItemDataRole.ToolTipRole) is None
        assert "2 个模型" in page.message.text()

    asyncio.run(scenario())


def test_provider_save_snapshots_preferences_before_keyring_wait(window):
    async def scenario():
        page = window.pages[3]
        waiting, release = asyncio.Event(), asyncio.Event()
        written = []

        async def save_key(reference, value):
            written.append((reference, value))
            waiting.set()
            await release.wait()

        window.session.save_key = save_key
        page.key.setText("temporary-test-secret")
        page.enabled.setChecked(True)
        page.streaming.setChecked(False)
        page.fallback.setChecked(False)
        original = page.identifier
        request = asyncio.create_task(page.save())
        await waiting.wait()
        assert page.key.text() == ""
        page.new()
        page.enabled.setChecked(False)
        page.streaming.setChecked(True)
        page.fallback.setChecked(True)
        release.set()
        await request
        settings = window.session.store.load_settings()
        assert settings.polishing_provider == original
        assert settings.polishing_enabled
        assert not settings.polishing_fallback
        assert not settings.polishing_streaming
        assert page.identifier != original
        assert written[0][1] == "temporary-test-secret"
        assert (
            "temporary-test-secret"
            not in (window.session.store.root / "config.json").read_text()
        )

    asyncio.run(scenario())


def test_protocol_controls_preserve_json_model_rate_and_saved_configuration(window):
    page = window.pages[2]
    store = window.session.store
    before = {p: p.read_bytes() for p in store.root.rglob("*.json")}
    original_model = page.model.currentText()
    original_rate = store.load_settings().sample_rate
    assert page.protocol.currentData() == "http"
    page.parameters.setPlainText('{"asr_options":{"enable_itn":false}}')
    page.protocol.setCurrentIndex(page.protocol.findData(PROTOCOL))
    page.realtime_url.setText("wss://asr.example.invalid/realtime")
    assert page.parameter_values() == {
        "asr_protocol": PROTOCOL,
        "realtime_url": "wss://asr.example.invalid/realtime",
        "asr_options": {"enable_itn": False},
    }
    page.protocol.setCurrentIndex(page.protocol.findData("http"))
    assert page.parameter_values() == {"asr_options": {"enable_itn": False}}
    assert page.model.currentText() == original_model
    assert store.load_settings().sample_rate == original_rate
    assert before == {p: p.read_bytes() for p in store.root.rglob("*.json")}


def test_invalid_json_is_never_replaced_by_protocol_controls_or_save(window):
    async def scenario():
        page = window.pages[2]
        stored = window.session.store.load_provider(page.identifier)
        original = '{"unfinished":'
        page.parameters.setPlainText(original)
        page.protocol.setCurrentIndex(page.protocol.findData(PROTOCOL))
        page.realtime_url.setText("wss://example.invalid/fixture")
        assert page.parameters.toPlainText() == original
        await page.run(page.save())
        assert "JSON" in page.message.text()
        assert page.parameters.toPlainText() == original
        assert window.session.store.load_provider(page.identifier) == stored

    asyncio.run(scenario())


def test_advanced_protocol_json_updates_controls_without_discarding_unknown_data(
    window,
):
    page = window.pages[2]
    values = {"asr_protocol": PROTOCOL, "realtime_url": "wss://example.invalid/r"}
    page.parameters.setPlainText(json.dumps(values))
    assert page.protocol.currentData() == PROTOCOL
    assert page.realtime_url.text() == values["realtime_url"]
    values["asr_protocol"] = "future_protocol"
    values["realtime_url"] = {"invalid": "preserved"}
    page.parameters.setPlainText(json.dumps(values))
    assert page.protocol.currentIndex() == -1
    assert page.parameter_values() == values


def test_explicit_official_realtime_controls_validate_without_changing_model(window):
    page = window.pages[2]
    page.model.setCurrentText("qwen3-asr-flash-realtime")
    page.protocol.setCurrentIndex(page.protocol.findData(PROTOCOL))
    config = RealtimeConfig.from_provider(page.provider())
    assert config.url.startswith("wss://dashscope.aliyuncs.com/api-ws/v1/realtime?")
    assert page.realtime_url.text() == ""
    assert "已选择边录边识别" in page.model_hint.text()


def test_custom_realtime_requires_wss_before_credentials_or_microphone(window):
    async def scenario():
        page = window.pages[2]
        page.model.setCurrentText("qwen3-asr-flash-realtime")
        page.url.setText("https://proxy.example.invalid/v1")
        page.protocol.setCurrentIndex(page.protocol.findData(PROTOCOL))

        async def forbidden(*_args, **_kwargs):
            raise AssertionError("preflight must precede external access")

        window.session.key = forbidden
        window.session.sample_audio = forbidden
        await page.run(page.capability())
        assert "服务配置或请求参数不正确" in page.message.text()
        page.realtime_url.setText("wss://proxy.example.invalid/realtime")
        page.validate_protocol(page.provider())
        assert page.provider().parameters["realtime_url"] == page.realtime_url.text()

    asyncio.run(scenario())


def test_realtime_sample_rate_preflight_does_not_change_settings_or_record(window):
    async def scenario():
        page = window.pages[2]
        store = window.session.store
        store.save_settings(replace(store.load_settings(), sample_rate=48000))
        page.model.setCurrentText("qwen3-asr-flash-realtime")
        page.protocol.setCurrentIndex(page.protocol.findData(PROTOCOL))

        async def forbidden(*_args, **_kwargs):
            raise AssertionError("sample rate preflight must run first")

        window.session.key = forbidden
        window.session.sample_audio = forbidden
        await page.run(page.capability())
        assert "16 kHz" in page.message.text()
        assert store.load_settings().sample_rate == 48000

    asyncio.run(scenario())


def test_realtime_capability_page_passes_explicit_protocol_without_injection(window):
    async def scenario():
        page = window.pages[2]
        page.model.setCurrentText("qwen3-asr-flash-realtime")
        page.protocol.setCurrentIndex(page.protocol.findData(PROTOCOL))
        calls = []

        async def key(_reference):
            return "fixture-key"

        async def sample():
            return b"fixture-audio"

        class Client:
            async def test_capability(self, provider, value, *, audio, streaming):
                calls.append((provider.parameters, value, audio, streaming))
                return Result("fixture result", Usage(), 0.01)

        window.session.key = key
        window.session.sample_audio = sample
        window.session.provider_client = lambda _role: Client()
        await page.capability()
        assert calls == [
            ({"asr_protocol": PROTOCOL}, "fixture-key", b"fixture-audio", False)
        ]
        assert "未向其他窗口输入" in page.message.text()

    asyncio.run(scenario())


@pytest.mark.parametrize("streaming", [False, True])
def test_polish_capability_uses_saved_streaming_setting(window, streaming):
    async def scenario():
        page = window.pages[3]
        store = window.session.store
        store.save_settings(
            replace(store.load_settings(), polishing_streaming=streaming)
        )
        calls = []

        async def key(_reference):
            return "fixture-key"

        class Client:
            async def test_capability(self, _provider, _key, **options):
                calls.append(options)
                return Result("fixture", Usage(), 0)

        window.session.key = key
        window.session.provider_client = lambda _role: Client()
        await page.capability()
        assert calls == [{"audio": None, "streaming": streaming}]

    asyncio.run(scenario())


def test_streaming_checkbox_roundtrips_and_warns_about_partial_output(window):
    async def scenario():
        page = window.pages[3]
        assert page.streaming.isChecked()
        page.streaming.setChecked(False)
        await page.save()
        assert not window.session.store.load_settings().polishing_streaming
        assert not page.streaming.isChecked()

    asyncio.run(scenario())


@pytest.mark.parametrize("control", ["protocol", "endpoint", "json", "streaming"])
def test_new_provider_controls_invalidate_late_status(window, control):
    async def scenario():
        page = window.pages[3 if control == "streaming" else 2]
        if control == "endpoint":
            page.protocol.setCurrentIndex(page.protocol.findData(PROTOCOL))
        entered, release = asyncio.Event(), asyncio.Event()

        async def failed():
            entered.set()
            await release.wait()
            raise ProviderError("unavailable")

        task = page.run(failed())
        await entered.wait()
        if control == "protocol":
            page.protocol.setCurrentIndex(page.protocol.findData(PROTOCOL))
        elif control == "endpoint":
            page.realtime_url.setText("wss://example.invalid/realtime")
        elif control == "json":
            page.parameters.setPlainText('{"asr_options":{}}')
        else:
            page.streaming.setChecked(not page.streaming.isChecked())
        page.message.setText("changed form")
        release.set()
        await task
        assert page.message.text() == "changed form"

    asyncio.run(scenario())


@pytest.mark.parametrize("selected", [False, True])
@pytest.mark.parametrize(
    "endpoint",
    [
        "wss://fake-user:fake-secret@asr.example.invalid/realtime",
        "wss://asr.example.invalid/realtime?api_key=fake-secret",
        "wss://asr.example.invalid/realtime?model=qwen3-asr-flash-realtime&token=fake-secret",
        "wss://asr.example.invalid/realtime#fake-secret",
    ],
)
def test_secret_bearing_realtime_url_is_rejected_before_any_save(
    window, selected, endpoint
):
    async def scenario():
        page = window.pages[2]
        store = window.session.store
        before = {p: p.read_bytes() for p in store.root.rglob("*.json")}
        page.model.setCurrentText("qwen3-asr-flash-realtime")
        values = {"realtime_url": endpoint}
        if selected:
            values["asr_protocol"] = PROTOCOL
        original = json.dumps(values)
        page.parameters.setPlainText(original)
        page.key.setText("fake-key-input-not-to-be-saved")
        calls = []

        async def save_key(*args):
            calls.append(args)
            raise AssertionError("Invalid URL must fail before keyring access")

        window.session.save_key = save_key
        await page.run(page.save())
        assert calls == []
        assert page.key.text() == "fake-key-input-not-to-be-saved"
        assert page.parameters.toPlainText() == original
        assert before == {p: p.read_bytes() for p in store.root.rglob("*.json")}
        assert "服务配置或请求参数不正确" in page.message.text()

    asyncio.run(scenario())


def test_http_draft_without_model_remains_saveable(window):
    async def scenario():
        page = window.pages[2]
        page.new()
        assert page.model.currentText() == ""
        await page.save()
        stored = window.session.store.load_provider(page.identifier)
        assert stored.model == "" and stored.parameters == {}

    asyncio.run(scenario())
