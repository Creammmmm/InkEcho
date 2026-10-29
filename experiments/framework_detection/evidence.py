"""Conservative system-framework hypothesis, never a focused-widget claim.

Not wired into the product. Every Boolean must be verified by a collector; a
missing observation is None, never inferred from a process name or file alone.
"""

from dataclasses import dataclass
from typing import Literal

Framework = Literal["fcitx", "ibus"]


@dataclass(frozen=True)
class Evidence:
    # Values read from the actual graphical session, not the caller's guesses.
    xmodifiers: str | None
    gtk: str | None
    qt: str | None
    # Verified unique-owner process identity for the framework's live service.
    fcitx_owner: bool | None
    ibus_owner: bool | None
    # Authenticated bridge handshake, performed without sending text.
    fcitx_bridge: bool | None
    ibus_bridge: bool | None
    # GNOME settings readable and syntactically valid; NOT the stale current key.
    source_configuration_readable: bool


def choose(evidence: Evidence) -> Framework | None:
    if not evidence.source_configuration_readable:
        return None
    x = (evidence.xmodifiers or "").lower()
    gtk = (evidence.gtk or "").lower()
    qt = (evidence.qt or "").lower()
    # Explicit XIM, GTK and Qt overrides such as simple/xim/wayland do not prove
    # agreement. Require XMODIFIERS plus at least one matching toolkit hint.
    if x not in ("@im=fcitx", "@im=ibus"):
        return None
    selected = x.removeprefix("@im=")
    if gtk not in ("", selected) or qt not in ("", selected):
        return None
    if selected not in (gtk, qt):
        return None
    if selected == "fcitx":
        return (
            "fcitx"
            if evidence.fcitx_owner is True and evidence.fcitx_bridge is True
            else None
        )
    return (
        "ibus" if evidence.ibus_owner is True and evidence.ibus_bridge is True else None
    )
