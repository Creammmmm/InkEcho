import asyncio
from contextlib import asynccontextmanager

import pytest

from inkecho.platform.fcitx5 import FcitxOutputError
from inkecho.platform.ibus import IBusBridgeError
from inkecho.platform.keyboard import KeyboardError
from inkecho.platform.output_router import (
    OutputRouter,
    OutputRouterError,
    detect_input_framework,
)


class Keyboard:
    def __init__(self):
        self.authorized = False
        self.connects = self.authorizations = self.closes = 0
        self.sent = []

    async def connect(self):
        self.connects += 1

    async def authorize(self, parent_window=""):
        self.authorizations += 1
        self.authorized = True

    @asynccontextmanager
    async def output_session(self):
        yield

    async def insert(self, text, can_continue, **kwargs):
        assert can_continue()
        self.sent.append(text)
        return len(text)

    async def aclose(self):
        self.closes += 1


class Bridge:
    def __init__(self, failure=None):
        self.failure = failure
        self.sent = []
        self.closed = False

    async def connect(self, **_kwargs):
        if self.failure == "unavailable":
            raise FcitxOutputError("unavailable")

    async def insert(self, text, can_continue, **kwargs):
        assert can_continue()
        self.sent.append(text)
        if self.failure:
            raise FcitxOutputError(
                self.failure, uncertain=self.failure == "delivery_unknown"
            )
        return len(text)

    async def aclose(self):
        self.closed = True


@pytest.fixture(autouse=True)
def verified_explicit_bridge(monkeypatch):
    async def owner():
        return ":1.8"

    monkeypatch.setattr(
        "inkecho.platform.output_router.verified_explicit_fcitx_owner", owner
    )


def test_framework_detection_rejects_conflicting_hints():
    assert detect_input_framework({"XMODIFIERS": "@im=fcitx"}) == "fcitx"
    assert detect_input_framework({"QT_IM_MODULE": "ibus"}) == "ibus"
    assert (
        detect_input_framework({"GTK_IM_MODULE": "ibus", "QT_IM_MODULE": "fcitx"})
        is None
    )


def test_explicit_fcitx_is_task_scoped_and_does_not_authorize_keyboard():
    async def run():
        keyboard, bridge = Keyboard(), Bridge()
        router = OutputRouter(
            keyboard, bridge_factory=lambda: bridge, detector=lambda: "fcitx"
        )
        assert await router.prepare_task("fcitx") == "fcitx"
        async with router.output_session():
            assert await router.insert("甲", lambda: True) == 1
            assert await router.insert("乙", lambda: True) == 1
        assert bridge.sent == ["甲", "乙"] and bridge.closed
        assert keyboard.connects == keyboard.authorizations == 0
        assert router.selected is None

    asyncio.run(run())


@pytest.mark.parametrize("owners", [(None,), (":1.8", ":1.9"), (":1.8", None)])
def test_explicit_fcitx_rejects_unverified_or_changed_owner_before_sending(owners):
    async def run():
        keyboard, bridge = Keyboard(), Bridge()
        router = OutputRouter(keyboard, bridge_factory=lambda: bridge)
        remaining = iter(owners)

        async def detect():
            return next(remaining)

        router._explicit_fcitx_detector = detect
        with pytest.raises(OutputRouterError, match="fcitx_unavailable"):
            await router.prepare_task("fcitx")
        assert bridge.closed and bridge.sent == [] and keyboard.sent == []

    asyncio.run(run())


def test_auto_uses_keyboard_without_assuming_a_framework_from_environment():
    async def run():
        keyboard, bridge = Keyboard(), Bridge("unavailable")
        router = OutputRouter(
            keyboard, bridge_factory=lambda: bridge, detector=lambda: "fcitx"
        )
        assert await router.prepare_task() == "keyboard"
        assert not bridge.closed and keyboard.authorizations == 0
        assert await router.insert("甲", lambda: True) == 1
        assert keyboard.sent == ["甲"]

    asyncio.run(run())


def test_auto_selects_at_first_output_and_keeps_backend_across_fragments():
    async def run():
        keyboard, bridge = Keyboard(), Bridge()
        events = []

        async def detect():
            events.append("detect")
            return ("fcitx", ":1.42")

        router = OutputRouter(keyboard, bridge_factory=lambda: bridge)
        router._system_detector = detect
        await router.prepare_task("auto")
        assert keyboard.authorizations == 0 and events == []
        async with router.output_session():
            assert events == []
            assert await router.insert("甲", lambda: True) == 1
            assert await router.insert("乙", lambda: True) == 1
        assert events == ["detect", "detect"]
        assert bridge.sent == ["甲", "乙"] and keyboard.sent == []

    asyncio.run(run())


def test_auto_owner_change_falls_back_before_any_send():
    async def run():
        keyboard, bridge = Keyboard(), Bridge()
        outcomes = iter([("fcitx", ":1.42"), ("fcitx", ":1.43")])

        async def detect():
            return next(outcomes)

        router = OutputRouter(keyboard, bridge_factory=lambda: bridge)
        router._system_detector = detect
        await router.prepare_task("auto")
        assert await router.insert("甲", lambda: True) == 1
        assert bridge.closed and bridge.sent == [] and keyboard.sent == ["甲"]

    asyncio.run(run())


