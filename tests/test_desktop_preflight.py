"""Current desktop identity controls; no GUI, network, microphone or input."""

import importlib.util
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

PATH = Path(__file__).resolve().parents[1] / "scripts/validation/desktop_preflight.py"
SPEC = importlib.util.spec_from_file_location("desktop_preflight", PATH)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


def test_missing_xdg_session_id_uses_read_only_graphical_session_lookup(monkeypatch):
    monkeypatch.delenv("XDG_SESSION_ID", raising=False)
    calls = []

    def checked(argv, **_options):
        calls.append(argv)
        if argv[0] == "gdbus":
            stdout = "(false,)"
        elif argv[1] == "show-user":
            stdout = "42"
        else:
            stdout = f"User={os.getuid()}\nType=wayland\nLockedHint=no\n"
        return SimpleNamespace(returncode=0, stdout=stdout)

    monkeypatch.setattr(probe.subprocess, "run", checked)
    result = probe.preflight()
    assert result["runnable"] and result["logind_graphical_session_verified"]
    assert calls[1][:3] == ["loginctl", "show-user", str(os.getuid())]
    assert all("unlock" not in argv and "lock-session" not in argv for argv in calls)


@pytest.mark.parametrize("reply", ["(true,)", "unexpected"])
def test_locked_or_unknown_session_is_not_an_input_support_failure(monkeypatch, reply):
    calls = []

    def checked(argv, **_options):
        calls.append(argv)
        return SimpleNamespace(returncode=0, stdout=reply)

    monkeypatch.setattr(probe.subprocess, "run", checked)
    result = probe.preflight()
    assert not result["runnable"] and len(calls) == 1


@pytest.mark.parametrize("failure", [OSError("test"), subprocess.TimeoutExpired([], 2)])
def test_unavailable_lock_state_fails_before_session_lookup(monkeypatch, failure):
    def checked(*_args, **_options):
        raise failure

    monkeypatch.setattr(probe.subprocess, "run", checked)
    assert probe.preflight() == {
        "runnable": False,
        "code": "screen_lock_state_unavailable",
    }


@pytest.mark.parametrize(
    "identity",
    [
        "User=not-current\nType=wayland\nLockedHint=no",
        f"User={os.getuid()}\nType=x11\nLockedHint=no",
        f"User={os.getuid()}\nType=wayland\nLockedHint=yes",
        f"User={os.getuid()}\nType=wayland",
    ],
)
def test_mismatched_user_type_or_lock_is_not_ready(monkeypatch, identity):
    monkeypatch.setenv("XDG_SESSION_ID", "owned-session")

    def checked(argv, **_options):
        return SimpleNamespace(
            returncode=0, stdout="(false,)" if argv[0] == "gdbus" else identity
        )

    monkeypatch.setattr(probe.subprocess, "run", checked)
    assert probe.preflight() == {
        "runnable": False,
        "code": "graphical_session_not_ready",
    }


def test_invalid_session_identifier_never_reaches_logind(monkeypatch):
    monkeypatch.setenv("XDG_SESSION_ID", "invalid/session")
    calls = []

    def checked(argv, **_options):
        calls.append(argv)
        return SimpleNamespace(returncode=0, stdout="(false,)")

    monkeypatch.setattr(probe.subprocess, "run", checked)
    assert probe.preflight() == {
        "runnable": False,
        "code": "invalid_graphical_session_id",
    }
    assert len(calls) == 1
