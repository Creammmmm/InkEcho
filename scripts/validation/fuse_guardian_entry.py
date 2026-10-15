"""Test-only -m inkecho replacement for an owned private FUSE runtime probe.

This is not an application entry point and is never copied into the AppImage.
"""

import asyncio
import hashlib
import importlib
import json
import os
import sys
import time
from pathlib import Path


def write_json(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value))
    temporary.replace(path)


def validate_environment():
    root = Path(os.environ.get("INKECHO_FUSE_PROBE_ROOT", "/")).resolve()
    appdir = Path(os.environ.get("APPDIR", "/")).resolve()
    original = sys.orig_argv
    if (
        os.environ.get("INKECHO_FUSE_PROBE") != "private-parent-death-v1"
        or root.parent != Path("/tmp")
        or not root.name.startswith("inkecho-isolated-keymap-")
        or os.environ.get("XDG_RUNTIME_DIR") != str(root / "runtime")
        or os.environ.get("WAYLAND_DISPLAY") != "inkecho-isolated-keymap"
        or not os.environ.get("DBUS_SESSION_BUS_ADDRESS")
        or os.environ.get("DISPLAY")
        or "-m" not in original
        or original[original.index("-m") + 1 :] != ["inkecho"]
        or not Path(sys.executable).resolve().is_relative_to(appdir)
        or Path.cwd().resolve() != root / "entry-shim"
    ):
        raise RuntimeError("private_fuse_entry_precondition_failed")
    mounts = [
        line.split()
        for line in Path("/proc/self/mountinfo").read_text().splitlines()
        if line.split()[4] == str(appdir)
    ]
    if len(mounts) != 1 or not mounts[0][mounts[0].index("-") + 1].startswith("fuse"):
        raise RuntimeError("actual_fuse_mount_required")
    # The standard -m cwd lookup selected this external test shim. Imports below
    # must resolve only to the actual mounted package, never this shim or source.
    sys.path[:] = [
        str(appdir / "packages"),
        *[path for path in sys.path if path and Path(path).resolve() != Path.cwd()],
    ]
    modules = {}
    for name in (
        "inkecho",
        "inkecho.platform.keyboard",
        "inkecho.platform.eis",
        "inkecho.platform.wayland_keymap",
        "inkecho.platform.wayland_worker",
        "inkecho.platform.wayland_keyboard",
    ):
        module = importlib.import_module(name)
        path = Path(module.__file__).resolve()
        if not path.is_relative_to(appdir / "packages" / "inkecho"):
            raise RuntimeError("mounted_module_source_mismatch")
        modules[name] = {
            "path": str(path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    return root, appdir, modules


async def run(root, appdir, modules):
    from inkecho.platform.wayland_keyboard import WaylandKeyboardInput

    workdir = root / "worker-cwd"
    workdir.mkdir(exist_ok=True)

    async def spawn(*command, **options):
        return await asyncio.create_subprocess_exec(*command, cwd=workdir, **options)

    inputs = WaylandKeyboardInput(spawn=spawn)
    await inputs.connect()
    await inputs.authorize()
    write_json(root / "fuse-parent-authorized.json", {"parent_pid": os.getpid()})
    readiness_deadline = time.monotonic() + 10
    while not (root / "fuse-parent-go.json").exists():
        if time.monotonic() >= readiness_deadline:
            await inputs.aclose()
            raise RuntimeError("owned_fixture_readiness_timeout")
        await asyncio.sleep(0.025)
    request = inputs._request
    keys = 0

    async def hold_after_first_ack(operation, **fields):
        nonlocal keys
        response = await request(operation, **fields)
        if operation == "key":
            keys += 1
            if keys == 1:
                write_json(
                    root / "fuse-parent-ready.json",
                    {
                        "parent_pid": os.getpid(),
                        "guardian_pid": inputs._process.pid,
                        "appdir": str(appdir),
                        "python": str(Path(sys.executable).resolve()),
                        "production_modules": modules,
                        "key_acknowledgements": keys,
                        "test_entry_replaces_gui_main": True,
                    },
                )
                await asyncio.Event().wait()  # Supervisor kills only this owned parent.
        return response

    inputs._request = hold_after_first_ack
    try:
        await inputs.insert("中不得继续", lambda: True, deadline=time.monotonic() + 30)
    finally:
        await inputs.aclose()


def main():
    root, appdir, modules = validate_environment()
    asyncio.run(run(root, appdir, modules))


if __name__ == "__main__":
    main()
