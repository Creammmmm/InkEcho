"""Bounded queue invariants; no desktop events or cloud requests."""

import asyncio
import time

import pytest

from inkecho.platform.keyboard import KeyboardError
from inkecho.providers import ProviderError
from inkecho.streaming_output import (
    CHUNK_CHARACTERS,
    MAX_TEXT_CHARACTERS,
    QUEUE_CHUNKS,
    StreamingOutput,
    TextDelta,
)


async def capture(deltas, final):
    chunks = []

    async def send(text):
        chunks.append(text)
        return len(text)

    output = StreamingOutput(send, lambda: True)
    consumer = asyncio.create_task(output.run())
    try:
        for delta in deltas:
            await output.append(delta)
        await output.finish(final)
        count = await consumer
        return "".join(chunks), count
    finally:
        if not consumer.done():
            consumer.cancel()
        await asyncio.gather(consumer, return_exceptions=True)
        output.close()


def test_unicode_offsets_overlap_dedup_keep_intentional_repeated_words_and_tail():
    result, count = asyncio.run(
        capture(
            [
                TextDelta(0, "中🙂"),
                TextDelta(0, "中🙂"),
                TextDelta(1, "🙂好"),
                TextDelta(3, "好"),
            ],
            "中🙂好好！",
        )
    )
    assert result == "中🙂好好！" and count == 5
    assert "private" not in repr(TextDelta(0, "private transcript"))


@pytest.mark.parametrize(
    "parts,final,expected",
    [
        (["甲\r", "\n乙"], "甲\r\n乙", "甲\n乙"),
        (["甲\r", "\r", "\n乙"], "甲\r\r\n乙", "甲\n\n乙"),
        (["甲\r"], "甲\r", "甲\n"),
        (["\r", "\n甲"], "\r\n甲", "\n甲"),
        (["甲\r", "乙"], "甲\r乙", "甲\n乙"),
    ],
)
def test_crlf_normalization_crosses_delta_boundaries(parts, final, expected):
    deltas = []
    offset = 0
    for part in parts:
        deltas.append(TextDelta(offset, part))
        offset += len(part)
    result, count = asyncio.run(capture(deltas, final))
    assert result == expected and count == len(expected)


@pytest.mark.parametrize(
    "delta",
    [
        TextDelta(1, "gap"),
        TextDelta(-1, "negative"),
        TextDelta(True, "boolean"),
        TextDelta(0, "\t"),
        TextDelta(0, "\0"),
        TextDelta(0, "\x7f"),
        TextDelta(0, "\x85"),
        TextDelta(0, "\ud800"),
        TextDelta(0, "x" * (MAX_TEXT_CHARACTERS + 1)),
    ],
)
def test_invalid_offsets_controls_surrogates_and_output_limit_fail_before_send(delta):
    async def scenario():
        async def forbidden(_text):
            pytest.fail("Invalid queued text must not reach transport")

        output = StreamingOutput(forbidden, lambda: True)
        with pytest.raises(ProviderError) as error:
            await output.append(delta)
        expected = (
            "response_control"
            if delta.text in {"\t", "\0", "\x7f", "\x85"}
            else "response"
        )
        assert error.value.code == expected and not output.attempted
        output.close()

    asyncio.run(scenario())


def test_conflicting_overlap_and_non_prefix_final_never_rewrite_dispatched_text():
    async def scenario():
        sent = []

        async def send(text):
            sent.append(text)
            return len(text)

        output = StreamingOutput(send, lambda: True)
        consumer = asyncio.create_task(output.run())
        await output.append(TextDelta(0, "甲乙"))
        await asyncio.sleep(0)
        assert sent == ["甲乙"]
        with pytest.raises(ProviderError):
            await output.append(TextDelta(1, "丙"))
        with pytest.raises(ProviderError):
            await output.finish("甲丙")
        consumer.cancel()
        await asyncio.gather(consumer, return_exceptions=True)
        output.close()
        assert sent == ["甲乙"]

    asyncio.run(scenario())


def test_empty_final_never_emits_initial_whitespace():
    async def scenario():
        async def forbidden(_text):
            pytest.fail("Whitespace-only failed results must not emit text")

        output = StreamingOutput(forbidden, lambda: True)
        await output.append(TextDelta(0, " \r"))
        await output.append(TextDelta(2, "\n "))
        with pytest.raises(ProviderError) as error:
            await output.finish(" \r\n ")
        assert error.value.code == "empty" and not output.attempted
        output.close()

    asyncio.run(scenario())


