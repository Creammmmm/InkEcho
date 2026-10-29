"""Offline policy tests; live GNOME46 evidence is recorded separately."""

import asyncio
from contextlib import asynccontextmanager

import pytest

from inkecho.platform.fcitx5 import FcitxOutputError
from inkecho.platform.ibus import IBusBridgeError
from inkecho.platform.ibus_owned_default import DefaultAutoOutputRouter
from inkecho.platform.output_router import OutputRouterError


class Keyboard:
    authorized = True

    async def connect(self):
        pass

    async def aclose(self):
        pass

    @asynccontextmanager
    async def output_session(self):
        yield

    async def insert(self, *args, **kwargs):
        raise AssertionError("keyboard bypass")


class Fcitx:
    def __init__(self, *, accepted=0, uncertain=False, code="no_target"):
        self._accepted = accepted
        self.uncertain = uncertain
        self.code = code
        self.closed = 0

    async def connect(self, **kwargs):
        pass

    async def aclose(self):
        self.closed += 1

    async def insert(self, *args, **kwargs):
        raise FcitxOutputError(
            self.code,
            accepted=self._accepted,
            uncertain=self.uncertain,
            unsent_offset=0,
        )


class Owned:
    def __init__(self, failure=None):
        self.sent = []
        self.closed = 0
        self.owner = None
        self.failure = failure

    async def connect(self, expected_owner=None):
        self.owner = expected_owner

    async def aclose(self):
        self.closed += 1

    async def insert(self, text, active, **kwargs):
        if not active():
            raise IBusBridgeError("cancelled")
        if self.failure:
            raise IBusBridgeError(self.failure)
        self.sent.append(text)
        return len(text)


@pytest.mark.parametrize(
    "case",
    [
        "normal",
        "preedit",
        "cancel_probe",
        "task_cancel",
        "expired",
        "fc_owner",
        "owned_owner",
        "disabled",
        "state_error",
        "no_proof",
        "unknown",
        "accepted",
        "uncertain",
        "ambiguous",
        "cross_fragment",
    ],
)
def test_only_enabled_authenticated_zero_task_may_handoff(case):
    async def run():
        active = True
        states = 0
        detects = 0
        probes = 0
        fc = Fcitx(
            accepted=1 if case == "accepted" else 0,
            uncertain=case == "uncertain",
            code="ambiguous_target" if case == "ambiguous" else "no_target",
        )
        owned = Owned("delivery_unknown" if case == "preedit" else None)

        async def state():
            nonlocal states
            states += 1
            if case == "unknown":
                return "unknown"
            if states > 1 and case == "disabled":
                return "disabled"
            if states > 1 and case == "state_error":
                raise OutputRouterError("input_capability_unknown")
            return "enabled"

        async def detect():
            nonlocal detects
            detects += 1
            return ("fcitx", ":1.9" if case == "fc_owner" and detects > 3 else ":1.8")

        async def probe():
            nonlocal probes, active
            probes += 1
            if case == "cancel_probe":
                active = False
            if case == "task_cancel":
                raise asyncio.CancelledError
            if case == "no_proof":
                return None
            return (
                "ibus",
                ":1.19" if case == "owned_owner" and probes > 1 else ":1.17",
            )

        router = DefaultAutoOutputRouter(
            Keyboard(),
            state_probe=state,
            system_detector=detect,
            owned_probe=probe,
            bridge_factory=lambda: fc,
            owned_factory=lambda: owned,
        )
        await router.prepare_task("auto")
        if case == "cross_fragment":

            async def fragment(text, active, **kwargs):
                if text == "先":
                    fc._accepted += 1
                    return 1
                raise FcitxOutputError("no_target", accepted=0, unsent_offset=0)

            fc.insert = fragment
        with pytest.raises((OutputRouterError, asyncio.CancelledError)):
            async with router.output_session():
                if case == "cross_fragment":
                    assert await router.insert("先", lambda: active) == 1
                await router.insert(
                    "甲", lambda: active, deadline=0 if case == "expired" else None
                )
        assert owned.sent == (["甲"] if case == "normal" else [])
        if case == "normal":
            assert owned.owner == ":1.17" and fc.closed
        if case in {
            "unknown",
            "accepted",
            "uncertain",
            "ambiguous",
            "cross_fragment",
            "expired",
        }:
            assert probes == 0

    asyncio.run(run())


