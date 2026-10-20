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
from synthetic_providers import SYNTHETIC_PROVIDERS

from inkecho.app import Session
from inkecho.config import BUILTIN_PROMPT, ConfigError, ConfigStore
from inkecho.core import Failure, State
from inkecho.integration import DesktopIntegration
from inkecho.logging import DiagnosticLog
from inkecho.platform.hotkeys import ShortcutError
from inkecho.providers import ProviderError
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
    for provider in SYNTHETIC_PROVIDERS:
        store.save_provider(
            replace(
                provider,
                model=(
                    "qwen3-asr-flash"
                    if provider.role == "transcription"
                    else "deepseek-chat"
                ),
            )
        )
    store.save_settings(
        replace(
            store.load_settings(),
            transcription_provider="qwen",
            polishing_provider="deepseek",
        )
    )
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


def select_platform(page, preset):
    page.apply_preset(page.preset.findData(preset))
    page.name.setText("Synthetic model configuration")


def click(widget, text):
    matches = [item for item in widget.findChildren(QPushButton) if item.text() == text]
    assert len(matches) == 1
    QTest.mouseClick(matches[0], Qt.MouseButton.LeftButton)


def test_appearance_save_reload_and_builtin_prompt_copy(window, qt_app):
    page = window.settings_page.appearance
    window.navigation.setCurrentRow(3)
    page.style.setCurrentIndex(page.style.findData("pulse"))
    page.position.setCurrentIndex(page.position.findData("top-center"))
    reloaded = AppearancePage(window.session)
    assert reloaded.style.currentData() == "pulse"
    assert reloaded.position.currentData() == "top-center"
    reloaded.close()
    prompts = window.pages[2]
    window.navigation.setCurrentRow(2)
    prompts.open_template(BUILTIN_PROMPT.id)
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
    assert "重新启用" in window.statusBar().currentMessage()
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


def test_notification_service_failure_keeps_original_error_in_status_bar(window):
    async def scenario():
        async def unavailable(*args, **kwargs):
            return False

        window.wayland = True
        window.notifications.show = unavailable
        window.hide()
        message = "当前文本控件不支持安全输入。"
        window.show_problem(message)
        await asyncio.gather(*window.session.ui_tasks)
        assert message in window.statusBar().currentMessage()
        assert "系统通知不可用" in window.statusBar().currentMessage()
        assert not window.isVisible()
        assert not window.problem_notice.isVisible()

    asyncio.run(scenario())


@pytest.mark.parametrize("failed", [False, True])
def test_shortcut_saves_only_after_registration(window, monkeypatch, failed):
    async def scenario():
        page = window.settings_page.recording
        old = window.session.store.load_settings().shortcut
        calls = []

        async def operation(function, *args):
            assert window.session.store.load_settings().shortcut == old
            calls.append(args)
            if failed:
                raise ShortcutError("conflict")

        monkeypatch.setattr("inkecho.ui.settings.asyncio.to_thread", operation)
        await page.enable("Ctrl+F8")
        assert calls[0][0] == "Ctrl+F8"
        expected = old if failed else "Ctrl+F8"
        assert window.session.store.load_settings().shortcut == expected
        assert page.shortcut.text() == expected
        assert page.shortcut.isEnabled()

    asyncio.run(scenario())


def test_shortcut_mutations_are_serialized_in_user_action_order(window, monkeypatch):
    async def scenario():
        page = window.settings_page.recording
        entered, release = asyncio.Event(), asyncio.Event()
        calls = []

        async def operation(function, *args):
            calls.append(args[0])
            if args[0] == "Ctrl+F8":
                entered.set()
                await release.wait()

        monkeypatch.setattr("inkecho.ui.settings.asyncio.to_thread", operation)
        first = asyncio.create_task(page.enable("Ctrl+F8"))
        await entered.wait()
        second = asyncio.create_task(page.enable("Ctrl+F9"))
        await asyncio.sleep(0)
        assert calls == ["Ctrl+F8"]
        release.set()
        await asyncio.gather(first, second)
        assert calls == ["Ctrl+F8", "Ctrl+F9"]
        assert window.session.store.load_settings().shortcut == "Ctrl+F9"

    asyncio.run(scenario())


