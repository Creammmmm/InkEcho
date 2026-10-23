"""Synthetic Session streaming through the real Xorg pair-mapping implementation.

Only X hardware calls are replaced; decode the mapping at each physical press,
not merely its keycode, to catch repeated-prefix Unicode corruption.
"""

import asyncio

import pytest
from test_application_streaming import Client, sessions, until
from test_xorg_pair import ImmediatePacer, hardware

from inkecho.core import State
from inkecho.platform.keyboard import KeyboardInput
from inkecho.providers import Result, Usage

# Re-export the fixture so pytest can create the ordinary configured Session.
__all__ = ["sessions"]


@pytest.mark.parametrize(
    "fragments",
    [
        ("中文", "输入", "中文", "验证", " café", " Ω", " 字符逐个出现。"),
        tuple("中文输入中文验证 café Ω 字符逐个出现。"),
        ("中", "文输入中文验证 café Ω 字符逐个出现。"),
    ],
)
def test_session_streaming_decodes_every_remapped_symbol(
    sessions, monkeypatch, fragments
):
    driver, rows, writes, events, _ = hardware(monkeypatch)
    before = rows.copy()
    received = []
    original_send = driver.send

    def send(window, code, pressed):
        if pressed:
            symbol = rows[code - driver.first][0]
            received.append(chr(symbol & 0xFFFFFF))
        original_send(window, code, pressed)

    driver.send = send

    async def scenario():
        inputs = KeyboardInput(driver_factory=lambda: driver, pacer=ImmediatePacer())
        await inputs.connect()

        class StreamClient(Client):
            async def polish_stream(self, _provider, _key, _text, _prompt, on_delta):
                expected = ""
                for fragment in fragments:
                    await on_delta(fragment)
                    expected += fragment
                    await until(lambda expected=expected: "".join(received) == expected)
                    assert inputs._output_owner is not None
                return Result(expected, Usage(), 0)

        session = sessions(StreamClient())
        session.inputs = inputs
        outcomes = []
        session.finished.connect(outcomes.append)
        await session.toggle()
        session.stop_recording()
        await until(lambda: not session.pending)
        expected = "".join(fragments)
        assert "".join(received) == expected
        assert session.controller.outcome == State.SUCCEEDED
        assert outcomes[0]["characters"] == len(expected)
        assert len(events) == len(expected) * 2
        assert rows == before
        assert not driver._batch and not driver._pair_applied
        assert inputs._output_owner is None
        assert all(write[-1] == 2 for write in writes[:-2])
        await session.close()

    asyncio.run(scenario())


@pytest.mark.parametrize("action", ["cancel", "expire", "replace", "close"])
def test_pair_session_invalidated_between_fragments_never_sends_late_text(
    sessions, monkeypatch, action
):
    driver, rows, _writes, events, _ = hardware(monkeypatch)
    before = rows.copy()

    async def scenario():
        inputs = KeyboardInput(driver_factory=lambda: driver, pacer=ImmediatePacer())
        await inputs.connect()
        release = asyncio.Event()

        class LateClient(Client):
            async def polish_stream(self, _provider, _key, _text, _prompt, on_delta):
                await on_delta("中文")
                try:
                    await release.wait()
                except asyncio.CancelledError:
                    await release.wait()
                await on_delta("迟到内容")
                return Result("中文迟到内容", Usage(), 0)

        session = sessions(LateClient())
        session.inputs = inputs
        await session.toggle()
        session.stop_recording()
        await until(lambda: len(events) == 4 and inputs._task is None)
        assert driver._pair_applied and inputs._output_owner is not None
        if action == "expire":
            session.controller.task.deadline = 0
            session.controller.tick()
        elif action == "close":
            closing = asyncio.create_task(session.close())
        else:
            session.cancel()
            if action == "replace":
                session.last_toggle = 0
                await session.toggle()
                replacement = session.controller.task.id
        release.set()
        await until(lambda: inputs._output_owner is None)
        assert len(events) == 4
        assert rows == before and not driver._pair_applied
        assert [event[2] for event in events] == [True, False, True, False]
        if action == "replace":
            assert session.controller.task.id == replacement
            assert session.controller.state == State.RECORDING
        if action == "close":
            await closing
        else:
            await session.close()

    asyncio.run(scenario())
