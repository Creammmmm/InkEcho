#!/usr/bin/env python3
"""Real microphone/local HTTPS/current-cursor workflow in owned desktop windows.

Requires explicit native validation coordination. No cloud, user credential,
clipboard or system input method is used. The production keyboard transport is
restricted by an additional test-only ownership check before key presses.
"""

import argparse
import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import replace
from pathlib import Path

import httpx
from PySide6.QtWidgets import QApplication
from qasync import QEventLoop
from voice_workflow_probe import SAMPLE, LocalProvider, TestSecret, wait_for

import inkecho
from inkecho.app import Session
from inkecho.config import ConfigStore
from inkecho.core import State
from inkecho.integration import DesktopIntegration
from inkecho.logging import DiagnosticLog

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feasibility"))

from historical_accessibility import (
    ACCESSIBLE,
    ACTIVE,
    EDITABLE,
    EDITABLE_STATE,
    FOCUSED,
    ROOT,
    AccessibilityInput,
    has_state,
)

from inkecho.platform.keyboard import KeyboardError
from inkecho.providers import ProviderClient
from inkecho.statistics import Statistics
from inkecho.ui.window import MainWindow


class OwnedWindow:
    def __init__(self, process, output, access, *, editable):
        self.process, self.output, self.access = process, output, access
        self.editable = editable
        self.address = None

    def snapshot(self):
        if not self.output.exists():
            return None
        state = json.loads(self.output.read_text())
        if state["pid"] != self.process.pid:
            raise RuntimeError("Fixture PID mismatch")
        return state

    async def focused(self):
        state = self.snapshot()
        if (
            self.process.poll() is not None
            or state is None
            or time.monotonic() - state["sampled_at"] > 1
            or not state["window_active"]
            or not state["has_focus"]
        ):
            return False
        if self.address is None:
            applications = (await self.access._call(ROOT, ACCESSIBLE, "GetChildren"))[0]
            for address in applications:
                try:
                    pid = await self.access._external_process_id(tuple(address))
                except Exception:
                    continue
                if pid == self.process.pid:
                    self.address = tuple(address)
                    break
        if self.address is None:
            return False
        if await self.access._external_process_id(self.address) != self.process.pid:
            raise RuntimeError("Accessible application ownership changed")
        windows = (await self.access._call(self.address, ACCESSIBLE, "GetChildren"))[0]
        for window in windows:
            if not has_state(await self.access._state(tuple(window)), ACTIVE):
                continue
            pending = [tuple(window)]
            visited = 0
            while pending and visited < 128:
                address = pending.pop()
                visited += 1
                states = await self.access._state(address)
                if has_state(states, FOCUSED):
                    interfaces = (
                        await self.access._call(address, ACCESSIBLE, "GetInterfaces")
                    )[0]
                    editable = EDITABLE in interfaces and has_state(
                        states, EDITABLE_STATE
                    )
                    return editable == self.editable
                pending.extend(
                    tuple(item)
                    for item in (
                        await self.access._call(address, ACCESSIBLE, "GetChildren")
                    )[0]
                )
        return False

    def guard_send(self, driver, window):
        """Restrict a synchronous send to this live owned XWayland window."""
        state = self.snapshot()
        if (
            self.process.poll() is not None
            or state is None
            or not 0 <= time.monotonic() - state["sampled_at"] <= 0.5
            or not state["window_active"]
            or not state["has_focus"]
        ):
            raise KeyboardError("unsupported_target")
        # The production focus query checks that the focus window descends from
        # the compositor's active X window. This extra ownership check exists
        # only in the harness, never in the production adapter.
        if driver.focus() != window:
            raise KeyboardError("unsupported_target")
        with driver._checked():
            active = driver._property(driver.root, driver.active_atom)
            pid = driver._property(active, driver.pid_atom) if active else 0
        if pid != self.process.pid:
            raise KeyboardError("unsupported_target")
        if driver.focus() != window:
            raise KeyboardError("unsupported_target")

    async def wait_focused(self):
        async with asyncio.timeout(5):
            while not await self.focused():
                await asyncio.sleep(0.03)


