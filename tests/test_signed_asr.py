"""Independent bounded framing and revision safety for signed ASR protocols."""

import asyncio
import base64
import gzip
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qs, urlsplit

import pytest
from test_realtime import certificate as shared_certificate
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

from inkecho.asr_streaming import create_streaming_session, streaming_config
from inkecho.config import Provider
from inkecho.provider_credentials import encode_credentials
from inkecho.providers import ProviderError
from inkecho.tencent_realtime import TencentConfig
from inkecho.volc_realtime import VolcConfig, decode_frame, encode_frame
from inkecho.xfyun_realtime import XfyunConfig, XfyunSession


def revision(sn, text, **options):
    return {"sn": sn, "ws": [{"cw": [{"w": text}]}], **options}


def test_xfyun_revisions_do_not_resurrect_superseded_text():
    session = XfyunSession(XfyunConfig("wss://localhost/v2/iat", "iat"), "synthetic")
    session._revision(revision(0, "first"))
    session._revision(revision(1, "second"))
    session._revision(revision(2, "replacement", pgs="rpl", rg=[0, 1]))
    session._revision(revision(0, "first"))
    assert session._pieces == {2: "replacement"}
    with pytest.raises(ProviderError):
        session._revision(revision(0, "conflicting"))


@pytest.mark.parametrize("first", [2, 3])
def test_xfyun_missing_or_out_of_order_revision_fails(first):
    session = XfyunSession(XfyunConfig("wss://localhost/v2/iat", "iat"), "synthetic")
    with pytest.raises(ProviderError):
        session._revision(revision(first, "late", pgs="rpl", rg=[0, 0]))
    assert not session._pieces


def test_xfyun_sid_is_optional_after_first_response():
    async def scenario():
        session = XfyunSession(
            XfyunConfig("wss://localhost/v2/iat", "iat"), "synthetic"
        )
        session._done = asyncio.get_running_loop().create_future()
        await session._event(
            {
                "code": 0,
                "sid": "synthetic",
                "data": {"status": 0, "result": revision(0, "final")},
            }
        )
        session._finish_sent = True
        await session._event({"code": 0, "data": {"status": 2}})
        assert session._done.result() == "final"
        with pytest.raises(ProviderError):
            await session._event({"code": 0, "sid": "other", "data": {"status": 1}})

    asyncio.run(scenario())


def server_frame(body, flags=3, sequence=3, compression=1):
    payload = json.dumps(body).encode()
    if compression:
        payload = gzip.compress(payload)
    prefix = bytes((0x11, 0x90 | flags, 0x10 | compression, 0))
    if flags & 1:
        prefix += sequence.to_bytes(4, "big", signed=True)
    return prefix + len(payload).to_bytes(4, "big") + payload


@pytest.mark.parametrize("flags,sequence", [(2, 0), (3, 3), (3, -3)])
def test_volc_final_flag_not_sequence_sign(flags, sequence):
    final, value = decode_frame(
        server_frame({"result": {"text": "final"}}, flags, sequence)
    )
    assert final and value == {"result": {"text": "final"}}


def test_volc_client_final_has_no_sequence():
    frame = encode_frame(2, b"", final=True)
    assert frame[:4] == bytes((0x11, 0x22, 0x01, 0))
    assert int.from_bytes(frame[4:8], "big") == len(frame) - 8
    assert gzip.decompress(frame[8:]) == b""


@pytest.mark.parametrize("mode", ["truncated", "extra", "bomb", "text", "flags"])
def test_volc_decoder_rejects_malformed_and_expansion(mode):
    frame = server_frame({"result": {"text": "final"}})
    if mode == "truncated":
        frame = frame[:-1]
    elif mode == "extra":
        frame += b"extra"
    elif mode == "bomb":
        frame = server_frame({"result": {"text": "x" * (1024 * 1024 + 1)}})
    elif mode == "text":
        frame = "not binary"
    else:
        frame = frame[:1] + bytes((0x97,)) + frame[2:]
    with pytest.raises(ProviderError):
        decode_frame(frame)


@pytest.mark.parametrize("base", [0, 1])
def test_xfyun_sequence_base_is_locked(base):
    session = XfyunSession(XfyunConfig("wss://localhost/v2/iat", "iat"), "synthetic")
    session._revision(revision(base, "first"))
    session._revision(revision(base + 1, "second"))
    with pytest.raises(ProviderError):
        session._revision(revision(base + 3, "gap"))
    assert session._pieces == {base: "first", base + 1: "second"}


# The server below parses raw frames independently, rather than using the client
# codec. It has no actual credentials, remote provider or microphone.
certificate = shared_certificate


