"""Configured explicit bounded route, actual client/bridge with fake D-Bus."""

import asyncio
import time
from dataclasses import replace

import pytest
from test_output_router import Keyboard
from test_owned_bounded_protocol import Bus, Cap, async_true, xml

from inkecho.config import ConfigStore
from inkecho.platform.ibus_owned import Client, IBusBridge
from inkecho.platform.ibus_owned_default import DefaultAutoOutputRouter
from inkecho.platform.output_router import OutputRouterError


def router_for(*, state="enabled", proof=("ibus", ":1.23"), schema=None, bus=None):
    bus = bus or Bus(schema or xml())
    keyboard, calls = Keyboard(), []

    async def state_probe():
        calls.append("state")
        if isinstance(state, Exception):
            raise state
        return state

    async def owned_probe():
        calls.append("probe")
        if isinstance(proof, Exception):
            raise proof
        return proof

    async def forbidden_detector():
        raise AssertionError("explicit bounded mode must not select Fcitx")

    def factory():
        calls.append("factory")
        return IBusBridge(
            runtime_dir="/unused",
            capability_factory=lambda _: Cap(),
            client_factory=lambda cap, **options: Client(
                cap,
                bus_factory=lambda: bus,
                owner_verifier=lambda _: async_true(),
                **options,
            ),
        )

    router = DefaultAutoOutputRouter(
        keyboard,
        state_probe=state_probe,
        owned_probe=owned_probe,
        owned_factory=factory,
        system_detector=forbidden_detector,
    )
    return router, bus, keyboard, calls


def test_explicit_recording_preparation_never_probes_or_pins_target():
    async def run():
        router, bus, keyboard, calls = router_for()
        await router.prepare_task("ibus-owned")
        assert not calls and not bus.calls and keyboard.connects == 0
        with pytest.raises(OutputRouterError, match="ibus_delivery_unknown") as error:
            async with router.output_session():
                assert await router.prepare_stream(lambda: True)
                assert await router.insert("甲", lambda: True) == 1
                assert await router.insert("乙\n", lambda: True) == 2
        assert error.value.dispatch_complete
        assert error.value.acknowledged_attempts == 3
        commits = [body[1] for name, _, body in bus.calls if name == "CommitBounded"]
        assert commits == ["甲", "乙\n"]
        assert bus.disconnected and keyboard.connects == 0 and keyboard.sent == []
        assert calls.count("factory") == 1

    asyncio.run(run())


@pytest.mark.parametrize(
    "state", ["absent", "disabled", "unknown", None, TimeoutError()]
)
def test_installation_uncertainty_stops_without_any_other_route(state):
    async def run():
        router, bus, keyboard, calls = router_for(state=state)
        await router.prepare_task("ibus-owned")
        expected = (
            "ibus_unavailable"
            if state in ("absent", "disabled")
            else "input_capability_unknown"
        )
        with pytest.raises(OutputRouterError, match=expected):
            async with router.output_session():
                await router.insert("X", lambda: True)
        assert "factory" not in calls and not bus.calls
        assert keyboard.connects == 0 and keyboard.sent == []

    asyncio.run(run())


@pytest.mark.parametrize(
    "proof", [None, ("ibus", "invalid"), ("fcitx", ":1.23"), TimeoutError()]
)
def test_no_compatible_target_or_unknown_probe_cannot_fallback(proof):
    async def run():
        router, bus, keyboard, calls = router_for(proof=proof)
        await router.prepare_task("ibus-owned")
        expected = (
            "ibus_target_unavailable" if proof is None else "input_capability_unknown"
        )
        with pytest.raises(OutputRouterError, match=expected):
            async with router.output_session():
                await router.insert("X", lambda: True)
        assert "factory" not in calls and not bus.calls and not keyboard.sent

    asyncio.run(run())


def test_complete_legacy_protocol_requires_upgrade_without_begin_or_replay():
    async def run():
        router, bus, keyboard, calls = router_for(schema=xml(legacy=True))
        await router.prepare_task("ibus-owned")
        with pytest.raises(OutputRouterError, match="ibus_upgrade_required"):
            async with router.output_session():
                await router.insert("X", lambda: True)
        assert not any(name.startswith(("Begin", "Commit")) for name, _, _ in bus.calls)
        assert calls.count("factory") == 1 and bus.disconnected and not keyboard.sent

    asyncio.run(run())


