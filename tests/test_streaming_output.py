"""Bounded queue invariants; no desktop events or cloud requests."""

import asyncio

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
        assert error.value.code == "response" and not output.attempted
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
        live = [True]

        async def send(text):
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
        assert output._queue.qsize() == QUEUE_CHUNKS
        assert not producer.done()
        live[0] = False
        producer.cancel()
        consumer.cancel()
        release.set()
        await asyncio.gather(producer, consumer, return_exceptions=True)
        output.close()
        assert not emitted and not output._text and output._queue.empty()

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
