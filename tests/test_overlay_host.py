"""Display IPC stays bounded, ordered and independent of input/credentials."""

import asyncio
import copy
import json
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QProcess

from inkecho.ui import overlay_proxy
from inkecho.ui.overlay_host import MAX_FRAME, DisplayChannel, decode_frame


def frame(revision=1, state="recording", text="Synthetic preview"):
    return {
        "revision": revision,
        "state": state,
        "text": text,
        "level": 0.5,
        "capture_ready": False,
        "settings": {
            "overlay_style": "siri",
            "overlay_opacity": 0.8,
            "overlay_position": "bottom-center",
            "overlay_seconds": 2.0,
        },
    }


def test_decode_display_snapshot():
    value = frame()
    assert decode_frame(json.dumps(value).encode()) == value


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("revision", True),
        ("revision", -1),
        ("state", "unknown"),
        ("text", "x" * 241),
        ("text", None),
        ("level", float("nan")),
        ("level", True),
        ("level", 1.1),
        ("capture_ready", 1),
    ],
)
def test_decode_rejects_invalid_fields(field, value):
    value_frame = frame()
    value_frame[field] = value
    with pytest.raises(ValueError):
        decode_frame(json.dumps(value_frame))


@pytest.mark.parametrize("extra", ["api_key", "base_url", "model", "parameters"])
def test_decode_rejects_non_display_configuration(extra):
    value = frame()
    value["settings"][extra] = "synthetic-only"
    with pytest.raises(ValueError):
        decode_frame(json.dumps(value))


def test_decode_rejects_extra_envelope_and_oversized_frame():
    value = frame()
    value["command"] = "inject"
    for encoded in (json.dumps(value), b" " * (MAX_FRAME + 1), "[]", "{"):
        with pytest.raises(ValueError):
            decode_frame(encoded)


class FakeOverlay:
    def __init__(self):
        self.state = "idle"
        self.visible = False
        self.text = ""
        self.states = []

    def isVisible(self):
        return self.visible

    def show_state(self, state):
        self.state = state
        self.visible = state != "idle"
        self.states.append(state)

    def set_text(self, text):
        self.text = text

    def set_capture_ready(self, ready):
        self.capture_ready = ready

    def set_level(self, level):
        self.level = level


@pytest.mark.parametrize("terminal", ["idle", "cancelled", "failed", "succeeded"])
def test_channel_terminal_clears_and_older_snapshot_cannot_revive(terminal):
    overlay, store = FakeOverlay(), SimpleNamespace()
    channel = DisplayChannel(overlay, store)
    channel.apply(frame(1))
    assert overlay.text == "Synthetic preview"
    channel.apply(frame(3, terminal, "must be discarded"))
    assert overlay.text == ""
    channel.apply(frame(2))
    channel.apply(frame(3))
    assert overlay.state == terminal
    assert overlay.text == ""
    assert channel.revision == 3
    assert vars(store.settings) == frame()["settings"]


class Event:
    def connect(self, callback):
        self.callback = callback


class FakeProcess:
    ProcessChannelMode = QProcess.ProcessChannelMode
    ProcessState = QProcess.ProcessState
    nullDevice = staticmethod(QProcess.nullDevice)

    def __init__(self, _):
        for name in (
            "started",
            "readyReadStandardOutput",
            "bytesWritten",
            "errorOccurred",
            "finished",
        ):
            setattr(self, name, Event())
        self.status = self.ProcessState.NotRunning
        self.writes, self.starts = [], []
        self.output = b""
        self.write_closed = False
        self.queued = 0

    def setProcessEnvironment(self, environment):
        self.environment = environment

    def setProcessChannelMode(self, mode):
        self.mode = mode

    def setStandardErrorFile(self, path):
        self.error_path = path

    def state(self):
        return self.status

    def start(self, executable, args):
        self.starts.append((executable, args))
        self.status = self.ProcessState.Starting

    def bytesToWrite(self):
        return self.queued

    def write(self, data):
        self.writes.append(data)
        return len(data)

    def readAllStandardOutput(self):
        data, self.output = self.output, b""
        return data

    def closeWriteChannel(self):
        self.write_closed = True


