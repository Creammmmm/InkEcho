import asyncio
from types import SimpleNamespace

import pytest
from dbus_next import MessageType
from test_ibus import Bus, trusted_owner
from test_output_router import Keyboard

from inkecho.platform.ibus import CandidateError, Capability, Client, IBusBridgeError
from inkecho.platform.output_router import OutputRouter, OutputRouterError


def test_zero_prefix_authenticated_no_service(tmp_path):
    async def run():
        tmp_path.chmod(0o700)
        cap = Capability(tmp_path)
        bus = Bus()
        bus.outcomes = ["no_service"]
        client = Client(cap, bus_factory=lambda: bus, owner_verifier=trusted_owner)
        await client.begin()
        with pytest.raises(CandidateError, match="no_service"):
            await client.insert("甲乙", lambda: True)
        assert [m.member for m in bus.calls].count("Commit") == 1
        with pytest.raises(CandidateError, match="not_ready"):
            await client.insert("甲", lambda: True)
        await client.close()

    asyncio.run(run())


def test_no_service_after_prior_attempt_is_unknown(tmp_path):
    async def run():
        tmp_path.chmod(0o700)
        cap = Capability(tmp_path)
        bus = Bus()
        bus.outcomes = ["attempted", "no_service"]
        client = Client(cap, bus_factory=lambda: bus, owner_verifier=trusted_owner)
        await client.begin()
        assert await client.insert("甲", lambda: True) == 1
        with pytest.raises(CandidateError, match="delivery_unknown"):
            await client.insert("乙", lambda: True)
        await client.close()

    asyncio.run(run())


def test_spoofed_no_service_is_unknown(tmp_path):
    async def run():
        tmp_path.chmod(0o700)
        cap = Capability(tmp_path)
        bus = Bus()
        original = bus.call

        async def call(message):
            if message.member == "Commit":
                bus.calls.append(message)
                return SimpleNamespace(
                    message_type=MessageType.METHOD_RETURN,
                    body=["no_service"],
                    sender=":1.99",
                )
            return await original(message)

        bus.call = call
        client = Client(cap, bus_factory=lambda: bus, owner_verifier=trusted_owner)
        await client.begin()
        with pytest.raises(CandidateError, match="delivery_unknown"):
            await client.insert("甲", lambda: True)
        await client.close()

    asyncio.run(run())


@pytest.mark.parametrize(
    "failure,expect_fallback", [("no_service", True), ("delivery_unknown", False)]
)
def test_explicit_ibus_safe_fallback_only(failure, expect_fallback):
    async def run():
        keyboard = Keyboard()

        class Bridge:
            closed = False

            async def connect(self):
                pass

            async def insert(self, *_args, **_kwargs):
                raise IBusBridgeError(failure)

            async def aclose(self):
                self.closed = True

        bridge = Bridge()
        router = OutputRouter(keyboard, ibus_factory=lambda: bridge)
        await router.prepare_task("ibus")
        if expect_fallback:
            assert await router.insert("甲乙", lambda: True) == 2
            assert keyboard.sent == ["甲乙"]
        else:
            with pytest.raises(OutputRouterError, match="ibus_delivery_unknown"):
                await router.insert("甲乙", lambda: True)
            assert keyboard.sent == []
        assert bridge.closed

    asyncio.run(run())


def test_prior_fragment_never_fallbacks():
    async def run():
        keyboard = Keyboard()

        class Bridge:
            n = 0

            async def connect(self):
                pass

            async def insert(self, text, *_args, **_kwargs):
                self.n += 1
                if self.n == 1:
                    return len(text)
                raise IBusBridgeError("no_service")

            async def aclose(self):
                pass

        router = OutputRouter(keyboard, ibus_factory=Bridge)
        await router.prepare_task("ibus")
        with pytest.raises(OutputRouterError, match="ibus_no_service"):
            async with router.output_session():
                await router.insert("甲", lambda: True)
                await router.insert("乙", lambda: True)
        assert keyboard.sent == []

    asyncio.run(run())