def test_queue_backpressure_and_cancel_clear_unsent_text():
    async def scenario():
        release = asyncio.Event()
        entered = asyncio.Event()
        emitted = []
        inflight = []
        live = [True]

        async def send(text):
            inflight.append(text)
            entered.set()
            await release.wait()
            if not live[0]:
                raise asyncio.CancelledError
            emitted.append(text)
            return len(text)

        output = StreamingOutput(send, lambda: live[0])
        text = "中" * (CHUNK_CHARACTERS * (QUEUE_CHUNKS + 2))
        consumer = asyncio.create_task(output.run())
        producer = asyncio.create_task(output.append(TextDelta(0, text)))
        await entered.wait()
        await asyncio.sleep(0)
        assert len(output._queue) == QUEUE_CHUNKS
        assert sum(len(delta.text) for delta in output._queue) == 4096
        assert len(inflight) == 1 and len(inflight[0]) == 128
        assert (
            sum(len(delta.text) for delta in output._queue) + len(inflight[0]) == 4224
        )
        assert not producer.done()
        live[0] = False
        producer.cancel()
        consumer.cancel()
        release.set()
        await asyncio.gather(producer, consumer, return_exceptions=True)
        output.close()
        assert not emitted and not output._text and not output._queue

    asyncio.run(scenario())


@pytest.mark.parametrize("count", [None, False, -1, 0, 2])
def test_uncertain_or_partial_dispatch_count_never_replays(count):
    async def scenario():
        calls = []

        async def send(text):
            calls.append(text)
            return count

        output = StreamingOutput(send, lambda: True)
        consumer = asyncio.create_task(output.run())
        await output.append(TextDelta(0, "甲"))
        with pytest.raises(KeyboardError):
            await consumer
        assert calls == ["甲"] and output.attempted
        output.close()

    asyncio.run(scenario())


def test_first_available_character_sends_before_future_then_merges_queued_text():
    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        calls = []

        async def send(text):
            calls.append(text)
            if len(calls) == 1:
                entered.set()
                await release.wait()
            return len(text)

        output = StreamingOutput(send, lambda: True)
        consumer = asyncio.create_task(output.run())
        await output.append(TextDelta(0, "甲"))
        async with asyncio.timeout(1):
            await entered.wait()
        assert calls == ["甲"]  # No later provider delta exists yet.
        for offset, character in enumerate("乙乙\r\n丙🙂", 1):
            await output.append(TextDelta(offset, character))
        await output.finish("甲乙乙\r\n丙🙂！")
        release.set()
        assert await consumer == len("甲乙乙\n丙🙂！")
        assert calls == ["甲", "乙乙\n丙🙂！"]
        assert output.sent_characters == len("".join(calls))
        assert not output._queue  # The terminal sentinel was consumed separately.
        output.close()

    asyncio.run(scenario())


def test_merge_stops_at_128_and_does_not_prefetch_oversized_next_block():
    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        calls = []

        async def send(text):
            calls.append(text)
            if len(calls) == 1:
                entered.set()
                await release.wait()
            return len(text)

        output = StreamingOutput(send, lambda: True)
        text = "甲" * 80 + "乙" * 48 + "丙" * 80
        await output.append(TextDelta(0, "甲" * 80))
        await output.append(TextDelta(80, "乙" * 48))
        await output.append(TextDelta(128, "丙" * 80))
        await output.finish(text)
        consumer = asyncio.create_task(output.run())
        await entered.wait()
        assert calls == [text[:128]]
        assert list(output._queue) == [TextDelta(128, "丙" * 80), None]
        release.set()
        assert await consumer == len(text)
        assert calls == [text[:128], text[128:]]
        output.close()

    asyncio.run(scenario())


def test_discontinuous_queued_offset_is_rejected_before_merged_dispatch():
    async def scenario():
        calls = []

        async def send(text):
            calls.append(text)
            return len(text)

        output = StreamingOutput(send, lambda: True)
        await output.append(TextDelta(0, "甲"))
        await output._put(TextDelta(2, "乙"))
        with pytest.raises(ProviderError, match="response"):
            await output.run()
        assert not calls and not output.attempted
        output.close()

    asyncio.run(scenario())


@pytest.mark.parametrize("waiting", ["producer", "consumer"])
def test_close_wakes_blocked_queue_waiters_and_clears_unsent_text(waiting):
    async def scenario():
        async def forbidden(_text):
            pytest.fail("Closed output must not send text")

        output = StreamingOutput(forbidden, lambda: True)
        if waiting == "producer":
            operation = output.append(
                TextDelta(0, "中" * (CHUNK_CHARACTERS * (QUEUE_CHUNKS + 1)))
            )
        else:
            operation = output.run()
        task = asyncio.create_task(operation)
        await asyncio.sleep(0)
        assert not task.done()
        if waiting == "producer":
            assert len(output._queue) == QUEUE_CHUNKS
        output.close()
        async with asyncio.timeout(1):
            with pytest.raises(asyncio.CancelledError):
                await task
        assert not output._queue and not output._text and not output.attempted

    asyncio.run(scenario())


