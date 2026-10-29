"""Default auto dispatch with an explicitly installed, versioned optional bridge."""

from inkecho.platform.framework_detection import detect_system_framework
from inkecho.platform.ibus import IBusBridgeError
from inkecho.platform.ibus_owned_auto import OwnedAutoOutputRouter
from inkecho.platform.output_router import OutputRouter, OutputRouterError
from inkecho.platform.owned_installation import installation_state


class DefaultAutoOutputRouter(OwnedAutoOutputRouter):
    """Absent/disabled retains legacy policy; installed uncertainty stops text.

    Nothing installs extensions or changes settings. All checks happen during
    actual output. Existing verified Fcitx retains priority over optional IBus.
    """

    def __init__(
        self,
        keyboard,
        *,
        state_probe=installation_state,
        system_detector=detect_system_framework,
        **kwargs,
    ):
        super().__init__(keyboard, system_detector=system_detector, **kwargs)
        self._state_probe = state_probe
        self._legacy_detector = system_detector

    async def _legacy_auto(self, active, deadline, *, pinned=None):
        flag, detector = self._owned_auto_candidate, self._system_detector
        self._owned_auto_candidate = False
        self._owned_auto_scope = False

        async def checked_detector():
            evidence = await self._legacy_detector()
            if pinned is not None and evidence != pinned:
                raise OutputRouterError("input_capability_unknown")
            return evidence

        self._system_detector = checked_detector
        try:
            result = await OutputRouter._choose_auto(self, active, deadline)
            # If installed-state uncertainty exists, a failed Fcitx preflight
            # cannot silently authorize text through fallback keyboard.
            if pinned is not None and self._kind != "fcitx":
                raise OutputRouterError("input_capability_unknown")
            return result
        finally:
            self._owned_auto_candidate = flag
            self._system_detector = detector

    async def _choose_auto(self, can_continue=lambda: True, deadline=None):
        self._owned_auto_candidate = True
        self._fcitx_keyboard_fallback_allowed = False
        self._owned_install_state = "unknown"
        self._fcitx_evidence = None
        try:
            state = await self._wait_auto_preflight(
                self._state_probe(), can_continue, deadline, timeout=1.5
            )
        except OutputRouterError as error:
            if error.code != "input_capability_unknown":
                raise
            state = "unknown"
        except Exception:
            state = "unknown"
        self._owned_install_state = state
        if state in {"absent", "disabled"}:
            self._fcitx_keyboard_fallback_allowed = True
            return await self._legacy_auto(can_continue, deadline)
        # A broken optional extension must not block a proven Fcitx route.
        try:
            evidence = await self._wait_auto_preflight(
                self._legacy_detector(), can_continue, deadline, timeout=1.5
            )
        except OutputRouterError:
            raise
        except Exception:
            evidence = None
        if (
            isinstance(evidence, tuple)
            and len(evidence) == 2
            and evidence[0] == "fcitx"
            and isinstance(evidence[1], str)
            and evidence[1].startswith(":")
        ):
            self._fcitx_evidence = evidence
            return await self._legacy_auto(can_continue, deadline, pinned=evidence)
        if state != "enabled":
            raise OutputRouterError("input_capability_unknown")
        return await super()._choose_auto(can_continue, deadline)

    async def _handoff_unsent_fcitx(self, error, text, active, deadline, on_first_sent):
        previous = self._selected
        try:
            return await self._handoff_owned(
                error, text, active, deadline, on_first_sent
            )
        except BaseException as failure:
            # A preflight error must survive Fcitx cleanup during scope exit.
            if self._selected is previous:
                self._selected = self._kind = None
                try:
                    await previous.aclose()
                except Exception:
                    self._report_cleanup_failure()
            if isinstance(failure, Exception):
                # Probe transport errors are inability to establish capability,
                # never authorization to switch output methods. A stop that
                # arrived during failure/cleanup still takes precedence.
                self._check_task(active, deadline)
                if not isinstance(failure, OutputRouterError):
                    raise OutputRouterError("input_capability_unknown") from None
            raise

    async def _handoff_owned(self, error, text, active, deadline, on_first_sent):
        """Only a verified zero-attempt task may try the separately enabled bridge."""
        previous = self._selected
        accepted = getattr(previous, "_accepted", None)
        if (
            self._owned_install_state != "enabled"
            or type(accepted) is not int
            or accepted != 0
            or error.code != "no_target"
        ):
            raise OutputRouterError("fcitx_" + error.code) from None
        self._check_task(active, deadline)
        # Installation and both service identities must remain valid. Probe's
        # blocked result deliberately reaches the bridge's preedit protection.
        state = await self._wait_auto_preflight(
            self._state_probe(), active, deadline, timeout=1.5
        )
        if state != "enabled":
            raise OutputRouterError("input_capability_unknown")
        evidence = await self._wait_auto_preflight(
            self._legacy_detector(), active, deadline, timeout=1.5
        )
        if evidence != self._fcitx_evidence:
            raise OutputRouterError("input_capability_unknown")
        proof = await self._wait_auto_preflight(
            self._owned_probe(), active, deadline, timeout=1.5
        )
        if not (
            isinstance(proof, tuple)
            and len(proof) == 2
            and proof[0] == "ibus"
            and isinstance(proof[1], str)
            and proof[1].startswith(":")
        ):
            raise OutputRouterError("input_capability_unknown")
        candidate = self._owned_factory()
        try:
            await self._wait_auto_preflight(
                candidate.connect(expected_owner=proof[1]), active, deadline
            )
            refreshed = await self._wait_auto_preflight(
                self._owned_probe(), active, deadline, timeout=1.5
            )
            current = await self._wait_auto_preflight(
                self._legacy_detector(), active, deadline, timeout=1.5
            )
            if refreshed != proof or current != evidence:
                raise OutputRouterError("input_capability_unknown")
            self._check_task(active, deadline)
            # Real Fcitx close releases its local resources in finally, even
            # when capability cleanup fails. Detach it before that one close so
            # scope teardown cannot retry and replace the primary diagnostic.
            self._selected = self._kind = None
            try:
                # Await inline: a task/active guard must not cancel a newly
                # created close coroutine before it starts its cleanup finally.
                # Real Fcitx close already bounds its remote Cancel request.
                await previous.aclose()
            except Exception:
                self._report_cleanup_failure()
                self._check_task(active, deadline)
                raise OutputRouterError("input_cleanup_failed") from None
            self._check_task(active, deadline)
        except BaseException as failure:
            await self._abort_preflight_after_stop(candidate)
            if isinstance(failure, IBusBridgeError):
                self._check_task(active, deadline)
                raise OutputRouterError(self._owned_failure_code(failure)) from None
            raise
        self._selected, self._kind = candidate, "ibus"
        self._owned_auto_scope = True
        self._owned_handoff_scope = True
        try:
            sent = await candidate.insert(
                text, active, deadline=deadline, on_first_sent=on_first_sent
            )
        except IBusBridgeError as failure:
            raise OutputRouterError(
                self._owned_failure_code(failure),
                acknowledged_attempts=failure.acknowledged_attempts,
            ) from None
        if type(sent) is int and sent > 0:
            self._ibus_attempted = True
            self._ibus_acknowledged_attempts += sent
        return sent

    @staticmethod
    def _owned_failure_code(failure):
        # No-service is a stop here, never permission to bypass the enabled
        # extension. Emit only diagnostic identifiers understood by Session.
        known = {
            "authorization_failed",
            "permission_denied",
            "untrusted_owner",
            "unavailable",
            "delivery_unknown",
            "cancelled",
            "unsupported_text",
        }
        if failure.code in known:
            return "ibus_" + failure.code
        if failure.acknowledged_attempts:
            return "ibus_delivery_unknown"
        return "input_capability_unknown"
