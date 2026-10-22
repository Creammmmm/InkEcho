"""A cache hint follows the current focus and never gates a key release."""

import ctypes
from types import SimpleNamespace

import pytest
from test_xorg_pair import hardware

from inkecho.platform.keyboard import KeyboardError, _Event, _XTestDriver


def notifier(monkeypatch):
    driver, rows, _, _, _ = hardware(monkeypatch)
    calls = []

    def notice(display, target, propagate, mask, event):
        value = ctypes.cast(event, ctypes.POINTER(_Event)).contents.mapping
        calls.append(
            ("map", target, value.type, value.request, value.first_keycode, value.count)
        )
        return 1

    driver.x11.XSendEvent = notice
    driver.xtst = SimpleNamespace(
        XTestFakeKeyEvent=lambda display, code, pressed, delay: (
            calls.append(("key", code, pressed)) or 1
        )
    )
    driver.send = _XTestDriver.send.__get__(driver)
    return driver, rows, calls


def test_map_notice_is_deduplicated_but_follows_new_focus_and_revision(monkeypatch):
    driver, rows, calls = notifier(monkeypatch)
    before = rows.copy()
    driver.prepare("中文", 0)
    code = driver.map("中")
    driver.send(21, code, True)
    driver.send(99, code, False)
    driver.send(99, code, True)
    driver.send(99, code, False)
    assert [call[0] for call in calls] == ["map", "key", "key", "map", "key", "key"]
    assert calls[0] == calls[3] == ("map", 1, 34, 1, 183, 2)
    driver.send(99, code, True)
    driver.send(99, code, False)
    assert [call[0] for call in calls[-2:]] == ["key", "key"]
    driver.prepare("验证", 0)
    driver.send(99, driver.map("验"), True)
    driver.send(99, driver.map("验"), False)
    assert calls[-3][0] == "map"
    driver.restore()
    assert rows == before and calls[-1] == ("map", 1, 34, 1, 183, 2)
    assert driver._notified is None


def test_failed_notice_prevents_press_but_not_release_or_map_restore(monkeypatch):
    driver, rows, calls = notifier(monkeypatch)
    before = rows.copy()
    driver.prepare("中文", 0)
    code = driver.map("中")
    driver.x11.XSendEvent = lambda *_: 0
    with pytest.raises(KeyboardError, match="injection_failed"):
        driver.send(21, code, True)
    assert not calls
    driver.send(99, code, False)
    assert calls == [("key", code, 0)]
    driver.restore()
    assert rows == before and not driver._pair_applied


def test_return_has_no_unicode_cache_hint(monkeypatch):
    driver, _, calls = notifier(monkeypatch)
    driver.prepare("中", 0)
    driver.send(21, 36, True)
    driver.send(21, 36, False)
    assert calls == [("key", 36, 1), ("key", 36, 0)]
    driver.restore()