async def probe(args):
    if os.environ.get("XDG_SESSION_TYPE") != "wayland":
        raise RuntimeError("Native Wayland session required")
    if not QApplication.platformName().startswith("wayland"):
        raise RuntimeError("Qt must use native Wayland")
    if args.fixture_backend != "x11":
        raise RuntimeError("This keyboard transport requires owned XWayland fixtures")
    package = Path(inkecho.__file__).resolve()
    if not package.is_relative_to(args.package_root.resolve()):
        raise RuntimeError("Unexpected application import root")
    fixture = (
        Path(__file__).resolve().parents[1] / "feasibility/current_cursor_fixture.py"
    )
    children = []
    session = window = log = local = None
    access = AccessibilityInput()
    states, outcomes, diagnostics, notifications = [], [], [], []
    presses = 0
    with tempfile.TemporaryDirectory(prefix="inkecho-current-cursor-") as temporary:
        folder = Path(temporary)

        def launch(mode):
            environment = dict(os.environ, GDK_BACKEND=args.fixture_backend)
            for name in ("PYTHONHOME", "PYTHONPATH", "LD_LIBRARY_PATH"):
                environment.pop(name, None)
            output = folder / f"{mode}.json"
            child = subprocess.Popen(
                ["/usr/bin/python3", str(fixture), mode, str(output)], env=environment
            )
            children.append(child)
            return OwnedWindow(child, output, access, editable=mode == "editor")

        try:
            local = LocalProvider(folder)
            # Polishing is disabled below, so only ASR requests are delayed.
            local.delay = 2
            store = ConfigStore(folder / "config")
            store.initialize()
            for entry in store.providers():
                store.save_provider(replace(entry, base_url=local.url, model="fixture"))
            store.save_settings(replace(store.load_settings(), polishing_enabled=False))
            stats = Statistics(folder / "statistics.json")
            log = DiagnosticLog(folder / "logs")
            async with httpx.AsyncClient(verify=local.context, trust_env=False) as http:
                session = Session(
                    store, client=ProviderClient(http=http), secrets=TestSecret()
                )
                if type(session.inputs).__name__ != "KeyboardInput":
                    raise RuntimeError("The production keyboard adapter is required")
                integration = DesktopIntegration(
                    Path(sys.executable),
                    data_home=folder / "desktop-data",
                    config_home=folder / "desktop-config",
                )
                window = MainWindow(session, stats, log, integration, [sys.executable])
                session.state_changed.connect(states.append)
                session.finished.connect(lambda item: outcomes.append(item["outcome"]))
                session.diagnostic.connect(diagnostics.append)
                original_show = window.notifications.show

                async def show(message, **options):
                    accepted = await original_show(message, **options)
                    notifications.append(accepted)
                    return accepted

                window.notifications.show = show
                await session.initialize()
                assert session.connected
                # Initialize the actual transport before creating either target.
                assert await session.authorize_input()
                await access.connect()
                first = launch("button")
                await first.wait_focused()
                second = None

                original_emit = session.inputs._send
                driver = session.inputs._driver
                original_map = driver._mapping()

                def guarded_emit(window, keycode, pressed):
                    nonlocal presses
                    if pressed:
                        task = session.controller.task
                        if task is None or second is None:
                            raise KeyboardError("input_cancelled")
                        second.guard_send(driver, window)
                        if not session.active(task.id):
                            raise KeyboardError("input_cancelled")
                        presses += 1
                    # No await between validation and the actual send. Release
                    # events bypass the test gate so cancellation cannot stick a key.
                    return original_emit(window, keycode, pressed)

                session.inputs._send = guarded_emit

                async def begin_recording():
                    before = len(diagnostics)
                    session.last_toggle = 0
                    window.handle_command("toggle")
                    await wait_for(
                        lambda: (
                            session.controller.state == State.RECORDING
                            or len(diagnostics) > before
                        )
                    )
                    assert session.controller.state == State.RECORDING, diagnostics
                    await asyncio.sleep(0.65)
                    assert session.controller.state == State.RECORDING
                    assert not any(
                        item.isVisible() for item in QApplication.topLevelWidgets()
                    )

                await begin_recording()
                assert await first.focused(), "Noneditable window lost focus"
                window.handle_command("toggle")
                await wait_for(lambda: len(local.requests) == 1)
                assert session.controller.state == State.TRANSCRIBING
                second = launch("editor")
                await second.wait_focused()
                assert session.controller.state == State.TRANSCRIBING
                assert not await first.focused()
                await wait_for(lambda: session.controller.task is None, seconds=10)
                await wait_for(lambda: second.snapshot()["text"] == SAMPLE)
                assert first.snapshot()["text"] == ""
                assert outcomes == ["succeeded"], (outcomes, diagnostics)
                assert session.recorder.source is None and not session.recorder.pcm

                await begin_recording()
                window.handle_command("toggle")
                await wait_for(lambda: len(local.requests) == 2)
                before_cancel = presses
                window.handle_command("cancel")
                await asyncio.sleep(local.delay + 0.3)
                assert session.controller.task is None
                assert second.snapshot()["text"] == SAMPLE
                assert presses == before_cancel
                assert outcomes == ["succeeded", "cancelled"], outcomes
                assert session.recorder.source is None and not session.recorder.pcm
                await wait_for(lambda: not session.ui_tasks)
                assert notifications and all(notifications)
                assert stats.today()["characters"] == len(SAMPLE)
                assert not list(folder.rglob("*.wav"))

                def normalized(mapping):
                    width, values = mapping
                    rows = []
                    for offset in range(0, len(values), width):
                        row = list(values[offset : offset + width])
                        while row and row[-1] == 0:
                            row.pop()
                        rows.append(row)
                    return rows

                assert normalized(original_map) == normalized(driver._mapping())
                result = {
                    "passed": True,
                    "version": inkecho.__version__,
                    "package_module": str(package),
                    "host_session": "wayland",
                    "fixture_backend": args.fixture_backend,
                    "target_transport": (
                        "xwayland"
                        if args.fixture_backend == "x11"
                        else "native-wayland"
                    ),
                    "recording_started_on_noneditable_target": True,
                    "focus_change_during_transcription_did_not_cancel": True,
                    "output_reached_new_focus": True,
                    "exact_unicode_characters": len(SAMPLE),
                    "cancelled_late_reply_unchanged": True,
                    "guarded_key_presses": presses,
                    "normalized_keyboard_map_restored": True,
                    "notifications_accepted": len(notifications),
                    "visible_qt_windows": 0,
                    "states": states,
                    "diagnostics": diagnostics,
                    "statistics": stats.today(),
                    "requests": local.requests,
                    "real_microphone": True,
                    "local_verified_https_only": True,
                    "audio_files_written": False,
                    "real_credentials_used": False,
                    "cloud_requested": False,
                    "clipboard_used": False,
                    "system_input_method_used": False,
                    "physical_shortcut_tested": False,
                    "focus_change_during_emission_tested": False,
                    "partial_output_cancel_tested": False,
                }
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(result, indent=2) + "\n")
                print(json.dumps(result, indent=2), flush=True)
        finally:
            if session:
                await session.close()
            if window:
                await window.notifications.shutdown()
                window.dispose()
            access.close()
            if log:
                log.handler.close()
            for child in reversed(children):
                if child.poll() is None:
                    child.terminate()
                try:
                    child.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
            if local:
                local.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument(
        "--fixture-backend",
        choices=("x11", "wayland"),
        required=True,
        help="Explicitly distinguish XWayland targets from native Wayland targets",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    with QEventLoop(app) as loop:
        asyncio.set_event_loop(loop)
        loop.run_until_complete(asyncio.wait_for(probe(args), 90))


if __name__ == "__main__":
    main()