def test_auto_bridge_can_work_when_keyboard_authorization_fails():
    async def run():
        class UnavailableKeyboard(Keyboard):
            async def authorize(self, parent_window=""):
                self.authorizations += 1
                raise KeyboardError("permission_required")

        keyboard, bridge = UnavailableKeyboard(), Bridge()

        async def detect():
            return ("ibus", ":1.9")

        router = OutputRouter(keyboard, ibus_factory=lambda: bridge)
        router._system_detector = detect
        await router.prepare_task("auto")
        assert keyboard.authorizations == 0
        with pytest.raises(OutputRouterError, match="ibus_delivery_unknown"):
            await router.insert("甲", lambda: True)
        assert bridge.sent == ["甲"] and keyboard.sent == []

    asyncio.run(run())


def test_auto_bridge_can_work_when_keyboard_driver_raises_unexpected_error():
    async def run():
        class BrokenKeyboard(Keyboard):
            async def connect(self):
                raise OSError("private driver details")

        keyboard, bridge = BrokenKeyboard(), Bridge()

        async def detect():
            return ("ibus", ":1.9")

        router = OutputRouter(keyboard, ibus_factory=lambda: bridge)
        router._system_detector = detect
        await router.prepare_task("auto")
        with pytest.raises(OutputRouterError, match="ibus_delivery_unknown"):
            await router.insert("甲", lambda: True)
        assert bridge.sent == ["甲"] and keyboard.sent == []

    asyncio.run(run())


def test_auto_reports_keyboard_error_only_if_no_bridge_can_be_selected():
    async def run():
        class UnavailableKeyboard(Keyboard):
            async def authorize(self, parent_window=""):
                raise KeyboardError("permission_required")

        router = OutputRouter(UnavailableKeyboard())

        async def detect():
            return None

        router._system_detector = detect
        await router.prepare_task("auto")
        with pytest.raises(KeyboardError, match="permission_required"):
            await router.insert("甲", lambda: True)

    asyncio.run(run())


def test_auto_ambiguous_bridge_delivery_is_never_replayed():
    async def run():
        keyboard, bridge = Keyboard(), Bridge("delivery_unknown")

        async def detect():
            return ("fcitx", ":1.42")

        router = OutputRouter(keyboard, bridge_factory=lambda: bridge)
        router._system_detector = detect
        await router.prepare_task("auto")
        with pytest.raises(OutputRouterError, match="fcitx_delivery_unknown"):
            await router.insert("甲", lambda: True)
        assert bridge.sent == ["甲"] and keyboard.sent == []

    asyncio.run(run())


@pytest.mark.parametrize("case", ["cancel", "unknown"])
def test_ibus_compatibility_fcitx_route_preserves_stop_and_no_replay(monkeypatch, case):
    from inkecho.platform import framework_detection as detection
    from inkecho.platform.fcitx5_install import FcitxInstaller

    class Bus:
        async def connect(self):
            return self

        def disconnect(self):
            pass

    async def command(*args):
        if args[0].endswith("systemctl"):
            return "XMODIFIERS=@im=ibus\nQT_IM_MODULE=ibus\n"
        return "[('xkb', 'us')]\n"

    async def owner(_bus, _name, **_kwargs):
        return ("fcitx", ":1.42")

    async def live(_owner, _version):
        return True

    monkeypatch.setattr(detection, "MessageBus", Bus)
    monkeypatch.setattr(detection, "_command", command)
    monkeypatch.setattr(detection, "owner_identity", owner)
    monkeypatch.setattr(detection, "_live_fcitx_version_matches", live)
    monkeypatch.setattr(FcitxInstaller, "auto_version", lambda _self: "5.1.19")

    async def run():
        keyboard, bridge = Keyboard(), Bridge("delivery_unknown")
        router = OutputRouter(keyboard, bridge_factory=lambda: bridge)
        router._system_detector = detection.detect_system_framework
        await router.prepare_task("auto")
        with pytest.raises(
            OutputRouterError,
            match="input_cancelled" if case == "cancel" else "fcitx_delivery_unknown",
        ):
            await router.insert("甲", lambda: case != "cancel")
        assert keyboard.sent == []
        assert bridge.sent == ([] if case == "cancel" else ["甲"])

    asyncio.run(run())


def test_auto_fcitx_falls_back_when_no_text_was_committed():
    async def run():
        keyboard = Keyboard()

        class NoTarget(Bridge):
            async def insert(self, _text, _can_continue, **_kwargs):
                raise FcitxOutputError("no_target", accepted=0, unsent_offset=0)

        async def detect():
            return ("fcitx", ":1.42")

        router = OutputRouter(keyboard, bridge_factory=NoTarget)
        router._system_detector = detect
        await router.prepare_task("auto")
        assert await router.insert("甲乙", lambda: True) == 2
        assert keyboard.sent == ["甲乙"]

    asyncio.run(run())