@pytest.mark.parametrize("action", ["cancel", "expire", "replace", "close"])
def test_inflight_invalidation_stops_all_queued_and_merged_tail(action):
    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        calls = []
        live, task_id, deadline = True, "original", time.monotonic() + 60

        def active():
            return live and task_id == "original" and time.monotonic() < deadline

        async def send(text):
            calls.append(text)
            entered.set()
            await release.wait()
            return len(text)

        output = StreamingOutput(send, active)
        consumer = asyncio.create_task(output.run())
        await output.append(TextDelta(0, "甲"))
        await entered.wait()
        for index, character in enumerate("乙丙丁", 1):
            await output.append(TextDelta(index, character))
        await output.finish("甲乙丙丁")
        if action == "cancel":
            live = False
        elif action == "expire":
            deadline = time.monotonic() - 1
        elif action == "replace":
            task_id = "replacement"
        else:
            output.close()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await consumer
        assert calls == ["甲"] and output.attempted
        # Ambiguous partial dispatch is not counted as complete or replayed.
        assert output.sent_characters == 0
        output.close()
        assert not output._queue

    asyncio.run(scenario())


def test_fast_character_deltas_reduce_real_production_mapping_calls(monkeypatch):
    from test_keyboard import mapped_keyboard

    async def scenario():
        inputs, driver, rows, writes, events = mapped_keyboard(monkeypatch)
        await inputs.connect()
        first_pressed = asyncio.Event()
        chunks, dispatched = [], []
        original_send = driver.send

        def observed_send(window, code, pressed):
            original_send(window, code, pressed)
            if pressed:
                dispatched.append("\n" if code == 36 else chr(rows[1][0] & 0xFFFFFF))

        driver.send = observed_send

        async def send(text):
            chunks.append(text)
            return await inputs.insert(
                text, lambda: True, on_first_sent=lambda _at: first_pressed.set()
            )

        sample = "你好，InkEcho！ café Ω 😀\n第二行。" * 6
        assert len(sample) == 150 and len(sample.replace("\n", "")) == 144
        output = StreamingOutput(send, lambda: True)
        consumer = asyncio.create_task(output.run())
        await output.append(TextDelta(0, sample[0]))

        async def produce():
            await first_pressed.wait()
            for index, character in enumerate(sample[1:], 1):
                await output.append(TextDelta(index, character))
            await output.finish(sample)

        producer = asyncio.create_task(produce())
        await producer
        assert await consumer == 150
        assert chunks[0] == sample[:1] and len(chunks) == 6
        assert max(map(len, chunks)) <= CHUNK_CHARACTERS
        assert "".join(dispatched) == sample
        assert len(writes) == 144 + len(chunks) == 150
        assert sum(not any(row) for row in writes) == len(chunks)
        assert [event[2] for event in events] == [True, False] * 150
        assert rows == [(97, 65), (0, 0)] and driver.applied is None
        assert inputs._task is None
        output.close()
        await inputs.aclose()

    asyncio.run(scenario())


def test_cancel_inside_coalesced_insert_releases_real_owned_row_and_never_replays(
    monkeypatch,
):
    from test_keyboard import mapped_keyboard

    live = True
    events = []

    def cancel_after_second_press(_count):
        nonlocal live
        if sum(pressed for _window, _code, pressed in events) == 2:
            live = False

    async def scenario():
        nonlocal events
        inputs, driver, rows, writes, events = mapped_keyboard(
            monkeypatch, cancel_after_second_press
        )
        await inputs.connect()
        first_pressed = asyncio.Event()
        chunks = []

        async def send(text):
            chunks.append(text)
            return await inputs.insert(
                text, lambda: live, on_first_sent=lambda _at: first_pressed.set()
            )

        output = StreamingOutput(send, lambda: live)
        consumer = asyncio.create_task(output.run())
        await output.append(TextDelta(0, "甲"))
        await first_pressed.wait()
        for index, character in enumerate("乙丙丁戊", 1):
            await output.append(TextDelta(index, character))
        await output.finish("甲乙丙丁戊")
        with pytest.raises(KeyboardError, match="input_cancelled"):
            await consumer
        assert chunks == ["甲", "乙丙丁戊"]
        assert [event[2] for event in events] == [True, False] * 2
        assert len(writes) == 4 and rows == [(97, 65), (0, 0)]
        assert driver.applied is None and inputs._task is None
        assert output.sent_characters == 1 and output.attempted
        output.close()
        await inputs.aclose()

    asyncio.run(scenario())
