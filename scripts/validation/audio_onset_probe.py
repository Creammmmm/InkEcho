#!/usr/bin/env python3
"""Measure Recorder against an owned virtual source, never a physical microphone.

Requires a running PulseAudio-compatible desktop service and pactl/paplay.
Creates two uniquely named temporary modules, leaves defaults unchanged, sends
only generated PCM, and prints timing/count metadata. No audio is written to disk.
"""

import json
import shutil
import struct
import subprocess
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer  # noqa: E402

from inkecho.audio import Recorder  # noqa: E402


def pulse(*args):
    return subprocess.run(
        ["pactl", *args], capture_output=True, check=True, text=True, timeout=5
    ).stdout.strip()


def run():
    if not all(shutil.which(name) for name in ("pactl", "paplay")):
        raise RuntimeError("synthetic_audio_tools_unavailable")
    defaults = (pulse("get-default-sink"), pulse("get-default-source"))
    suffix = uuid.uuid4().hex[:12]
    sink, source = f"inkecho_onset_{suffix}", f"inkecho_onset_source_{suffix}"
    description = f"InkEchoSyntheticOnset_{suffix}"
    modules = []
    recorder = None
    player = None
    try:
        for arguments in (
            ["module-null-sink", f"sink_name={sink}", "rate=16000", "channels=1"],
            [
                "module-remap-source",
                f"master={sink}.monitor",
                f"source_name={source}",
                f"source_properties=device.description={description}",
            ],
        ):
            module = pulse("load-module", *arguments)
            if not module.isdecimal():
                raise RuntimeError("invalid_owned_module_id")
            modules.append(module)
        app = QCoreApplication.instance() or QCoreApplication([])
        # Let Qt observe the new node; do not fall back to the default device.
        until = time.monotonic() + 3
        device = None
        while device is None and time.monotonic() < until:
            app.processEvents()
            device = next(
                (
                    identifier
                    for identifier, name in Recorder.devices()
                    if name == description
                ),
                None,
            )
            if device is None:
                time.sleep(0.02)
        if device is None:
            raise RuntimeError("owned_virtual_source_not_enumerated")
        results = []
        for _ in range(3):
            recorder = Recorder()
            loop = QEventLoop()
            clock = {"start": time.monotonic()}
            counts = {"bytes": 0, "nonzero_samples": 0}
            errors = []

            def capture(clock=clock):
                clock.setdefault("first_frame", time.monotonic())

            def consume(pcm, counts=counts, clock=clock):
                counts["bytes"] += len(pcm)
                samples = struct.unpack(f"<{len(pcm) // 2}h", pcm)
                nonzero = sum(abs(value) >= 2000 for value in samples)
                counts["nonzero_samples"] += nonzero
                if nonzero:
                    clock.setdefault("first_signal", time.monotonic())

            def play(clock=clock):
                nonlocal player
                clock["play_requested"] = time.monotonic()
                player = subprocess.Popen(
                    [
                        "paplay",
                        f"--device={sink}",
                        "--raw",
                        "--format=s16le",
                        "--rate=16000",
                        "--channels=1",
                    ],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                # 100 ms marker at the very beginning, then 300 ms silence.
                pcm = struct.pack("<1600h", *([8000, -8000] * 800)) + b"\0" * 9600
                player.stdin.write(pcm)
                player.stdin.close()

            recorder.capturing.connect(capture)
            recorder.pcm_ready.connect(consume)
            recorder.failed.connect(errors.append)
            if not recorder.start(device, streaming=True, max_seconds=3):
                raise RuntimeError("synthetic_capture_start_failed")
            QTimer.singleShot(80, play)
            QTimer.singleShot(1000, loop.quit)
            loop.exec()
            recorder.stop()
            if player is None or player.wait(timeout=3) != 0:
                raise RuntimeError("synthetic_playback_failed")
            player = None
            if errors or "first_frame" not in clock or "first_signal" not in clock:
                raise RuntimeError("synthetic_marker_not_captured")
            if counts["nonzero_samples"] < 1200:
                raise RuntimeError("synthetic_onset_marker_incomplete")
            results.append(
                {
                    "start_to_first_frame_ms": round(
                        (clock["first_frame"] - clock["start"]) * 1000, 3
                    ),
                    "play_to_first_signal_ms": round(
                        (clock["first_signal"] - clock["play_requested"]) * 1000, 3
                    ),
                    **counts,
                }
            )
            recorder.cancel()
            recorder.deleteLater()
            recorder = None
        print(json.dumps({"status": "passed", "synthetic_only": True, "runs": results}))
    finally:
        if recorder is not None:
            recorder.cancel()
        if player is not None and player.poll() is None:
            player.terminate()
            player.wait(timeout=3)
        cleanup_failed = False
        for module in reversed(modules):
            try:
                pulse("unload-module", module)
            except (subprocess.SubprocessError, OSError):
                cleanup_failed = True
        if (pulse("get-default-sink"), pulse("get-default-source")) != defaults:
            raise RuntimeError("audio_defaults_changed")
        if cleanup_failed:
            raise RuntimeError("owned_module_cleanup_failed")


if __name__ == "__main__":
    try:
        run()
    except Exception as error:
        # Do not expose service stderr, device details, or arbitrary exception text.
        print(json.dumps({"status": "failed", "error_type": type(error).__name__}))
        sys.exit(1)