def test_auto_fcitx_does_not_handoff_after_partial_commit():
    async def run():
        keyboard = Keyboard()

        class Partial(Bridge):
            async def insert(self, text, can_continue, **_kwargs):
                self.sent.append(text[:2])
                raise FcitxOutputError("no_target", accepted=2, unsent_offset=2)

        bridge = Partial()

        async def detect():
            return ("fcitx", ":1.42")

        router = OutputRouter(keyboard, bridge_factory=lambda: bridge)
        router._system_detector = detect
        await router.prepare_task("auto")
        with pytest.raises(OutputRouterError, match="partial_input_failed"):
            await router.insert("甲乙丙丁", lambda: True)
        assert bridge.sent == ["甲乙"]
        assert keyboard.sent == []

    asyncio.run(run())


@pytest.mark.parametrize("mode", ["keyboard", "fcitx", "ibus"])
def test_nonstreaming_normalizes_crlf_and_cr_for_all_backends(mode):
    async def run():
        keyboard, bridge = Keyboard(), Bridge()
        router = OutputRouter(
            keyboard, bridge_factory=lambda: bridge, ibus_factory=lambda: bridge
        )
        await router.prepare_task(mode)
        if mode == "ibus":
            with pytest.raises(OutputRouterError, match="ibus_delivery_unknown"):
                await router.insert("甲\r\n乙\r丙", lambda: True)
        else:
            assert await router.insert("甲\r\n乙\r丙", lambda: True) == 5
        assert (keyboard.sent if mode == "keyboard" else bridge.sent) == ["甲\n乙\n丙"]

    asyncio.run(run())


def test_partial_failure_keeps_normalized_prefix_without_handoff():
    async def run():
        keyboard = Keyboard()

        class Partial(Bridge):
            async def insert(self, text, can_continue, **_kwargs):
                assert text == "甲\n乙"
                self.sent.append(text[:2])
                raise FcitxOutputError("no_target", accepted=2, unsent_offset=2)

        bridge = Partial()

        async def detect():
            return ("fcitx", ":1.42")

        router = OutputRouter(keyboard, bridge_factory=lambda: bridge)
        router._system_detector = detect
        await router.prepare_task("auto")
        with pytest.raises(OutputRouterError, match="partial_input_failed"):
            await router.insert("甲\r\n乙", lambda: True)
        assert bridge.sent == ["甲\n"] and keyboard.sent == []

    asyncio.run(run())


@pytest.mark.parametrize("keyboard_failure", ["authorization", "send"])
def test_partial_handoff_failure_reports_prefix_without_text(keyboard_failure):
    async def run():
        class BrokenKeyboard(Keyboard):
            async def authorize(self, parent_window=""):
                if keyboard_failure == "authorization":
                    raise KeyboardError("permission_required")
                self.authorized = True

            async def insert(self, text, can_continue, **_kwargs):
                raise KeyboardError("injection_failed")

        class Partial(Bridge):
            async def insert(self, text, can_continue, **_kwargs):
                raise FcitxOutputError("no_target", accepted=1, unsent_offset=1)

        async def detect():
            return ("fcitx", ":1.42")

        router = OutputRouter(BrokenKeyboard(), bridge_factory=Partial)
        router._system_detector = detect
        await router.prepare_task("auto")
        with pytest.raises(OutputRouterError) as caught:
            await router.insert("private text", lambda: True)
        assert caught.value.code == "partial_input_failed"
        assert "private" not in str(caught.value)

    asyncio.run(run())


def test_auto_fcitx_partial_failure_does_not_replay_prior_fragments():
    async def run():
        keyboard = Keyboard()

        class LaterPartial(Bridge):
            async def insert(self, text, can_continue, **_kwargs):
                if text == "甲":
                    self.sent.append(text)
                    return 1
                self.sent.append(text[:1])
                raise FcitxOutputError("no_target", accepted=2, unsent_offset=1)

        bridge = LaterPartial()

        async def detect():
            return ("fcitx", ":1.42")

        router = OutputRouter(keyboard, bridge_factory=lambda: bridge)
        router._system_detector = detect
        await router.prepare_task("auto")
        with pytest.raises(OutputRouterError, match="partial_input_failed"):
            async with router.output_session():
                assert await router.insert("甲", lambda: True) == 1
                await router.insert("乙丙丁", lambda: True)
        assert bridge.sent == ["甲", "乙"]
        assert keyboard.sent == []

    asyncio.run(run())


@pytest.mark.parametrize(
    "active,expected", [(True, "partial_input_failed"), (False, "input_cancelled")]
)
def test_partial_focus_expiry_reports_failure_or_cancel_without_fallback(
    active, expected
):
    async def run():
        keyboard = Keyboard()

        class Expired(Bridge):
            async def insert(self, _text, _can_continue, **_kwargs):
                raise FcitxOutputError("expired", accepted=1)

        async def detect():
            return ("fcitx", ":1.42")

        router = OutputRouter(keyboard, bridge_factory=Expired)
        router._system_detector = detect
        await router.prepare_task("auto")
        # Select the bridge while active, then model expiry racing cancellation.
        with pytest.raises(OutputRouterError, match=expected):
            async with router.output_session():
                await router._choose_auto()
                await router.insert("乙", lambda: active)
        assert keyboard.sent == []

    asyncio.run(run())