async def wire_exercise(ca, family, mode="normal", operation=None):
    frames, stamps, messages, requests = [], [], [], []

    def make_session(config, key, **policy):
        adapter, protocol = {
            "xfyun": ("xfyun", "xfyun_iat"),
            "tencent": ("tencent-asr", "tencent_asr"),
        }.get(family, ("volcengine", "volc_binary"))
        parameters = {"asr_protocol": protocol, "realtime_url": config.endpoint}
        if family.startswith("volc"):
            parameters.update(
                resource_id=config.resource_id, credential_mode=config.credential_mode
            )
        provider = Provider(
            "local",
            "Synthetic",
            "transcription",
            adapter,
            "https://synthetic.invalid",
            config.model,
            parameters=parameters,
        )
        selected = streaming_config(provider)
        assert selected == config
        return create_streaming_session(provider, selected, key, **policy)

    async def handler(ws):
        requests.append(ws.request)
        query = parse_qs(urlsplit(ws.request.path).query)
        voice = query.get("voice_id", [None])[0]
        if family == "tencent":
            assert query["engine_model_type"] == ["16k_zh"]
            assert query["voice_format"] == ["1"] and query["signature"]
            parts = urlsplit(ws.request.path)
            canonical = "&".join(
                f"{key}={query[key][0]}" for key in sorted(query) if key != "signature"
            )
            expected = base64.b64encode(
                hmac.new(
                    b"test-secret",
                    (
                        "GET"
                        + ws.request.headers["Host"]
                        + parts.path
                        + "?"
                        + canonical
                    ).encode(),
                    hashlib.sha1,
                ).digest()
            ).decode()
            assert query["signature"] == [expected]
            assert ws.request.path.startswith("/asr/v2/123?")
            await ws.send(json.dumps({"code": 0, "voice_id": voice}))
        elif family == "xfyun":
            auth = base64.b64decode(query["authorization"][0]).decode()
            assert 'algorithm="hmac-sha256"' in auth and 'api_key="test-key"' in auth
            assert query["host"] == [ws.request.headers["Host"]] and query["date"]
            canonical = (
                f"host: {query['host'][0]}\ndate: {query['date'][0]}\n"
                "GET /v2/iat HTTP/1.1"
            )
            expected = base64.b64encode(
                hmac.new(b"test-secret", canonical.encode(), hashlib.sha256).digest()
            ).decode()
            assert f'signature="{expected}"' in auth
        else:
            assert not query
            if family == "volc-app":
                assert ws.request.headers["X-Api-App-Key"] == "test-app"
                assert ws.request.headers["X-Api-Access-Key"] == "test-access"
                assert "X-Api-Key" not in ws.request.headers
            else:
                assert ws.request.headers["X-Api-Key"] == "test-key"
                assert "X-Api-App-Key" not in ws.request.headers
            assert ws.request.headers["X-Api-Resource-Id"] == "synthetic-resource"
            assert ws.request.headers["X-Api-Request-Id"]
        assert "Authorization" not in ws.request.headers
        try:
            async for raw in ws:
                final = False
                if family.startswith("volc"):
                    assert isinstance(raw, bytes)
                    assert raw[0] == 0x11 and raw[3] == 0
                    assert int.from_bytes(raw[4:8], "big") == len(raw) - 8
                    payload = gzip.decompress(raw[8:])
                    if raw[1] >> 4 == 1:
                        assert raw[2] == 0x11
                        value = json.loads(payload)
                        assert value["audio"] == {
                            "format": "pcm",
                            "codec": "raw",
                            "rate": 16000,
                            "bits": 16,
                            "channel": 1,
                        }
                        assert value["request"]["model_name"] == "bigmodel"
                        messages.append(value)
                        continue
                    assert raw[2] == 0x01 and raw[1] in {0x20, 0x22}
                    final = raw[1] == 0x22
                    if not final:
                        frames.append(payload)
                        stamps.append(time.monotonic())
                    else:
                        assert payload == b""
                elif family == "xfyun":
                    value = json.loads(raw)
                    messages.append(value)
                    data = value["data"]
                    final = data["status"] == 2
                    if not final:
                        if not frames:
                            assert data["status"] == 0
                            assert value["common"] == {"app_id": "123"}
                            assert value["business"]["dwa"] == "wpgs"
                        else:
                            assert data["status"] == 1 and "common" not in value
                        assert data["format"] == "audio/L16;rate=16000"
                        frames.append(base64.b64decode(data["audio"]))
                        stamps.append(time.monotonic())
                    else:
                        assert data["audio"] == ""
                else:
                    if isinstance(raw, bytes):
                        frames.append(raw)
                        stamps.append(time.monotonic())
                    else:
                        assert json.loads(raw) == {"type": "end"}
                        messages.append(json.loads(raw))
                        final = True
                if mode == "close":
                    await ws.close()
                    return
                if not final or mode == "timeout":
                    continue
                if mode == "error":
                    if family == "xfyun":
                        await ws.send(json.dumps({"code": 10105}))
                    elif family == "tencent":
                        await ws.send(json.dumps({"code": 4001, "voice_id": voice}))
                    else:
                        await ws.send(
                            bytes((0x11, 0xF0, 0x10, 0))
                            + (45000001).to_bytes(4, "big")
                            + (2).to_bytes(4, "big")
                            + b"{}"
                        )
                    continue
                if family == "xfyun":
                    await ws.send(
                        json.dumps(
                            {
                                "code": 0,
                                "sid": "test-session",
                                "data": {"status": 1, "result": revision(1, "final")},
                            }
                        )
                    )
                    await ws.send(
                        json.dumps(
                            {
                                "code": 0,
                                "sid": "wrong"
                                if mode == "identity"
                                else "test-session",
                                "data": {"status": 2},
                            }
                        )
                    )
                elif family == "tencent":
                    await ws.send(
                        json.dumps(
                            {
                                "code": 0,
                                "voice_id": voice,
                                "result": {
                                    "index": 0,
                                    "slice_type": 2,
                                    "voice_text_str": "final",
                                },
                            }
                        )
                    )
                    await ws.send(
                        json.dumps(
                            {
                                "code": 0,
                                "voice_id": "wrong" if mode == "identity" else voice,
                                "final": 1,
                            }
                        )
                    )
                else:
                    await ws.send(
                        server_frame({"result": {"text": "final"}}, flags=3, sequence=3)
                    )
        except ConnectionClosed:
            pass

    async with serve(handler, "127.0.0.1", 0, ssl=ca[0]) as server:
        port = server.sockets[0].getsockname()[1]
        endpoint = f"wss://127.0.0.1:{port}"
        if family == "xfyun":
            session = make_session(
                XfyunConfig(endpoint + "/v2/iat", "iat"),
                encode_credentials(
                    {
                        "app_id": "123",
                        "api_key": "test-key",
                        "api_secret": "test-secret",
                    },
                    ("app_id", "api_key", "api_secret"),
                ),
                timeout_seconds=0.45,
                tls_context=ca[1],
            )
        elif family == "tencent":
            session = make_session(
                TencentConfig(endpoint + "/asr/v2", "16k_zh"),
                encode_credentials(
                    {
                        "app_id": "123",
                        "secret_id": "test-id",
                        "secret_key": "test-secret",
                    },
                    ("app_id", "secret_id", "secret_key"),
                ),
                timeout_seconds=0.45,
                tls_context=ca[1],
            )
        else:
            session = make_session(
                VolcConfig(
                    endpoint + "/bigmodel_async",
                    "bigmodel",
                    "synthetic-resource",
                    "app_access" if family == "volc-app" else "api_key",
                ),
                encode_credentials(
                    {"app_key": "test-app", "access_key": "test-access"},
                    ("app_key", "access_key"),
                )
                if family == "volc-app"
                else "test-key",
                timeout_seconds=0.45,
                tls_context=ca[1],
            )
        try:
            if operation:
                await operation(session)
            else:
                await session.start()
                await session.feed(bytes(range(100)) * 65)
                result = await session.finish()
                assert result.text == "final"
        finally:
            await session.aclose()
        assert all(task.done() for task in session._tasks)
        assert session._socket.close_code is not None and session._key == ""
    assert len(requests) == 1
    return frames, stamps, messages


