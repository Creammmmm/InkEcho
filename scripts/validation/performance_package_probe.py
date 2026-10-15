"""Package-runtime smoke with loopback TLS and fixed simulated recognition.

Default capture and delivery are synthetic. The host desktop option uses a real
microphone; the Ubuntu 24 VM option keeps fixed synthetic audio. Both desktop
modes use the production X11 backend only in a newly owned GTK window.
Audio stays in RAM and goes only to the loopback fixture, never a cloud service.
"""

import argparse
import asyncio
import base64
import difflib
import hashlib
import importlib
import json
import logging
import os
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import unicodedata
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

FINAL = "你好，InkEcho！ café Ω 😀\n第二行。"
PARTS = ["你好，", "InkEcho！", " café Ω 😀\n第二行。"]
ASR_FINAL = "固定转写"
ASR_PREVIEW = "不会输出的预览"
ROOT = Path(__file__).resolve().parents[2]
QUIET = logging.Logger("inkecho.package.fixture")
QUIET.disabled = True


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def configure_environment(args):
    """Verify the selected desktop before starting Qt or owned input fixtures."""
    from keyboard_latency_probe import verify_ubuntu24_vm_x11

    real_microphone = args.owned_xwayland_live_mic
    real_desktop_input = real_microphone or args.owned_ubuntu24_vm_x11
    if real_microphone and args.owned_ubuntu24_vm_x11:
        raise RuntimeError("Choose one owned desktop mode")
    metadata = None
    if args.owned_ubuntu24_vm_x11:
        if not args.xdotool:
            raise RuntimeError("Ubuntu VM owned input requires xdotool")
        metadata = verify_ubuntu24_vm_x11()
        if os.environ.get("QT_QPA_PLATFORM", "xcb") != "xcb":
            raise RuntimeError(
                "Ubuntu VM owned input requires the actual X11 Qt platform"
            )
    elif real_microphone:
        if not args.xdotool or os.environ.get("XDG_SESSION_TYPE") != "wayland":
            raise RuntimeError("Coordinated host Wayland/XWayland and xdotool required")
    else:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return {
        "real_microphone": real_microphone,
        "real_desktop_input": real_desktop_input,
        "environment_metadata": metadata,
    }


def audit_appdir(appdir):
    inventory = json.loads(
        (appdir / "usr/share/doc/inkecho/inventory.json").read_text()
    )
    files = inventory["files"]
    if any(digest(appdir / name) != expected for name, expected in files.items()):
        raise RuntimeError("Packaged inventory checksum mismatch")
    for name, target in inventory["symlinks"].items():
        path = appdir / name
        if str(path.readlink()) != target or not path.resolve().is_relative_to(appdir):
            raise RuntimeError("Packaged symlink escaped its runtime")
    source_files = [
        path
        for path in (ROOT / "src/inkecho").rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    ]
    for source in source_files:
        relative = source.relative_to(ROOT / "src")
        if digest(source) != digest(appdir / "packages" / relative):
            raise RuntimeError("Application source does not match selected package")
    licenses = [
        appdir / "packages/websockets-15.0.1.dist-info/LICENSE",
        appdir / "usr/share/doc/inkecho/licenses/websockets-LICENSE.txt",
    ]
    if any(
        digest(path) != digest(ROOT / "assets/licenses/websockets-LICENSE.txt")
        for path in licenses
    ):
        raise RuntimeError("WebSocket license missing or changed")
    if inventory["python_distributions"].get("websockets") != "15.0.1":
        raise RuntimeError("Incorrect WebSocket runtime version")
    return {
        "inventory_application": inventory["application"],
        "inventory_files_verified": len(files),
        "inventory_links_verified": len(inventory["symlinks"]),
        "application_files_match_source": len(source_files),
        "websockets_license_copies_verified": len(licenses),
    }


async def wait_for(predicate, seconds=8):
    async with asyncio.timeout(seconds):
        while not predicate():
            await asyncio.sleep(0.01)


async def stable_text(read):
    previous = read()
    since = time.monotonic()
    async with asyncio.timeout(3):
        while time.monotonic() - since < 0.3:
            await asyncio.sleep(0.05)
            current = read()
            if current != previous:
                previous, since = current, time.monotonic()
    return previous