def test_auto_fcitx_no_target_does_not_handoff_after_cancel():
    async def run():
        keyboard = Keyboard()
        active = [True]

        class Cancelled(Bridge):
            async def insert(self, text, can_continue, **_kwargs):
                active[0] = False
                raise FcitxOutputError("no_target", unsent_offset=0)

        bridge = Cancelled()

        async def detect():
            return ("fcitx", ":1.42")

        router = OutputRouter(keyboard, bridge_factory=lambda: bridge)
        router._system_detector = detect
        await router.prepare_task("auto")
        with pytest.raises(OutputRouterError, match="input_cancelled"):
            await router.insert("甲", lambda: active[0])
        assert keyboard.sent == []

    asyncio.run(run())


def test_auto_fcitx_no_target_without_verified_offset_never_hands_off():
    async def run():
        keyboard, bridge = Keyboard(), Bridge("no_target")

        async def detect():
            return ("fcitx", ":1.42")

        router = OutputRouter(keyboard, bridge_factory=lambda: bridge)
        router._system_detector = detect
        await router.prepare_task("auto")
        with pytest.raises(OutputRouterError, match="fcitx_no_target"):
            await router.insert("甲", lambda: True)
        assert keyboard.sent == []

    asyncio.run(run())


def test_auto_fcitx_uncertain_result_never_hands_off():
    async def run():
        keyboard = Keyboard()

        class Uncertain(Bridge):
            async def insert(self, text, can_continue, **_kwargs):
                raise FcitxOutputError("no_target", uncertain=True, unsent_offset=0)

        bridge = Uncertain()

        async def detect():
            return ("fcitx", ":1.42")

        router = OutputRouter(keyboard, bridge_factory=lambda: bridge)
        router._system_detector = detect
        await router.prepare_task("auto")
        with pytest.raises(OutputRouterError, match="fcitx_no_target"):
            await router.insert("甲", lambda: True)
        assert keyboard.sent == []

    asyncio.run(run())


def test_auto_keeps_session_but_does_not_lock_recording_focus():
    async def run():
        keyboard = Keyboard()
        focus = ["recording-window"]

        class FocusBridge(Bridge):
            async def insert(self, text, can_continue, **_kwargs):
                self.sent.append((focus[0], text))
                return len(text)

        bridge = FocusBridge()

        async def detect():
            return ("ibus", ":1.9")

        router = OutputRouter(keyboard, ibus_factory=lambda: bridge)
        router._system_detector = detect
        await router.prepare_task("auto")
        focus[0] = "first-output-window"
        with pytest.raises(OutputRouterError, match="ibus_delivery_unknown"):
            async with router.output_session():
                await router.insert("甲", lambda: True)
                focus[0] = "second-output-window"
                await router.insert("乙", lambda: True)
        assert bridge.sent == [
            ("first-output-window", "甲"),
            ("second-output-window", "乙"),
        ]

    asyncio.run(run())


def test_authorization_notice_only_when_keyboard_requires_authorization():
    async def run():
        keyboard, bridge = Keyboard(), Bridge()
        notices = []
        router = OutputRouter(
            keyboard, bridge_factory=lambda: bridge, detector=lambda: "fcitx"
        )
        await router.prepare_task(
            "fcitx", on_keyboard_authorization=lambda: notices.append(True)
        )
        assert notices == []
        await router.discard_task()
        await router.prepare_task(
            "keyboard", on_keyboard_authorization=lambda: notices.append(True)
        )
        assert notices == [True]
        await router.discard_task()
        await router.prepare_task(
            "keyboard", on_keyboard_authorization=lambda: notices.append(True)
        )
        assert notices == [True]
        await router.discard_task()

    asyncio.run(run())


@pytest.mark.parametrize("failure", ["no_target", "delivery_unknown", "cancelled"])
def test_input_failure_never_switches_or_replays_after_send(failure):
    async def run():
        keyboard, bridge = Keyboard(), Bridge(failure)
        router = OutputRouter(
            keyboard, bridge_factory=lambda: bridge, detector=lambda: "fcitx"
        )
        await router.prepare_task("fcitx")
        with pytest.raises(OutputRouterError) as caught:
            async with router.output_session():
                await router.insert("甲", lambda: True)
        assert caught.value.code == "fcitx_" + failure
        assert bridge.sent == ["甲"] and bridge.closed
        assert keyboard.sent == [] and keyboard.authorizations == 0

    asyncio.run(run())


def test_first_fragment_success_later_failure_never_replays():
    async def run():
        keyboard, bridge = Keyboard(), Bridge()
        router = OutputRouter(
            keyboard, bridge_factory=lambda: bridge, detector=lambda: "fcitx"
        )
        await router.prepare_task("fcitx")
        with pytest.raises(OutputRouterError):
            async with router.output_session():
                await router.insert("甲", lambda: True)
                bridge.failure = "no_target"
                await router.insert("乙", lambda: True)
        assert bridge.sent == ["甲", "乙"] and not keyboard.sent

    asyncio.run(run())


