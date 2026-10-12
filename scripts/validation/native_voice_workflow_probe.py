#!/usr/bin/env python3
"""Native Wayland package workflow using owned GTK and localhost-only RAM audio.

The hidden production MainWindow supplies the actual desktop notification policy.
No physical shortcut, cloud quality, arbitrary application or clipboard is tested.
"""

import argparse
import asyncio
import json
import os
import subprocess
import sys
import tempfile
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
from inkecho.platform.accessibility import AccessibilityInput, InputUnavailable
from inkecho.providers import ProviderClient
from inkecho.statistics import Statistics
from inkecho.ui.window import MainWindow


class OwnedInput(AccessibilityInput):
    """Add an ownership restriction without changing production focus checks."""

    owner_pid = None
    captures = 0
    capture_error = None

    async def capture_target(self):
        try:
            target = await super().capture_target()
        except InputUnavailable as error:
            self.capture_error = str(error)
            raise
        if target.process_id != self.owner_pid or not await self._current(target):
            self.capture_error = "Owned PID or fresh focus check failed"
            raise InputUnavailable(self.capture_error)
        self.captures += 1
        return target


async def probe(args):
    if os.environ.get("XDG_SESSION_TYPE") != "wayland":
        raise RuntimeError("A native Wayland session is required")
    if not QApplication.platformName().startswith("wayland"):
        raise RuntimeError("Qt must use its native Wayland platform")
    package = Path(inkecho.__file__).resolve()
    if not package.is_relative_to(args.package_root.resolve()):
        raise RuntimeError("Application imports must come from the extracted package")
    fixture = (
        Path(__file__).resolve().parents[1] / "feasibility/wayland_editor_fixture.py"
    )
    children = []
    session = window = log = provider = None
    with tempfile.TemporaryDirectory(prefix="inkecho-native-voice-") as temporary:
        folder = Path(temporary)

        def editor(output):
            environment = dict(os.environ, GDK_BACKEND="wayland")
            for name in ("PYTHONHOME", "PYTHONPATH", "LD_LIBRARY_PATH"):
                environment.pop(name, None)
            child = subprocess.Popen(
                ["/usr/bin/python3", str(fixture), str(output)], env=environment
            )
            children.append(child)
            return child

        outcomes, states, notices, diagnostics = [], [], [], []
        inputs = OwnedInput()
        try:
            provider = LocalProvider(folder)
            store = ConfigStore(folder / "config")
            store.initialize()
            for entry in store.providers():
                store.save_provider(
                    replace(entry, base_url=provider.url, model="local-fixture")
                )
            store.save_settings(replace(store.load_settings(), polishing_enabled=True))
            stats = Statistics(folder / "statistics.json")
            log = DiagnosticLog(folder / "logs")
            async with httpx.AsyncClient(
                verify=provider.context, trust_env=False
            ) as http:
                session = Session(
                    store,
                    inputs=inputs,
                    client=ProviderClient(http=http),
                    secrets=TestSecret(),
                )
                integration = DesktopIntegration(
                    Path(sys.executable),
                    data_home=folder / "desktop-data",
                    config_home=folder / "desktop-config",
                )
                window = MainWindow(session, stats, log, integration, [sys.executable])
                assert window.wayland and not window.isVisible()
                session.finished.connect(lambda item: outcomes.append(item["outcome"]))
                session.state_changed.connect(states.append)
                session.diagnostic.connect(diagnostics.append)
                original_show = window.notifications.show

                async def observe_show(message, **options):
                    accepted = await original_show(message, **options)
                    notices.append(
                        {"accepted": accepted, "recording": options.get("recording")}
                    )
                    return accepted

                window.notifications.show = observe_show
                await session.initialize()
                assert session.connected
                output = folder / "received.json"
                owned = editor(output)
                inputs.owner_pid = owned.pid
                await wait_for(output.exists)
                await asyncio.sleep(1.2)

                async def record():
                    session.last_toggle = 0
                    window.handle_command("toggle")
                    previous_diagnostics = len(diagnostics)
                    await wait_for(
                        lambda: (
                            session.controller.state == State.RECORDING
                            or len(diagnostics) > previous_diagnostics
                        )
                    )
                    assert session.controller.state == State.RECORDING, diagnostics
                    await asyncio.sleep(0.65)
                    task = session.controller.task
                    assert task and task.target.process_id == owned.pid
                    assert await inputs._current(task.target)
                    assert not any(
                        widget.isVisible() for widget in QApplication.topLevelWidgets()
                    ), "A production Qt window unexpectedly mapped"
                    assert any(
                        item["accepted"] and item["recording"] for item in notices
                    )
                    window.handle_command("toggle")

                await record()
                await wait_for(lambda: session.controller.task is None)
                await wait_for(lambda: json.loads(output.read_text()) == SAMPLE)
                assert outcomes == ["succeeded"], (outcomes, diagnostics)
                assert stats.today()["characters"] == len(SAMPLE)
                assert stats.today()["total_tokens"] == 12
                assert session.recorder.source is None and not session.recorder.pcm

                provider.delay = 0.8
                for action in ("cancel", "focus"):
                    before = len(provider.requests)
                    await record()
                    await wait_for(lambda count=before: len(provider.requests) > count)
                    if action == "cancel":
                        window.handle_command("cancel")
                    else:
                        other_output = folder / "other.json"
                        editor(other_output)
                        await wait_for(other_output.exists)
                    await wait_for(lambda: session.controller.task is None)
                    await asyncio.sleep(1)
                    assert json.loads(output.read_text()) == SAMPLE
                    assert session.recorder.source is None and not session.recorder.pcm
                assert outcomes == ["succeeded", "cancelled", "cancelled"], outcomes
                assert json.loads(other_output.read_text()) == ""
                await wait_for(lambda: not session.ui_tasks)
                assert notices and all(item["accepted"] for item in notices)
                assert not list(folder.rglob("*.wav"))
                result = {
                    "passed": True,
                    "version": inkecho.__version__,
                    "package_module": str(package),
                    "session": os.environ["XDG_SESSION_TYPE"],
                    "qt_platform": QApplication.platformName(),
                    "real_microphone": True,
                    "tls_verified_local_provider": True,
                    "production_main_window_notification_policy": True,
                    "notifications_accepted": len(notices),
                    "visible_qt_windows": 0,
                    "owned_pid_verified_captures": inputs.captures,
                    "capture_error": inputs.capture_error,
                    "exact_unicode_characters": len(SAMPLE),
                    "cancelled_late_reply_unchanged": True,
                    "native_focus_loss_late_reply_unchanged": True,
                    "second_owned_editor_unchanged": True,
                    "statistics": stats.today(),
                    "states": states,
                    "diagnostics": diagnostics,
                    "requests": provider.requests,
                    "audio_files_written": False,
                    "credential_backend": "disposable injected fixture",
                    "clipboard_accessed": False,
                    "cloud_asr_quality_tested": False,
                    "physical_shortcut_tested": False,
                    "physical_notification_action_tested": False,
                }
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(result, indent=2) + "\n")
                print(json.dumps(result, indent=2), flush=True)
        except Exception as error:
            failure = {
                "passed": False,
                "error": type(error).__name__,
                "states": states,
                "diagnostics": diagnostics,
                "owned_pid_verified_captures": inputs.captures,
                "capture_error": inputs.capture_error,
                "requests": provider.requests if provider else [],
            }
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(failure, indent=2) + "\n")
            print(json.dumps(failure), flush=True)
            raise
        finally:
            if session:
                await session.close()
            if window:
                await window.notifications.shutdown()
                window.dispose()
            if log:
                log.handler.close()
            for child in reversed(children):
                if child.poll() is None:
                    child.terminate()
                child.wait(timeout=5)
            if provider:
                provider.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    with QEventLoop(app) as loop:
        asyncio.set_event_loop(loop)
        loop.run_until_complete(asyncio.wait_for(probe(args), 45))


if __name__ == "__main__":
    main()