def test_physical_shortcut_capture_requires_complete_key_and_escape_cancels(qt_app):
    from inkecho.ui.settings import ShortcutCapture

    capture = ShortcutCapture("Ctrl+F4")
    capture.show()
    captured = []
    capture.captured.connect(captured.append)
    capture.begin()
    QTest.keyPress(capture, Qt.Key.Key_Control)
    QTest.keyRelease(capture, Qt.Key.Key_Control)
    assert captured == []
    QTest.keyClick(capture, Qt.Key.Key_Escape)
    assert capture.text() == "Ctrl+F4"
    capture.begin()
    QTest.keyPress(capture, Qt.Key.Key_F8, Qt.KeyboardModifier.ControlModifier)
    assert captured == []
    QTest.keyRelease(capture, Qt.Key.Key_F8, Qt.KeyboardModifier.ControlModifier)
    assert captured == ["Ctrl+F8"]
    capture.close()


def test_settings_autosave_and_separate_data_logs(window):
    page = window.settings_page
    assert [page.tabs.tabText(i) for i in range(page.tabs.count())] == [
        "识别与润色",
        "录音与快捷键",
        "悬浮提示",
        "输入兼容性",
        "数据",
        "日志",
        "桌面集成",
    ]
    page.streaming.setChecked(not page.streaming.isChecked())
    page.transcription_timeout.setValue(61)
    page.recording.limit.setValue(123)
    settings = window.session.store.load_settings()
    assert settings.polishing_streaming == page.streaming.isChecked()
    assert settings.transcription_timeout_seconds == 61
    assert settings.recording_limit_seconds == 123
    assert not hasattr(page.statistics, "logs")
    assert page.logs.logs.isReadOnly()
    assert not any(
        "保存" in item.text()
        or "测试麦克风" in item.text()
        or "预览波形" in item.text()
        for item in page.recording.findChildren(QPushButton)
    )


def test_no_tray_processing_retains_cancel_entry(window):
    window.hide()
    window.update_state("transcribing")
    assert window.controls.isVisible()
    assert not window.controls.stop.isEnabled()
    click(window.controls, "取消")
    assert "已取消" in window.statusBar().currentMessage()


def test_status_bar_retains_cancel_for_wayland_without_tray(window):
    window.wayland = True
    window.notify = lambda *_args, **_kwargs: None
    window.update_state("transcribing")
    assert not window.cancel_action.isHidden()
    click(window.statusBar(), "取消当前任务")
    assert "已取消" in window.statusBar().currentMessage()
    window.update_state("idle")
    assert window.cancel_action.isHidden()


def test_model_discovery_does_not_overwrite_another_form(window):
    async def scenario():
        page = window.models_page.transcription
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


def test_invalid_realtime_save_rejected_before_external_access(window):
    async def scenario():
        page = window.models_page.transcription
        page.model.setCurrentText("qwen3-asr-flash-realtime")

        async def forbidden(*args, **kwargs):
            raise AssertionError("Protocol preflight must precede external access")

        window.session.key = forbidden
        window.session.sample_audio = forbidden
        window.session.provider_client = forbidden
        await page.run(page.save())
        assert "当前连接方式与模型能力或协议不匹配" in page.message.text()
        assert "语音识别模型与对应转写方式" in page.message.text()
        assert "当前连接方式与模型能力或协议不匹配" in page.model_hint.text()

    asyncio.run(scenario())


def test_provider_failure_is_actionable_chinese(window):
    async def scenario():
        page = window.models_page.transcription

        async def failed():
            raise ProviderError("unavailable")

        await page.run(failed())
        assert "云端服务暂时不可用" in page.message.text()
        assert "稍后重试" in page.message.text()
        assert "unavailable" not in page.message.text()

    asyncio.run(scenario())


