"""Default auto dispatch with an explicitly installed, versioned optional bridge."""

from inkecho.platform.framework_detection import detect_system_framework
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
            return await self._legacy_auto(can_continue, deadline, pinned=evidence)
        if state != "enabled":
            raise OutputRouterError("input_capability_unknown")
        return await super()._choose_auto(can_continue, deadline)
