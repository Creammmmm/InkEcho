"""Owned virtual audio -> real Session -> local TLS ASR/SSE -> actual keyboard.

The target is independently created, focused and observed by the desktop runner.
Xorg targets use PID/XID guards; native Wayland uses a fresh owned focus guard.
Only key presses are guarded; releases always proceed.
No physical microphone, real configuration or cloud credentials are opened.
"""

import argparse
import asyncio
import base64
import hashlib
import json
import os
import ssl
import struct
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import replace
from pathlib import Path

import httpx
from PySide6.QtCore import QCoreApplication
from websockets.asyncio.server import serve

parser = argparse.ArgumentParser()
roots = parser.add_mutually_exclusive_group(required=True)
roots.add_argument("--source-root", type=Path)
roots.add_argument("--package-root", type=Path)
parser.add_argument("--owned-pid", type=int, default=0)
parser.add_argument("--owned-window", type=int, default=0)
parser.add_argument("--native-guard", type=Path)
parser.add_argument("--native-owner", type=int)
parser.add_argument("--native-helper-root", type=Path)
parser.add_argument("--native-work-root", type=Path)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
IMPORT_ROOT = (args.package_root or args.source_root).resolve(strict=True)
assert (IMPORT_ROOT / "inkecho/app.py").is_file()
if args.native_guard:
    assert args.native_owner and args.native_owner > 1
    assert args.native_helper_root and args.native_work_root
else:
    assert args.owned_pid > 1 and args.owned_window > 0
assert not args.output.exists()
sys.path.insert(0, str(IMPORT_ROOT))
# Production guardian subprocesses must resolve the same frozen/package root.
os.environ["PYTHONPATH"] = (
    str(IMPORT_ROOT) + os.pathsep + os.environ.get("PYTHONPATH", "")
)

from inkecho.app import Session  # noqa: E402
from inkecho.audio import Recorder  # noqa: E402
from inkecho.config import ConfigStore, Provider  # noqa: E402
from inkecho.platform.keyboard import KeyboardError, _row_identity  # noqa: E402
from inkecho.platform.wayland_keyboard import keyboard_for_desktop  # noqa: E402
from inkecho.providers import ProviderClient  # noqa: E402
from inkecho.realtime import QwenRealtimeSession  # noqa: E402
from inkecho.runtime import ManagedQtEventLoop  # noqa: E402


def pulse(*args):
    return subprocess.run(
        ["pactl", *args], capture_output=True, check=True, text=True, timeout=5
    ).stdout.strip()