def test_explicit_ibus_is_task_scoped_without_keyboard_authorization():
    async def run():
        keyboard, bridge = Keyboard(), Bridge()
        router = OutputRouter(keyboard, ibus_factory=lambda: bridge)
        assert await router.prepare_task("ibus") == "ibus"
        with pytest.raises(OutputRouterError, match="ibus_delivery_unknown"):
            async with router.output_session():
                assert await router.insert("甲", lambda: True) == 1
                assert await router.insert("乙", lambda: True) == 1
        assert bridge.sent == ["甲", "乙"] and bridge.closed
        assert keyboard.connects == keyboard.authorizations == 0

    asyncio.run(run())


def test_ibus_ambiguous_output_does_not_switch_to_keyboard():
    class AmbiguousIBus(Bridge):
        async def insert(self, text, can_continue, **kwargs):
            self.sent.append(text)
            raise IBusBridgeError("delivery_unknown")

    async def run():
        keyboard, bridge = Keyboard(), AmbiguousIBus()
        router = OutputRouter(keyboard, ibus_factory=lambda: bridge)
        await router.prepare_task("ibus")
        with pytest.raises(OutputRouterError, match="ibus_delivery_unknown"):
            await router.insert("甲", lambda: True)
        assert bridge.sent == ["甲"] and bridge.closed
        assert keyboard.sent == [] and keyboard.authorizations == 0

    asyncio.run(run())


@pytest.mark.parametrize(
    "mode,expected", [("fcitx", "fcitx_unavailable"), ("ibus", "ibus_unavailable")]
)
def test_explicit_unavailable_is_reported_without_fallback(mode, expected):
    async def run():
        keyboard = Keyboard()

        class IBusUnavailable(Bridge):
            async def connect(self):
                raise IBusBridgeError("unavailable")

        router = OutputRouter(
            keyboard,
            bridge_factory=lambda: Bridge("unavailable"),
            ibus_factory=IBusUnavailable,
        )
        with pytest.raises(OutputRouterError) as caught:
            await router.prepare_task(mode)
        assert caught.value.code == expected
        assert keyboard.connects == keyboard.authorizations == 0

    asyncio.run(run())


@pytest.mark.parametrize("mode", ["fcitx", "ibus"])
@pytest.mark.parametrize(
    "code,expected",
    [
        ("authorization_failed", "authorization_failed"),
        ("permission_denied", "permission_denied"),
        ("untrusted_owner", "untrusted_owner"),
        ("private sensitive text", "unavailable"),
    ],
)
def test_prepare_preserves_only_safe_error_categories(mode, code, expected):
    async def run():
        keyboard = Keyboard()

        class Failed(Bridge):
            async def connect(self, **_kwargs):
                error = FcitxOutputError if mode == "fcitx" else IBusBridgeError
                raise error(code)

        bridge = Failed()
        router = OutputRouter(
            keyboard, bridge_factory=lambda: bridge, ibus_factory=lambda: bridge
        )
        with pytest.raises(OutputRouterError) as caught:
            await router.prepare_task(mode)
        assert caught.value.code == f"{mode}_{expected}"
        assert "private sensitive text" not in str(caught.value)
        assert bridge.closed and keyboard.connects == keyboard.authorizations == 0

    asyncio.run(run())


def test_cancelled_task_discards_bridge_and_next_task_redetects():
    async def run():
        keyboard, bridge = Keyboard(), Bridge()
        router = OutputRouter(keyboard, bridge_factory=lambda: bridge)
        assert await router.prepare_task("fcitx") == "fcitx"
        await router.discard_task()
        assert bridge.closed
        assert await router.prepare_task() == "keyboard"
        assert keyboard.authorizations == 0
        await router.discard_task()

    asyncio.run(run())


def test_caught_error_poisoning_blocks_further_fragments():
    async def run():
        keyboard, bridge = Keyboard(), Bridge("no_target")
        router = OutputRouter(
            keyboard, bridge_factory=lambda: bridge, detector=lambda: "fcitx"
        )
        await router.prepare_task("fcitx")
        with pytest.raises(OutputRouterError, match="output_failed"):
            async with router.output_session():
                with pytest.raises(OutputRouterError, match="fcitx_no_target"):
                    await router.insert("甲", lambda: True)
                with pytest.raises(OutputRouterError, match="output_failed"):
                    await router.insert("乙", lambda: True)
        assert bridge.sent == ["甲"] and not keyboard.sent

    asyncio.run(run())


def test_close_cancels_preparation_and_closes_bridge():
    async def run():
        entered = asyncio.Event()

        class SlowBridge(Bridge):
            async def connect(self, **_kwargs):
                entered.set()
                await asyncio.Event().wait()

        keyboard, bridge = Keyboard(), SlowBridge()
        router = OutputRouter(
            keyboard, bridge_factory=lambda: bridge, detector=lambda: "fcitx"
        )
        preparing = asyncio.create_task(router.prepare_task("fcitx"))
        await entered.wait()
        with pytest.raises(OutputRouterError, match="busy"):
            await router.prepare_task()
        await router.aclose()
        assert preparing.cancelled() and bridge.closed and keyboard.closes == 1

    asyncio.run(run())