@pytest.mark.parametrize("failure", ["cleanup", "cancel_cleanup", "task_cancel"])
def test_handoff_closes_fcitx_once_and_preserves_stop(failure):
    async def run():
        active = True
        diagnostics = []

        class BrokenClose(Fcitx):
            async def aclose(self):
                nonlocal active
                self.closed += 1
                if failure == "cancel_cleanup":
                    active = False
                if failure == "task_cancel":
                    raise asyncio.CancelledError
                raise FcitxOutputError("cleanup_failed")

        async def enabled():
            return "enabled"

        async def detector():
            return ("fcitx", ":1.8")

        async def proof():
            return ("ibus", ":1.17")

        previous, owned = BrokenClose(), Owned()
        router = DefaultAutoOutputRouter(
            Keyboard(),
            state_probe=enabled,
            system_detector=detector,
            owned_probe=proof,
            bridge_factory=lambda: previous,
            owned_factory=lambda: owned,
        )
        router.set_diagnostic_handler(diagnostics.append)
        await router.prepare_task("auto")
        if failure == "task_cancel":
            with pytest.raises(asyncio.CancelledError):
                async with router.output_session():
                    await router.insert("甲", lambda: active)
        else:
            expected = (
                "input_cleanup_failed" if failure == "cleanup" else "input_cancelled"
            )
            with pytest.raises(OutputRouterError, match=expected):
                async with router.output_session():
                    await router.insert("甲", lambda: active)
            assert diagnostics == ["input_cleanup_failed"]
        assert previous.closed == 1 and owned.closed == 1
        assert owned.sent == [] and router.selected is None

    asyncio.run(run())


def test_handoff_owned_no_service_never_bypasses_enabled_guard():
    async def run():
        async def enabled():
            return "enabled"

        async def detector():
            return ("fcitx", ":1.8")

        async def proof():
            return ("ibus", ":1.17")

        previous, owned = Fcitx(), Owned("no_service")
        router = DefaultAutoOutputRouter(
            Keyboard(),
            state_probe=enabled,
            system_detector=detector,
            owned_probe=proof,
            bridge_factory=lambda: previous,
            owned_factory=lambda: owned,
        )
        await router.prepare_task("auto")
        with pytest.raises(OutputRouterError, match="input_capability_unknown"):
            async with router.output_session():
                await router.insert("甲", lambda: True)
        assert not owned.sent and previous.closed == 1 and owned.closed == 1

    asyncio.run(run())


@pytest.mark.parametrize("stage", ["connect", "insert"])
@pytest.mark.parametrize("code", ["untrusted_owner", "no_service", "not_ready"])
def test_handoff_normalizes_owned_failures_to_registered_diagnostic(stage, code):
    from inkecho.logging import CODES

    async def run():
        class Failure(Owned):
            async def connect(self, expected_owner=None):
                if stage == "connect":
                    raise IBusBridgeError(code)
                await super().connect(expected_owner)

            async def insert(self, *args, **kwargs):
                raise IBusBridgeError(code)

        async def enabled():
            return "enabled"

        async def detector():
            return ("fcitx", ":1.8")

        async def proof():
            return ("ibus", ":1.17")

        owned = Failure()
        router = DefaultAutoOutputRouter(
            Keyboard(),
            state_probe=enabled,
            system_detector=detector,
            owned_probe=proof,
            bridge_factory=Fcitx,
            owned_factory=lambda: owned,
        )
        await router.prepare_task("auto")
        with pytest.raises(OutputRouterError) as failure:
            async with router.output_session():
                await router.insert("甲", lambda: True)
        assert failure.value.code in CODES
        assert failure.value.code == (
            "ibus_untrusted_owner"
            if code == "untrusted_owner"
            else "input_capability_unknown"
        )
        assert not owned.sent and owned.closed == 1

    asyncio.run(run())


def test_owned_connect_failure_survives_previous_cleanup_failure():
    async def run():
        diagnostics = []

        class BrokenClose(Fcitx):
            async def aclose(self):
                self.closed += 1
                raise FcitxOutputError("cleanup_failed")

        class RejectedConnect(Owned):
            async def connect(self, **kwargs):
                raise IBusBridgeError("untrusted_owner")

        async def enabled():
            return "enabled"

        async def detector():
            return ("fcitx", ":1.8")

        async def proof():
            return ("ibus", ":1.17")

        previous, owned = BrokenClose(), RejectedConnect()
        router = DefaultAutoOutputRouter(
            Keyboard(),
            state_probe=enabled,
            system_detector=detector,
            owned_probe=proof,
            bridge_factory=lambda: previous,
            owned_factory=lambda: owned,
        )
        router.set_diagnostic_handler(diagnostics.append)
        await router.prepare_task("auto")
        with pytest.raises(OutputRouterError, match="ibus_untrusted_owner"):
            async with router.output_session():
                await router.insert("甲", lambda: True)
        assert previous.closed == 1 and owned.closed == 1
        assert not owned.sent and diagnostics == ["input_cleanup_failed"]

    asyncio.run(run())


