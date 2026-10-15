"""Loopback-only TLS fixture; fixed synthetic audio/text, never cloud credentials."""

import asyncio
import base64
import contextlib
import io
import json
import logging
import ssl
import subprocess
import wave

MODEL = "qwen3-asr-flash-realtime"
ASR = "固定转写"
PARTS = ("中", "Ω😀中\r", "\n尾")
FINAL = "中Ω😀中\n尾"
PCM = b"\x01\x00" * 3200


def audio_bytes():
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(PCM)
    return output.getvalue()


class Fixture:
    """Real HTTPS/WSS parsing with one-ASR/one-polish limits per configuration."""

    def __init__(self, directory, *, late=False):
        cert, key = directory / "cert.pem", directory / "key.pem"
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
        self.server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.server_context.load_cert_chain(cert, key)
        self.context = ssl.create_default_context(cafile=str(cert))
        self.calls = {"http_asr": 0, "wss_asr": 0, "polishing": 0}
        self.audio = bytearray()
        self.requested = asyncio.Event()
        self.release = asyncio.Event()
        if not late:
            self.release.set()
        self.handlers = set()
        self.errors = []
        self.polish_input_exact = False
        self.late_response_attempted = False

    async def __aenter__(self):
        from websockets.asyncio.server import serve

        self.http = await asyncio.start_server(
            self.handle_http, "127.0.0.1", 0, ssl=self.server_context
        )
        self.base = f"https://127.0.0.1:{self.http.sockets[0].getsockname()[1]}"
        self.websocket = await serve(
            self.handle_ws,
            "127.0.0.1",
            0,
            ssl=self.server_context,
            logger=logging.Logger("comparison.local.websocket"),
        )
        port = self.websocket.sockets[0].getsockname()[1]
        self.realtime_url = f"wss://127.0.0.1:{port}/realtime"
        return self

    async def __aexit__(self, *_args):
        self.release.set()
        self.http.close()
        await self.http.wait_closed()
        self.websocket.close()
        await self.websocket.wait_closed()
        if self.handlers:
            await asyncio.gather(*self.handlers)

    def count(self, role):
        self.calls[role] += 1
        if self.calls[role] != 1 or self.calls["http_asr"] + self.calls["wss_asr"] > 1:
            raise ValueError("fixture_request_budget")

    async def handle_http(self, reader, writer):
        task = asyncio.current_task()
        self.handlers.add(task)
        try:
            header = (await reader.readuntil(b"\r\n\r\n")).decode("ascii")
            lines = header.split("\r\n")
            if lines[0] != "POST /chat/completions HTTP/1.1":
                raise ValueError("fixture_request_path")
            headers = dict(line.split(": ", 1) for line in lines[1:] if line)
            size = int(headers["Content-Length"])
            if not 0 < size < 50_000:
                raise ValueError("fixture_request_size")
            body = json.loads(await reader.readexactly(size))
            if body["model"] == "qwen3-asr-flash":
                self.count("http_asr")
                encoded = body["messages"][0]["content"][0]["input_audio"]["data"]
                if base64.b64decode(encoded.split(",", 1)[1]) != audio_bytes():
                    raise ValueError("fixture_audio_mismatch")
                self.audio.extend(PCM)
                self.requested.set()
                await self.release.wait()
                self.late_response_attempted = True
                text = ASR
            else:
                if body["model"] != "deepseek-flash" or body["max_tokens"] != 128:
                    raise ValueError("fixture_polish_configuration")
                self.count("polishing")
                self.polish_input_exact = body["messages"][-1]["content"] == ASR
                if body.get("stream") is True:
                    writer.write(
                        b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n"
                        b"Connection: close\r\n\r\n"
                    )
                    for part in PARTS:
                        await self.delta(writer, {"content": part})
                        await asyncio.sleep(0.08)
                    await self.delta(writer, {}, finish="stop")
                    writer.write(b"data: [DONE]\n\n")
                    await writer.drain()
                    return
                await asyncio.sleep(0.08 * len(PARTS))
                text = "".join(PARTS)
            result = json.dumps({"choices": [{"message": {"content": text}}]}).encode()
            writer.write(
                b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                + f"Content-Length: {len(result)}\r\nConnection: close\r\n\r\n".encode()
                + result
            )
            await writer.drain()
        except (ConnectionError, ssl.SSLError):
            pass  # Cancellation intentionally disconnects a pending response.
        except Exception:
            self.errors.append("http_fixture_failed")
        finally:
            writer.close()
            with contextlib.suppress(ConnectionError, ssl.SSLError):
                await writer.wait_closed()
            self.handlers.discard(task)

    @staticmethod
    async def delta(writer, delta, *, finish=None):
        value = {"choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}
        writer.write(("data: " + json.dumps(value) + "\n\n").encode())
        await writer.drain()

    async def handle_ws(self, ws):
        from websockets.exceptions import ConnectionClosed

        async def send(kind, **fields):
            await ws.send(json.dumps({"type": kind, **fields}))

        try:
            self.count("wss_asr")
            await send("session.created", session={"id": "s1", "model": MODEL})
            async for encoded in ws:
                event = json.loads(encoded)
                match event["type"]:
                    case "session.update":
                        confirmation = {"id": "s1", "model": MODEL, **event["session"]}
                        if confirmation.pop("turn_detection") is not None:
                            raise ValueError("manual_commit_required")
                        await send("session.updated", session=confirmation)
                    case "input_audio_buffer.append":
                        self.audio.extend(
                            base64.b64decode(event["audio"], validate=True)
                        )
                    case "input_audio_buffer.commit":
                        self.requested.set()
                        await self.release.wait()
                        self.late_response_attempted = True
                        await send("input_audio_buffer.committed")
                    case "session.finish":
                        await send(
                            "conversation.item.input_audio_transcription.completed",
                            transcript=ASR,
                        )
                        await send("session.finished")
                    case _:
                        raise ValueError("fixture_event")
        except ConnectionClosed:
            pass
        except Exception:
            self.errors.append("wss_fixture_failed")
