"""Default auto dispatch with an explicitly installed, versioned optional bridge."""

import asyncio
from contextlib import asynccontextmanager

from inkecho.platform.framework_detection import detect_system_framework
from inkecho.platform.ibus import IBusBridgeError
from inkecho.platform.ibus_owned_auto import OwnedAutoOutputRouter
from inkecho.platform.output_router import OutputRouter, OutputRouterError
from inkecho.platform.owned_installation import installation_state
from inkecho.text_units import UNSENT_NEIGHBOR_ROUTE


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

    async def _prepare_task(self, mode, parent_window, on_keyboard_authorization):
        # Recording never captures a target or requests text-method permission.
        # This explicit option defers authentication until actual output, but
        # never permits the automatic Fcitx/keyboard fallback policy.
        self._explicit_owned_task = mode == "ibus-owned"
        self._explicit_owned_check = None
        return await super()._prepare_task(
            "auto" if self._explicit_owned_task else mode,
            parent_window,
            on_keyboard_authorization,
        )

    def _remember_explicit_task(self, active, deadline):
        owner = asyncio.current_task()
        if (
            not getattr(self, "_explicit_owned_task", False)
            or self._selected is None
            or self._closed
            or self._owner not in (None, owner)
            or self._busy
        ):
            return
        previous = getattr(self, "_explicit_owned_check", None)
        if previous is not None and previous[0] is owner and previous[2] is not None:
            deadline = previous[2] if deadline is None else min(previous[2], deadline)
        self._explicit_owned_check = (owner, active, deadline)

    async def prepare_stream(self, can_continue, *, deadline=None):
        self._remember_explicit_task(can_continue, deadline)
        return await super().prepare_stream(can_continue, deadline=deadline)

    async def insert(self, text, can_continue, *, deadline=None, on_first_sent=None):
        self._remember_explicit_task(can_continue, deadline)
        return await super().insert(
            text, can_continue, deadline=deadline, on_first_sent=on_first_sent
        )

    def _check_explicit_scope_stop(self, check, attempts, error=None):
        if check is None:
            return
        try:
            self._check_task(check[1], check[2])
        except OutputRouterError as stopped:
            acknowledged = getattr(error, "acknowledged_attempts", 0)
            if type(acknowledged) is not int or acknowledged < 0:
                acknowledged = 0
            raise OutputRouterError(
                stopped.code, acknowledged_attempts=max(attempts, acknowledged)
            ) from None

    @asynccontextmanager
    async def output_session(self):
        explicit = getattr(self, "_explicit_owned_task", False)
        owner = asyncio.current_task()
        attempts = 0
        body_error = None
        scope_check = None
        try:
            async with super().output_session():
                try:
                    yield
                except BaseException as error:
                    body_error = error
                    raise
                finally:
                    if explicit:
                        # Snapshot before base cleanup clears the selected client.
                        # Inflight input never becomes a confirmed receipt.
                        attempts = self.acknowledged_attempts
                        check = getattr(self, "_explicit_owned_check", None)
                        if check is not None and check[0] is owner:
                            scope_check = check
        except Exception as error:
            if explicit:
                cleanup_failed = error is not body_error and not isinstance(
                    error, OutputRouterError
                )
                if cleanup_failed:
                    self._report_cleanup_failure()
                if isinstance(body_error, asyncio.CancelledError):
                    raise body_error from None
                self._check_explicit_scope_stop(scope_check, attempts, error)
                if cleanup_failed:
                    # A transport cleanup fault cannot erase the dispatch record
                    # or authorize replay, even when it masks the body's error.
                    acknowledged = getattr(body_error, "acknowledged_attempts", 0)
                    if type(acknowledged) is not int or acknowledged < 0:
                        acknowledged = 0
                    attempts = max(attempts, acknowledged)
                    raise OutputRouterError(
                        "ibus_delivery_unknown" if attempts else "ibus_cleanup_failed",
                        acknowledged_attempts=attempts,
                    ) from None
            raise
        else:
            if explicit:
                self._check_explicit_scope_stop(scope_check, attempts)
        finally:
            if explicit and getattr(self, "_explicit_owned_check", None) is scope_check:
                self._explicit_owned_check = None

    async def _choose_explicit_owned(self, active, deadline):
        try:
            state = await self._wait_auto_preflight(
                self._state_probe(), active, deadline, timeout=1.5
            )
        except (asyncio.CancelledError, OutputRouterError):
            raise
        except Exception:
            raise OutputRouterError("input_capability_unknown") from None
        if state in {"absent", "disabled"}:
            raise OutputRouterError("ibus_unavailable")
        if state != "enabled":
            raise OutputRouterError("input_capability_unknown")

        async def checked_owned():
            proof = await self._owned_probe()
            if proof is None:
                raise OutputRouterError("ibus_target_unavailable")
            if not (
                isinstance(proof, tuple)
                and len(proof) == 2
                and proof[0] == "ibus"
                and isinstance(proof[1], str)
                and proof[1].startswith(":")
            ):
                # No compatible target is not authorization for another route.
                raise OutputRouterError("input_capability_unknown")
            return proof

        detector, factory = self._system_detector, self._ibus_factory
        self._system_detector, self._ibus_factory = checked_owned, self._owned_factory
        self._owned_auto_candidate = True
        try:
            result = await OutputRouter._choose_auto(self, active, deadline)
            self._owned_auto_scope = self._kind == "ibus"
            return result
        finally:
            self._system_detector, self._ibus_factory = detector, factory

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
        if getattr(self, "_explicit_owned_task", False):
            return await self._choose_explicit_owned(can_continue, deadline)
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
                candidate.connect(expected_owner=proof[1], deadline=deadline),
                active,
                deadline,
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
            # Cleanup can take time; a user may disable the owned extension
            # before it becomes the output route. Never send on stale consent.
            state = await self._wait_auto_preflight(
                self._state_probe(), active, deadline, timeout=1.5
            )
            if state != "enabled":
                raise OutputRouterError("input_capability_unknown")
            # The last state check is asynchronous. Recheck both identities;
            # none of these checks can make the subsequent send atomic.
            current = await self._wait_auto_preflight(
                self._legacy_detector(), active, deadline, timeout=1.5
            )
            refreshed = await self._wait_auto_preflight(
                self._owned_probe(), active, deadline, timeout=1.5
            )
            if current != evidence or refreshed != proof:
                raise OutputRouterError("input_capability_unknown")
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
        if getattr(self, "_stream_replan_armed", False) and bool(
            getattr(candidate, "supports_neighbor_batch", False)
        ):
            # The strict handoff checks proved the entire previous task unsent;
            # Begin only prepared this route. No owned Commit has happened.
            self._check_task(active, deadline)
            self._stream_replan_armed = False
            return UNSENT_NEIGHBOR_ROUTE
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
            "upgrade_required",
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