def test_later_owned_no_service_cannot_fall_back_even_after_zero_result():
    async def run():
        class ZeroThenNoService(Owned):
            async def insert(self, *args, **kwargs):
                if not self.sent:
                    self.sent.append("zero-result")
                    return 0
                raise IBusBridgeError("no_service")

        async def enabled():
            return "enabled"

        async def detector():
            return ("fcitx", ":1.8")

        async def proof():
            return ("ibus", ":1.17")

        owned = ZeroThenNoService()
        router = DefaultAutoOutputRouter(
            Keyboard(),
            state_probe=enabled,
            system_detector=detector,
            owned_probe=proof,
            bridge_factory=Fcitx,
            owned_factory=lambda: owned,
        )
        await router.prepare_task("auto")
        with pytest.raises(OutputRouterError, match="input_capability_unknown"):
            async with router.output_session():
                assert await router.insert("甲", lambda: True) == 0
                await router.insert("乙", lambda: True)
        assert owned.sent == ["zero-result"]
        assert not router._owned_handoff_scope

    asyncio.run(run())


@pytest.mark.parametrize(
    "stage",
    ["state", "detector", "probe", "refresh_probe", "refresh_detector", "connect"],
)
@pytest.mark.parametrize(
    "outcome", ["timeout", "error", "inactive_timeout", "task_cancel"]
)
def test_handoff_preflight_errors_are_classified_and_cancellation_wins(stage, outcome):
    async def run():
        active = True
        counts = {"state": 0, "detector": 0, "probe": 0}

        def fail():
            nonlocal active
            if outcome == "task_cancel":
                raise asyncio.CancelledError
            if outcome == "inactive_timeout":
                active = False
            if outcome == "error":
                raise OSError("private exception details must not escape")
            raise TimeoutError

        async def enabled():
            counts["state"] += 1
            if stage == "state" and counts["state"] == 2:
                fail()
            return "enabled"

        async def detector():
            counts["detector"] += 1
            target = 5 if stage == "refresh_detector" else 4
            if (
                stage in {"detector", "refresh_detector"}
                and counts["detector"] == target
            ):
                fail()
            return ("fcitx", ":1.8")

        async def proof():
            counts["probe"] += 1
            target = 2 if stage == "refresh_probe" else 1
            if stage in {"probe", "refresh_probe"} and counts["probe"] == target:
                fail()
            return ("ibus", ":1.17")

        class Candidate(Owned):
            async def connect(self, expected_owner=None):
                if stage == "connect":
                    fail()
                await super().connect(expected_owner)

        previous, owned = Fcitx(), Candidate()
        router = DefaultAutoOutputRouter(
            Keyboard(),
            state_probe=enabled,
            system_detector=detector,
            owned_probe=proof,
            bridge_factory=lambda: previous,
            owned_factory=lambda: owned,
        )
        await router.prepare_task("auto")
        if outcome == "task_cancel":
            with pytest.raises(asyncio.CancelledError):
                async with router.output_session():
                    await router.insert("甲", lambda: active)
        else:
            expected = (
                "input_cancelled"
                if outcome == "inactive_timeout"
                else "input_capability_unknown"
            )
            with pytest.raises(OutputRouterError, match=expected):
                async with router.output_session():
                    await router.insert("甲", lambda: active)
        assert not owned.sent and previous.closed == 1 and owned.closed <= 1
        assert router.selected is None

    asyncio.run(run())


def test_stop_at_detached_close_still_starts_fcitx_cleanup(monkeypatch):
    async def run():
        active = True
        previous, owned = Fcitx(), Owned()

        async def enabled():
            return "enabled"

        async def detector():
            return ("fcitx", ":1.8")

        async def proof():
            return ("ibus", ":1.17")

        router = DefaultAutoOutputRouter(
            Keyboard(),
            state_probe=enabled,
            system_detector=detector,
            owned_probe=proof,
            bridge_factory=lambda: previous,
            owned_factory=lambda: owned,
        )
        check = router._check_task

        def stop_once_detached(current, deadline):
            nonlocal active
            if router._selected is None:
                active = False
            return check(current, deadline)

        monkeypatch.setattr(router, "_check_task", stop_once_detached)
        await router.prepare_task("auto")
        with pytest.raises(OutputRouterError, match="input_cancelled"):
            async with router.output_session():
                await router.insert("甲", lambda: active)
        assert previous.closed == 1 and owned.closed == 1 and not owned.sent

    asyncio.run(run())