def test_lazy_auto_fcitx_does_not_request_keyboard_authorization():
    async def run():
        keyboard, bridge = Keyboard(), Bridge()
        notices = []
        router = OutputRouter(keyboard, bridge_factory=lambda: bridge)

        async def detect():
            return ("fcitx", ":1.42")

        router._system_detector = detect
        await router.prepare_task(
            "auto", on_keyboard_authorization=lambda: notices.append(True)
        )
        assert (keyboard.connects, keyboard.authorizations, notices) == (0, 0, [])
        assert await router.insert("甲", lambda: True) == 1
        assert (keyboard.connects, keyboard.authorizations, notices) == (0, 0, [])

    asyncio.run(run())


def test_lazy_no_target_falls_back_after_authorization():
    async def run():
        class NoTarget(Bridge):
            async def insert(self, *args, **kwargs):
                raise FcitxOutputError("no_target", accepted=0, unsent_offset=0)

        keyboard, bridge = Keyboard(), NoTarget()
        notices = []
        router = OutputRouter(keyboard, bridge_factory=lambda: bridge)

        async def detect():
            return ("fcitx", ":1.42")

        router._system_detector = detect
        await router.prepare_task(
            "auto", "parent", on_keyboard_authorization=lambda: notices.append(True)
        )
        assert await router.insert("甲", lambda: True) == 1
        assert bridge.closed and notices == [True] and keyboard.sent == ["甲"]

    asyncio.run(run())


def test_lazy_authorization_failure_never_sends():
    async def run():
        class Denied(Keyboard):
            async def authorize(self, parent_window=""):
                raise KeyboardError("permission_required")

        keyboard = Denied()
        router = OutputRouter(keyboard)

        async def detect():
            return None

        router._system_detector = detect
        await router.prepare_task("auto")
        with pytest.raises(KeyboardError, match="permission_required"):
            await router.insert("甲", lambda: True)
        assert keyboard.sent == []

    asyncio.run(run())


def test_lazy_cancel_during_authorization_never_sends():
    async def run():
        started = asyncio.Event()

        class Pending(Keyboard):
            async def authorize(self, parent_window=""):
                started.set()
                await asyncio.Event().wait()

        keyboard = Pending()
        router = OutputRouter(keyboard)

        async def detect():
            return None

        router._system_detector = detect
        await router.prepare_task("auto")
        task = asyncio.create_task(router.insert("甲", lambda: True))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert keyboard.sent == []

    asyncio.run(run())


@pytest.mark.parametrize("expired", [True, False])
def test_lazy_authorization_wait_stops_for_expiry_or_cancel(expired):
    async def run():
        import time

        started = asyncio.Event()
        cancelled = asyncio.Event()
        active = [True]

        class Pending(Keyboard):
            async def authorize(self, parent_window=""):
                started.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    cancelled.set()

            @asynccontextmanager
            async def output_session(self):
                raise AssertionError("must not open after cancellation")
                yield

        keyboard = Pending()
        router = OutputRouter(keyboard)

        async def detect():
            return None

        router._system_detector = detect
        await router.prepare_task("auto")
        deadline = time.monotonic() + 0.1 if expired else None
        task = asyncio.create_task(
            router.insert("甲", lambda: active[0], deadline=deadline)
        )
        await started.wait()
        if not expired:
            active[0] = False
        with pytest.raises(
            OutputRouterError, match="expired" if expired else "input_cancelled"
        ):
            await asyncio.wait_for(task, 1)
        assert cancelled.is_set() and keyboard.sent == []
        assert router.selected is None

    asyncio.run(run())


def test_lazy_callback_and_parent_are_task_scoped():
    async def run():
        class TrackingKeyboard(Keyboard):
            def __init__(self):
                super().__init__()
                self.parents = []

            async def authorize(self, parent_window=""):
                self.parents.append(parent_window)
                self.authorizations += 1
                self.authorized = True

        keyboard = TrackingKeyboard()
        router = OutputRouter(keyboard)
        calls = []

        async def detect():
            return None

        router._system_detector = detect
        await router.prepare_task(
            "auto", "old", on_keyboard_authorization=lambda: calls.append("old")
        )
        await router.discard_task()
        await router.prepare_task(
            "auto", "new", on_keyboard_authorization=lambda: calls.append("new")
        )
        await router.insert("甲", lambda: True)
        assert calls == ["new"] and keyboard.parents == ["new"]
        assert router._keyboard_notice is None and router._keyboard_parent == ""

    asyncio.run(run())


def test_lazy_connect_error_propagates_without_delivery():
    async def run():
        class Broken(Keyboard):
            async def connect(self):
                raise KeyboardError("display_unavailable")

        keyboard = Broken()
        router = OutputRouter(keyboard)

        async def detect():
            return None

        router._system_detector = detect
        await router.prepare_task("auto")
        with pytest.raises(KeyboardError, match="display_unavailable"):
            await router.insert("甲", lambda: True)
        assert keyboard.sent == [] and router.selected is None

    asyncio.run(run())