@pytest.mark.parametrize(
    "mode", ["first_no_service", "second_no_service", "lost_reply"]
)
def test_real_ibus_client_and_router_do_not_replay_uncertain_prefix(tmp_path, mode):
    from inkecho.platform.ibus import IBusBridge

    async def run():
        tmp_path.chmod(0o700)
        bus = Bus()
        bus.outcomes = {
            "first_no_service": ["no_service"],
            "second_no_service": ["attempted", "no_service"],
            "lost_reply": [TimeoutError("synthetic lost reply")],
        }[mode]
        keyboard = Keyboard()
        router = OutputRouter(
            keyboard,
            ibus_factory=lambda: IBusBridge(
                runtime_dir=str(tmp_path),
                client_factory=lambda cap: Client(
                    cap, bus_factory=lambda: bus, owner_verifier=trusted_owner
                ),
            ),
        )
        await router.prepare_task("ibus")
        if mode == "first_no_service":
            assert await router.insert("甲乙", lambda: True) == 2
            assert keyboard.sent == ["甲乙"]
        else:
            with pytest.raises(OutputRouterError, match="ibus_delivery_unknown"):
                await router.insert("甲乙", lambda: True)
            assert keyboard.sent == []
        commits = [message for message in bus.calls if message.member == "Commit"]
        assert [message.body[1] for message in commits] == (
            ["甲", "乙"] if mode == "second_no_service" else ["甲"]
        )
        assert bus.disconnected and router.selected is None
        assert list(tmp_path.iterdir()) == []

    asyncio.run(run())


@pytest.mark.parametrize("mode", ["task_cancel", "predicate", "expired"])
def test_ibus_fallback_stops_if_task_ends_during_bridge_close(tmp_path, mode):
    import time

    from inkecho.platform.ibus import IBusBridge

    async def run():
        class DelayedClose(IBusBridge):
            async def close_after_no_service(self):
                started.set()
                try:
                    await release.wait()
                finally:
                    await super().close_after_no_service()

        tmp_path.chmod(0o700)
        started, release = asyncio.Event(), asyncio.Event()
        bus = Bus()
        bus.outcomes = ["no_service"]
        keyboard = Keyboard()
        router = OutputRouter(
            keyboard,
            ibus_factory=lambda: DelayedClose(
                runtime_dir=str(tmp_path),
                client_factory=lambda cap: Client(
                    cap, bus_factory=lambda: bus, owner_verifier=trusted_owner
                ),
            ),
        )
        await router.prepare_task("ibus")
        active = [True]
        deadline = time.monotonic() + 0.2 if mode == "expired" else None
        task = asyncio.create_task(
            router.insert("甲乙", lambda: active[0], deadline=deadline)
        )
        await started.wait()
        if mode == "task_cancel":
            task.cancel()
        elif mode == "predicate":
            active[0] = False
            release.set()
        else:
            await asyncio.sleep(0.25)
            release.set()
        expected = (
            asyncio.CancelledError if mode == "task_cancel" else OutputRouterError
        )
        with pytest.raises(expected) as error:
            await asyncio.wait_for(task, 1)
        if mode != "task_cancel":
            assert error.value.code == (
                "expired" if mode == "expired" else "input_cancelled"
            )
        assert keyboard.sent == [] and bus.disconnected and router.selected is None
        assert [m.member for m in bus.calls].count("Commit") == 1
        assert list(tmp_path.iterdir()) == []

    asyncio.run(run())


