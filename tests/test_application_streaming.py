"""Synthetic provider and keyboard orchestration; not a cloud/desktop claim."""

import asyncio
import time
from dataclasses import replace

import pytest
from PySide6.QtCore import QObject, Signal

from inkecho.app import Session
from inkecho.config import ConfigStore
from inkecho.core import State
from inkecho.platform.keyboard import KeyboardError
from inkecho.providers import ProviderError, Result, Usage


class Recorder(QObject):
    level = Signal(float)
    finished = Signal(bytes, float)
    failed = Signal(str)

    def start(self, *_args, **_kwargs):
        return True

    def stop(self):
        self.finished.emit(b"synthetic-not-audio", 1)

    def cancel(self):
        pass


class Inputs:
    connected = True
    authorized = True
    supports_first_sent_callback = True

    def __init__(self):
        self.written = ""
        self.calls = []
        self.focus = "first"
        self.destinations = []
        self.before_character = lambda: None

    async def insert(self, text, can_continue, *, deadline=None, on_first_sent=None):
        self.calls.append(text)
        for index, character in enumerate(text):
            await asyncio.sleep(0)
            self.before_character()
            if not can_continue():
                raise KeyboardError("input_cancelled")
            self.written += character
            self.destinations.append(self.focus)
            if index == 0 and on_first_sent:
                on_first_sent(time.monotonic())
        return len(text)

    async def aclose(self):
        pass


class Client:
    async def transcribe(self, *_args):
        return Result("原始识别文本", Usage(), 0)

    async def polish(self, *_args):
        return Result("同步润色文本", Usage(), 0)


@pytest.fixture
def sessions(tmp_path):
    store = ConfigStore(tmp_path)
    store.initialize()
    store.save_settings(replace(store.load_settings(), polishing_enabled=True))
    store.save_provider(replace(store.load_provider("qwen"), model="synthetic-asr"))
    store.save_provider(
        replace(store.load_provider("deepseek"), model="synthetic-polish")
    )

    def create(client):
        session = Session(store, inputs=Inputs(), recorder=Recorder(), client=client)

        async def key(_reference):
            return "synthetic-not-a-key"

        session.key = key
        return session

    return create


async def until(predicate):
    for _ in range(100):
        if predicate():
            return
        await asyncio.sleep(0)
    raise AssertionError("Synthetic pipeline did not reach its expected boundary")


def test_streaming_outputs_before_polish_completion_normalizes_crlf_and_final_tail(
    sessions,
):
    async def scenario():
        release = asyncio.Event()

        class StreamClient(Client):
            async def polish_stream(self, _provider, _key, _text, _prompt, on_delta):
                await on_delta("甲\r")
                await release.wait()
                await on_delta("\n乙乙")
                return Result("甲\r\n乙乙！", Usage(3, 4, 7), 0)

        session = sessions(StreamClient())
        outcomes = []
        session.finished.connect(outcomes.append)
        await session.toggle()
        session.stop_recording()
        await until(lambda: session.inputs.written == "甲")
        assert session.controller.state == State.INJECTING
        assert session.controller.task.original == ""
        assert (
            session.task_timing.snapshot()["events_ms"]["polishing_completed"] is None
        )
        session.inputs.focus = "other"
        release.set()
        await until(lambda: not session.pending)
        assert session.inputs.written == "甲\n乙乙！"
        assert session.inputs.destinations == ["first"] + ["other"] * 4
        assert outcomes[0]["characters"] == 5
        assert outcomes[0]["usage"].total_tokens == 7
        events = session.last_performance["events_ms"]
        assert events["first_character_sent"] < events["polishing_completed"]
        assert events["output_completed"] >= events["polishing_completed"]
        assert session.controller.outcome == State.SUCCEEDED
        await session.close()

    asyncio.run(scenario())


@pytest.mark.parametrize("fallback", [True, False])
def test_stream_failure_before_output_respects_explicit_original_fallback(
    sessions, fallback
):
    async def scenario():
        class FailedClient(Client):
            async def polish_stream(self, *_args):
                raise ProviderError("response")

        session = sessions(FailedClient())
        session.store.save_settings(
            replace(session.settings, polishing_fallback=fallback)
        )
        await session.toggle()
        session.stop_recording()
        await until(lambda: not session.pending)
        assert session.inputs.written == ("原始识别文本" if fallback else "")
        assert len(session.inputs.calls) == (1 if fallback else 0)
        assert session.controller.outcome == (
            State.SUCCEEDED if fallback else State.FAILED
        )
        await session.close()

    asyncio.run(scenario())


