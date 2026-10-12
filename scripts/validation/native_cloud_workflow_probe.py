#!/usr/bin/env python3
"""Opt-in public WAV → real configured cloud → owned native GTK input.

Recorder is replaced by a public-file source. No ambient audio is captured.
Transcripts and secrets stay in memory; only safe outcome metadata is printed.
Run only after coordinating exclusive desktop focus with other validation agents.
"""

import argparse
import asyncio
import hashlib
import io
import json
import os
import subprocess
import time
import wave
from contextlib import contextmanager
from pathlib import Path

from dbus_next import Message, MessageType
from dbus_next.aio import MessageBus
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication
from qasync import QEventLoop

import inkecho
import inkecho.config as configuration
from inkecho import __version__
from inkecho.app import Session
from inkecho.config import ConfigStore
from inkecho.core import State
from inkecho.platform.accessibility import TEXT, AccessibilityInput, InputUnavailable
from inkecho.providers import ProviderClient

PUBLIC_SHA256 = "0d650ab4f08bd3a5d3d59fd67d085fd0765ddabe4729294f4106fceece321fdf"


class ConfigurationWriteBlocked(RuntimeError):
    """The diagnostic must not migrate, back up, or save user configuration."""


@contextmanager
def read_only_configuration():
    def reject_write(*_args, **_kwargs):
        raise ConfigurationWriteBlocked(
            "Configuration writes are disabled in this probe"
        )

    original = configuration.atomic_write
    configuration.atomic_write = reject_write
    try:
        yield
    finally:
        configuration.atomic_write = original


class PublicAudio(QObject):
    level = Signal(float)
    finished = Signal(bytes, float)
    failed = Signal(str)

    def __init__(self, audio):
        super().__init__()
        self.audio = audio
        with wave.open(io.BytesIO(audio), "rb") as wav:
            self.duration = wav.getnframes() / wav.getframerate()
        self.active = False

    def start(self, *_args, **_kwargs):
        self.active = True
        return True

    def stop(self):
        if self.active:
            self.active = False
            self.finished.emit(self.audio, self.duration)

    def cancel(self):
        self.active = False


class OwnedInput(AccessibilityInput):
    def __init__(self):
        super().__init__()
        self.owned_pid = None

    async def capture_target(self):
        target = await super().capture_target()
        if target.process_id != self.owned_pid:
            raise InputUnavailable("Owned fixture is not focused")
        return target

    async def inject(self, target, text, can_continue):
        if target.process_id != self.owned_pid:
            raise InputUnavailable("Unexpected target process")
        await super().inject(target, text, can_continue)


class BoundedClient(ProviderClient):
    """Delegate requests unchanged to production client, with per-role limits."""

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.calls = {"transcription": 0, "polishing": 0}
        self.expected = ""
        self.polish_succeeded = False

    async def transcribe(self, provider, key, audio):
        if self.calls["transcription"]:
            raise RuntimeError("ASR call limit")
        self.calls["transcription"] += 1
        result = await ProviderClient(
            timeout_seconds=self.settings.transcription_timeout_seconds
        ).transcribe(provider, key, audio)
        self.expected = result.text
        return result

    async def polish(self, provider, key, text, prompt):
        if self.calls["polishing"]:
            raise RuntimeError("Polishing call limit")
        self.calls["polishing"] += 1
        result = await ProviderClient(
            timeout_seconds=self.settings.polishing_timeout_seconds
        ).polish(provider, key, text, prompt)
        self.expected = result.text
        self.polish_succeeded = True
        return result


async def probe(args):
    with read_only_configuration():
        return await _probe(args)


