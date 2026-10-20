"""Synthetic-only localhost TLS acceptance for the selected package's Qwen VAD."""

import argparse
import asyncio
import importlib
import json
import logging
import ssl
import subprocess
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

FIRST, TAIL = "固定首句。", "固定尾句。"
QUIET = logging.Logger("inkecho.vad.fixture")
QUIET.disabled = True


async def probe(folder):
    from PySide6.QtCore import QObject, Signal
    from websockets.asyncio.server import serve
    from websockets.exceptions import ConnectionClosed

    import inkecho.realtime as wire
    from inkecho.app import Session
    from inkecho.config import ConfigStore, Provider, Settings
    from inkecho.qwen_vad import QwenVadSession

    cert, key = folder / "cert.pem", folder / "test-key.pem"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-keyout",
            str(key),
            "-out",
            str(cert),
            "-days",
            "1",
            "-subj",
            "/CN=localhost",
            "-addext",
            "subjectAltName=IP:127.0.0.1,DNS:localhost",
        ],
        check=True,
        capture_output=True,
        timeout=10,
    )
    server_tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_tls.load_cert_chain(cert, key)
    client_tls = ssl.create_default_context(cafile=str(cert))
    model = "qwen3-asr-flash-realtime"
    errors, commands, connections = [], [], []
    finished = asyncio.Event()

    async def handler(ws):
        connections.append(ws)
        counter, first = 0, False

        async def emit(kind, **body):
            nonlocal counter
            counter += 1
            await ws.send(json.dumps({"type": kind, "event_id": str(counter), **body}))

        await emit("session.created", session={"id": "s1", "model": model})
        try:
            async for message in ws:
                event = json.loads(message)
                commands.append(event["type"])
                if event["type"] == "session.update":
                    assert event["session"]["turn_detection"] == {
                        "type": "server_vad",
                        "threshold": 0.0,
                        "silence_duration_ms": 400,
                    }
                    await emit(
                        "session.updated",
                        session={"id": "s1", "model": model, **event["session"]},
                    )
                elif event["type"] == "input_audio_buffer.append" and not first:
                    first = True
                    await emit("input_audio_buffer.speech_started", item_id="one")
                    await emit("input_audio_buffer.speech_stopped", item_id="one")
                    await emit(
                        "input_audio_buffer.committed",
                        item_id="one",
                        previous_item_id=None,
                    )
                    await emit(
                        "conversation.item.input_audio_transcription.completed",
                        item_id="one",
                        transcript=FIRST,
                    )
                    await emit("input_audio_buffer.speech_started", item_id="two")
                elif event["type"] == "session.finish":
                    await emit(
                        "input_audio_buffer.committed",
                        item_id="two",
                        previous_item_id="one",
                    )
                    await emit(
                        "conversation.item.input_audio_transcription.completed",
                        item_id="two",
                        transcript=TAIL,
                    )
                    await emit("session.finished")
                    finished.set()
                    break
        except ConnectionClosed:
            pass
        except Exception as error:
            errors.append(type(error).__name__)

    class Recorder(QObject):
        level, pcm_ready = Signal(float), Signal(bytes)
        finished, failed = Signal(bytes, float), Signal(str)
        recording = False

        def start(self, *_args, **_options):
            self.recording = True
            return True

        def stop(self):
            self.recording = False
            self.finished.emit(b"", 0.1)

        def cancel(self):
            self.recording = False

    class Inputs:
        connected, authorized = True, False

        def __init__(self):
            self.inserted = []
            self.entered, self.release = asyncio.Event(), asyncio.Event()

        async def authorize(self):
            self.entered.set()
            await self.release.wait()
            self.authorized = True

        async def insert(self, text, can_continue, *, deadline=None):
            assert can_continue() and self.authorized
            self.inserted.append(text)
            return len(text)

        async def aclose(self):
            pass

    class NoHttp:
        async def transcribe(self, *_args):
            raise AssertionError("Unexpected HTTP transcription")

    results = []
    direct = wire._DirectConnect
    try:
        async with serve(
            handler, "127.0.0.1", 0, ssl=server_tls, logger=QUIET
        ) as server:
            port = server.sockets[0].getsockname()[1]

            def local_socket(_url, **options):
                options["ssl"] = client_tls
                return direct(f"wss://127.0.0.1:{port}/ws", **options)

            wire._DirectConnect = local_socket
            for cancel in (False, True):
                store = ConfigStore(folder / ("cancel" if cancel else "normal"))
                store.initialize()
                provider = Provider(
                    "synthetic",
                    "Synthetic",
                    "transcription",
                    "qwen",
                    "https://dashscope.aliyuncs.com/compatible-mode/v1",
                    model,
                    "synthetic",
                    {"asr_protocol": "qwen_realtime"},
                )
                store.save_provider(provider)
                store.save_settings(
                    replace(
                        Settings(),
                        transcription_provider=provider.id,
                        polishing_enabled=False,
                    )
                )
                inputs, recorder = Inputs(), Recorder()
                session = Session(
                    store, inputs=inputs, recorder=recorder, client=NoHttp()
                )
                previewed = asyncio.Event()
                done = asyncio.get_running_loop().create_future()
                session.preview.connect(
                    lambda text, seen=previewed: seen.set() if text == FIRST else None
                )
                session.finished.connect(
                    lambda result, target=done: (
                        target.set_result(result) if not target.done() else None
                    )
                )

                async def synthetic_key(_reference):
                    return "synthetic-not-a-real-key"

                session.key = synthetic_key
                toggle = asyncio.create_task(session.toggle())
                try:
                    await asyncio.wait_for(inputs.entered.wait(), 2)
                    connection = session.task_context["realtime"]
                    assert isinstance(connection, QwenVadSession)
                    recorder.pcm_ready.emit(b"\x01\x00" * 1600)
                    await asyncio.wait_for(previewed.wait(), 2)
                    assert recorder.recording and not inputs.inserted
                    if cancel:
                        session.cancel()
                    else:
                        session.stop_recording()
                        await asyncio.wait_for(finished.wait(), 2)
                        for _ in range(10):
                            await asyncio.sleep(0)
                        assert not inputs.inserted
                        inputs.release.set()
                    await toggle
                    outcome = await asyncio.wait_for(done, 2)
                    assert inputs.inserted == ([] if cancel else [FIRST + TAIL])
                    assert outcome["outcome"] == (
                        "cancelled" if cancel else "succeeded"
                    )
                    await session.close()
                    await asyncio.sleep(0)
                    assert (
                        connection._closed
                        and not connection._items
                        and not connection._committed
                    )
                    assert not session.pending and not recorder.recording
                    results.append(
                        {
                            "cancel": cancel,
                            "preview_before_stop": True,
                            "zero_input_before_consent_and_finish": True,
                            "final_exact_once": not cancel,
                            "cancel_zero_output": cancel,
                            "resources_cleared": True,
                        }
                    )
                finally:
                    await session.close()
            assert len(connections) == 2 and not errors
            assert "input_audio_buffer.commit" not in commands
    finally:
        wire._DirectConnect = direct
    return {
        "status": "passed",
        "synthetic_only": True,
        "real_cloud": False,
        "real_microphone": False,
        "real_keyboard": False,
        "connections": len(connections),
        "manual_commits": commands.count("input_audio_buffer.commit"),
        "cases": results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    select = parser.add_mutually_exclusive_group(required=True)
    select.add_argument("--package-root", type=Path)
    select.add_argument("--source-root", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    root = (args.package_root or args.source_root).resolve(strict=True)
    if args.package_root and not Path(sys.executable).resolve().is_relative_to(
        root.parent / "usr"
    ):
        raise RuntimeError("selected_package_interpreter_required")
    sys.path.insert(0, str(root))
    from PySide6.QtCore import QCoreApplication

    app = QCoreApplication.instance() or QCoreApplication([])
    assert app is not None
    with tempfile.TemporaryDirectory(prefix="inkecho-vad-fixture-") as temporary:
        result = asyncio.run(probe(Path(temporary)))
    import inkecho

    result["version"] = inkecho.__version__
    result["scope"] = "package" if args.package_root else "source"
    result["origins"] = {}
    for name in (
        "inkecho",
        "inkecho.app",
        "inkecho.realtime",
        "inkecho.qwen_vad",
        "inkecho.asr_streaming",
    ):
        origin = Path(importlib.import_module(name).__file__).resolve()
        if not origin.is_relative_to(root / "inkecho"):
            raise RuntimeError("module_origin_mismatch")
        result["origins"][name] = str(origin)
    with args.output.open("x") as output:
        output.write(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