def test_microphone_refresh_keeps_unavailable_saved_device(window):
    page = window.settings_page.recording
    store = window.session.store
    store.save_settings(replace(store.load_settings(), microphone="aabb"))
    page.refresh_devices()
    assert page.microphone.currentData() == "aabb"
    assert store.load_settings().microphone == "aabb"
    assert not any(
        "测试麦克风" in item.text() for item in page.findChildren(QPushButton)
    )


def test_late_provider_failure_does_not_overwrite_new_form(window):
    async def scenario():
        page = window.models_page.transcription
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
        page = window.models_page.transcription
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
        assert [page.model.itemText(i) for i in range(page.model.count())] == [
            "qwen3-asr-flash"
        ]
        assert "1 个模型" in page.message.text()
        assert "已按转写能力和协议过滤" in page.message.text()
        assert "协议尚不支持" not in page.message.text()

    asyncio.run(scenario())


@pytest.fixture
def discovered_protocol_models(window):
    page = window.models_page.transcription
    store = window.session.store
    before = {p: p.read_bytes() for p in store.root.rglob("*.json")}
    requests = []
    page.model.setCurrentText("qwen3-asr-flash-realtime")

    async def key(_reference):
        return "fixture-only"

    class Client:
        async def models(self, *_args):
            requests.append("models")
            return [
                "qwen3-asr-flash",
                "qwen3-asr-flash-realtime",
                "qwen3-asr-flash-filetrans",
            ]

    window.session.key = key
    window.session.provider_client = lambda _role: Client()
    asyncio.run(page.discover())
    return page, requests, before


def test_protocol_switch_relabels_existing_models_without_network_or_config_save(
    window, discovered_protocol_models
):
    page, requests, before = discovered_protocol_models
    page.key.setText("unsaved-fixture-key")
    model = page.model.currentText()
    rate = window.session.store.load_settings().sample_rate
    assert [page.model.itemText(i) for i in range(page.model.count())] == [
        "qwen3-asr-flash"
    ]
    page.protocol.setCurrentIndex(page.protocol.findData(PROTOCOL))
    assert [page.model.itemText(i) for i in range(page.model.count())] == [
        "qwen3-asr-flash-realtime"
    ]
    assert "边录边识别" in page.model_hint.text()
    page.protocol.setCurrentIndex(page.protocol.findData("http"))
    assert [page.model.itemText(i) for i in range(page.model.count())] == [
        "qwen3-asr-flash"
    ]
    assert page.model.currentText() == model
    assert page.key.text() == "unsaved-fixture-key"
    assert window.session.store.load_settings().sample_rate == rate
    assert before == {
        p: p.read_bytes() for p in window.session.store.root.rglob("*.json")
    }
    assert requests == ["models"]


@pytest.mark.parametrize("field", ["url", "endpoint", "model", "json"])
def test_invalid_configuration_clears_old_model_marks_and_repair_refreshes(
    window, discovered_protocol_models, field
):
    page, requests, before = discovered_protocol_models
    page.protocol.setCurrentIndex(page.protocol.findData(PROTOCOL))
    if field == "url":
        page.url.setText("https://dashscope.aliyuncs.com:invalid")
    elif field == "endpoint":
        page.realtime_url.setText("wss://fixture-user:fixture-secret@example.invalid/r")
    elif field == "model":
        page.model.setCurrentText("")
    else:
        page.parameters.setPlainText(
            json.dumps({"asr_protocol": PROTOCOL, "asr_options": {}})
        )
    for index in range(page.model.count()):
        assert page.model.itemData(index, Qt.ItemDataRole.ToolTipRole) is None
        assert page.model.itemData(index, Qt.ItemDataRole.ForegroundRole) is None
    assert "已选择边录边识别" not in page.model_hint.text()
    assert "协议尚不支持" not in page.message.text()

    if field == "url":
        page.url.setText("https://dashscope.aliyuncs.com/compatible-mode/v1")
    elif field == "endpoint":
        page.realtime_url.setText("")
    elif field == "model":
        page.model.setCurrentText("qwen3-asr-flash-realtime")
    else:
        page.parameters.setPlainText(json.dumps({"asr_protocol": PROTOCOL}))
    assert "边录边识别" in page.model_hint.text()
    assert [page.model.itemText(i) for i in range(page.model.count())] == [
        "qwen3-asr-flash-realtime"
    ]
    assert page.model.itemData(0, Qt.ItemDataRole.ForegroundRole) is None
    assert requests == ["models"]
    assert before == {
        p: p.read_bytes() for p in window.session.store.root.rglob("*.json")
    }