def test_lazy_auto_unexpected_keyboard_error_is_sanitized():
    async def run():
        class Broken(Keyboard):
            async def connect(self):
                raise OSError("private driver details")

        keyboard = Broken()
        router = OutputRouter(keyboard)

        async def detect():
            return None

        router._system_detector = detect
        await router.prepare_task("auto")
        with pytest.raises(KeyboardError, match="display_unavailable") as captured:
            await router.insert("甲", lambda: True)
        assert "private driver details" not in str(captured.value)
        assert keyboard.sent == [] and router.selected is None

    asyncio.run(run())


@pytest.mark.parametrize("phase", ["first_detect", "connect", "recheck"])
@pytest.mark.parametrize("expired", [True, False])
def test_auto_preflight_obeys_task_deadline_and_cancel(phase, expired):
    async def run():
        import time

        started = asyncio.Event()
        released = asyncio.Event()
        active = [True]
        calls = 0
        keyboard, bridge = Keyboard(), Bridge()

        async def blocked():
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                released.set()

        async def detect():
            nonlocal calls
            calls += 1
            if phase == "first_detect" or (phase == "recheck" and calls == 2):
                await blocked()
            return ("fcitx", ":1.8")

        if phase == "connect":

            async def connect(**_kwargs):
                await blocked()

            bridge.connect = connect
        router = OutputRouter(keyboard, bridge_factory=lambda: bridge)
        router._system_detector = detect
        await router.prepare_task("auto")
        deadline = time.monotonic() + 0.12 if expired else None
        task = asyncio.create_task(
            router.insert("甲", lambda: active[0], deadline=deadline)
        )
        await asyncio.wait_for(started.wait(), 0.5)
        if not expired:
            active[0] = False
        with pytest.raises(
            OutputRouterError, match="expired" if expired else "input_cancelled"
        ):
            await asyncio.wait_for(task, 0.5)
        assert released.is_set()
        assert keyboard.sent == bridge.sent == []
        assert keyboard.connects == 0
        assert router.selected is None
        if phase != "first_detect":
            assert bridge.closed

    asyncio.run(run())


def test_auto_expired_recheck_aborts_unsent_bridge_preflight():
    async def run():
        import time

        class Tracked(Bridge):
            def __init__(self):
                super().__init__()
                self.aborted = False

            async def abort_preflight(self):
                self.aborted = True
                self.closed = True

            async def aclose(self):
                raise AssertionError("slow normal close is not preflight abort")

        keyboard, bridge = Keyboard(), Tracked()
        router = OutputRouter(keyboard, bridge_factory=lambda: bridge)
        calls = 0

        async def detect():
            nonlocal calls
            calls += 1
            if calls == 2:
                await asyncio.Event().wait()
            return ("fcitx", ":1.8")

        router._system_detector = detect
        await router.prepare_task("auto")
        with pytest.raises(OutputRouterError, match="expired"):
            await asyncio.wait_for(
                router.insert("甲", lambda: True, deadline=time.monotonic() + 0.1), 0.5
            )
        assert bridge.aborted and keyboard.sent == bridge.sent == []

    asyncio.run(run())


def test_auto_cancelled_recheck_aborts_unsent_bridge_preflight():
    async def run():
        class Tracked(Bridge):
            def __init__(self):
                super().__init__()
                self.aborted = False

            async def abort_preflight(self):
                self.aborted = True
                self.closed = True

            async def aclose(self):
                raise AssertionError("normal close should not run in preflight")

        keyboard, bridge = Keyboard(), Tracked()
        router = OutputRouter(keyboard, bridge_factory=lambda: bridge)
        second_call = asyncio.Event()
        calls = 0

        async def detect():
            nonlocal calls
            calls += 1
            if calls == 2:
                second_call.set()
                await asyncio.Event().wait()
            return ("fcitx", ":1.8")

        router._system_detector = detect
        await router.prepare_task("auto")
        task = asyncio.create_task(router.insert("甲", lambda: True))
        await second_call.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert bridge.aborted and keyboard.sent == bridge.sent == []

    asyncio.run(run())


@pytest.mark.parametrize(
    "reason", ["owner_missing", "owner_changed", "detect_error", "connect_error"]
)
def test_auto_failed_preflight_aborts_unsent_bridge_before_keyboard_fallback(reason):
    async def run():
        class Tracked(Bridge):
            def __init__(self):
                super().__init__()
                self.aborted = False

            async def connect(self, **_kwargs):
                if reason == "connect_error":
                    raise FcitxOutputError("unavailable")

            async def abort_preflight(self):
                self.aborted = True
                self.closed = True

            async def aclose(self):
                raise AssertionError("unsent preflight must not wait for remote Cancel")

        keyboard, bridge = Keyboard(), Tracked()
        router = OutputRouter(keyboard, bridge_factory=lambda: bridge)
        calls = 0

        async def detect():
            nonlocal calls
            calls += 1
            if calls == 2:
                if reason == "owner_missing":
                    return None
                if reason == "owner_changed":
                    return ("fcitx", ":1.9")
                if reason == "detect_error":
                    raise OSError("test-only failure")
            return ("fcitx", ":1.8")

        router._system_detector = detect
        await router.prepare_task("auto")
        assert await router.insert("甲", lambda: True) == 1
        assert bridge.aborted and bridge.sent == [] and keyboard.sent == ["甲"]

    asyncio.run(run())


