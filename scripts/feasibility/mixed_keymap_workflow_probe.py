"""Private native→XWayland→native production-worker check; never use host UI."""

import asyncio
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import nested_keymap_probe as launcher
from dbus_next import Message, MessageType
from dbus_next.aio import MessageBus
from isolated_browser_fixture import parent_pid, write_json
from production_keymap_workflow import run_worker

SAMPLE = "你好 InkEcho，世界！ café Ω\n第二行。"
DESTINATION = launcher.DESTINATION
SOCKET = launcher.SOCKET


class PrivateDesktop:
    """Reuse only the strict private launcher's owned compositor environment."""

    def __init__(self, root):
        self.root = root.resolve()
        self.shell = self.bus = self.session = None

    async def call(self, path, interface, member, signature="", body=None):
        response = await asyncio.wait_for(
            self.bus.call(
                Message(
                    destination=DESTINATION,
                    path=path,
                    interface=interface,
                    member=member,
                    signature=signature,
                    body=body or [],
                )
            ),
            5,
        )
        if response.message_type == MessageType.ERROR:
            raise RuntimeError("private_" + member + "_failed")
        return response.body

    async def verify_owner(self):
        response = await self.bus.call(
            Message(
                destination="org.freedesktop.DBus",
                path="/org/freedesktop/DBus",
                interface="org.freedesktop.DBus",
                member="GetConnectionUnixProcessID",
                signature="s",
                body=[DESTINATION],
            )
        )
        if response.body != [self.shell.pid] or self.shell.poll() is not None:
            raise RuntimeError("private_compositor_owner_mismatch")

    async def keysym(self, value, pressed):
        await self.verify_owner()
        await self.call(
            self.session,
            DESTINATION + ".Session",
            "NotifyKeyboardKeysym",
            "ub",
            [value, pressed],
        )

    async def tap(self, value):
        try:
            await self.keysym(value, True)
        finally:
            await self.keysym(value, False)

    async def start(self):
        root = self.root
        if (
            root.parent != Path("/tmp")
            or not root.name.startswith("inkecho-isolated-keymap-")
            or os.environ.get("XDG_RUNTIME_DIR") != str(root / "runtime")
            or not os.environ.get("DBUS_SESSION_BUS_ADDRESS")
            or os.environ.get("DISPLAY")
            or os.environ.get("WAYLAND_DISPLAY")
        ):
            raise RuntimeError("private_environment_required")
        subprocess.run(
            [
                "gsettings",
                "set",
                "org.gnome.desktop.input-sources",
                "sources",
                "[('xkb', 'us')]",
            ],
            check=True,
            timeout=3,
        )
        self.bus = await MessageBus(negotiate_unix_fd=True).connect()
        with (root / "shell.log").open("wb") as log:
            self.shell = subprocess.Popen(
                [
                    "gnome-shell",
                    "--wayland",
                    "--headless",
                    "--virtual-monitor",
                    "1024x768",
                    "--wayland-display",
                    SOCKET,
                ],
                stdout=log,
                stderr=log,
            )
        for _ in range(150):
            if self.shell.poll() is not None:
                raise RuntimeError("private_compositor_exited")
            if (root / "runtime" / SOCKET).is_socket():
                try:
                    await self.verify_owner()
                    break
                except RuntimeError:
                    pass
            await asyncio.sleep(0.1)
        else:
            raise RuntimeError("private_compositor_timeout")
        self.session = (
            await self.call(
                "/org/gnome/Mutter/RemoteDesktop", DESTINATION, "CreateSession"
            )
        )[0]
        await self.call(self.session, DESTINATION + ".Session", "Start")
        await self.tap(0xFFE1)  # Bootstrap headless keyboard before any fixture exists.
        os.environ["WAYLAND_DISPLAY"] = SOCKET
        await asyncio.sleep(0.5)

    async def close(self):
        if self.session:
            try:
                await self.call(self.session, DESTINATION + ".Session", "Stop")
            except (RuntimeError, OSError):
                pass
        if self.bus:
            self.bus.disconnect()
        if self.shell and self.shell.poll() is None:
            self.shell.terminate()
            await asyncio.to_thread(self.shell.wait, 5)


async def metadata(observer):
    state, data = await observer.snapshot(refresh=True)
    return {
        "map_sha256": hashlib.sha256(data).hexdigest(),
        **{key: state[key] for key in ("group", "depressed", "latched", "locked")},
    }


