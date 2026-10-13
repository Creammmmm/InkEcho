"""Focused acceptance using extracted package code and disposable settings.

Historical alpha6 acceptance: its injected adapter uses the old Session API.
Use the corresponding historical checkout/artifact, not current product code.
"""

import asyncio
import json
import os
import tempfile
from dataclasses import replace
from pathlib import Path

from PySide6.QtWidgets import QApplication

import inkecho.app
from inkecho.app import AudioError, Session
from inkecho.config import ConfigStore
from inkecho.core import State


class ControlledInput:
    def target_is_current(self, _target):
        return True

    def close(self):
        pass


class ForbiddenCredentials:
    def get(self, _reference):
        raise AssertionError("This acceptance must not access credentials")


async def main():
    packaged = Path(os.environ["PYTHONPATH"]).resolve()
    assert Path(inkecho.app.__file__).resolve().is_relative_to(packaged)
    unhandled = []
    asyncio.get_running_loop().set_exception_handler(
        lambda _loop, context: unhandled.append(context)
    )
    with tempfile.TemporaryDirectory(prefix="inkecho-alpha6-audio-") as temporary:
        store = ConfigStore(Path(temporary) / "config")
        store.initialize()
        store.save_settings(
            replace(store.load_settings(), microphone=b"absent-test-device".hex())
        )
        session = Session(
            store, inputs=ControlledInput(), secrets=ForbiddenCredentials()
        )
        problems, diagnostics = [], []
        session.problem.connect(problems.append)
        session.diagnostic.connect(diagnostics.append)
        try:
            try:
                await session.sample_audio(seconds=0)
                raise AssertionError("Absent device must fail")
            except AudioError as error:
                assert error.code == "microphone_unavailable"
                assert "所选麦克风当前不可用" in str(error)
            assert diagnostics == ["microphone_unavailable"]
            assert not session.testing
            verified = []
            for reason, expected in (
                ("recording_timed_out", "recording_timed_out"),
                ("microphone_interrupted", "microphone_interrupted"),
                ("empty_recording", "empty_recording"),
                ("private-untrusted-detail", "audio_failed"),
            ):
                diagnostics.clear()
                problems.clear()
                assert session.controller.begin(object())
                session.recorder.failed.emit(reason)
                assert session.controller.state == State.IDLE
                assert session.controller.task is None
                assert session.audio_failure is None
                assert diagnostics == [expected]
                assert len(problems) == 1
                assert "private-untrusted-detail" not in problems[0]
                verified.append(expected)
            assert session.recorder.source is None and not session.recorder.pcm
            assert not list(Path(temporary).rglob("*.wav"))
        finally:
            await session.close()
        await asyncio.sleep(0)
        assert not unhandled
    result = {
        "passed": True,
        "actual_recorder_missing_device": True,
        "controlled_active_task_failures": verified,
        "raw_reason_sanitized": True,
        "unhandled_async_errors": 0,
        "microphone_recorded": False,
        "cloud_called": False,
        "credential_accessed": False,
        "native_input_tested": False,
        "packaged_module": str(inkecho.app.__file__),
    }
    Path("build/audio-alpha6-feedback-result.json").write_text(
        json.dumps(result, indent=2) + "\n"
    )
    print(json.dumps(result, indent=2))


application = QApplication([])
asyncio.run(main())