def fixture_sse_profile(name):
    if name == "normal":
        return list(PARTS), 0.35
    if name == "one-character-fast":
        return list(FINAL), 0.001
    if name == "one-character-fast-long":
        return list(FINAL * 6), 0.001
    raise ValueError("Unknown fixed SSE fixture profile")


def streaming_timing_accepted(profile, first_send_before_completed):
    # A short, fast response can finish before the first real key press.
    fixture_sse_profile(profile)
    return profile != "normal" or first_send_before_completed


class LocalHTTP:
    def __init__(self, folder, sse_profile="normal"):
        self.parts, self.delta_delay = fixture_sse_profile(sse_profile)
        self.cert, self.key = folder / "cert.pem", folder / "key.pem"
        subprocess.run(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-keyout",
                str(self.key),
                "-out",
                str(self.cert),
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
        self.context = ssl.create_default_context(cafile=str(self.cert))
        self.server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.server_context.load_cert_chain(self.cert, self.key)
        self.ports = []
        self.streams = 0
        self.completed_streams = 0
        self.deltas_sent = 0
        self.final_asr_inputs = []
        self.errors = []
        owner = self

        class Server(ThreadingHTTPServer):
            daemon_threads = False
            block_on_close = True

            def get_request(self):
                connection, address = super().get_request()
                connection.settimeout(3)
                try:
                    return owner.server_context.wrap_socket(
                        connection, server_side=True
                    ), address
                except Exception:
                    owner.errors.append("http_tls_handshake")
                    connection.close()
                    raise

            def handle_error(self, *_args):
                owner.errors.append("http_handler")

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *_):
                pass

            def do_POST(self):
                try:
                    self._post()
                except (
                    BrokenPipeError,
                    ConnectionResetError,
                    ssl.SSLEOFError,
                ):
                    self.close_connection = True
                except Exception:
                    owner.errors.append("http_request")
                    self.close_connection = True

            def _post(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                owner.ports.append(self.client_address[1])
                streaming = body.get("stream") is True
                if streaming:
                    owner.final_asr_inputs.append(
                        body.get("messages", [])[-1]
                        == {"role": "user", "content": ASR_FINAL}
                    )
                del body
                if not streaming:
                    encoded = json.dumps(
                        {"choices": [{"message": {"content": ASR_FINAL}}]}
                    ).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(encoded)))
                    self.end_headers()
                    self.wfile.write(encoded)
                    return
                owner.streams += 1
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Connection", "close")
                self.end_headers()
                for text in owner.parts:
                    message = {
                        "id": "local-fixed",
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": text},
                                "finish_reason": None,
                            }
                        ],
                    }
                    self.wfile.write(
                        (
                            "data: " + json.dumps(message, ensure_ascii=False) + "\n\n"
                        ).encode()
                    )
                    self.wfile.flush()
                    owner.deltas_sent += 1
                    time.sleep(owner.delta_delay)
                message = {
                    "id": "local-fixed",
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                }
                self.wfile.write(
                    ("data: " + json.dumps(message) + "\n\ndata: [DONE]\n\n").encode()
                )
                self.wfile.flush()
                owner.completed_streams += 1
                self.close_connection = True

        self.server = Server(("127.0.0.1", 0), Handler)

        def serve_http():
            try:
                self.server.serve_forever()
            except Exception:
                self.errors.append("http_listener")

        self.thread = threading.Thread(target=serve_http)
        self.thread.start()
        self.url = f"https://127.0.0.1:{self.server.server_port}/v1"

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()


