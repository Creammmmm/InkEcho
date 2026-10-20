"""Running-instance commands and asynchronous service startup ordering."""

from PySide6.QtNetwork import QLocalSocket
from PySide6.QtTest import QTest

from inkecho.__main__ import Instance, StartupCommands


def test_starting_instance_and_repeated_toggle_dispatch_only_after_ready():
    commands = []
    startup = StartupCommands(commands.append)
    startup.receive("toggle")
    assert commands == []
    startup.complete()
    assert commands == ["toggle"]
    startup.receive("toggle")
    assert commands == ["toggle", "toggle"]


def test_cancel_or_quit_invalidates_pending_start():
    for action in ("cancel", "quit"):
        commands = []
        startup = StartupCommands(commands.append)
        startup.receive("toggle")
        startup.receive(action)
        startup.complete()
        assert commands == [action]


def test_show_remains_available_during_startup():
    commands = []
    startup = StartupCommands(commands.append)
    startup.receive("show")
    assert commands == ["show"]


def test_real_local_socket_retains_command_before_handler_attaches(tmp_path, qt_app):
    instance = Instance(tmp_path)
    socket = QLocalSocket()
    try:
        assert instance.acquire("show")
        socket.connectToServer(instance.name)
        assert socket.waitForConnected(1000)
        socket.write(b"toggle\n")
        socket.flush()
        QTest.qWait(30)
        assert instance.pending_commands == ["toggle"]
        received = []
        startup = StartupCommands(received.append)
        instance.attach(startup.receive)
        assert received == []
        startup.complete()
        assert received == ["toggle"]
    finally:
        socket.abort()
        instance.close()


def test_control_command_without_instance_does_not_create_server(tmp_path, qt_app):
    instance = Instance(tmp_path)
    try:
        assert not instance.acquire("toggle", allow_start=False)
        assert not instance.server.isListening()
        assert not instance.lock.isLocked()
        # A later deliberate launch must still be able to acquire the instance.
        assert instance.acquire("show")
    finally:
        instance.close()


def test_control_command_reaches_running_hidden_instance(tmp_path, qt_app):
    instance = Instance(tmp_path)
    client = Instance(tmp_path)
    received = []
    try:
        assert instance.acquire("show")
        instance.attach(received.append)
        assert not client.acquire("toggle", allow_start=False)
        QTest.qWait(30)
        assert received == ["toggle"]
    finally:
        client.close()
        instance.close()


def test_control_commands_after_exit_leave_config_uninitialized(tmp_path):
    import os
    import subprocess
    import sys

    config = tmp_path / "config"
    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    env = {
        **os.environ,
        "QT_QPA_PLATFORM": "offscreen",
        "XDG_RUNTIME_DIR": str(runtime),
        "XDG_CONFIG_HOME": str(tmp_path / "xdg-config"),
        "XDG_DATA_HOME": str(tmp_path / "xdg-data"),
        "XDG_CACHE_HOME": str(tmp_path / "xdg-cache"),
        "XDG_STATE_HOME": str(tmp_path / "xdg-state"),
    }
    for action in ("toggle", "cancel", "quit"):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "inkecho",
                f"--{action}",
                "--config-dir",
                str(config),
            ],
            env=env,
            capture_output=True,
            timeout=15,
        )
        assert result.returncode == 0, result.stderr.decode()
        assert not config.exists()
        assert list(runtime.iterdir()) == []


def test_real_application_quit_then_toggle_does_not_revive(tmp_path):
    import os
    import subprocess
    import sys
    import time

    config = tmp_path / "config"
    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    env = {
        **os.environ,
        "QT_QPA_PLATFORM": "offscreen",
        "XDG_RUNTIME_DIR": str(runtime),
        "XDG_CONFIG_HOME": str(tmp_path / "xdg-config"),
        "XDG_DATA_HOME": str(tmp_path / "xdg-data"),
        "XDG_CACHE_HOME": str(tmp_path / "xdg-cache"),
        "XDG_STATE_HOME": str(tmp_path / "xdg-state"),
    }
    command = [sys.executable, "-m", "inkecho", "--config-dir", str(config)]
    owner = subprocess.Popen(
        [*command, "--background"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        deadline = time.monotonic() + 15
        while not (config / "config.json").exists():
            assert owner.poll() is None
            assert time.monotonic() < deadline
            time.sleep(0.02)
        quit_result = subprocess.run(
            [*command, "--quit"], env=env, capture_output=True, timeout=15
        )
        assert quit_result.returncode == 0, quit_result.stderr.decode()
        _, stderr = owner.communicate(timeout=15)
        assert owner.returncode == 0, stderr.decode()
        before = {path.name: path.stat().st_mtime_ns for path in config.iterdir()}
        runtime_before = set(runtime.iterdir())
        assert not list(runtime.glob("inkecho-*.lock"))
        toggle_result = subprocess.run(
            [*command, "--toggle"], env=env, capture_output=True, timeout=15
        )
        assert toggle_result.returncode == 0, toggle_result.stderr.decode()
        assert {
            path.name: path.stat().st_mtime_ns for path in config.iterdir()
        } == before
        assert set(runtime.iterdir()) == runtime_before
    finally:
        if owner.poll() is None:
            owner.terminate()
            owner.communicate(timeout=15)


def test_control_processes_do_not_load_gui_audio_or_providers(tmp_path):
    import json
    import os
    import subprocess
    import sys

    heavy = [
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PySide6.QtMultimedia",
        "inkecho.app",
        "inkecho.audio",
        "inkecho.ui.window",
        "inkecho.providers",
        "httpx",
        "qasync",
    ]
    code = """
import json, sys
from inkecho import __main__ as entry
entry.main()
print(json.dumps(sorted(sys.modules)))
"""
    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    env = {
        **os.environ,
        # A control command must not even attempt to load a GUI platform plugin.
        "QT_QPA_PLATFORM": "invalid-control-test-plugin",
        "XDG_RUNTIME_DIR": str(runtime),
    }
    for action in ("toggle", "cancel", "quit"):
        result = subprocess.run(
            [sys.executable, "-c", code, f"--{action}", "--config-dir", str(tmp_path)],
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 0, result.stderr
        loaded = json.loads(result.stdout)
        assert all(name not in loaded for name in heavy)
        assert "PySide6.QtCore" in loaded
        assert "PySide6.QtNetwork" in loaded


def test_control_error_is_sanitized_without_loading_gui(tmp_path):
    import os
    import subprocess
    import sys

    code = """
from inkecho import __main__ as entry
def fail(*args, **kwargs):
    raise RuntimeError('private-test-error-detail')
entry.Instance.acquire = fail
entry.main()
"""
    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    result = subprocess.run(
        [sys.executable, "-c", code, "--toggle", "--config-dir", str(tmp_path)],
        env={
            **os.environ,
            "QT_QPA_PLATFORM": "invalid-control-test-plugin",
            "XDG_RUNTIME_DIR": str(runtime),
        },
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 1
    assert result.stderr.strip() == "InkEcho 控制命令未送达，请稍后重试。"
    assert "private-test-error-detail" not in result.stderr
    assert str(tmp_path) not in result.stderr