async def production_with_test_settle(sample, after_character, delay):
    x_diagnostic = bool(os.environ.get("INKECHO_MIXED_XMAP_DIAGNOSTIC"))
    release_delay = float(os.environ.get("INKECHO_MIXED_RELEASE_SETTLE", "0"))
    if not 0 <= release_delay <= 0.5:
        raise RuntimeError("invalid_release_settle")
    if not delay and not x_diagnostic and not release_delay:
        return await run_worker(sample, after_character=after_character)
    original_spawn = asyncio.create_subprocess_exec

    async def spawn(*command, **options):
        if command[1:] == ("-m", "inkecho.platform.wayland_worker"):
            code = (
                "import asyncio\n"
                "from inkecho.platform import wayland_worker as worker\n"
                "original = worker.MutterSession.set_map\n"
                "async def delayed(self, *args, **kwargs):\n"
                "    result = await original(self, *args, **kwargs)\n"
                f"    await asyncio.sleep({delay!r})\n"
                "    return result\n"
                "worker.MutterSession.set_map = delayed\n"
                "asyncio.run(worker.main())\n"
            )
            if release_delay:
                code = code.replace(
                    "asyncio.run(worker.main())",
                    "original_key = worker.MutterSession.key\n"
                    "async def delayed_key(self, code, pressed, *, newline=False):\n"
                    "    result = await original_key(\n"
                    "        self, code, pressed, newline=newline)\n"
                    "    if not pressed:\n"
                    f"        await asyncio.sleep({release_delay!r})\n"
                    "    return result\n"
                    "worker.MutterSession.key = delayed_key\n"
                    "asyncio.run(worker.main())",
                )
            if x_diagnostic:
                code = code.replace(
                    "asyncio.run(worker.main())",
                    "from private_xmap_delivery_diagnostic import install\n"
                    "install(worker)\nasyncio.run(worker.main())",
                )
                options["env"]["PYTHONPATH"] += os.pathsep + str(
                    Path(__file__).parent.resolve()
                )
            command = (command[0], "-c", code)
        return await original_spawn(*command, **options)

    asyncio.create_subprocess_exec = spawn
    try:
        return await run_worker(sample, after_character=after_character)
    finally:
        asyncio.create_subprocess_exec = original_spawn