def test_ibus_zero_prefix_fallback_keeps_current_target_for_later_fragments():
    async def run():
        class KeyboardAtFocus(Keyboard):
            def __init__(self):
                super().__init__()
                self.focus = "A"
                self.received = []

            async def insert(self, text, can_continue, **kwargs):
                assert can_continue()
                self.received.append((self.focus, text))
                return len(text)

        class NoService:
            async def connect(self):
                pass

            async def insert(self, *_args, **_kwargs):
                raise IBusBridgeError("no_service")

            async def aclose(self):
                pass

        keyboard = KeyboardAtFocus()
        router = OutputRouter(keyboard, ibus_factory=NoService)
        await router.prepare_task("ibus")
        async with router.output_session():
            assert await router.insert("甲", lambda: True) == 1
            keyboard.focus = "B"
            assert await router.insert("乙", lambda: True) == 1
        assert keyboard.received == [("A", "甲"), ("B", "乙")]

    asyncio.run(run())


def test_ibus_confirmed_no_service_disconnects_without_remote_cancel(tmp_path):
    from inkecho.platform.ibus import IBusBridge

    async def run():
        tmp_path.chmod(0o700)
        bus = Bus()
        bus.outcomes = ["no_service"]
        keyboard = Keyboard()
        router = OutputRouter(
            keyboard,
            ibus_factory=lambda: IBusBridge(
                runtime_dir=str(tmp_path),
                client_factory=lambda cap: Client(
                    cap, bus_factory=lambda: bus, owner_verifier=trusted_owner
                ),
            ),
        )
        await router.prepare_task("ibus")
        assert await asyncio.wait_for(router.insert("甲乙", lambda: True), 0.5) == 2
        assert keyboard.sent == ["甲乙"]
        assert [m.member for m in bus.calls].count("Commit") == 1
        assert all(m.member != "Cancel" for m in bus.calls)
        assert bus.disconnected and list(tmp_path.iterdir()) == []

    asyncio.run(run())


@pytest.mark.parametrize("mode", ["before_commit", "attempted", "lost_reply"])
def test_fast_ibus_close_rejects_unconfirmed_or_sent_input(tmp_path, mode):
    from inkecho.platform.ibus import IBusBridge

    async def run():
        tmp_path.chmod(0o700)
        bus = Bus()
        bus.outcomes = ["attempted" if mode == "attempted" else TimeoutError()]
        bridge = IBusBridge(
            runtime_dir=str(tmp_path),
            client_factory=lambda cap: Client(
                cap, bus_factory=lambda: bus, owner_verifier=trusted_owner
            ),
        )
        await bridge.connect()
        if mode == "attempted":
            assert await bridge.insert("甲", lambda: True) == 1
        elif mode == "lost_reply":
            with pytest.raises(IBusBridgeError, match="delivery_unknown"):
                await bridge.insert("甲", lambda: True)
        with pytest.raises(IBusBridgeError, match="delivery_unknown"):
            await bridge.close_after_no_service()
        assert not bus.disconnected
        await bridge.aclose()
        assert bus.disconnected and list(tmp_path.iterdir()) == []

    asyncio.run(run())


@pytest.mark.parametrize("mode", ["predicate", "expired"])
def test_confirmed_no_service_after_task_end_fast_closes_without_output(tmp_path, mode):
    import time

    from inkecho.platform.ibus import IBusBridge

    async def run():
        started, release = asyncio.Event(), asyncio.Event()

        class DelayedReply(Bus):
            async def call(self, message):
                if message.member == "Commit":
                    self.calls.append(message)
                    started.set()
                    await release.wait()
                    return SimpleNamespace(
                        message_type=MessageType.METHOD_RETURN,
                        body=["no_service"],
                        sender=":1.12",
                    )
                return await super().call(message)

        tmp_path.chmod(0o700)
        bus = DelayedReply()
        keyboard = Keyboard()
        router = OutputRouter(
            keyboard,
            ibus_factory=lambda: IBusBridge(
                runtime_dir=str(tmp_path),
                client_factory=lambda cap: Client(
                    cap, bus_factory=lambda: bus, owner_verifier=trusted_owner
                ),
            ),
        )
        await router.prepare_task("ibus")
        active = [True]
        deadline = time.monotonic() + 0.15 if mode == "expired" else None
        task = asyncio.create_task(
            router.insert("甲", lambda: active[0], deadline=deadline)
        )
        await started.wait()
        if mode == "predicate":
            active[0] = False
        else:
            await asyncio.sleep(0.2)
        release.set()
        with pytest.raises(OutputRouterError) as error:
            await asyncio.wait_for(task, 0.5)
        assert error.value.code == (
            "expired" if mode == "expired" else "input_cancelled"
        )
        assert not any(m.member == "Cancel" for m in bus.calls)
        assert keyboard.sent == [] and bus.disconnected and not list(tmp_path.iterdir())

    asyncio.run(run())