def origins():
    found = {}
    for name, module in sys.modules.items():
        if name == "inkecho" or name.startswith("inkecho."):
            origin = getattr(module, "__file__", None)
            if origin:
                path = Path(origin).resolve()
                if not path.is_relative_to(IMPORT_ROOT):
                    raise RuntimeError("unexpected_product_module_origin")
                found[name] = {
                    "path": str(path),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
    return found


async def run():
    defaults = (pulse("get-default-sink"), pulse("get-default-source"))
    name = "inkecho_pipeline_" + uuid.uuid4().hex[:12]
    modules, players, session = [], [], None
    http = None
    times, wire, errors = {}, bytearray(), []
    report = {
        "public_sample": "本地完整链路测试。",
        "events": [],
        "import_root": str(IMPORT_ROOT),
        "package_imports": bool(args.package_root),
    }
    inputs, driver, before = None, None, None
    native_monitor = None
    try:
        modules.append(
            pulse(
                "load-module",
                "module-null-sink",
                f"sink_name={name}",
                "rate=16000",
                "channels=1",
            )
        )
        modules.append(
            pulse(
                "load-module",
                "module-remap-source",
                f"master={name}.monitor",
                f"source_name={name}_source",
                f"source_properties=device.description={name}",
            )
        )
        async with asyncio.timeout(3):
            while True:
                device = next((i for i, n in Recorder.devices() if n == name), None)
                if device is not None:
                    break
                await asyncio.sleep(0.02)
        with tempfile.TemporaryDirectory(prefix="inkecho-pipeline-") as folder:
            folder = Path(folder)
            subprocess.run(
                [
                    "openssl",
                    "req",
                    "-x509",
                    "-newkey",
                    "rsa:2048",
                    "-nodes",
                    "-keyout",
                    str(folder / "key.pem"),
                    "-out",
                    str(folder / "cert.pem"),
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
            tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            tls.load_cert_chain(folder / "cert.pem", folder / "key.pem")
            trust = ssl.create_default_context(cafile=str(folder / "cert.pem"))

            async def protocol(ws):
                counter = 0

                async def emit(kind, **values):
                    nonlocal counter
                    counter += 1
                    await ws.send(
                        json.dumps({"event_id": str(counter), "type": kind, **values})
                    )

                try:
                    await emit(
                        "session.created",
                        session={"id": "s1", "model": "qwen3-asr-flash-realtime"},
                    )
                    async for raw in ws:
                        event = json.loads(raw)
                        kind = event["type"]
                        if kind == "session.update":
                            await emit(
                                "session.updated",
                                session={
                                    "id": "s1",
                                    "model": "qwen3-asr-flash-realtime",
                                    **event["session"],
                                },
                            )
                        elif kind == "input_audio_buffer.append":
                            times.setdefault("first_audio_on_wire", time.monotonic())
                            wire.extend(base64.b64decode(event["audio"]))
                        elif kind == "input_audio_buffer.commit":
                            await emit("input_audio_buffer.committed", item_id="i1")
                        elif kind == "session.finish":
                            await asyncio.sleep(0.12)
                            times["final_asr"] = time.monotonic()
                            await emit(
                                "conversation.item.input_audio_transcription.completed",
                                item_id="i1",
                                content_index=0,
                                transcript="本地完整链路测试。",
                            )
                            await emit("session.finished")
                except Exception as error:
                    # Never include audio or event contents in diagnostics.
                    errors.append(type(error).__name__)

            def event(content=None, finish=None):
                return (
                    b"data: "
                    + json.dumps(
                        {
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": {"content": content} if content else {},
                                    "finish_reason": finish,
                                }
                            ]
                        }
                    ).encode()
                    + b"\n\n"
                )

            async def polish(reader, writer):
                try:
                    header = await reader.readuntil(b"\r\n\r\n")
                    length = next(
                        int(line.split(b":", 1)[1])
                        for line in header.split(b"\r\n")
                        if line.lower().startswith(b"content-length:")
                    )
                    body = json.loads(await reader.readexactly(length))
                    assert body["stream"] is True
                    times["polishing_request"] = time.monotonic()
                    await asyncio.sleep(0.08)
                    times["polishing_first_delta"] = time.monotonic()
                    first = event("本地")
                    tail = (
                        event("完整链路测试。")
                        + event(finish="stop")
                        + b"data: [DONE]\n\n"
                    )
                    writer.write(
                        b"HTTP/1.1 200 OK\r\n"
                        b"Content-Type: text/event-stream\r\n"
                        + f"Content-Length: {len(first) + len(tail)}\r\n".encode()
                        + b"Connection: close\r\n\r\n"
                        + first
                    )
                    await writer.drain()
                    await asyncio.sleep(0.4)
                    times["polishing_full_text"] = time.monotonic()
                    writer.write(tail)
                    await writer.drain()
                except Exception as error:
                    errors.append(type(error).__name__)
                finally:
                    writer.close()
                    await writer.wait_closed()

            https = await asyncio.start_server(polish, "127.0.0.1", 0, ssl=tls)
            async with https, serve(protocol, "127.0.0.1", 0, ssl=tls) as server:
                port = server.sockets[0].getsockname()[1]
                store = ConfigStore(folder / "config")
                store.initialize()
                store.save_provider(
                    Provider(
                        "probe",
                        "Synthetic probe",
                        "transcription",
                        "qwen",
                        model="qwen3-asr-flash-realtime",
                        key_ref="synthetic",
                        parameters={
                            "asr_protocol": "qwen_realtime",
                            "realtime_url": f"wss://127.0.0.1:{port}/realtime",
                        },
                    )
                )
                store.save_settings(
                    replace(
                        store.load_settings(),
                        transcription_provider="probe",
                        microphone=device.hex(),
                    )
                )
                https_port = https.sockets[0].getsockname()[1]
                store.save_provider(
                    Provider(
                        "polish",
                        "Synthetic polish",
                        "polishing",
                        "openai",
                        base_url=f"https://127.0.0.1:{https_port}/v1",
                        model="fixture-model",
                        key_ref="synthetic-polish",
                    )
                )
                store.save_settings(
                    replace(
                        store.load_settings(),
                        polishing_enabled=True,
                        polishing_provider="polish",
                    )
                )
                assert store.load_settings().polishing_streaming is True
                http = httpx.AsyncClient(verify=trust, trust_env=False)
                inputs = keyboard_for_desktop()
                if args.native_guard:
                    from audio_pipeline_native_guard import NativePipelineGuard

                    native_monitor = NativePipelineGuard(
                        IMPORT_ROOT,
                        args.native_helper_root,
                        args.native_guard,
                        args.native_owner,
                        args.native_work_root,
                    )
                    native_monitor.configure(inputs)
                await inputs.connect()
                x11 = getattr(inputs, "x11", inputs)
                driver = x11._driver
                before = driver._mapping()
                if native_monitor is not None:
                    native_monitor.refuse_x11_presses(inputs)
                    await native_monitor.before_capture()
                    report["target_scope"] = "owned native Wayland fixture"
                else:
                    original_send = x11._send
                    owned_start = (
                        Path("/proc") / str(args.owned_pid) / "stat"
                    ).read_text()
                    owned_start = owned_start.rsplit(")", 1)[1].split()[19]
                    report["owned_pid_start_ticks"] = owned_start
                    report["desktop_session"] = os.environ.get("XDG_SESSION_TYPE")
                    report["target_scope"] = "owned Xorg/XWayland X11 window"
                    native = getattr(inputs, "native", None)
                    if native is not None:
                        original_native_request = native._request

                        async def guard_native(operation, **fields):
                            # This fixture owns an X11 receiver only. A newly selected
                            # native receiver is outside that owned target, so refuse
                            # its atomic key operation; permit cleanup operations.
                            if operation == "key":
                                raise KeyboardError("input_cancelled")
                            return await original_native_request(operation, **fields)

                        native._request = guard_native

                    def dispatch(window, code, pressed):
                        if pressed:
                            with driver._checked():
                                top = driver._property(driver.root, driver.active_atom)
                                pid = (
                                    driver._property(top, driver.pid_atom) if top else 0
                                )
                            started = (
                                Path("/proc") / str(args.owned_pid) / "stat"
                            ).read_text()
                            started = started.rsplit(")", 1)[1].split()[19]
                            if (
                                top != args.owned_window
                                or pid != args.owned_pid
                                or started != owned_start
                            ):
                                raise KeyboardError("input_cancelled")
                            times.setdefault("first_dispatch", time.monotonic())
                        result = original_send(window, code, pressed)
                        report["events"].append(
                            {
                                "pressed": pressed,
                                "code": code,
                                "seconds": time.monotonic() - times["toggle_requested"],
                            }
                        )
                        return result

                    x11._send = dispatch
                report["factory_type"] = type(inputs).__name__
                report["origins_before"] = origins()
                session = Session(
                    store,
                    inputs=inputs,
                    client=ProviderClient(http=http),
                    realtime_factory=lambda *a, **kw: QwenRealtimeSession(
                        *a, **kw, tls_context=trust
                    ),
                )
                done = asyncio.get_running_loop().create_future()
                session.finished.connect(
                    lambda result: done.set_result(result) if not done.done() else None
                )
                session.capture_ready.connect(
                    lambda ready: (
                        times.setdefault("first_capture", time.monotonic())
                        if ready
                        else None
                    )
                )

                async def key(_):
                    times["credential_wait_started"] = time.monotonic()
                    await asyncio.sleep(0.4)
                    times["credential_wait_finished"] = time.monotonic()
                    return "synthetic-test-key"

                session.key = key

                async def play_marker():
                    await asyncio.sleep(0.08)
                    times["play_requested"] = time.monotonic()
                    player = await asyncio.create_subprocess_exec(
                        "paplay",
                        f"--device={name}",
                        "--raw",
                        "--format=s16le",
                        "--rate=16000",
                        "--channels=1",
                        stdin=asyncio.subprocess.PIPE,
                        stdout=asyncio.subprocess.DEVNULL,
                        stderr=asyncio.subprocess.DEVNULL,
                    )
                    players.append(player)
                    marker = struct.pack("<1600h", *(([8000] * 8 + [-8000] * 8) * 100))
                    await player.communicate(marker + b"\0" * 9600)
                    assert player.returncode == 0

                times["toggle_requested"] = time.monotonic()
                playback = asyncio.create_task(play_marker())
                await session.toggle()
                await asyncio.sleep(0.5)
                times["stop_requested"] = time.monotonic()
                session.stop_recording()
                async with asyncio.timeout(5):
                    result = await done
                await playback
                samples = struct.unpack(f"<{len(wire) // 2}h", wire)
                marker_count = sum(abs(value) >= 2000 for value in samples)
                assert result["outcome"] == "succeeded"
                if native_monitor is not None:
                    assert native_monitor.ack_count == len("本地完整链路测试。")
                    times["first_dispatch"] = native_monitor.first_sent_at
                else:
                    assert sum(e["pressed"] for e in report["events"]) == len(
                        "本地完整链路测试。"
                    )
                assert (
                    times["final_asr"]
                    < times["polishing_first_delta"]
                    <= times["first_dispatch"]
                    < times["polishing_full_text"]
                )
                # The server may observe client abort after valid session finish.
                assert set(errors) <= {"ConnectionClosedError"}
                zero = times["toggle_requested"]
                report["clock_origin_monotonic"] = zero
                report["timeline_monotonic"] = times.copy()
                print(
                    json.dumps(
                        {
                            "status": "passed"
                            if marker_count >= 1200
                            else "failed_onset",
                            "synthetic_only": True,
                            "input_transport": "actual_factory_with_owned_press_guard",
                            "events_ms": {
                                k: round((v - zero) * 1000, 3) for k, v in times.items()
                            },
                            "marker_samples": marker_count,
                            "wire_bytes": len(wire),
                            "performance": session.last_performance,
                        },
                        ensure_ascii=False,
                    )
                )
                assert marker_count >= 1200, "onset_marker_incomplete"
    finally:
        cleanup_errors = []
        if session is not None:
            try:
                session.cancel()
                await asyncio.gather(*list(session.pending), return_exceptions=True)
            except BaseException as error:
                cleanup_errors.append("session_cancel:" + type(error).__name__)
        if driver is not None and before is not None:
            try:
                after = driver._mapping()
                report["mapping_restored"] = all(
                    _row_identity(before[1][i * before[0] : (i + 1) * before[0]])
                    == _row_identity(after[1][i * after[0] : (i + 1) * after[0]])
                    for i in range(driver.count)
                )
            except BaseException as error:
                cleanup_errors.append("mapping_check:" + type(error).__name__)
        try:
            if session is not None:
                await session.close()
            elif inputs is not None:
                await inputs.aclose()
        except BaseException as error:
            cleanup_errors.append("input_close:" + type(error).__name__)
        if native_monitor is not None:
            try:
                report["native"] = await native_monitor.after_close()
                native_counts = report["native"]["counts"]
                assert (
                    native_counts["press_success"]
                    == native_counts["release_success"]
                    == len("本地完整链路测试。")
                    and native_counts["guard_rejections"] == 0
                    and report["native"].get("native_mapping_restored") is True
                    and all(
                        worker["natural_exit_code"] == 0
                        for worker in report["native"].get("workers", [])
                    )
                )
            except BaseException as error:
                cleanup_errors.append("native_cleanup:" + type(error).__name__)
        try:
            if http is not None:
                await http.aclose()
        except BaseException as error:
            cleanup_errors.append("http_close:" + type(error).__name__)
        for player in players:
            if player.returncode is None:
                player.terminate()
                await player.wait()
        for module in reversed(modules):
            try:
                pulse("unload-module", module)
            except BaseException as error:
                cleanup_errors.append("pulse_unload:" + type(error).__name__)
        try:
            report["defaults_unchanged"] = defaults == (
                pulse("get-default-sink"),
                pulse("get-default-source"),
            )
        except BaseException as error:
            cleanup_errors.append("pulse_defaults:" + type(error).__name__)
        report["origins_after"] = origins()
        report["balanced"] = sum(e["pressed"] for e in report["events"]) == sum(
            not e["pressed"] for e in report["events"]
        )
        report["cleanup_errors"] = cleanup_errors
        with args.output.open("x") as stream:
            json.dump(report, stream, indent=2, ensure_ascii=False)
        assert (
            not cleanup_errors
            and report["balanced"]
            and report.get("mapping_restored") is True
            and report["defaults_unchanged"]
        )


if __name__ == "__main__":
    app = QCoreApplication([])
    loop = ManagedQtEventLoop(app)
    asyncio.set_event_loop(loop)
    with loop:
        loop.run_until_complete(run())