def test_protocol_json_relabels_models_but_bad_json_remains_untouched(
    window, discovered_protocol_models
):
    page, requests, before = discovered_protocol_models
    page.parameters.setPlainText(json.dumps({"asr_protocol": PROTOCOL}))
    assert page.model.itemData(1, Qt.ItemDataRole.ForegroundRole) is None
    bad = '{"unfinished":'
    page.parameters.setPlainText(bad)
    assert "JSON" in page.model_hint.text()
    assert all(
        page.model.itemData(i, Qt.ItemDataRole.ForegroundRole) is None
        for i in range(page.model.count())
    )
    page.url.setText("https://proxy.example.invalid/v1")
    page.protocol.setCurrentIndex(page.protocol.findData("http"))
    assert page.parameters.toPlainText() == bad
    assert "JSON" in page.model_hint.text()
    page.parameters.setPlainText("{}")
    assert page.protocol.currentData() == "http"
    assert [page.model.itemText(i) for i in range(page.model.count())] == [
        "qwen3-asr-flash"
    ]
    assert page.model.currentText() == "qwen3-asr-flash-realtime"
    assert requests == ["models"]
    assert before == {
        p: p.read_bytes() for p in window.session.store.root.rglob("*.json")
    }


def test_discovery_with_missing_custom_wss_does_not_mark_all_models_unsupported(
    window,
):
    async def scenario():
        page = window.models_page.transcription
        page.model.setCurrentText("qwen3-asr-flash-realtime")
        page.protocol.setCurrentIndex(page.protocol.findData(PROTOCOL))
        page.url.setText("https://proxy.example.invalid/v1")
        requests = []

        async def key(_reference):
            return "fixture-only"

        class Client:
            async def models(self, *_args):
                requests.append("models")
                return ["qwen3-asr-flash", "qwen3-asr-flash-realtime"]

        window.session.key = key
        window.session.provider_client = lambda _role: Client()
        await page.discover()
        assert "服务配置或请求参数不正确" in page.model_hint.text()
        assert "1 个模型" in page.message.text()
        assert "协议尚不支持" not in page.message.text()
        for index in range(page.model.count()):
            assert page.model.itemData(index, Qt.ItemDataRole.ToolTipRole) is None
            assert page.model.itemData(index, Qt.ItemDataRole.ForegroundRole) is None
        page.realtime_url.setText("wss://proxy.example.invalid/realtime")
        assert "边录边识别" in page.model_hint.text()
        assert page.model.count() == 1
        assert page.model.itemData(0, Qt.ItemDataRole.ForegroundRole) is None
        assert requests == ["models"]

    asyncio.run(scenario())


@pytest.mark.parametrize("control", ["protocol", "json"])
def test_pending_discovery_cannot_mark_or_replace_models_after_protocol_edit(
    window, control
):
    async def scenario():
        page = window.models_page.transcription
        page.model.addItem("existing-model")
        page.model.setCurrentText("qwen3-asr-flash-realtime")
        entered, release = asyncio.Event(), asyncio.Event()

        async def key(_reference):
            return "fixture-only"

        class Client:
            async def models(self, *_args):
                entered.set()
                await release.wait()
                return ["late-model", "qwen3-asr-flash-filetrans"]

        window.session.key = key
        window.session.provider_client = lambda _role: Client()
        pending = asyncio.create_task(page.discover())
        await entered.wait()
        if control == "protocol":
            page.protocol.setCurrentIndex(page.protocol.findData(PROTOCOL))
        else:
            page.parameters.setPlainText(json.dumps({"asr_protocol": PROTOCOL}))
        page.message.setText("edited form")
        release.set()
        await pending
        assert page.message.text() == "edited form"
        assert page.model.findText("existing-model") == -1
        assert page.model.findText("late-model") == -1
        assert page.model.findText("qwen3-asr-flash-filetrans") == -1
        assert page.model.currentText() == "qwen3-asr-flash-realtime"
        assert page.protocol.currentData() == PROTOCOL
        assert "边录边识别" in page.model_hint.text()

    asyncio.run(scenario())


