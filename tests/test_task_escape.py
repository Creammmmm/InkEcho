"""Task-scoped shortcut lifecycle; actual desktop grabs need desktop acceptance."""

import os

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QLineEdit

from inkecho.platform.escape import EscapeUnavailable, TaskEscape, _lock_combinations


class Backend:
    def __init__(self):
        self.fd, self.write_fd = os.pipe()
        self.closed = False
        self.ready = False

    def pressed(self):
        os.read(self.fd, 1)
        return self.ready

    def close(self):
        self.closed = True
        os.close(self.fd)
        os.close(self.write_fd)


@pytest.fixture
def escape(qt_app, monkeypatch):
    monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
    backends, cancelled = [], []

    def create():
        backend = Backend()
        backends.append(backend)
        return backend

    guard = TaskEscape(lambda: cancelled.append(True), factory=create)
    yield guard, backends, cancelled
    guard.close()


def test_grab_lives_only_during_task_and_can_rearm(escape, qt_app):
    guard, backends, cancelled = escape
    guard.set_active(True)
    qt_app.processEvents()
    assert len(backends) == 1
    guard.set_active(True)
    qt_app.processEvents()
    assert len(backends) == 1
    guard.set_active(False)
    assert backends[0].closed
    guard.set_active(True)
    qt_app.processEvents()
    assert len(backends) == 2
    assert not cancelled


def test_stale_deferred_arm_does_not_grab_escape(escape, qt_app):
    guard, backends, _ = escape
    guard.set_active(True)
    guard.set_active(False)
    qt_app.processEvents()
    assert not backends


def test_global_escape_cancels_once_and_releases_before_callback(escape, qt_app):
    guard, backends, cancelled = escape
    guard.set_active(True)
    qt_app.processEvents()
    backend = backends[0]
    backend.ready = True
    os.write(backend.write_fd, b"e")
    qt_app.processEvents()
    assert cancelled == [True]
    assert backend.closed
    assert guard.backend is None
    assert not guard.active


def test_local_escape_does_not_capture_ordinary_keys_or_idle_escape(escape, qt_app):
    guard, _, cancelled = escape
    edit = QLineEdit()
    edit.show()
    edit.setFocus()
    guard.set_active(True)
    QTest.keyClicks(edit, "hello")
    assert edit.text() == "hello"
    QTest.keyClick(edit, Qt.Key.Key_Escape)
    assert cancelled == [True]
    QTest.keyClick(edit, Qt.Key.Key_Escape)
    assert cancelled == [True]
    edit.close()


def test_modified_escape_is_not_our_cancel_shortcut(escape):
    guard, _, cancelled = escape
    guard.set_active(True)
    event = QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.AltModifier
    )
    assert not guard.eventFilter(None, event)
    assert not cancelled


def test_wayland_does_not_pretend_xwayland_grab_is_global(escape, monkeypatch, qt_app):
    guard, backends, _ = escape
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    guard.set_active(True)
    qt_app.processEvents()
    assert not backends
    assert guard.active


def test_conflicting_shortcut_is_not_replaced(qt_app, monkeypatch):
    monkeypatch.setenv("XDG_SESSION_TYPE", "x11")

    def denied():
        raise EscapeUnavailable

    guard = TaskEscape(lambda: None, factory=denied)
    guard.set_active(True)
    qt_app.processEvents()
    assert guard.backend is None
    assert guard.active  # Local Escape remains available.
    guard.close()


def test_lock_masks_follow_remapped_numlock_and_preserve_real_modifiers():
    rows = [(50, 62), (66,), (37, 105), (64, 108), (), (77,), (), ()]
    assert _lock_combinations(rows, {66, 77}) == (0, 2, 32, 34)
    # Sharing a column with a real Alt key must not make Alt+Escape our shortcut.
    rows[5] = (77, 64)
    assert _lock_combinations(rows, {66, 77}) == (0, 2)


def test_lock_masks_do_not_grab_unassigned_modifier_combinations():
    assert _lock_combinations([()] * 8, {66, 77}) == (0,)