@pytest.mark.parametrize("mode", ["task_cancel", "predicate", "expired"])
def test_preflight_cleanup_error_preserves_stop_and_reports(mode):
    async def run():
        import time

        class BrokenCleanup(Bridge):
            async def abort_preflight(self):
                self.closed = True
                raise FcitxOutputError("cleanup_failed")

        keyboard, bridge = Keyboard(), BrokenCleanup()
        router = OutputRouter(keyboard, bridge_factory=lambda: bridge)
        reports = []
        router._diagnostic_handler = reports.append
        active = [True]
        started = asyncio.Event()
        calls = 0

        async def detect():
            nonlocal calls
            calls += 1
            if calls == 2:
                started.set()
                await asyncio.Event().wait()
            return ("fcitx", ":1.8")

        router._system_detector = detect
        await router.prepare_task("auto")
        deadline = time.monotonic() + 0.12 if mode == "expired" else None
        task = asyncio.create_task(
            router.insert("甲", lambda: active[0], deadline=deadline)
        )
        await started.wait()
        if mode == "task_cancel":
            task.cancel()
        elif mode == "predicate":
            active[0] = False
        expected = (
            asyncio.CancelledError if mode == "task_cancel" else OutputRouterError
        )
        with pytest.raises(expected) as caught:
            await asyncio.wait_for(task, 1)
        if mode != "task_cancel":
            assert caught.value.code == (
                "expired" if mode == "expired" else "input_cancelled"
            )
        assert reports == ["input_cleanup_failed"]
        assert bridge.closed and bridge.sent == keyboard.sent == []
        assert router.selected is None

    asyncio.run(run())


def test_successful_auto_fcitx_next_task_redetects_new_owner():
    async def run():
        class OwnedBridge(Bridge):
            async def connect(self, *, expected_owner):
                self.owner = expected_owner

        bridges = []

        def create_bridge():
            bridge = OwnedBridge()
            bridges.append(bridge)
            return bridge

        keyboard = Keyboard()
        router = OutputRouter(keyboard, bridge_factory=create_bridge)
        current = [":1.42"]

        async def detect():
            return ("fcitx", current[0])

        router._system_detector = detect
        await router.prepare_task("auto")
        assert await router.insert("甲", lambda: True) == 1
        assert bridges[0].owner == ":1.42"
        assert bridges[0].sent == ["甲"] and bridges[0].closed
        current[0] = ":1.43"
        await router.prepare_task("auto")
        assert await router.insert("乙", lambda: True) == 1
        assert bridges[1].owner == ":1.43"
        assert bridges[1].sent == ["乙"] and bridges[1].closed
        assert keyboard.sent == [] and router.selected is None

    asyncio.run(run())


def test_unconfirmed_ibus_result_does_not_contaminate_next_keyboard_task():
    async def run():
        keyboard, bridge = Keyboard(), Bridge()
        router = OutputRouter(keyboard, ibus_factory=lambda: bridge)
        await router.prepare_task("ibus")
        with pytest.raises(OutputRouterError, match="ibus_delivery_unknown"):
            await router.insert("甲", lambda: True)
        assert bridge.sent == ["甲"] and bridge.closed
        assert keyboard.sent == [] and router.selected is None
        await router.prepare_task("keyboard")
        assert await router.insert("乙", lambda: True) == 1
        assert keyboard.sent == ["乙"] and router.selected is None

    asyncio.run(run())


@pytest.mark.parametrize("accepted,uncertain", [(2, False), (2, True), (0, True)])
def test_fcitx_error_preserves_acknowledged_attempt_count(accepted, uncertain):
    async def run():
        class Partial(Bridge):
            async def insert(self, *_args, **_kwargs):
                raise FcitxOutputError(
                    "delivery_unknown" if uncertain else "owner_changed",
                    accepted=accepted,
                    uncertain=uncertain,
                )

        keyboard, bridge = Keyboard(), Partial()
        router = OutputRouter(keyboard, bridge_factory=lambda: bridge)

        async def detect():
            return ("fcitx", ":1.42")

        router._system_detector = detect
        await router.prepare_task("auto")
        with pytest.raises(OutputRouterError) as error:
            await router.insert("甲乙丙", lambda: True)
        assert error.value.acknowledged_attempts == accepted
        assert keyboard.sent == [] and bridge.closed

    asyncio.run(run())


def test_receiver_feedback_never_treats_ime_receipt_as_frame_signal():
    async def run():
        keyboard = type(
            "KeyboardStatus", (), {"receiver_feedback_status": "available"}
        )()
        router = OutputRouter(keyboard)
        assert router.receiver_feedback_status == "not_checked"
        router._owner = asyncio.current_task()
        for method in ("fcitx", "ibus"):
            router._kind = method
            assert router.receiver_feedback_status == "unsupported"
        router._kind = "keyboard"
        assert router.receiver_feedback_status == "available"
        router._owner = None
        assert router.receiver_feedback_status == "not_checked"

    asyncio.run(run())
