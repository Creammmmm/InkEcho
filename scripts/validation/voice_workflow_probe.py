#!/usr/bin/env python3
"""Actual microphone + HTTPS + Session + AT-SPI on an isolated X11 fixture.

Only a local test provider receives RAM audio; fixed replies do not prove ASR quality.
"""

import argparse
import asyncio
import base64
import io
import json
import os
import ssl
import subprocess
import tempfile
import threading
import time
import wave
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx
from PySide6.QtWidgets import QApplication
from qasync import QEventLoop

from inkecho.app import Session
from inkecho.config import ConfigStore
from inkecho.core import State
from inkecho.providers import ProviderClient
from inkecho.statistics import Statistics
from inkecho.ui.overlay import Overlay

SAMPLE = "你好 InkEcho，世界！ café Ω 😀\n第二行。"


class TestSecret:
    def get(self, _reference):
        return "disposable-local-test-key"


class LocalProvider:
    def __init__(self, folder):
        cert, key = folder / "cert.pem", folder / "key.pem"
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
                "subjectAltName=IP:127.0.0.1",
            ],
            check=True,
            capture_output=True,
        )
        self.requests = []
        self.delay = 0
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                message = body["messages"][0]["content"]
                metadata = {"audio_bytes": 0, "polishing": isinstance(message, str)}
                if not metadata["polishing"]:
                    data = base64.b64decode(
                        message[0]["input_audio"]["data"].split(",")[1]
                    )
                    with wave.open(io.BytesIO(data), "rb") as audio:
                        assert audio.getnchannels() == 1
                        assert audio.getsampwidth() == 2
                        assert audio.getframerate() == 16000
                        assert audio.getnframes() > 0
                    metadata["audio_bytes"] = len(data)
                    del data
                owner.requests.append(metadata)
                del body, message
                time.sleep(owner.delay)
                reply = json.dumps(
                    {
                        "choices": [{"message": {"content": SAMPLE}}],
                        "usage": {
                            "prompt_tokens": 5,
                            "completion_tokens": 7,
                            "total_tokens": 12,
                        },
                    }
                ).encode()
                try:
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(reply)))
                    self.end_headers()
                    self.wfile.write(reply)
                except (BrokenPipeError, ConnectionResetError, ssl.SSLError):
                    pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert, key)
        self.server.socket = context.wrap_socket(self.server.socket, server_side=True)
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.context = ssl.create_default_context(cafile=str(cert))
        self.url = f"https://127.0.0.1:{self.server.server_port}/v1"

    def close(self):
        self.server.shutdown()
        self.worker.join(timeout=3)
        self.server.server_close()


async def wait_for(predicate, seconds=5):
    async with asyncio.timeout(seconds):
        while not predicate():
            await asyncio.sleep(0.02)


async def probe(args):
    if os.environ.get("DISPLAY") in (None, ":0", ":1"):
        raise RuntimeError("Use a private Xvfb display, never a user's display.")
    if os.environ.get("XDG_SESSION_TYPE") != "x11":
        raise RuntimeError("This diagnostic requires an isolated X11 session.")
    fixture = Path(__file__).resolve().parents[1] / "feasibility/gtk_target.py"
    with tempfile.TemporaryDirectory(prefix="inkecho-voice-acceptance-") as temporary:
        folder = Path(temporary)
        output = folder / "received.json"
        provider = LocalProvider(folder)
        process = subprocess.Popen(
            ["/usr/bin/python3", str(fixture), "editor", str(output)],
            env=dict(os.environ, GDK_BACKEND="x11", PYTHONHOME="", PYTHONPATH=""),
        )
        session = overlay = None
        try:
            await wait_for(output.exists)

            def xdo(*values):
                return subprocess.check_output(
                    [args.xdotool, *values], text=True
                ).strip()

            window = xdo(
                "search", "--pid", str(process.pid), "--name", "InkEcho isolated editor"
            ).splitlines()[-1]
            store = ConfigStore(folder / "config")
            store.initialize()
            for entry in store.providers():
                store.save_provider(
                    replace(entry, base_url=provider.url, model="local-fixture")
                )
            store.save_settings(replace(store.load_settings(), polishing_enabled=True))
            stats = Statistics(folder / "statistics.json")
            outcomes = []
            async with httpx.AsyncClient(
                verify=provider.context, trust_env=False
            ) as http:
                session = Session(
                    store, client=ProviderClient(http=http), secrets=TestSecret()
                )
                session.finished.connect(
                    lambda result: outcomes.append(result["outcome"])
                )
                session.finished.connect(lambda result: stats.record(**result))
                overlay = Overlay(store)
                session.state_changed.connect(overlay.show_state)
                session.level.connect(overlay.set_level)
                await session.initialize()
                assert session.connected

                async def record():
                    xdo("windowfocus", window)
                    await asyncio.sleep(0.25)
                    session.last_toggle = 0
                    await session.toggle()
                    assert session.controller.state == State.RECORDING, outcomes
                    await asyncio.sleep(0.6)
                    assert xdo("getwindowfocus") == window, "Overlay stole target focus"
                    await session.toggle()

                await record()
                await wait_for(lambda: session.controller.task is None)
                await wait_for(lambda: json.loads(output.read_text()) == SAMPLE)
                assert outcomes == ["succeeded"], outcomes
                assert stats.today()["characters"] == len(SAMPLE)
                assert stats.today()["total_tokens"] == 12
                assert session.recorder.source is None and not session.recorder.pcm

                provider.delay = 0.8
                for action in ("cancel", "focus"):
                    before = len(provider.requests)
                    await record()
                    await wait_for(lambda count=before: len(provider.requests) > count)
                    if action == "cancel":
                        session.cancel()
                    else:
                        xdo("windowfocus", "1")
                        await asyncio.sleep(0.15)
                        xdo("windowfocus", window)
                    await asyncio.sleep(1)
                    assert session.controller.task is None
                    assert json.loads(output.read_text()) == SAMPLE
                    assert session.recorder.source is None and not session.recorder.pcm
                assert outcomes == ["succeeded", "cancelled", "cancelled"], outcomes
                assert not list(folder.rglob("*.wav"))
                result = {
                    "passed": True,
                    "display": os.environ["DISPLAY"],
                    "real_microphone": True,
                    "tls_verified_local_provider": True,
                    "real_cloud_asr_quality_tested": False,
                    "exact_unicode": True,
                    "overlay_preserved_focus": True,
                    "cancelled_reply_unchanged": True,
                    "focus_away_back_reply_unchanged": True,
                    "statistics": stats.today(),
                    "requests": provider.requests,
                    "audio_files_written": False,
                    "credential_backend": "disposable injected fixture",
                    "clipboard_accessed": False,
                }
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(result, indent=2) + "\n")
                print(json.dumps(result, indent=2))
        finally:
            if session:
                await session.close()
            if overlay:
                overlay.close()
            process.terminate()
            process.wait(timeout=5)
            provider.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xdotool", default="xdotool")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    with QEventLoop(app) as loop:
        asyncio.set_event_loop(loop)
        loop.run_until_complete(asyncio.wait_for(probe(args), 40))


if __name__ == "__main__":
    main()