async def probe(args):
    import httpx
    from PySide6.QtCore import QObject, Signal, qVersion
    from PySide6.QtWidgets import QApplication
    from websockets.asyncio.server import serve
    from websockets.exceptions import ConnectionClosed

    import inkecho
    from inkecho.app import Session
    from inkecho.audio import Recorder, wav_bytes
    from inkecho.config import ConfigStore
    from inkecho.core import State
    from inkecho.platform.keyboard import KeyboardInput
    from inkecho.providers import ProviderClient
    from inkecho.realtime import QwenRealtimeSession
    from inkecho.ui.providers import ProviderPage

    real_microphone = args.execution["real_microphone"]
    real_desktop_input = args.execution["real_desktop_input"]
    report = {
        "version": inkecho.__version__,
        "passed": False,
        "real_microphone": real_microphone,
        "real_desktop_input": real_desktop_input,
        "cloud_requests": 0,
        "user_credentials_read": False,
        "runtime_kind": "source" if args.package_root == ROOT / "src" else "package",
        "pacing_override_seconds": args.pacing,
        "fixture_sse_profile": args.fixture_sse_profile,
    }
    if args.owned_ubuntu24_vm_x11:
        report["environment"] = "ubuntu24-vm-x11"
        report["environment_metadata"] = args.execution["environment_metadata"]
        report["qt_platform"] = QApplication.instance().platformName()
        report["qt_version"] = qVersion()
        report["event_loop_class"] = type(asyncio.get_running_loop()).__name__
        if report["qt_platform"] != "xcb":
            raise RuntimeError("Actual X11 Qt application required")
    if report["runtime_kind"] == "package":
        appdir = args.package_root.parent
        if not Path(sys.executable).resolve().is_relative_to(appdir / "usr"):
            raise RuntimeError("Use the interpreter shipped in the selected AppImage")
        report["package_inventory"] = audit_appdir(appdir)
    modules = [
        "inkecho",
        "inkecho.app",
        "inkecho.audio",
        "inkecho.providers",
        "inkecho.realtime",
        "inkecho.polish_stream",
        "inkecho.streaming_output",
        "inkecho.ui.providers",
        "inkecho.runtime",
        "websockets",
    ]
    for name in modules:
        module = importlib.import_module(name)
        path = Path(module.__file__).resolve()
        if not path.is_relative_to(args.package_root) and not (
            name == "websockets" and report["runtime_kind"] == "source"
        ):
            raise RuntimeError("Runtime module escaped selected package root")
    report["runtime_modules_verified"] = len(modules)
    if args.pacing is not None:
        from inkecho.platform import keyboard

        keyboard.MAP_SETTLE_SECONDS = args.pacing
        keyboard.PRESS_SETTLE_SECONDS = args.pacing
        keyboard.RELEASE_SETTLE_SECONDS = args.pacing

    class SyntheticRecorder(QObject):
        level = Signal(float)
        pcm_ready = Signal(bytes)
        finished = Signal(bytes, float)
        failed = Signal(str)

        def start(self, *_args, **_kwargs):
            return True

        def stop(self):
            self.finished.emit(b"", 0.2)

        def cancel(self):
            pass

    class SyntheticInputs:
        connected = authorized = supports_first_sent_callback = True

        def __init__(self):
            self.inserted = ""
            self.cancel_callback = None

        async def connect(self):
            pass

        async def authorize(self):
            pass

        async def insert(self, text, active, *, deadline=None, on_first_sent=None):
            for index, character in enumerate(text):
                if not active():
                    raise asyncio.CancelledError
                self.inserted += character
                if index == 0 and on_first_sent:
                    on_first_sent(time.monotonic())
                if self.cancel_callback:
                    callback, self.cancel_callback = self.cancel_callback, None
                    asyncio.get_running_loop().call_soon(callback)
                await asyncio.sleep(0.001)
            return len(text)

        async def aclose(self):
            pass

    with tempfile.TemporaryDirectory(
        prefix="inkecho-package-performance-"
    ) as folder_name:
        folder = Path(folder_name)
        local = LocalHTTP(folder, args.fixture_sse_profile)
        fixture_final = "".join(local.parts)
        report["fixture_final_codepoints"] = len(fixture_final)
        report["fixture_final_printable_codepoints"] = sum(
            character.isprintable() for character in fixture_final
        )
        ws_counts = {
            "connections": 0,
            "audio_bytes": 0,
            "finish": 0,
            "manual_confirmation_omitted": 0,
            "placeholder_created": 0,
            "early_preview": 0,
        }

        async def websocket(ws):
            ws_counts["connections"] += 1
            number = 0
            first_append = True

            async def send(kind, **fields):
                nonlocal number
                number += 1
                await ws.send(
                    json.dumps({"type": kind, "event_id": str(number), **fields})
                )

            try:
                await send(
                    "session.created",
                    session={"id": "s1", "model": "qwen3-asr-flash-realtime"},
                )
                async for encoded in ws:
                    event = json.loads(encoded)
                    kind = event["type"]
                    if kind == "session.update":
                        confirmation = {
                            "id": "s1",
                            "model": "qwen3-asr-flash-realtime",
                            **event["session"],
                        }
                        if confirmation.pop("turn_detection", "unexpected") is not None:
                            raise ValueError("Fixture requires explicit manual mode")
                        await send(
                            "session.updated",
                            session=confirmation,
                        )
                        ws_counts["manual_confirmation_omitted"] += 1
                    elif kind == "input_audio_buffer.append":
                        audio = base64.b64decode(event["audio"], validate=True)
                        if first_append:
                            first_append = False
                            # Observed official notifications are not commit IDs.
                            await send(
                                "conversation.item.created", item={"type": "message"}
                            )
                            ws_counts["placeholder_created"] += 1
                            await send(
                                "conversation.item.input_audio_transcription.text",
                                text=ASR_PREVIEW,
                            )
                            ws_counts["early_preview"] += 1
                        ws_counts["audio_bytes"] += len(audio)
                        del audio
                    elif kind == "input_audio_buffer.commit":
                        await send("input_audio_buffer.committed", item_id="i1")
                    elif kind == "session.finish":
                        ws_counts["finish"] += 1
                        await send(
                            "conversation.item.input_audio_transcription.completed",
                            item_id="i1",
                            content_index=0,
                            transcript=ASR_FINAL,
                        )
                        await send("session.finished")
                    else:
                        raise ValueError("Unknown fixture event")
            except ConnectionClosed:
                pass  # The client intentionally aborts its completed/cancelled session.
            except Exception:
                local.errors.append("wss_request")

        session = None
        owned = None
        try:
            async with serve(
                websocket, "127.0.0.1", 0, ssl=local.server_context, logger=QUIET
            ) as ws_server:
                ws_port = ws_server.sockets[0].getsockname()[1]
                store = ConfigStore(folder / "config")
                store.initialize()
                store.save_settings(
                    replace(
                        store.load_settings(),
                        polishing_enabled=True,
                        polishing_streaming=True,
                    )
                )
                store.save_provider(
                    replace(
                        store.load_provider("qwen"),
                        base_url=local.url,
                        model="qwen3-asr-flash-realtime",
                        parameters={
                            "asr_protocol": "qwen_realtime",
                            "realtime_url": f"wss://127.0.0.1:{ws_port}/realtime",
                        },
                    )
                )
                store.save_provider(
                    replace(
                        store.load_provider("deepseek"),
                        base_url=local.url,
                        model="fixture-polish",
                    )
                )
                async with httpx.AsyncClient(
                    verify=local.context, trust_env=False
                ) as http:
                    client = ProviderClient(http=http)
                    # Two real HTTPS calls on the same verified fixture connection.
                    asr = replace(
                        store.load_provider("qwen"), parameters={}, model="fixture-http"
                    )
                    wav = wav_bytes(b"\0\0" * 160, 16000)
                    for _ in range(2):
                        await client.transcribe(asr, "fixture-key", wav)
                    report["http_connection_reused"] = len(set(local.ports[:2])) == 1
                    pcm = b"\x01\x00" * 3200
                    report["audio_wav_encoding"] = wav.startswith(b"RIFF")
                    inputs = (
                        KeyboardInput() if real_desktop_input else SyntheticInputs()
                    )
                    recorder = Recorder() if real_microphone else SyntheticRecorder()

                    def realtime(config, key, **options):
                        return QwenRealtimeSession(
                            config, key, tls_context=local.context, **options
                        )

                    session = Session(
                        store,
                        inputs=inputs,
                        recorder=recorder,
                        client=client,
                        realtime_factory=realtime,
                    )

                    async def key(_reference):
                        return "fixture-key"

                    session.key = key
                    diagnostics = []
                    session.diagnostic.connect(diagnostics.append)
                    if real_desktop_input:
                        owned = OwnedTarget(args.xdotool, folder, inputs)
                        await owned.open()
                    await session.initialize()
                    transcription = ProviderPage(session, "transcription")
                    polishing = ProviderPage(session, "polishing")
                    report["ui_protocol_and_stream_loaded"] = (
                        transcription.protocol.currentData() == "qwen_realtime"
                        and polishing.streaming.isChecked()
                    )
                    transcription.deleteLater()
                    polishing.deleteLater()
                    for cancelled in (False, True):
                        if owned:
                            owned.intervals.clear()
                            before_mapping = dict(owned.mapping_counts)
                        read = owned.text if owned else lambda: inputs.inserted
                        baseline_text = read()
                        before_audio = ws_counts["audio_bytes"]
                        await session.toggle()
                        if not real_microphone:
                            recorder.pcm_ready.emit(pcm)
                        await wait_for(
                            lambda before=before_audio: (
                                ws_counts["audio_bytes"] > before
                            )
                        )
                        report.setdefault("uploaded_before_stop", []).append(
                            ws_counts["audio_bytes"] - before_audio
                        )
                        preview_ignored = await stable_text(read) == baseline_text
                        report.setdefault("preview_ignored_before_stop", []).append(
                            preview_ignored
                        )
                        if cancelled:
                            if owned:
                                owned.cancel_callback = session.cancel
                            else:
                                inputs.cancel_callback = session.cancel
                        session.stop_recording()
                        await wait_for(lambda: not session.pending, seconds=12)
                        if cancelled:
                            await asyncio.sleep(1.2)
                        actual = await stable_text(read)
                        expected = baseline_text + (
                            fixture_final[:1] if cancelled else fixture_final
                        )
                        report.setdefault("readback", []).append(
                            {
                                "expected_codepoints": len(expected),
                                "received_codepoints": len(actual),
                                "nfc_equivalent": unicodedata.normalize("NFC", expected)
                                == unicodedata.normalize("NFC", actual),
                                "nfd_equivalent": unicodedata.normalize("NFD", expected)
                                == unicodedata.normalize("NFD", actual),
                                "newline_normalized_equivalent": expected.replace(
                                    "\r\n", "\n"
                                ).replace("\r", "\n")
                                == actual.replace("\r\n", "\n").replace("\r", "\n"),
                                "mismatch_spans": [
                                    span
                                    for span in difflib.SequenceMatcher(
                                        a=expected, b=actual, autojunk=False
                                    ).get_opcodes()
                                    if span[0] != "equal"
                                ],
                                "first_mismatch_index": next(
                                    (
                                        index
                                        for index, pair in enumerate(
                                            zip(expected, actual, strict=False)
                                        )
                                        if pair[0] != pair[1]
                                    ),
                                    min(len(expected), len(actual))
                                    if expected != actual
                                    else None,
                                ),
                            }
                        )
                        report[
                            "cancel_no_tail" if cancelled else "final_text_exact"
                        ] = actual == expected
                        if not cancelled:
                            timeline = session.last_performance["events_ms"]
                            report["first_send_before_polish_completed"] = (
                                timeline["first_character_sent"] is not None
                                and timeline["polishing_completed"] is not None
                                and timeline["first_character_sent"]
                                < timeline["polishing_completed"]
                            )
                            report["streaming_timing_accepted"] = (
                                streaming_timing_accepted(
                                    args.fixture_sse_profile,
                                    report["first_send_before_polish_completed"],
                                )
                            )
                            report["timing_fields_present"] = all(
                                timeline[name] is not None
                                for name in (
                                    "asr_started",
                                    "asr_completed",
                                    "recording_stopped",
                                    "polishing_first_segment",
                                    "polishing_completed",
                                    "first_character_sent",
                                    "output_completed",
                                )
                            )
                            if owned:
                                report["keyboard_actual_waits_ms"] = owned.summary()
                                report["backend_received_exact_text"] = (
                                    owned.requested_text == fixture_final
                                )
                        else:
                            report["cancelled_outcome"] = (
                                session.controller.outcome == State.CANCELLED
                            )
                        report.setdefault("task_performance", []).append(
                            session.last_performance
                        )
                        if owned:
                            report.setdefault("keyboard_mapping_counts", []).append(
                                {
                                    name: value - before_mapping[name]
                                    for name, value in owned.mapping_counts.items()
                                }
                            )
                        session.last_toggle = 0
                    report["wss_connections"] = ws_counts["connections"]
                    report["wss_finish_events"] = ws_counts["finish"]
                    report["manual_confirmation_without_turn_detection"] = (
                        ws_counts["manual_confirmation_omitted"] == 2
                    )
                    report["precommit_placeholder_and_preview"] = (
                        ws_counts["placeholder_created"] == 2
                        and ws_counts["early_preview"] == 2
                    )
                    report["only_final_asr_reached_polishing"] = (
                        local.final_asr_inputs == [True, True]
                    )
                    report["diagnostics_empty"] = diagnostics == []
                    report["diagnostic_codes"] = diagnostics
                    if owned:
                        report["balanced_desktop_events"] = owned.events == [
                            True,
                            False,
                        ] * (len(fixture_final) + 1)
                        report["desktop_map_restored"] = (
                            owned.original_map == inputs._driver._mapping()
                        )
                    await session.close()
                    session = None
                report["passed"] = (
                    all(
                        report[name]
                        for name in (
                            "http_connection_reused",
                            "audio_wav_encoding",
                            "ui_protocol_and_stream_loaded",
                            "final_text_exact",
                            "cancel_no_tail",
                            "streaming_timing_accepted",
                            "timing_fields_present",
                            "cancelled_outcome",
                            "diagnostics_empty",
                            "manual_confirmation_without_turn_detection",
                            "precommit_placeholder_and_preview",
                            "only_final_asr_reached_polishing",
                        )
                    )
                    and all(report["preview_ignored_before_stop"])
                    and all(
                        report.get(name, True)
                        for name in ("balanced_desktop_events", "desktop_map_restored")
                    )
                )
        finally:
            if session:
                await session.close()
            if owned:
                owned.close()
            local.close()
            report["fixture_sse_deltas_per_completed_stream"] = len(local.parts)
            # Flushed by the fixture, not necessarily received before cancellation.
            report["fixture_sse_deltas_sent"] = local.deltas_sent
            report["fixture_sse_completed_streams"] = local.completed_streams
            report["server_errors"] = list(local.errors)
            report["fixture_threads_closed"] = not local.thread.is_alive() and not any(
                thread.is_alive() for thread in local.server._threads
            )
            report["passed"] = (
                report.get("passed", False)
                and not local.errors
                and report["fixture_threads_closed"]
            )
    return report


