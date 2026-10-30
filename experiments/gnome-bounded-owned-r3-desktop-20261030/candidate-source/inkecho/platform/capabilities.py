"""Conservative platform detection; available protocols are not support claims."""

import os
import platform
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DesktopCapabilities:
    system: str
    distribution: str
    session: str
    desktop: str
    injection_ready: bool
    reason: str


def detect_desktop(environ=None, release_path=Path("/etc/os-release")):
    env = os.environ if environ is None else environ
    system = platform.system()
    release = {}
    if release_path.is_file():
        for line in release_path.read_text().splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                release[key] = value.strip('"')
    session = env.get("XDG_SESSION_TYPE", "unknown").lower()
    if system != "Linux":
        reason = "This release implements Linux only."
    elif session == "wayland":
        reason = (
            "GNOME Wayland has an experimental current-cursor keyboard route "
            "for native and XWayland clients; BMP text and runtime checks required."
            if "GNOME" in env.get("XDG_CURRENT_DESKTOP", "").upper().split(":")
            else "Current-cursor keyboard delivery supports compatible XWayland apps. "
            "Native delivery on this desktop has not been validated."
        )
    elif session == "x11":
        reason = (
            "X11 keyboard delivery requires a connection "
            "and a supported receiver at output."
        )
    else:
        reason = "The desktop session could not be verified."
    return DesktopCapabilities(
        system,
        release.get("PRETTY_NAME", system),
        session,
        env.get("XDG_CURRENT_DESKTOP", "unknown"),
        False,
        reason,
    )
