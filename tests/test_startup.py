"""Cold-start command ordering, before asynchronous input services are ready."""

from PySide6.QtNetwork import QLocalSocket
from PySide6.QtTest import QTest

from inkecho.__main__ import Instance, StartupCommands


def test_cold_start_and_repeated_toggle_dispatch_only_after_ready():
    commands = []
    startup = StartupCommands(commands.append, toggle=True)
    startup.receive("toggle")
    assert commands == []
    startup.complete()
    assert commands == ["toggle"]
    startup.receive("toggle")
    assert commands == ["toggle", "toggle"]


def test_cancel_or_quit_invalidates_pending_start():
    for action in ("cancel", "quit"):
        commands = []
        startup = StartupCommands(commands.append, toggle=True)
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
