#!/usr/bin/env python3
"""Reproducible synthetic orchestration baseline; no microphone/network/keys."""

import argparse
import asyncio
import json
import os
import statistics
import tempfile
import time
from dataclasses import replace
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, Signal  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from inkecho.app import Session  # noqa: E402
from inkecho.config import ConfigStore  # noqa: E402
from inkecho.providers import Result, Usage  # noqa: E402


class Recorder(QObject):
    level = Signal(float)
    finished = Signal(bytes, float)
    failed = Signal(str)

    def start(self, *_args, **_kwargs):
        return True

    def stop(self):
        self.finished.emit(b"synthetic-not-audio", 1.0)

    def cancel(self):
        pass


class Client:
    def __init__(self, args):
        self.args = args

    async def transcribe(self, *_args):
        await asyncio.sleep(self.args.asr_ms / 1000)
        return Result("中" * self.args.characters, Usage(), 0)

    async def polish(self, *_args):
        await asyncio.sleep(self.args.polish_ms / 1000)
        return Result("中" * self.args.characters, Usage(), 0)


class Inputs:
    """Simulated transport with a measured synthetic dispatch callback."""

    supports_first_sent_callback = True
    connected = True
    authorized = True

    def __init__(self, args):
        self.args = args

    async def insert(self, text, can_continue, *, deadline=None, on_first_sent=None):
        count = 0
        for _character in text:
            await asyncio.sleep(self.args.char_ms / 3000)
            if not can_continue():
                return count
            if count == 0 and on_first_sent:
                on_first_sent(time.monotonic())
            count += 1
            await asyncio.sleep(self.args.char_ms / 1500)
        return count

    async def aclose(self):
        pass


async def baseline(args):
    with tempfile.TemporaryDirectory(prefix="inkecho-synthetic-timing-") as root:
        store = ConfigStore(Path(root))
        store.initialize()
        store.save_settings(
            replace(store.load_settings(), polishing_enabled=not args.no_polishing)
        )
        store.save_provider(replace(store.load_provider("qwen"), model="synthetic-asr"))
        store.save_provider(
            replace(store.load_provider("deepseek"), model="synthetic-polish")
        )
        session = Session(
            store, inputs=Inputs(args), recorder=Recorder(), client=Client(args)
        )

        async def no_credential(_reference):
            return "synthetic-not-a-key"

        session.key = no_credential
        samples = []
        session.performance.connect(samples.append)
        try:
            for _sample in range(args.samples):
                session.last_toggle = 0
                await session.toggle()
                session.last_toggle = 0
                await session.toggle()
                while session.pending:
                    await asyncio.gather(*list(session.pending))
        finally:
            await session.close()
    names = (
        "stop_to_first_character_ms",
        "output_ms",
        "stop_to_output_completed_ms",
    )
    result = {
        "evidence_kind": "synthetic_headless",
        "desktop_validated": False,
        "cloud_validated": False,
        "parameters": vars(args),
        "samples": samples,
        "median_ms": {
            name: statistics.median(
                sample["durations_ms"][name]
                for sample in samples
                if sample["durations_ms"][name] is not None
            )
            for name in names
        },
    }
    print(json.dumps(result, ensure_ascii=True, indent=2, allow_nan=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--characters", type=int, default=10)
    parser.add_argument("--asr-ms", type=float, default=150)
    parser.add_argument("--polish-ms", type=float, default=100)
    parser.add_argument("--char-ms", type=float, default=120)
    parser.add_argument("--no-polishing", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.samples <= 100 or not 1 <= args.characters <= 1000:
        parser.error("Samples/characters must be in the documented bounded range.")
    for value in (args.asr_ms, args.polish_ms, args.char_ms):
        if not 0 <= value <= 60_000:
            parser.error("Synthetic delays must be finite and between 0 and 60000 ms.")
    application = QApplication.instance() or QApplication([])
    application.setQuitOnLastWindowClosed(False)
    asyncio.run(baseline(args))


if __name__ == "__main__":
    main()
