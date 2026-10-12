#!/usr/bin/env python3
"""Production input checks in a separate headless GNOME Wayland compositor.

The private bus, display, settings and test documents never use the user's desktop.
GNOME Shell, GTK 3 introspection and the development environment are required.
"""

import asyncio
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from inkecho.platform.accessibility import AccessibilityInput, InputUnavailable

SAMPLE = "你好 InkEcho，世界！ café Ω 😀\n第二行。"


async def inside(root: Path):
    backend = AccessibilityInput()
    children = []
    with (root / "compositor.log").open("w") as log:
        try:
            compositor = subprocess.Popen(
                [
                    "gnome-shell",
                    "--headless",
                    "--mode=inkecho-test",
                    "--wayland",
                    "--no-x11",
                    "--wayland-display=inkecho-test",
                    "--virtual-monitor=1024x768",
                ],
                stdout=log,
                stderr=log,
            )
            children.append(compositor)
            for _ in range(100):
                if (root / "runtime/inkecho-test").exists():
                    break
                if compositor.poll() is not None:
                    raise RuntimeError("Isolated GNOME compositor did not start")
                await asyncio.sleep(0.1)
            await asyncio.sleep(2)
            output = root / "received.json"
            fixture = subprocess.Popen(
                [
                    "/usr/bin/python3",
                    str(Path(__file__).with_name("wayland_editor_fixture.py")),
                    str(output),
                ],
                stdout=log,
                stderr=log,
            )
            children.append(fixture)
            await backend.connect()
            target = None
            for _ in range(60):
                try:
                    target = await backend.capture_target()
                    break
                except InputUnavailable:
                    await asyncio.sleep(0.2)
            if target is None:
                raise RuntimeError("Isolated Wayland fixture did not gain safe focus")
            process_id = (
                await backend._call(
                    ("org.freedesktop.DBus", "/org/freedesktop/DBus"),
                    "org.freedesktop.DBus",
                    "GetConnectionUnixProcessID",
                    "s",
                    [target.address[0]],
                )
            )[0]
            assert process_id == fixture.pid, "Refusing any other input target"
            await backend.inject(target, SAMPLE, lambda: True)
            await asyncio.sleep(0.2)
            assert json.loads(output.read_text()) == SAMPLE
            target = await backend.capture_target()
            try:
                await backend.inject(target, "NEVER_INSERT_CANCELLED", lambda: False)
            except InputUnavailable:
                pass
            else:
                raise AssertionError("Cancelled operation was accepted")
            assert json.loads(output.read_text()) == SAMPLE
            print(
                json.dumps(
                    {
                        "session": "isolated headless GNOME Wayland",
                        "exact_unicode": True,
                        "cancelled_unchanged": True,
                        "native_user_desktop_test": False,
                    }
                ),
                flush=True,
            )
        finally:
            backend.close()
            for child in reversed(children):
                if child.poll() is None:
                    child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--inside":
        root = Path(sys.argv[2])
        if os.environ.get("WAYLAND_DISPLAY") != "inkecho-test":
            raise SystemExit("A dedicated Wayland display is required")
        if os.environ.get("XDG_RUNTIME_DIR") != str(root / "runtime"):
            raise SystemExit("A private runtime directory is required")
        asyncio.run(asyncio.wait_for(inside(root), timeout=35))
        return
    with tempfile.TemporaryDirectory(prefix="inkecho-gnome-wayland-") as folder:
        root = Path(folder)
        env = dict(os.environ)
        for key in (
            "DISPLAY",
            "SESSION_MANAGER",
            "XDG_SESSION_ID",
            "AT_SPI_BUS_ADDRESS",
        ):
            env.pop(key, None)
        for variable, name in (
            ("XDG_RUNTIME_DIR", "runtime"),
            ("XDG_CONFIG_HOME", "config"),
            ("XDG_DATA_HOME", "data"),
            ("XDG_CACHE_HOME", "cache"),
            ("XDG_STATE_HOME", "state"),
        ):
            (root / name).mkdir(mode=0o700)
            env[variable] = str(root / name)
        env.update(
            WAYLAND_DISPLAY="inkecho-test",
            GDK_BACKEND="wayland",
            QT_QPA_PLATFORM="wayland",
            XDG_SESSION_TYPE="wayland",
            GSETTINGS_BACKEND="memory",
        )
        modes = root / "data/gnome-shell/modes"
        modes.mkdir(parents=True)
        (modes / "inkecho-test.json").write_text(
            json.dumps({"parentMode": "user", "hasOverview": False})
        )
        env["XDG_DATA_DIRS"] = str(root / "data") + ":/usr/local/share:/usr/share"
        applications = root / "data/applications"
        applications.mkdir()
        (applications / "io.github.Creammmmm.InkEcho.InputFixture.desktop").write_text(
            "[Desktop Entry]\nType=Application\nName=InkEcho input fixture\n"
            "Exec=true\nStartupNotify=true\n"
        )
        result = subprocess.run(
            ["dbus-run-session", "--", sys.executable, __file__, "--inside", str(root)],
            env=env,
            timeout=60,
        )
        if result.returncode:
            print((root / "compositor.log").read_text()[-4000:], file=sys.stderr)
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