def test_provider_save_does_not_overwrite_settings_during_credential_wait(window):
    async def scenario():
        page = window.models_page.polishing
        waiting, release = asyncio.Event(), asyncio.Event()
        written = []

        async def save_key(reference, value):
            written.append((reference, value))
            waiting.set()
            await release.wait()

        window.session.save_key = save_key
        page.key.setText("temporary-test-secret")
        preferences = window.settings_page
        preferences.polishing_enabled.setChecked(True)
        preferences.streaming.setChecked(False)
        preferences.fallback.setChecked(False)
        original = page.identifier
        request = asyncio.create_task(page.save())
        await waiting.wait()
        assert page.key.text() == ""
        page.new()
        preferences.polishing_enabled.setChecked(False)
        preferences.streaming.setChecked(True)
        preferences.fallback.setChecked(True)
        release.set()
        await request
        settings = window.session.store.load_settings()
        assert settings.polishing_provider == original
        assert not settings.polishing_enabled
        assert settings.polishing_fallback
        assert settings.polishing_streaming
        assert page.identifier != original
        assert written[0][1] == "temporary-test-secret"
        assert (
            "temporary-test-secret"
            not in (window.session.store.root / "config.json").read_text()
        )

    asyncio.run(scenario())


def test_protocol_controls_preserve_json_model_rate_and_saved_configuration(window):
    page = window.models_page.transcription
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
        page = window.models_page.transcription
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
    page = window.models_page.transcription
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
    page = window.models_page.transcription
    page.model.setCurrentText("qwen3-asr-flash-realtime")
    page.protocol.setCurrentIndex(page.protocol.findData(PROTOCOL))
    config = RealtimeConfig.from_provider(page.provider())
    assert config.url.startswith("wss://dashscope.aliyuncs.com/api-ws/v1/realtime?")
    assert page.realtime_url.text() == ""
    assert "边录边识别" in page.model_hint.text()


def test_custom_realtime_requires_wss_before_credentials_or_microphone(window):
    async def scenario():
        page = window.models_page.transcription
        page.model.setCurrentText("qwen3-asr-flash-realtime")
        page.url.setText("https://proxy.example.invalid/v1")
        page.protocol.setCurrentIndex(page.protocol.findData(PROTOCOL))

        async def forbidden(*_args, **_kwargs):
            raise AssertionError("preflight must precede external access")

        window.session.key = forbidden
        window.session.sample_audio = forbidden
        await page.run(page.save())
        assert "服务配置或请求参数不正确" in page.message.text()
        page.realtime_url.setText("wss://proxy.example.invalid/realtime")
        page.validate_protocol(page.provider())
        assert page.provider().parameters["realtime_url"] == page.realtime_url.text()

    asyncio.run(scenario())


def test_realtime_sample_rate_preflight_does_not_change_settings_or_record(window):
    async def scenario():
        page = window.models_page.transcription
        store = window.session.store
        store.save_settings(replace(store.load_settings(), sample_rate=48000))
        page.model.setCurrentText("qwen3-asr-flash-realtime")
        page.protocol.setCurrentIndex(page.protocol.findData(PROTOCOL))

        async def forbidden(*_args, **_kwargs):
            raise AssertionError("sample rate preflight must run first")

        window.session.key = forbidden
        window.session.sample_audio = forbidden
        await page.run(page.save())
        assert "16 kHz" in page.message.text()
        assert store.load_settings().sample_rate == 48000

    asyncio.run(scenario())


@pytest.mark.parametrize("control", ["protocol", "endpoint", "json"])
def test_new_provider_controls_invalidate_late_status(window, control):
    async def scenario():
        page = window.models_page.transcription
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
        else:
            page.parameters.setPlainText('{"asr_options":{}}')
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
        page = window.models_page.transcription
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