class OwnedTarget:
    def __init__(self, xdotool, folder, inputs):
        self.xdotool, self.folder, self.inputs = xdotool, folder, inputs
        self.output = folder / "owned-text.json"
        self.process = None
        self.events = []
        self.intervals = []
        self.mapped_at = self.pressed_at = self.released_at = None
        self.cancel_callback = None
        self.requested_text = ""
        self.mapping_counts = {
            "mapping_writes": 0,
            "successful_restore_calls": 0,
            "completed_insert_calls": 0,
        }

    def command(self, *parts):
        return subprocess.check_output(
            [self.xdotool, *parts], text=True, timeout=3
        ).strip()

    def identity(self):
        return (
            (Path("/proc") / str(self.process.pid) / "stat")
            .read_text()
            .rsplit(")", 1)[1]
            .split()[19]
        )

    async def open(self):
        from keyboard_latency_probe import fixture_environment

        self.process = subprocess.Popen(
            [
                "/usr/bin/python3",
                str(ROOT / "scripts/validation/keyboard_latency_probe.py"),
                "--fixture",
                "gtk",
                "--output",
                str(self.output),
            ],
            env=fixture_environment(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.started = self.identity()
        window = []
        for _ in range(100):
            try:
                window = self.command(
                    "search", "--onlyvisible", "--pid", str(self.process.pid)
                ).splitlines()
            except subprocess.CalledProcessError:
                pass
            if window and self.output.exists():
                break
            await asyncio.sleep(0.05)
        if not window:
            raise RuntimeError("Owned desktop target unavailable")
        self.window = int(window[0])
        if int(self.command("getwindowpid", str(self.window))) != self.process.pid:
            raise RuntimeError("Owned target PID mismatch")
        self.command("windowactivate", "--sync", str(self.window))
        await asyncio.sleep(0.3)
        await self.inputs.connect()
        self.original_map = self.inputs._driver._mapping()
        self.observe_input()

    def observe_input(self):
        original = self.inputs._send
        driver = self.inputs._driver
        original_map, original_restore = driver.map, driver.restore
        original_write = driver._write

        def written(values):
            result = original_write(values)
            self.mapping_counts["mapping_writes"] += 1
            return result

        def mapped(character):
            code = original_map(character)
            self.mapped_at = time.monotonic()
            return code

        def restored():
            if self.released_at is not None:
                self.intervals.append(
                    ("release_to_restore", time.monotonic() - self.released_at)
                )
                self.released_at = None
            result = original_restore()
            self.mapping_counts["successful_restore_calls"] += 1
            return result

        driver.map, driver.restore = mapped, restored
        driver._write = written

        def guarded(window, code, pressed):
            driver = self.inputs._driver
            if pressed:
                active = driver._property(driver.root, driver.active_atom)
                if (
                    self.process.poll() is not None
                    or self.identity() != self.started
                    or active != self.window
                    or driver._property(active, driver.pid_atom) != self.process.pid
                    or driver.focus() != window
                ):
                    raise RuntimeError("Refusing delivery outside owned desktop target")
            original(window, code, pressed)
            now = time.monotonic()
            if pressed:
                self.intervals.append(("map_to_press", now - self.mapped_at))
                self.pressed_at = now
            elif self.pressed_at is not None:
                self.intervals.append(("press_to_release", now - self.pressed_at))
                self.released_at, self.pressed_at = now, None
            self.events.append(pressed)
            if pressed and self.cancel_callback:
                callback, self.cancel_callback = self.cancel_callback, None
                asyncio.get_running_loop().call_soon(callback)

        self.inputs._send = guarded
        original_insert = self.inputs.insert

        async def insert(text, *arguments, **options):
            self.requested_text += text
            result = await original_insert(text, *arguments, **options)
            self.mapping_counts["completed_insert_calls"] += 1
            return result

        self.inputs.insert = insert

    def summary(self):
        result = {}
        for name in ("map_to_press", "press_to_release", "release_to_restore"):
            values = [
                seconds * 1000 for kind, seconds in self.intervals if kind == name
            ]
            result[name] = {
                "count": len(values),
                "min": round(min(values), 3) if values else None,
                "max": round(max(values), 3) if values else None,
                "mean": round(sum(values) / len(values), 3) if values else None,
            }
        return result

    def text(self):
        return json.loads(self.output.read_text())["text"]

    def close(self):
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    desktop = parser.add_mutually_exclusive_group()
    desktop.add_argument("--owned-xwayland-live-mic", action="store_true")
    desktop.add_argument("--owned-ubuntu24-vm-x11", action="store_true")
    parser.add_argument("--xdotool")
    parser.add_argument("--pacing", type=float)
    parser.add_argument(
        "--fixture-sse-profile",
        choices=("normal", "one-character-fast", "one-character-fast-long"),
        default="normal",
    )
    args = parser.parse_args()
    args.package_root = args.package_root.resolve(strict=True)
    if args.pacing is not None and not 0.005 <= args.pacing <= 0.04:
        parser.error("test-only pacing must be in [0.005, 0.04]")
    sys.path.insert(0, str(args.package_root))
    args.execution = configure_environment(args)
    from PySide6.QtWidgets import QApplication

    from inkecho.runtime import ManagedQtEventLoop

    application = QApplication([])
    application.setQuitOnLastWindowClosed(False)
    with ManagedQtEventLoop(application) as loop:
        report = loop.run_until_complete(probe(args))
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, sort_keys=True))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