@pytest.mark.parametrize("family", ["xfyun", "tencent", "volc"])
def test_signed_protocol_real_wss_frames_and_exact_pcm(certificate, family):
    frames, stamps, messages = asyncio.run(wire_exercise(certificate, family))
    assert b"".join(frames) == bytes(range(100)) * 65
    limit = 3200 if family.startswith("volc") else 1280
    assert all(0 < len(frame) <= limit for frame in frames)
    assert all(
        stamps[n + 1] - stamps[n] >= len(frames[n]) / 32000 - 0.015
        for n in range(len(stamps) - 1)
    )
    if not family.startswith("volc"):
        assert len(frames) == 6 and list(map(len, frames)) == [1280] * 5 + [100]


@pytest.mark.parametrize("family", ["xfyun", "tencent", "volc"])
def test_signed_protocol_timeout_never_promotes_partial(certificate, family):
    with pytest.raises(ProviderError) as caught:
        asyncio.run(wire_exercise(certificate, family, "timeout"))
    assert caught.value.code == "timeout"


@pytest.mark.parametrize("family", ["xfyun", "tencent", "volc"])
@pytest.mark.parametrize("stop", ["cancel", "inactive", "deadline"])
def test_signed_protocol_cancel_expiry_deadline_no_late_success(
    certificate, family, stop
):
    async def operation(session):
        await session.start()
        await session.feed(b"\0\0" * 1600)
        task = asyncio.create_task(session.finish())
        await asyncio.sleep(0.12)
        if stop == "cancel":
            task.cancel()
        elif stop == "inactive":
            session.active = lambda: False
        else:
            session.deadline = time.monotonic() - 1
        if stop == "deadline":
            with pytest.raises(ProviderError) as caught:
                await task
            assert caught.value.code == "timeout"
        else:
            with pytest.raises(asyncio.CancelledError):
                await task
        assert session._done.cancelled() or not session._done.done()

    asyncio.run(wire_exercise(certificate, family, "timeout", operation))