def test_http_draft_requires_explicit_model_before_save(window):
    async def scenario():
        page = window.models_page.transcription
        page.new()
        assert page.model.currentText() == ""
        with pytest.raises(ConfigError):
            await page.save()
        assert page.selector.findData(page.identifier) == -1

    asyncio.run(scenario())


def test_preset_uses_new_credential_reference_and_never_overwrites_old_provider(window):
    page = window.models_page.transcription
    old = page.provider()
    before = {p: p.read_bytes() for p in window.session.store.root.rglob("*.json")}
    page.key.setText("unsaved-synthetic")
    select_platform(page, "groq")
    item = page.provider()
    assert item.id != old.id and item.key_ref != old.key_ref
    assert (
        item.adapter == "multipart"
        and item.base_url == "https://api.groq.com/openai/v1"
    )
    assert page.key.text() == ""
    assert before == {
        p: p.read_bytes() for p in window.session.store.root.rglob("*.json")
    }
    page.new()
    assert page.preset.currentIndex() == -1 and page.name.text() == ""


def test_static_model_catalog_never_reads_secrets_or_claims_connection(window):
    page = window.models_page.transcription
    select_platform(page, "elevenlabs")

    async def key(_):
        pytest.fail("built-in list must not read credentials or contact network")

    window.session.key = key
    asyncio.run(page.discover())
    assert (
        "尚未联网验证" in page.message.text() and "连接成功" not in page.message.text()
    )
    assert page.model.count() == 2


def test_unknown_manual_id_is_preserved_but_known_text_capability_is_blocked(window):
    page = window.models_page.transcription
    select_platform(page, "custom-asr")
    page.url.setText("https://example.invalid/v1")
    page.model.setCurrentText("private-future-speech-v7")
    assert "能力未知" in page.model_hint.text()
    page.model.setCurrentText("deepseek-chat")
    with pytest.raises(ProviderError) as caught:
        page.validate_protocol(page.provider())
    assert caught.value.code == "protocol"


def test_realtime_preset_switch_resets_protocol_and_endpoint_draft(window):
    page = window.models_page.transcription
    page.protocol.setCurrentIndex(page.protocol.findData(PROTOCOL))
    page.realtime_url.setText("wss://fixture.invalid/realtime")
    select_platform(page, "groq")
    assert page.protocol.currentData() == "http" and not page.protocol.isEnabled()
    assert page.realtime_url.text() == "" and page.provider().parameters == {}
    page.validate_protocol(page.provider())
    select_platform(page, "qwen")
    assert page.protocol.currentData() == "http" and page.protocol.isEnabled()
    assert page.provider().parameters == {}
    page.validate_protocol(page.provider())


def test_step_realtime_preset_has_own_protocol_and_16khz_validation(window):
    page = window.models_page.transcription
    select_platform(page, "stepfun-realtime")
    assert page.protocol.currentData() == "stepfun_realtime"
    assert page.provider().adapter == "stepfun-realtime"
    assert page.provider().model == "stepaudio-2.5-asr-stream"
    assert page.provider().parameters == {"asr_protocol": "stepfun_realtime"}
    page.validate_protocol(page.provider())
    select_platform(page, "groq")
    assert page.protocol.currentData() == "http" and page.provider().parameters == {}


@pytest.mark.parametrize("preset", ["dashscope-fun", "stepfun-realtime"])
def test_unselected_ws_url_secret_is_rejected_before_credential_save(window, preset):
    page = window.models_page.transcription
    select_platform(page, preset)
    page.parameters.setPlainText(
        json.dumps({"realtime_url": "wss://user:secret@fixture.invalid/asr"})
    )
    page.key.setText("not-to-save")
    before = {p: p.read_bytes() for p in window.session.store.root.rglob("*.json")}

    async def forbidden(*_):
        pytest.fail("invalid endpoint must precede secret access")

    window.session.save_key = forbidden

    async def scenario():
        await page.run(page.save())

    asyncio.run(scenario())
    assert "服务配置或请求参数不正确" in page.message.text()
    assert page.key.text() == "not-to-save"
    assert before == {
        p: p.read_bytes() for p in window.session.store.root.rglob("*.json")
    }


