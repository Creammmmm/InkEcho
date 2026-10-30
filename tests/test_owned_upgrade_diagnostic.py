"""Actual direct-owned default selection, no Fcitx handoff or real desktop."""

import asyncio
import time

import pytest
from test_output_router import Keyboard
from test_owned_bounded_protocol import Bus, Cap, async_true, xml

from inkecho.platform.ibus_owned import Client, IBusBridge
from inkecho.platform.ibus_owned_default import DefaultAutoOutputRouter
from inkecho.platform.output_router import OutputRouterError


@pytest.mark.parametrize(
    ("schema", "trusted", "expected"),
    [
        (
            xml(legacy=True)
            .replace("BeginBatch", "Begin")
            .replace("CommitBatch", "Commit")
            .replace('<arg direction="in" type="u"/>', "", 1),
            True,
            "ibus_upgrade_required",
        ),
        (xml(legacy=True), True, "ibus_upgrade_required"),
        (xml(begin="ssud"), True, "input_capability_unknown"),
        (xml(legacy=True), False, "input_capability_unknown"),
    ],
    ids=["legacy-scalar", "legacy-batch", "malformed", "untrusted-owner"],
)
def test_direct_owned_diagnosis_never_authorizes_fallback(schema, trusted, expected):
    async def run():
        keyboard = Keyboard()
        bus = Bus(schema)
        clients, caps = [], []

        async def state():
            return "enabled"

        async def detector():
            return None

        async def owned_probe():
            return ("ibus", ":1.23")

        async def verifier(_):
            return trusted

        def factory():
            def capability(_):
                cap = Cap()
                caps.append(cap)
                return cap

            def client(cap, **options):
                value = Client(
                    cap, bus_factory=lambda: bus, owner_verifier=verifier, **options
                )
                clients.append(value)
                return value

            return IBusBridge(
                runtime_dir="/unused",
                capability_factory=capability,
                client_factory=client,
            )

        router = DefaultAutoOutputRouter(
            keyboard,
            state_probe=state,
            system_detector=detector,
            owned_probe=owned_probe,
            owned_factory=factory,
        )
        await router.prepare_task("auto")
        with pytest.raises(OutputRouterError, match="^" + expected + "$"):
            async with router.output_session():
                await router.insert("X", lambda: True, deadline=time.monotonic() + 1)
        assert keyboard.connects == keyboard.authorizations == 0 and keyboard.sent == []
        assert len(clients) == 1 and bus.disconnected and caps[0].closed
        assert not any(
            member.startswith("Commit") or member.startswith("Begin")
            for member, _, _ in bus.calls
        )
        assert router.acknowledged_attempts == 0
        with pytest.raises(OutputRouterError):
            await router.insert("X", lambda: True)
        assert len(clients) == 1  # no retry or replacement route

    asyncio.run(run())


def test_upgrade_error_does_not_override_cancellation():
    async def run():
        active = True
        keyboard = Keyboard()

        class CancellingBus(Bus):
            async def call(self, message):
                nonlocal active
                reply = await super().call(message)
                if message.member == "Introspect":
                    active = False
                return reply

        bus = CancellingBus(xml(legacy=True))

        async def state():
            return "enabled"

        async def detector():
            return None

        async def probe():
            return ("ibus", ":1.23")

        def factory():
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
            state_probe=state,
            system_detector=detector,
            owned_probe=probe,
            owned_factory=factory,
        )
        await router.prepare_task("auto")
        with pytest.raises(OutputRouterError, match="^input_cancelled$"):
            async with router.output_session():
                await router.insert("X", lambda: active)
        assert bus.disconnected and keyboard.sent == []
        assert not any(member.startswith("Commit") for member, _, _ in bus.calls)

    asyncio.run(run())