def test_volc_app_access_headers_over_real_wss(certificate):
    frames, _, _ = asyncio.run(wire_exercise(certificate, "volc-app"))
    assert b"".join(frames) == bytes(range(100)) * 65


@pytest.mark.parametrize("family", ["xfyun", "tencent", "volc"])
@pytest.mark.parametrize("mode", ["close", "error"])
def test_signed_remote_error_or_close_never_returns_final(certificate, family, mode):
    with pytest.raises(ProviderError):
        asyncio.run(wire_exercise(certificate, family, mode))


@pytest.mark.parametrize("family", ["xfyun", "tencent"])
def test_signed_mismatched_identity_is_rejected(certificate, family):
    with pytest.raises(ProviderError) as caught:
        asyncio.run(wire_exercise(certificate, family, "identity"))
    assert caught.value.code == "response"


def test_xfyun_sixty_second_limit_rejects_before_queue_write():
    async def scenario():
        session = XfyunSession(
            XfyunConfig("wss://localhost/v2/iat", "iat"), "synthetic"
        )
        session._audio_bytes = 60 * 32000
        with pytest.raises(ProviderError) as caught:
            session.feed_nowait(b"\0\0")
        assert caught.value.code == "audio" and session._queue.empty()
        await session.aclose()

    asyncio.run(scenario())


def test_fixed_signatures_cover_path_date_sorting_and_tampering():
    from inkecho.tencent_realtime import signed_url as tencent_url
    from inkecho.xfyun_realtime import signed_url as xfyun_url

    tx = tencent_url(
        TencentConfig("wss://asr.cloud.tencent.com/asr/v2", "16k_zh"),
        {"app_id": "123", "secret_id": "id", "secret_key": "secret"},
        "voice",
        now=1700000000,
        nonce=42,
    )
    query = parse_qs(urlsplit(tx).query)
    canonical = (
        "GETasr.cloud.tencent.com/asr/v2/123?engine_model_type=16k_zh"
        "&expired=1700000600&needvad=1&nonce=42&secretid=id"
        "&timestamp=1700000000&voice_format=1&voice_id=voice"
    )
    expected = base64.b64encode(
        hmac.new(b"secret", canonical.encode(), hashlib.sha1).digest()
    ).decode()
    assert query["signature"] == [expected]
    assert query["signature"] != [
        base64.b64encode(
            hmac.new(
                b"secret",
                canonical.replace("nonce=42", "nonce=43").encode(),
                hashlib.sha1,
            ).digest()
        ).decode()
    ]
    xf = xfyun_url(
        "wss://iat-api.xfyun.cn/v2/iat",
        {"api_key": "key", "api_secret": "secret"},
        now=1700000000,
    )
    query = parse_qs(urlsplit(xf).query)
    assert query["date"] == ["Tue, 14 Nov 2023 22:13:20 GMT"]
    auth = base64.b64decode(query["authorization"][0]).decode()
    canonical = (
        "host: iat-api.xfyun.cn\ndate: Tue, 14 Nov 2023 22:13:20 GMT\n"
        "GET /v2/iat HTTP/1.1"
    )
    expected = base64.b64encode(
        hmac.new(b"secret", canonical.encode(), hashlib.sha256).digest()
    ).decode()
    assert f'signature="{expected}"' in auth
    tampered = base64.b64encode(
        hmac.new(
            b"secret", canonical.replace("/v2/iat", "/wrong").encode(), hashlib.sha256
        ).digest()
    ).decode()
    assert f'signature="{tampered}"' not in auth


@pytest.mark.parametrize("value", [[], {}, True, None])
def test_signature_configs_reject_malformed_json_types(value):
    with pytest.raises(ProviderError) as caught:
        TencentConfig("wss://localhost/asr/v2", value)
    assert caught.value.code == "configuration"
    with pytest.raises(ProviderError) as caught:
        VolcConfig("wss://localhost/asr", "bigmodel", "resource", value)
    assert caught.value.code == "configuration"
