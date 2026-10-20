"""Read-only desktop lock and graphical-session checks for owned input tests."""

import os
import re
import subprocess


def preflight():
    """Read-only lock/session checks; never change idle policy or unlock."""
    clean = dict(os.environ)
    for key in ("PYTHONHOME", "PYTHONPATH", "LD_LIBRARY_PATH", "QT_PLUGIN_PATH"):
        clean.pop(key, None)
    try:
        response = subprocess.run(
            [
                "gdbus",
                "call",
                "--session",
                "--dest",
                "org.gnome.ScreenSaver",
                "--object-path",
                "/org/gnome/ScreenSaver",
                "--method",
                "org.gnome.ScreenSaver.GetActive",
            ],
            env=clean,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"runnable": False, "code": "screen_lock_state_unavailable"}
    active = {"(true,)": True, "(false,)": False}.get(response.stdout.strip())
    if response.returncode != 0 or active is not False:
        return {
            "runnable": False,
            "code": "host_locked_or_lock_state_unknown",
            "screensaver_active": active,
        }
    # XDG_SESSION_ID is legitimately absent in the desktop app's environment.
    session = clean.get("XDG_SESSION_ID", "")
    if not session:
        try:
            display = subprocess.run(
                ["loginctl", "show-user", str(os.getuid()), "-p", "Display", "--value"],
                env=clean,
                capture_output=True,
                text=True,
                timeout=2,
            )
            session = display.stdout.strip() if display.returncode == 0 else ""
        except (OSError, subprocess.TimeoutExpired):
            session = ""
    result = {
        "runnable": True,
        "screensaver_active": False,
        "session_type": "wayland",
        "logind_graphical_session_verified": False,
    }
    if session:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", session):
            return {"runnable": False, "code": "invalid_graphical_session_id"}
        try:
            response = subprocess.run(
                [
                    "loginctl",
                    "show-session",
                    session,
                    "-p",
                    "User",
                    "-p",
                    "Type",
                    "-p",
                    "LockedHint",
                ],
                env=clean,
                capture_output=True,
                text=True,
                timeout=2,
            )
        except (OSError, subprocess.TimeoutExpired):
            return {"runnable": False, "code": "graphical_session_unavailable"}
        fields = dict(
            line.split("=", 1) for line in response.stdout.splitlines() if "=" in line
        )
        if (
            response.returncode != 0
            or fields.get("User") != str(os.getuid())
            or fields.get("Type") != "wayland"
            or fields.get("LockedHint") != "no"
        ):
            return {"runnable": False, "code": "graphical_session_not_ready"}
        result["logind_graphical_session_verified"] = True
    return result