@pytest.mark.parametrize("mode", ["active", "predicate", "expired"])
def test_ibus_fast_close_cleanup_failure_is_reported_without_masking_stop(
    tmp_path, monkeypatch, mode
):
    import time

    from inkecho.platform import ibus_lifecycle
    from inkecho.platform.ibus import IBusBridge

    async def run():
        class DelayedReply(Bus):
            async def call(self, message):
                if message.member == "Commit":
                    self.calls.append(message)
                    started.set()
                    await release.wait()
                    return SimpleNamespace(
                        message_type=MessageType.METHOD_RETURN,
                        body=["no_service"],
                        sender=":1.12",
                    )
                return await super().call(message)

        tmp_path.chmod(0o700)
        started, release = asyncio.Event(), asyncio.Event()
        bus = DelayedReply()
        keyboard = Keyboard()
        router = OutputRouter(
            keyboard,
            ibus_factory=lambda: IBusBridge(
                runtime_dir=str(tmp_path),
                client_factory=lambda cap: Client(
                    cap, bus_factory=lambda: bus, owner_verifier=trusted_owner
                ),
            ),
        )
        diagnostics = []
        router.set_diagnostic_handler(diagnostics.append)
        await router.prepare_task("ibus")
        caps = router._selected._client._cap

        def fail_unlink(*_args):
            raise OSError("private path and token must not leak")

        monkeypatch.setattr(ibus_lifecycle, "_matching_unlink", fail_unlink)
        active = [True]
        deadline = time.monotonic() + 0.15 if mode == "expired" else None
        task = asyncio.create_task(
            router.insert("甲", lambda: active[0], deadline=deadline)
        )
        await started.wait()
        if mode == "predicate":
            active[0] = False
        elif mode == "expired":
            await asyncio.sleep(0.2)
        release.set()
        with pytest.raises(OutputRouterError) as error:
            await asyncio.wait_for(task, 1)
        expected = {
            "active": "ibus_cleanup_failed",
            "predicate": "input_cancelled",
            "expired": "expired",
        }[mode]
        assert error.value.code == expected
        assert "private path" not in str(error.value)
        assert diagnostics == ["input_cleanup_failed"]
        assert bus.disconnected and keyboard.sent == [] and router.selected is None
        assert caps._fd is None and caps.token == ""

    asyncio.run(run())


def test_ibus_acknowledged_prefix_survives_uncertain_following_commit(tmp_path):
    from inkecho.platform.ibus import IBusBridge

    async def run():
        tmp_path.chmod(0o700)
        bus = Bus()
        bus.outcomes = ["attempted", TimeoutError("synthetic unknown")]
        keyboard = Keyboard()
        router = OutputRouter(
            keyboard,
            ibus_factory=lambda: IBusBridge(
                runtime_dir=str(tmp_path),
                client_factory=lambda cap: Client(
                    cap, bus_factory=lambda: bus, owner_verifier=trusted_owner
                ),
            ),
        )
        await router.prepare_task("ibus")
        with pytest.raises(OutputRouterError, match="ibus_delivery_unknown") as error:
            await router.insert("甲乙丙", lambda: True)
        assert error.value.acknowledged_attempts == 1
        assert keyboard.sent == []
        assert [m.body[1] for m in bus.calls if m.member == "Commit"] == ["甲", "乙"]
        assert bus.disconnected and list(tmp_path.iterdir()) == []

    asyncio.run(run())
