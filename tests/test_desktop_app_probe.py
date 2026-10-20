"""The disposable desktop driver preserves failed startup evidence."""

import subprocess

import desktop_app_probe
import pytest


def test_early_exit_preserves_profile_and_original_wait(tmp_path, monkeypatch):
    class Exited:
        pid = 123

        def poll(self):
            return 1

        def wait(self, timeout):
            return 1

    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: Exited())
    output = tmp_path / "probe"
    with pytest.raises(RuntimeError, match="before rendering"):
        desktop_app_probe.probe(output, None)
    assert (output / "private" / "home").is_dir()
    assert '"returncode": 1' in (output / "terminal.json").read_text()
    assert '"signals_sent": []' in (output / "terminal.json").read_text()


def test_timeout_keeps_owner_and_does_not_terminate(tmp_path, monkeypatch):
    class Running:
        pid = 456

        def poll(self):
            return None

        def wait(self, timeout):
            raise subprocess.TimeoutExpired("owned desktop", timeout)

    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: Running())
    ticks = iter([0, 20])
    monkeypatch.setattr(desktop_app_probe.time, "monotonic", lambda: next(ticks))
    output = tmp_path / "probe"
    with pytest.raises(subprocess.TimeoutExpired):
        desktop_app_probe.probe(output, None)
    assert (output / "private").is_dir()
    assert '"running": true' in (output / "terminal.json").read_text()