def test_provider_failure_after_partial_output_never_falls_back_or_replays(sessions):
    async def scenario():
        sent = asyncio.Event()

        class FailedClient(Client):
            async def polish_stream(self, _provider, _key, _text, _prompt, on_delta):
                await on_delta("前缀")
                await sent.wait()
                raise ProviderError("timeout")

        session = sessions(FailedClient())
        await session.toggle()
        session.stop_recording()
        await until(lambda: session.inputs.written == "前缀")
        sent.set()
        await until(lambda: not session.pending)
        assert session.inputs.written == "前缀" and session.inputs.calls == ["前缀"]
        assert session.controller.outcome == State.FAILED
        assert session.last_performance["events_ms"]["output_completed"] is None
        await session.close()

    asyncio.run(scenario())


def test_keyboard_failure_cancels_waiting_provider_without_fallback(sessions):
    async def scenario():
        cancelled = asyncio.Event()

        class WaitingClient(Client):
            async def polish_stream(self, _provider, _key, _text, _prompt, on_delta):
                await on_delta("不可发送")
                try:
                    await asyncio.Event().wait()
                finally:
                    cancelled.set()

        session = sessions(WaitingClient())

        async def fail_insert(*_args, **_kwargs):
            raise KeyboardError("unsupported_text")

        session.inputs.insert = fail_insert
        await session.toggle()
        session.stop_recording()
        await until(lambda: not session.pending)
        assert cancelled.is_set() and not session.inputs.written
        assert session.controller.outcome == State.FAILED
        await session.close()

    asyncio.run(scenario())


@pytest.mark.parametrize("action", ["cancel", "expire", "replace"])
def test_partial_cancel_expiry_and_replacement_never_send_late_deltas(sessions, action):
    async def scenario():
        release = asyncio.Event()

        class LateClient(Client):
            async def polish_stream(self, _provider, _key, _text, _prompt, on_delta):
                await on_delta("前缀")
                try:
                    await release.wait()
                except asyncio.CancelledError:
                    await release.wait()
                await on_delta("迟到文本")
                return Result("前缀迟到文本", Usage(), 0)

        session = sessions(LateClient())
        await session.toggle()
        session.stop_recording()
        await until(lambda: session.inputs.written == "前缀")
        if action == "expire":
            session.controller.task.deadline = time.monotonic() - 1
            session.controller.tick()
        else:
            session.cancel()
        if action == "replace":
            session.last_toggle = 0
            await session.toggle()
            new_id = session.controller.task.id
        release.set()
        for _ in range(30):
            await asyncio.sleep(0)
        assert session.inputs.written == "前缀"
        if action == "replace":
            assert session.controller.task.id == new_id
            assert session.controller.state == State.RECORDING
        await session.close()

    asyncio.run(scenario())


def test_explicit_streaming_off_uses_one_synchronous_request(sessions):
    async def scenario():
        class NeverStream(Client):
            async def polish_stream(self, *_args):
                pytest.fail("An explicitly disabled stream must use synchronous polish")

        session = sessions(NeverStream())
        session.store.save_settings(
            replace(session.settings, polishing_streaming=False)
        )
        await session.toggle()
        session.stop_recording()
        await until(lambda: not session.pending)
        assert session.inputs.written == "同步润色文本"
        await session.close()

    asyncio.run(scenario())


def test_cancel_inside_one_chunk_stops_remaining_characters(sessions):
    async def scenario():
        class StreamClient(Client):
            async def polish_stream(self, _provider, _key, _text, _prompt, on_delta):
                await on_delta("甲乙丙丁戊己")
                return Result("甲乙丙丁戊己", Usage(), 0)

        session = sessions(StreamClient())

        def cancel_after_two():
            if len(session.inputs.written) == 2:
                session.cancel()

        session.inputs.before_character = cancel_after_two
        await session.toggle()
        session.stop_recording()
        await until(lambda: not session.pending)
        assert session.inputs.written == "甲乙"
        assert session.controller.outcome == State.CANCELLED
        assert session.last_performance["events_ms"]["first_character_sent"] is not None
        assert session.last_performance["events_ms"]["output_completed"] is None
        await session.close()

    asyncio.run(scenario())


@pytest.mark.parametrize("mode", ["bad_final", "bad_unicode"])
def test_invalid_later_unicode_or_changed_final_stops_after_prefix(sessions, mode):
    async def scenario():
        release = asyncio.Event()

        class BadClient(Client):
            async def polish_stream(self, _provider, _key, _text, _prompt, on_delta):
                await on_delta("前缀")
                await release.wait()
                if mode == "bad_unicode":
                    await on_delta("\ud800")
                return Result("修改全文", Usage(), 0)

        session = sessions(BadClient())
        await session.toggle()
        session.stop_recording()
        await until(lambda: session.inputs.written == "前缀")
        release.set()
        await until(lambda: not session.pending)
        assert session.inputs.written == "前缀"
        assert session.controller.outcome == State.FAILED
        await session.close()

    asyncio.run(scenario())
