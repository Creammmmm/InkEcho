"""Offline exercise of the owned-target probe; no graphical input is sent."""

import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_x11_acceptance import Driver, fixture

ENTRY = (
    Path(__file__).resolve().parents[1] / "scripts/validation/x11_mapping_wait_probe.py"
)


def test_probe_can_measure_driver_with_map_but_no_prepare(monkeypatch):
    monkeypatch.syspath_prepend(str(ENTRY.parent))
    spec = importlib.util.spec_from_file_location("mapping_wait_probe_map_test", ENTRY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class MapDriver(Driver):
        _map_revision = 0

        def map(self, character):
            code = super().map(character)
            self._map_revision += 1
            return code

    driver = MapDriver()
    driver.pid = 21
    driver.text[21] = ""
    inputs = SimpleNamespace(_driver=driver, _send=driver.send)
    timings = []
    with module.measure_mapping_wait(inputs, timings):
        code = driver.map("中")
        inputs._send(211, code, True)
    assert len(timings) == 1 and timings[0]["initial"]
    assert driver.text[21] == "中"


@pytest.mark.parametrize(
    ("mode", "scope"),
    [
        ("normal", "ubuntu24-xorg"),
        ("cancel", "ubuntu24-xorg"),
        ("currentcursor", "ubuntu24-xorg"),
        ("currentcursor", "ubuntu26-xwayland"),
        ("currentcursor-textareas", "ubuntu26-xwayland"),
        ("contenteditable", "ubuntu26-xwayland"),
    ],
)
def test_probe_uses_session_configuration_and_owned_target(
    qt_app, monkeypatch, tmp_path, mode, scope
):
    monkeypatch.syspath_prepend(str(ENTRY.parent))
    spec = importlib.util.spec_from_file_location("mapping_wait_probe_test", ENTRY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    from inkecho.platform.keyboard import KeyboardInput
    from inkecho.platform.output_pacing import OutputPacer

    class ImmediatePacer(OutputPacer):
        async def _wait(self, token, active, deadline, until):
            self._check(token, active, deadline)

    class RealisticDriver(Driver):
        _map_revision = 0

        def prepare(self, text, index):
            if text[index] != "\n":
                self._map_revision += 1

        def map(self, character):
            if character == "\n":
                self.character = character
                return 20
            return super().map(character)

    driver = RealisticDriver()
    keyboard = KeyboardInput(driver_factory=lambda: driver, pacer=ImmediatePacer())
    if scope == "ubuntu26-xwayland":
        from inkecho.platform.hybrid_keyboard import HybridKeyboardInput

        class Native:
            connected = authorized = True

            async def connect(self):
                pass

            async def authorize(self, parent_window=""):
                pass

            async def aclose(self):
                pass

        inputs = HybridKeyboardInput(native=Native(), x11=keyboard)
    else:
        inputs = keyboard
    monkeypatch.setattr("inkecho.app.keyboard_for_desktop", lambda: inputs)
    monkeypatch.setenv("DISPLAY", ":pure-test-only")
    monkeypatch.setattr(module, "desktop", lambda _scope: {"pure_test": True})
    browsers = []

    class Browser:
        def __init__(self, root, *, field, platform):
            self.__dict__.update(fixture(driver, 21 + len(browsers)).__dict__)
            self.errors = []
            browsers.append(self)

        def start(self, *, reviewed):
            assert reviewed
            driver.pid = self.process.pid
            driver.text[driver.pid] = ""

        def close(self):
            assert driver.closed
            return 0

    monkeypatch.setattr(module, "NaturalOwnedBrowser", Browser)
    args = SimpleNamespace(
        work_root=tmp_path / "exclusive", mode=mode, wait_ms=40, scope=scope
    )
    report = {"passed": False}
    asyncio.run(module.run(args, report))
    assert report["passed"]
    assert report["saved_wait_ms"] == report["session_wait_ms"] == 40
    assert report["mapping_to_press"]
    assert report["counts"]["guard_rejections"] == 0
    if mode == "cancel":
        assert report["confirmed_characters"] == 8
    if mode in {"currentcursor", "currentcursor-textareas"}:
        assert len(browsers) == 2