@pytest.mark.parametrize(
    "preset,fields",
    [
        ("xfyun", ("app_id", "api_key", "api_secret")),
        ("tencent-asr", ("app_id", "secret_id", "secret_key")),
        ("volcengine-app", ("app_key", "access_key")),
    ],
)
def test_multi_credentials_save_one_secret_bundle_and_blank_preserves(
    window, preset, fields
):
    async def scenario():
        page = window.models_page.transcription
        select_platform(page, preset)
        if preset.startswith("volcengine"):
            page.resource_id.setText("synthetic-resource")
        saved = []

        async def save_key(reference, value):
            saved.append((reference, value))

        window.session.save_key = save_key
        for name in fields:
            page.credential_inputs[name].setText(
                "123" if name == "app_id" else "test-" + name
            )
        reference = page.reference
        await page.save()
        assert len(saved) == 1 and saved[0][0] == reference
        bundle = json.loads(saved[0][1])
        assert set(bundle) == set(fields)
        assert all(not widget.text() for widget in page.credential_inputs.values())
        await page.save()
        assert len(saved) == 1
        provider = window.session.store.load_provider(page.identifier)
        assert not any(name in provider.parameters for name in fields)

    asyncio.run(scenario())


def test_partial_credential_bundle_does_not_write_anything(window):
    async def scenario():
        page = window.models_page.transcription
        select_platform(page, "xfyun")
        page.credential_inputs["app_id"].setText("123")

        async def forbidden(*args):
            pytest.fail(
                "partial credentials must be rejected before FileCredentialStore"
            )

        window.session.save_key = forbidden
        before = window.session.store.providers()
        with pytest.raises(ConfigError):
            await page.save()
        assert window.session.store.providers() == before

    asyncio.run(scenario())


def test_volc_credential_mode_requires_new_ref_and_complete_bundle(window):
    async def scenario():
        page = window.models_page.transcription
        select_platform(page, "volcengine-key")
        page.resource_id.setText("synthetic-resource")
        page.key.setText("old-synthetic")
        saved = []

        async def save_key(reference, value):
            saved.append((reference, value))

        window.session.save_key = save_key
        await page.save()
        old_id, old_ref = page.identifier, page.reference
        values = page.parameter_values()
        values["credential_mode"] = "app_access"
        page.parameters.setPlainText(json.dumps(values))
        assert page.credential_inputs["app_key"].isHidden() is False
        assert page.key.isHidden()
        with pytest.raises(ConfigError):
            await page.save()
        page.credential_inputs["app_key"].setText("new-app")
        page.credential_inputs["access_key"].setText("new-access")
        await page.save()
        assert page.identifier != old_id and page.reference != old_ref
        assert window.session.store.load_provider(old_id).key_ref == old_ref
        assert len(saved) == 2 and saved[-1][0] != old_ref
        page.load()
        assert page.preset.currentData() == "volcengine-app"
        assert page.credential_fields() == ("app_key", "access_key")
        assert page.parameter_values()["credential_mode"] == "app_access"

    asyncio.run(scenario())


def test_dashscope_static_discovery_includes_paraformer_without_secret_access(window):
    async def scenario():
        page = window.models_page.transcription
        select_platform(page, "dashscope-paraformer")

        async def forbidden(*args):
            pytest.fail("static discovery must not read credentials")

        window.session.key = forbidden
        await page.discover()
        assert "paraformer-realtime-v2" in page.available_models
        assert "尚未联网验证" in page.message.text()
        assert "连接成功" not in page.message.text()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "preset,adapter",
    [
        ("openai-responses", "responses"),
        ("anthropic-messages", "messages"),
        ("gemini-native", "gemini"),
        ("opencode-responses", "responses"),
        ("minimax-chat", "openai"),
    ],
)
def test_polishing_native_presets_select_protocol_without_reusing_credentials(
    window, preset, adapter
):
    page = window.models_page.polishing
    old_ref = page.reference
    page.key.setText("unsaved-old-key")
    select_platform(page, preset)
    assert page.provider().adapter == adapter
    assert page.reference != old_ref and not page.key.text()
    assert "当前协议" in page.model_hint.text()