async def inner(root, *_args, **_kwargs):
    from inkecho.platform.wayland_worker import MutterSession

    desktop = PrivateDesktop(root)
    fixture = observer = None
    report = {
        "passed": False,
        "isolated": True,
        "host_desktop_used": False,
        "same_transaction": True,
        "sample_codepoints": len(SAMPLE),
    }
    delay = float(os.environ.get("INKECHO_MIXED_MAP_SETTLE", "0"))
    if not 0 <= delay <= 0.5:
        raise RuntimeError("invalid_test_settle")
    report["test_only_map_settle_seconds"] = delay
    report["test_only_release_settle_seconds"] = float(
        os.environ.get("INKECHO_MIXED_RELEASE_SETTLE", "0")
    )
    if os.environ.get("INKECHO_MIXED_NO_X_DIAGNOSTIC") and not os.environ.get(
        "INKECHO_MIXED_BASELINE"
    ):
        raise RuntimeError("no_x_observation_only_allowed_for_failing_baseline")
    try:
        await desktop.start()
        output, state_path = root / "mixed-text.json", root / "mixed-state.json"
        activation = root / "mixed-activation.json"
        environment = dict(os.environ, GDK_BACKEND="wayland", NO_AT_BRIDGE="1")
        for key in ("PYTHONHOME", "PYTHONPATH", "LD_LIBRARY_PATH"):
            environment.pop(key, None)
        with (root / "fixture.log").open("wb") as log:
            fixture = subprocess.Popen(
                [
                    "/usr/bin/python3",
                    str(
                        Path(__file__).with_name("isolated_lifecycle_editor_fixture.py")
                    ),
                    "--compositor-pid",
                    str(desktop.shell.pid),
                    "--text-output",
                    str(output),
                    "--state-output",
                    str(state_path),
                    "--activate-file",
                    str(activation),
                ],
                env=environment,
                stdout=log,
                stderr=log,
            )

        async def focused(kind, since=0):
            for _ in range(120):
                if fixture.poll() is not None:
                    raise RuntimeError("owned_fixture_exited")
                if state_path.exists():
                    states = json.loads(state_path.read_text())
                    if kind not in states:
                        await asyncio.sleep(0.025)
                        continue
                    state = states[kind]
                    if (
                        state["target_parent_pid"] != fixture.pid
                        or parent_pid(state["target_pid"]) != fixture.pid
                    ):
                        raise RuntimeError("owned_fixture_identity_mismatch")
                    if (
                        state["active"]
                        and state["focused"]
                        and (
                            kind != "xwayland"
                            or state.get(
                                "x_focus_owned",
                                bool(os.environ.get("INKECHO_MIXED_NO_X_DIAGNOSTIC")),
                            )
                        )
                        and state["sampled_at"] > since
                        and time.monotonic() - state["sampled_at"] < 0.25
                    ):
                        return states
                await asyncio.sleep(0.025)
            raise RuntimeError("owned_" + kind + "_focus_unavailable")

        for _ in range(100):
            if state_path.exists():
                break
            if fixture.poll() is not None:
                raise RuntimeError("owned_fixture_start_failed")
            await asyncio.sleep(0.05)
        await desktop.tap(0xFF1B)  # Leave only the private Shell's overview.
        states = await focused("native")
        report["display_backends"] = {"native": states["native"]["display_backend"]}
        report["switch_mechanism"] = "owned_xwayland_window_create_then_close"
        observer = MutterSession()
        await observer.connect()
        await observer.authorize()
        report["before"] = await metadata(observer)
        switches = []

        async def after_character(count):
            report["last_acknowledged_count"] = count
            if count in (5, 10):
                kind = "xwayland" if count == 5 else "native"
                previous = "native" if count == 5 else "xwayland"
                expected = SAMPLE[:5] if count == 5 else SAMPLE[5:10]
                for _ in range(100):
                    if json.loads(output.read_text()).get(previous) == expected:
                        break
                    await asyncio.sleep(0.025)
                else:
                    raise RuntimeError("owned_prefix_before_switch_not_exact")
                switched_at = time.monotonic()
                write_json(activation, {"target": kind, "serial": count})
                states = await focused(kind, switched_at)
                report["display_backends"][kind] = states[kind]["display_backend"]
                switches.append(kind)
                if kind == "xwayland" and os.environ.get("INKECHO_MIXED_BASELINE"):
                    await asyncio.sleep(0.5)
                    await desktop.tap(ord("a"))
                    await asyncio.sleep(0.2)
                    report["baseline_state"] = json.loads(state_path.read_text())
                    raise RuntimeError("test_only_xwayland_baseline_complete")

        report["sent_codepoints"] = await production_with_test_settle(
            SAMPLE, after_character, delay
        )
        await asyncio.sleep(0.2)
        received = json.loads(output.read_text())
        report["native_exact"] = received["native"] == SAMPLE[:5] + SAMPLE[10:]
        report["xwayland_exact"] = received["xwayland"] == SAMPLE[5:10]
        report["received_counts"] = {key: len(value) for key, value in received.items()}
        report["switches"] = switches
        report["after"] = await metadata(observer)
        report["map_and_modifiers_restored"] = report["before"] == report["after"]
        report["passed"] = (
            report["sent_codepoints"] == len(SAMPLE)
            and report["native_exact"]
            and report["xwayland_exact"]
            and switches == ["xwayland", "native"]
            and report["map_and_modifiers_restored"]
        )
    except Exception as error:
        report["error"] = str(error)
        if "state_path" in locals() and state_path.exists():
            report["last_owned_states"] = json.loads(state_path.read_text())
        if "output" in locals() and output.exists():
            report["owned_received_codepoints"] = {
                key: [ord(character) for character in value]
                for key, value in json.loads(output.read_text()).items()
            }
    finally:
        x_diagnostic_path = root / "x-delivery-diagnostic.json"
        if x_diagnostic_path.exists():
            report["test_only_x_map_before_press"] = json.loads(
                x_diagnostic_path.read_text()
            )
        if observer:
            if "before" in report:
                try:
                    report["after_cleanup"] = await metadata(observer)
                    report["cleanup_map_and_modifiers_restored"] = (
                        report["before"] == report["after_cleanup"]
                    )
                except Exception as cleanup_error:
                    report["cleanup_metadata_error"] = type(cleanup_error).__name__
            await observer.close()
        if fixture and fixture.poll() is None:
            fixture.terminate()
            await asyncio.to_thread(fixture.wait, 5)
        await desktop.close()
        print(json.dumps(report, sort_keys=True), flush=True)
    return report["passed"]


if __name__ == "__main__":
    if "--map-settle" in sys.argv:
        index = sys.argv.index("--map-settle")
        os.environ["INKECHO_MIXED_MAP_SETTLE"] = sys.argv[index + 1]
        del sys.argv[index : index + 2]
    # Reuse the existing strict private bus/XDG launcher and cleanup unchanged.
    # Its child re-enters this wrapper; no nested probe file is modified.
    launcher.inner = inner
    launcher.__file__ = __file__
    launcher.main()