async def _probe(args):
    if not args.allow_live_cloud:
        raise RuntimeError("Explicit live-cloud opt-in required")
    if os.environ.get("XDG_SESSION_TYPE") != "wayland":
        raise RuntimeError("Native Wayland required")
    if not QApplication.platformName().startswith("wayland"):
        raise RuntimeError("Native Qt Wayland required")
    if not Path(inkecho.__file__).resolve().is_relative_to(args.package_root.resolve()):
        raise RuntimeError("Extracted package imports required")
    audio = args.sample.read_bytes()
    if hashlib.sha256(audio).hexdigest() != PUBLIC_SHA256:
        raise RuntimeError("Public fixture hash mismatch")
    bus = await MessageBus().connect()
    try:
        reply = await bus.call(
            Message(
                destination="org.gnome.ScreenSaver",
                path="/org/gnome/ScreenSaver",
                interface="org.gnome.ScreenSaver",
                member="GetActive",
            )
        )
        if reply.message_type == MessageType.ERROR or reply.body != [False]:
            raise RuntimeError("Unlocked session required")
    finally:
        bus.disconnect()

    store = ConfigStore()
    settings = store.load_settings()
    client = BoundedClient(settings)
    inputs = OwnedInput()
    session = Session(store, inputs=inputs, recorder=PublicAudio(audio), client=client)
    outcomes, states, diagnostics = [], [], []
    session.finished.connect(lambda result: outcomes.append(result["outcome"]))
    session.state_changed.connect(states.append)
    session.diagnostic.connect(diagnostics.append)
    child = None
    started = time.monotonic()
    report = {"version": __version__, "real_microphone": False, "public_sample": True}
    try:
        await session.initialize()
        if not session.connected:
            raise RuntimeError("Accessibility unavailable")
        fixture = (
            Path(__file__).resolve().parents[1]
            / "feasibility/wayland_editor_fixture.py"
        )
        child = subprocess.Popen(
            ["/usr/bin/python3", str(fixture), "-"],
            env={
                **os.environ,
                "GDK_BACKEND": "wayland",
                "PYTHONHOME": "",
                "PYTHONPATH": "",
            },
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        inputs.owned_pid = child.pid
        await asyncio.sleep(1.2)
        target = await inputs.capture_target()
        assert target.process_id == child.pid and await inputs._current(target)
        await session.toggle()
        assert session.controller.state == State.RECORDING
        assert session.controller.task.target.process_id == child.pid
        await asyncio.sleep(0.4)
        assert await inputs._current(inputs.target)
        await session.toggle()
        async with asyncio.timeout(125):
            while session.controller.task:
                await asyncio.sleep(0.025)
        assert outcomes == ["succeeded"]
        assert await inputs._external_process_id(inputs.target.address) == child.pid
        received = (
            await inputs._call(inputs.target.address, TEXT, "GetText", "ii", [0, -1])
        )[0]
        report.update(
            passed=received == client.expected and bool(received),
            characters=len(received),
            owned_output_matches_returned_text=received == client.expected,
            polishing_enabled=settings.polishing_enabled,
            polishing_succeeded=client.polish_succeeded,
            fallback_enabled=settings.polishing_fallback,
        )
        del received
    except Exception as error:
        report.update(passed=False, error_type=type(error).__name__)
    finally:
        report.update(
            states=states,
            outcomes=outcomes,
            diagnostic_codes=diagnostics,
            calls=client.calls,
            seconds=round(time.monotonic() - started, 3),
            transcript_saved=False,
            clipboard_accessed=False,
        )
        await session.close()
        client.expected = ""
        if child and child.poll() is None:
            child.terminate()
            await asyncio.wait_for(asyncio.to_thread(child.wait), 5)
    print(json.dumps(report))
    return report["passed"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", type=Path, required=True)
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--allow-live-cloud", action="store_true")
    args = parser.parse_args()
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    with QEventLoop(app) as loop:
        asyncio.set_event_loop(loop)
        try:
            passed = loop.run_until_complete(asyncio.wait_for(probe(args), 145))
        except Exception as error:
            print(
                json.dumps(
                    {"passed": False, "preflight_error_type": type(error).__name__}
                )
            )
            passed = False
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