@pytest.fixture
def proxy(monkeypatch):
    monkeypatch.setattr(overlay_proxy, "QProcess", FakeProcess)
    settings = SimpleNamespace(**frame()["settings"], api_key="synthetic-not-real")
    instance = overlay_proxy.OverlayProxy(
        SimpleNamespace(load_settings=lambda: settings)
    )
    yield instance
    instance.close()


def test_proxy_starts_display_only_child_and_coalesces_pending_frames(proxy):
    proxy.show_state("recording")
    assert len(proxy.process.starts) == 1
    assert proxy.process.environment.value("QT_QPA_PLATFORM") == "xcb"
    assert proxy.process.starts[0][1] == ["-m", "inkecho.ui.overlay_host"]
    proxy.set_text("obsolete")
    proxy.set_text("latest")
    proxy.process.status = QProcess.ProcessState.Running
    proxy.flush()
    assert len(proxy.process.writes) == 1
    decoded = decode_frame(proxy.process.writes[0])
    assert decoded["text"] == "latest"
    assert "api_key" not in decoded["settings"]
    assert b"synthetic-not-real" not in proxy.process.writes[0]


def test_proxy_cancellation_replaces_buffered_draft(proxy):
    proxy.show_state("recording")
    proxy.set_text("draft")
    proxy.show_state("cancelled")
    proxy.process.status = QProcess.ProcessState.Running
    proxy.flush()
    assert decode_frame(proxy.process.writes[-1])["text"] == ""
    assert proxy.text == ""


@pytest.mark.parametrize("callback", ["process_error", "finished"])
def test_host_failure_reports_once_clears_preview_and_closes_stdin(proxy, callback):
    failures = []
    proxy.failed.connect(failures.append)
    proxy.show_state("recording")
    proxy.set_text("draft")
    getattr(proxy, callback)(1)
    getattr(proxy, callback)(1)
    assert len(failures) == 1
    assert "录音与输入仍可继续" in failures[0]
    assert proxy.broken and proxy.process.write_closed
    assert proxy.text == "" and proxy.pending is None
    assert not proxy.isVisible()


def test_proxy_ignores_old_reply_and_accepts_current_metadata(proxy):
    proxy.show_state("recording")
    proxy.set_text("current")
    reply = {
        "revision": proxy.state_revision - 1,
        "visible": True,
        "exposed": True,
        "text_length": 99,
    }
    proxy.process.output = json.dumps(reply).encode() + b"\n"
    proxy.read_reply()
    assert not proxy.isVisible()
    reply.update(revision=proxy.revision, text_length=7)
    proxy.process.output = json.dumps(reply).encode() + b"\n"
    proxy.read_reply()
    assert proxy.isVisible() and proxy.exposed and proxy.text_length == 7


def test_proxy_close_uses_eof_and_no_restart(proxy):
    proxy.show_state("recording")
    starts = copy.copy(proxy.process.starts)
    proxy.close()
    proxy.show_state("recording")
    proxy.set_text("must not be queued")
    proxy.flush()
    assert proxy.process.write_closed
    assert proxy.pending is None and proxy.text == ""
    assert proxy.process.starts == starts
    assert not proxy.timer.isActive()
    proxy.process.status = QProcess.ProcessState.NotRunning
    asyncio.run(proxy.shutdown())


def test_host_eof_hides_and_quits_without_real_desktop(monkeypatch):
    from inkecho.ui import overlay_host

    events = []

    class Application:
        def __init__(self, _):
            pass

        def setApplicationName(self, _):
            pass

        def setDesktopFileName(self, _):
            pass

        def setWindowIcon(self, _):
            pass

        def setQuitOnLastWindowClosed(self, _):
            pass

        def platformName(self):
            return "xcb"

        def exec(self):
            notifier[0].activated.callback()
            return 0

        def quit(self):
            events.append("quit")

    class HostOverlay:
        def __init__(self, _):
            pass

        def hide(self):
            events.append("hide")

        def close(self):
            events.append("close")

    notifier = []

    class Notifier:
        Type = overlay_host.QSocketNotifier.Type

        def __init__(self, *_):
            self.activated = Event()
            notifier.append(self)

        def setEnabled(self, enabled):
            events.append(("notifier", enabled))

    class Timer:
        def __init__(self):
            self.timeout = Event()

        def setInterval(self, _):
            pass

        def start(self):
            pass

    monkeypatch.setattr(overlay_host, "QApplication", Application)
    monkeypatch.setattr(overlay_host, "Overlay", HostOverlay)
    monkeypatch.setattr(overlay_host, "QSocketNotifier", Notifier)
    monkeypatch.setattr(overlay_host.sys, "stdin", SimpleNamespace(fileno=lambda: 0))
    monkeypatch.setattr(overlay_host.os, "read", lambda *_: b"")
    monkeypatch.setattr("PySide6.QtCore.QTimer", Timer)
    assert overlay_host.main() == 0
    assert events == [("notifier", False), "hide", "close", "quit"]