def test_unknown_dispatch_is_terminal_not_replayed():
    async def run():
        class UnknownBus(Bus):
            async def call(self, message):
                reply = await super().call(message)
                if message.member == "CommitBounded":
                    reply.body = ["unknown"]
                return reply

        router, bus, keyboard, calls = router_for(bus=UnknownBus(xml()))
        await router.prepare_task("ibus-owned")
        with pytest.raises(OutputRouterError, match="ibus_delivery_unknown") as error:
            async with router.output_session():
                await router.insert("X", lambda: True)
        assert not error.value.dispatch_complete
        assert sum(name == "CommitBounded" for name, _, _ in bus.calls) == 1
        assert bus.disconnected and not keyboard.sent and calls.count("factory") == 1
        with pytest.raises(OutputRouterError):
            await router.insert("X", lambda: True)
        assert sum(name == "CommitBounded" for name, _, _ in bus.calls) == 1

    asyncio.run(run())


@pytest.mark.parametrize("stop", ["cancel", "expire"])
def test_stop_during_authentication_closes_before_body(stop):
    async def run():
        entered, release = asyncio.Event(), asyncio.Event()

        class WaitingBus(Bus):
            async def call(self, message):
                if message.member == "Introspect":
                    entered.set()
                    await release.wait()
                return await super().call(message)

        router, bus, keyboard, _ = router_for(bus=WaitingBus(xml()))
        await router.prepare_task("ibus-owned")
        active = True
        deadline = time.monotonic() + (0.1 if stop == "expire" else 2)

        async def output():
            async with router.output_session():
                await router.insert("X", lambda: active, deadline=deadline)

        task = asyncio.create_task(output())
        await entered.wait()
        if stop == "cancel":
            active = False
        with pytest.raises(OutputRouterError, match="input_cancelled|expired"):
            await asyncio.wait_for(task, 1)
        assert bus.disconnected and not keyboard.sent
        assert not any(name.startswith("Commit") for name, _, _ in bus.calls)

    asyncio.run(run())


def test_config_persists_new_explicit_choice_without_migrating_old_v2(tmp_path):
    store = ConfigStore(tmp_path)
    store.initialize()
    for method in ["ibus", "ibus-owned", "auto"]:
        store.save_settings(replace(store.load_settings(), output_method=method))
        assert store.load_settings().output_method == method


def test_owner_replacement_between_authentication_and_commit_is_zero_attempt():
    async def run():
        router, bus, keyboard, _ = router_for()
        proofs = iter([("ibus", ":1.23"), ("ibus", ":1.24")])

        async def changing_probe():
            return next(proofs)

        router._owned_probe = changing_probe
        await router.prepare_task("ibus-owned")
        with pytest.raises(OutputRouterError, match="input_capability_unknown"):
            async with router.output_session():
                await router.insert("X", lambda: True)
        assert bus.disconnected and not keyboard.sent
        assert not any(name.startswith("Commit") for name, _, _ in bus.calls)

    asyncio.run(run())


def test_next_auto_task_does_not_retain_explicit_owned_policy():
    async def run():
        router, _, _, calls = router_for()
        await router.prepare_task("ibus-owned")
        assert router._explicit_owned_task
        await router.discard_task()
        await router.prepare_task("auto")
        assert not router._explicit_owned_task and calls == []
        await router.discard_task()

    asyncio.run(run())


def test_post_auth_no_service_stops_without_keyboard_or_replay():
    async def run():
        class GoneTargetBus(Bus):
            async def call(self, message):
                reply = await super().call(message)
                if message.member == "CommitBounded":
                    reply.body = ["no_service"]
                return reply

        router, bus, keyboard, calls = router_for(bus=GoneTargetBus(xml()))
        await router.prepare_task("ibus-owned")
        with pytest.raises(
            OutputRouterError, match="^ibus_target_unavailable$"
        ) as error:
            async with router.output_session():
                await router.insert("X", lambda: True)
        assert error.value.acknowledged_attempts == 0
        assert not error.value.dispatch_complete
        assert sum(name == "CommitBounded" for name, _, _ in bus.calls) == 1
        assert keyboard.connects == keyboard.authorizations == 0 and keyboard.sent == []
        assert bus.disconnected and calls.count("factory") == 1
        with pytest.raises(OutputRouterError):
            await router.insert("X", lambda: True)
        assert calls.count("factory") == 1 and keyboard.sent == []

    asyncio.run(run())


def test_native_then_nonapplicable_target_keeps_partial_unknown_terminal():
    async def run():
        class ChangingTargetBus(Bus):
            async def call(self, message):
                reply = await super().call(message)
                if message.member == "CommitBounded" and message.body[0] > 0:
                    reply.body = ["no_service"]
                return reply

        router, bus, keyboard, calls = router_for(bus=ChangingTargetBus(xml()))
        await router.prepare_task("ibus-owned")
        with pytest.raises(OutputRouterError, match="^ibus_delivery_unknown$") as error:
            async with router.output_session():
                assert await router.insert("A", lambda: True) == 1
                await router.insert("B", lambda: True)
        assert error.value.acknowledged_attempts == 1
        assert not error.value.dispatch_complete
        assert calls.count("factory") == 1 and not keyboard.sent
        assert [body[1] for name, _, body in bus.calls if name == "CommitBounded"] == [
            "A",
            "B",
        ]
        # Switching back cannot resume/replay the failed original output scope.
        with pytest.raises(OutputRouterError):
            await router.insert("B", lambda: True)
        assert sum(name == "CommitBounded" for name, _, _ in bus.calls) == 2

    asyncio.run(run())