def test_qwen_protocol_picker_disables_other_vendor_protocols(window):
    page = window.models_page.transcription
    select_platform(page, "qwen")
    for index in range(page.protocol.count()):
        allowed = page.protocol.itemData(index) in {"http", PROTOCOL}
        assert page.protocol.model().item(index).isEnabled() == allowed
    page.parameters.setPlainText(json.dumps({"asr_protocol": "unsupported-mode"}))
    assert page.protocol.currentIndex() == -1
    assert page.parameter_values()["asr_protocol"] == "unsupported-mode"


def test_provider_page_persists_bundle_in_own_config_file(window):
    from inkecho.provider_credentials import decode_credentials
    from inkecho.security import FileCredentialStore

    async def scenario():
        page = window.models_page.transcription
        select_platform(page, "volcengine-app")
        page.model.setCurrentText("bigmodel")
        page.resource_id.setText("synthetic-resource")
        page.credential_inputs["app_key"].setText("synthetic-app")
        page.credential_inputs["access_key"].setText("synthetic-access")
        await page.save()
        reference = page.reference
        saved = FileCredentialStore(window.session.store.root).get(reference)
        assert decode_credentials(saved, ("app_key", "access_key")) == {
            "app_key": "synthetic-app",
            "access_key": "synthetic-access",
        }
        assert await window.session.key(reference) == saved
        ordinary = (
            window.session.store.root / "providers" / f"{page.identifier}.json"
        ).read_text()
        assert "synthetic-access" not in ordinary and "synthetic-app" not in ordinary
        page.load()
        assert not any(widget.text() for widget in page.credential_inputs.values())
        select_platform(page, "groq")
        assert page.reference != reference
        with pytest.raises(ConfigError, match="完整凭据"):
            await page.save()
        assert (
            FileCredentialStore(window.session.store.root).get(page.reference) is None
        )
        assert FileCredentialStore(window.session.store.root).get(reference) == saved

    async def bounded():
        await asyncio.wait_for(scenario(), timeout=8)

    asyncio.run(bounded())


@pytest.mark.parametrize("style", ["siri", "waveform", "pulse"])
def test_wayland_displays_every_configured_overlay_style(window, qt_app, style):
    window.wayland = True
    window.notify = lambda *args, **kwargs: None
    window.session.store.save_settings(
        replace(window.session.store.load_settings(), overlay_style=style)
    )
    window.update_state("recording")
    qt_app.processEvents()
    assert window.overlay.isVisible()
    assert window.overlay.style == style
    assert "启动" in window.overlay.caption()
    window.overlay.set_capture_ready(True)
    assert window.overlay.caption() == "正在聆听"
    window.session.preview.emit("Synthetic preview")
    assert window.overlay.text == "Synthetic preview"
    window.update_state("cancelled")
    assert not window.overlay.capture_ready
    assert not window.overlay.text
    window.update_state("idle")


def test_shortcut_config_failure_restores_previous_registration(window, monkeypatch):
    async def scenario():
        page = window.settings_page.recording
        store = window.session.store
        previous = store.load_settings().shortcut
        registered = []

        async def operation(function, shortcut, command):
            registered.append(shortcut)

        def fail(_settings):
            raise OSError("isolated synthetic save failure")

        monkeypatch.setattr("inkecho.ui.settings.asyncio.to_thread", operation)
        monkeypatch.setattr(store, "save_settings", fail)
        await page.enable("Ctrl+F8")
        assert registered == ["Ctrl+F8", previous]
        assert store.load_settings().shortcut == previous
        assert page.shortcut.text() == previous

    asyncio.run(scenario())


def test_help_release_link_shares_update_row_and_shows_actual_environment(window):
    from PySide6.QtWidgets import QLabel

    page = window.help_page
    assert page.update_button.parentWidget() == page.release.parentWidget()
    labels = [item.text() for item in page.findChildren(QLabel)]
    assert any("X11" in text for text in labels)
    assert not any("不使用剪贴板" in text for text in labels)