def deliver_reply(proxy, revision, *, visible=True, exposed=True):
    proxy.process.output = (
        json.dumps(
            {
                "revision": revision,
                "visible": visible,
                "exposed": exposed,
                "text_length": 3,
            }
        ).encode()
        + b"\n"
    )
    proxy.read_reply()


def test_current_state_ack_survives_continuous_level_snapshots(proxy):
    proxy.show_state("recording")
    acknowledged = proxy.revision
    for level in (0.1, 0.2, 0.3):
        proxy.set_level(level)
    assert acknowledged < proxy.revision
    deliver_reply(proxy, acknowledged)
    assert proxy.visible and proxy.exposed
    assert proxy.last_ack_revision == acknowledged
    assert not proxy.ack_timeout.isActive()
    # An equal revision may later become exposed without another snapshot.
    deliver_reply(proxy, acknowledged, exposed=False)
    assert proxy.visible and not proxy.exposed
    deliver_reply(proxy, acknowledged, exposed=True)
    assert proxy.exposed


def test_cancel_rejects_prior_state_ack_even_when_level_updates_follow(proxy):
    proxy.show_state("recording")
    proxy.set_level(0.4)
    previous = proxy.revision
    deliver_reply(proxy, previous)
    proxy.show_state("cancelled")
    deliver_reply(proxy, proxy.state_revision, visible=False, exposed=False)
    deliver_reply(proxy, previous)
    assert not proxy.visible and not proxy.exposed
    assert proxy.last_ack_revision == proxy.state_revision


def test_first_ack_timeout_fails_safely_without_restart(proxy):
    errors = []
    proxy.failed.connect(errors.append)
    proxy.show_state("recording")
    assert proxy.ack_timeout.isActive()
    assert proxy.ack_timeout.interval() == 3000
    proxy.ack_timeout.timeout.emit()
    proxy.process.status = QProcess.ProcessState.NotRunning
    proxy.show_state("recording")
    proxy.set_text("must stay cleared")
    proxy.set_level(0.8)
    proxy.flush()
    assert len(errors) == 1
    assert proxy.broken and proxy.process.write_closed
    assert len(proxy.process.starts) == 1
    assert proxy.pending is None and proxy.text == ""
    assert not proxy.ack_timeout.isActive()


def test_shutdown_stuck_owned_host_has_bounded_kill_cleanup(proxy, monkeypatch):
    proxy.process.status = QProcess.ProcessState.Running
    deadlines, killed = [], []

    async def bounded_wait(awaitable, timeout):
        deadlines.append(timeout)
        if len(deadlines) == 1:
            awaitable.close()
            raise TimeoutError
        return await awaitable

    def kill():
        killed.append(True)
        proxy.process.status = QProcess.ProcessState.NotRunning

    monkeypatch.setattr(overlay_proxy.asyncio, "wait_for", bounded_wait)
    monkeypatch.setattr(proxy.process, "kill", kill, raising=False)
    errors = []
    proxy.failed.connect(errors.append)
    asyncio.run(proxy.shutdown())
    assert deadlines == [3, 3]
    assert killed == [True]
    assert proxy.closed and proxy.process.write_closed
    assert proxy.pending is None and proxy.text == ""
    assert len(errors) == 1
    assert not proxy.timer.isActive()


def test_capture_ready_is_display_only_and_clears_at_terminal(proxy):
    proxy.show_state("recording")
    proxy.set_capture_ready(True)
    assert decode_frame(proxy.pending)["capture_ready"] is True
    proxy.show_state("cancelled")
    assert decode_frame(proxy.pending)["capture_ready"] is False
    proxy.set_capture_ready(True)
    assert decode_frame(proxy.pending)["capture_ready"] is False