def test_target_before_recording_is_not_pinned_and_later_native_target_is_used():
    async def run():
        target = "xwayland"
        targets = []

        class CurrentTargetBus(Bus):
            async def call(self, message):
                if message.member == "CommitBounded":
                    targets.append(target)
                return await super().call(message)

        router, bus, keyboard, calls = router_for(bus=CurrentTargetBus(xml()))

        async def current_probe():
            calls.append("probe")
            return ("ibus", ":1.23") if target.startswith("native") else None

        router._owned_probe = current_probe
        await router.prepare_task("ibus-owned")
        assert calls == []  # no initial xwayland target captured or rejected
        target = "native-a"
        with pytest.raises(OutputRouterError, match="ibus_delivery_unknown") as error:
            async with router.output_session():
                assert await router.insert("A", lambda: True) == 1
                target = "native-b"
                assert await router.insert("B", lambda: True) == 1
        assert error.value.dispatch_complete and targets == ["native-a", "native-b"]
        assert not keyboard.sent

    asyncio.run(run())


def test_explicit_target_diagnostic_is_registered_without_text(tmp_path):
    from inkecho.app import KEYBOARD_LABELS
    from inkecho.logging import CODES, DiagnosticLog

    assert "ibus_target_unavailable" in CODES
    assert "原生 Wayland" in KEYBOARD_LABELS["ibus_target_unavailable"]
    log = DiagnosticLog(tmp_path)
    try:
        log.record("error", "ibus_target_unavailable")
        assert "ibus_target_unavailable" in log.recent()
    finally:
        log.handler.close()


def test_cancellation_observed_with_no_service_still_takes_priority():
    async def run():
        active = True

        class CancelledNoServiceBus(Bus):
            async def call(self, message):
                nonlocal active
                reply = await super().call(message)
                if message.member == "CommitBounded":
                    active = False
                    reply.body = ["no_service"]
                return reply

        router, bus, keyboard, _ = router_for(bus=CancelledNoServiceBus(xml()))
        await router.prepare_task("ibus-owned")
        with pytest.raises(OutputRouterError, match="^input_cancelled$"):
            async with router.output_session():
                await router.insert("X", lambda: active)
        assert bus.disconnected and not keyboard.sent and keyboard.connects == 0
        assert sum(name == "CommitBounded" for name, _, _ in bus.calls) == 1

    asyncio.run(run())


@pytest.mark.parametrize("stop", ["cancel", "expire"])
@pytest.mark.parametrize("probe_failure", ["none", "unknown"])
def test_stop_during_failed_preflight_cleanup_overrides_earlier_target_error(
    stop, probe_failure
):
    async def run():
        router, bus, keyboard, calls = router_for()
        active = True
        deadline = time.monotonic() + 2
        proof_count = 0
        cleanup_started_valid = []
        original_factory = router._owned_factory

        async def changing_probe():
            nonlocal proof_count
            proof_count += 1
            if proof_count == 1:
                return ("ibus", ":1.23")
            if probe_failure == "unknown":
                raise OutputRouterError("input_capability_unknown")
            return None

        def factory():
            bridge = original_factory()
            original_close = bridge.aclose

            async def stop_during_close():
                nonlocal active
                cleanup_started_valid.append(active and time.monotonic() < deadline)
                await original_close()
                if stop == "cancel":
                    active = False
                else:
                    await asyncio.sleep(max(0, deadline - time.monotonic()) + 0.01)

            bridge.aclose = stop_during_close
            return bridge

        router._owned_probe, router._owned_factory = changing_probe, factory
        await router.prepare_task("ibus-owned")
        expected = "input_cancelled" if stop == "cancel" else "expired"
        with pytest.raises(OutputRouterError, match="^" + expected + "$"):
            async with router.output_session():
                await router.insert("X", lambda: active, deadline=deadline)
        assert cleanup_started_valid == [True]
        assert bus.disconnected and calls.count("factory") == 1
        assert not any(name.startswith("Commit") for name, _, _ in bus.calls)
        assert keyboard.connects == keyboard.authorizations == 0 and keyboard.sent == []

    asyncio.run(run())
