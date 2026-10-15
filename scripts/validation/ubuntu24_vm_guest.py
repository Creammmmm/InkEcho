"""Run only inside the new Noble KVM guest and its actual GDM login session.

May be sent on stdin through the lab controller's loopback SSH. Read the new
guest's GNOME environment, retaining/outputting only eight whitelisted fields;
never inherit SSH's graphical identity or read a user credential store.
"""

import argparse
import hashlib
import json
import os
import platform
import re
import stat
import subprocess
import tempfile
import time
from pathlib import Path

INPUT = Path("/mnt/input")
OUTPUT = Path("/mnt/output")
RUNTIME = Path.home() / "inkecho-a10-runtime"
EXPECTED_SHA256 = "5c515dd0e3ceb8eb910baa45f392d8be28bfda109c5e1d59865e5a0733b7d55a"
WHITELIST = {
    "DISPLAY",
    "WAYLAND_DISPLAY",
    "XAUTHORITY",
    "DBUS_SESSION_BUS_ADDRESS",
    "XDG_RUNTIME_DIR",
    "XDG_SESSION_ID",
    "XDG_SESSION_TYPE",
    "XDG_CURRENT_DESKTOP",
}
NATIVE_CHECK = """
import asyncio, json, xml.etree.ElementTree as ET
from dbus_next import Message, MessageType
from dbus_next.aio import MessageBus
from inkecho.platform.wayland_keyboard import WaylandKeyboardInput
from inkecho.platform.keyboard import KeyboardError


async def main():
    report = {
        "clipboard_requested": False,
        "input_method_requested": False,
        "text_input_requested": False,
    }
    bus = await MessageBus(negotiate_unix_fd=True).connect()
    service = "org.gnome.Mutter.RemoteDesktop"
    interface = service + ".Session"
    reply = await bus.call(
        Message(
            destination=service,
            path="/org/gnome/Mutter/RemoteDesktop",
            interface=service,
            member="CreateSession",
        )
    )
    if reply.message_type == MessageType.ERROR:
        raise RuntimeError("session_creation_failed")
    path = reply.body[0]
    try:
        reply = await bus.call(
            Message(
                destination=service,
                path=path,
                interface="org.freedesktop.DBus.Introspectable",
                member="Introspect",
            )
        )
        if reply.message_type == MessageType.ERROR:
            raise RuntimeError("introspection_failed")
        node = next(
            x
            for x in ET.fromstring(reply.body[0]).findall("interface")
            if x.get("name") == interface
        )
        methods = {x.get("name") for x in node.findall("method")}
        properties = {x.get("name") for x in node.findall("property")}
        report.update(
            set_keymap="SetKeymap" in methods,
            connect_to_eis="ConnectToEIS" in methods,
            notify_keycode="NotifyKeyboardKeycode" in methods,
            notify_keysym="NotifyKeyboardKeysym" in methods,
            keymap_capabilities="KeymapCapabilities" in properties,
        )
    finally:
        await bus.call(
            Message(destination=service, path=path, interface=interface, member="Stop")
        )
        bus.disconnect()
    inputs = WaylandKeyboardInput()
    report["worker_connected"] = False
    report["worker_authorized"] = False
    try:
        await inputs.connect()
        report["worker_connected"] = True
        await inputs.authorize()
        report["worker_authorized"] = True
    except KeyboardError as error:
        report["worker_code"] = error.code
    finally:
        try:
            await inputs.aclose()
            report["worker_cleanup_completed"] = True
        except KeyboardError as error:
            report["worker_cleanup_completed"] = False
            report["worker_cleanup_code"] = error.code
    print(json.dumps(report))


asyncio.run(main())
"""


def checked(command, **options):
    return subprocess.run(command, check=True, **options)


def text(command):
    return checked(command, capture_output=True, text=True, timeout=5).stdout.strip()


def desktop():
    release = platform.freedesktop_os_release()
    virtualization = text(["systemd-detect-virt", "--vm"])
    if (
        release.get("ID") != "ubuntu"
        or release.get("VERSION_ID") != "24.04"
        or virtualization not in {"kvm", "qemu"}
        or os.getuid() != 1000
    ):
        raise RuntimeError("actual_disposable_noble_vm_required")
    sessions = []
    for line in text(["loginctl", "list-sessions", "--no-legend"]).splitlines():
        fields = line.split()
        if len(fields) < 2 or fields[1] != str(os.getuid()):
            continue
        properties = dict(
            line.split("=", 1)
            for line in text(["loginctl", "show-session", fields[0]]).splitlines()
            if "=" in line
        )
        if (
            properties.get("Type") in {"x11", "wayland"}
            and properties.get("Active") == "yes"
        ):
            sessions.append((fields[0], properties))
    if len(sessions) != 1:
        raise RuntimeError("exactly_one_actual_graphical_session_required")
    session, properties = sessions[0]
    if properties.get("Name") != "inkecho" or properties.get("User") != "1000":
        raise RuntimeError("unexpected_graphical_session_owner")
    pids = text(["pgrep", "-u", str(os.getuid()), "-x", "gnome-shell"]).splitlines()
    if len(pids) != 1:
        raise RuntimeError("exactly_one_guest_gnome_shell_required")
    source = (Path("/proc") / pids[0] / "environ").read_bytes()
    observed = {}
    for entry in source.split(b"\0"):
        key, separator, value = entry.partition(b"=")
        if separator and key.decode() in WHITELIST:
            observed[key.decode()] = value.decode()
    if not observed.get("DBUS_SESSION_BUS_ADDRESS") or not observed.get(
        "XDG_RUNTIME_DIR"
    ):
        raise RuntimeError("graphical_session_environment_incomplete")
    activation_env = dict(os.environ, **observed)
    activation = checked(
        ["systemctl", "--user", "show-environment"],
        env=activation_env,
        capture_output=True,
        text=True,
        timeout=5,
    ).stdout
    # The compositor creates its own display after its process environment was
    # formed; its real client addresses are exported to user-service activation.
    for line in activation.splitlines():
        key, separator, value = line.partition("=")
        if separator and key in {"DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY"}:
            observed.setdefault(key, value)
    if properties["Type"] == "x11" and (
        not observed.get("DISPLAY") or observed.get("WAYLAND_DISPLAY")
    ):
        raise RuntimeError("graphical_x11_environment_mismatch")
    if properties["Type"] == "wayland" and not observed.get("WAYLAND_DISPLAY"):
        raise RuntimeError("graphical_wayland_environment_mismatch")
    if properties["Type"] == "wayland":
        runtime = Path(observed["XDG_RUNTIME_DIR"]).resolve(strict=True)
        socket = Path(observed["WAYLAND_DISPLAY"])
        socket = socket if socket.is_absolute() else runtime / socket
        socket = socket.resolve(strict=True)
        metadata = socket.stat()
        if (
            not socket.is_relative_to(runtime)
            or not stat.S_ISSOCK(metadata.st_mode)
            or metadata.st_uid != os.getuid()
        ):
            raise RuntimeError("guest_wayland_socket_ownership_mismatch")
    env = dict(os.environ)
    for key in WHITELIST:
        env.pop(key, None)
    env.update(observed)
    # These values come from this actual graphical logind session, not SSH.
    env.update(
        XDG_SESSION_ID=session,
        XDG_SESSION_TYPE=properties["Type"],
        GTK_IM_MODULE="gtk-im-context-simple",
        QT_IM_MODULE="compose",
        XMODIFIERS="@im=none",
        LIBGL_ALWAYS_SOFTWARE="1",
    )
    metadata = {
        "os": platform.freedesktop_os_release()["PRETTY_NAME"],
        "kernel": platform.release(),
        "virtualization": virtualization,
        "session_id": session,
        "session_type": properties["Type"],
        "session_locked_hint": properties.get("LockedHint"),
        "session_idle_hint": properties.get("IdleHint"),
        "desktop": properties.get("Desktop"),
        "uid": os.getuid(),
        "gnome_shell_pid": int(pids[0]),
        "gnome_shell_version": text(["gnome-shell", "--version"]),
        "graphical_environment_sources": [
            "own_gnome_shell_process",
            "own_user_service_activation",
        ],
        "target_input_environment": {
            key: env[key] for key in ["GTK_IM_MODULE", "QT_IM_MODULE", "XMODIFIERS"]
        },
    }
    return env, metadata


def package_environment(env):
    artifact = INPUT / "InkEcho.AppImage"
    with artifact.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != EXPECTED_SHA256:
            raise RuntimeError("unexpected_preview_artifact")
    appdir = RUNTIME / "squashfs-root"
    if not appdir.exists():
        RUNTIME.mkdir(mode=0o700, exist_ok=True)
        with (OUTPUT / "appimage-extract.log").open("w") as log:
            checked([str(artifact), "--appimage-extract"], cwd=RUNTIME, stdout=log)
    env = dict(
        env,
        APPDIR=str(appdir),
        PYTHONHOME=str(appdir / "usr"),
        PYTHONPATH=str(appdir / "packages"),
        PYTHONNOUSERSITE="1",
        QT_PLUGIN_PATH=str(appdir / "packages/PySide6/Qt/plugins"),
        LD_LIBRARY_PATH=str(appdir / "usr/lib/inkecho"),
    )
    return appdir, env


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=[
            "identity",
            "native-preflight",
            "ui",
            "keyboard-phase0",
            "keyboard40",
            "keyboard20",
            "keyboard-cancel",
            "keyboard-browser-phase0",
            "keyboard-browser40",
            "keyboard-browser20",
            "fixture-diagnose",
            "wm-diagnose",
            "pipeline40",
            "pipeline20",
        ],
    )
    parser.add_argument("--target", choices=["gtk", "vte"])
    parser.add_argument("--label")
    parser.add_argument("--probe-generation", choices=["r3", "r4"], default="r3")
    args = parser.parse_args()
    if args.label and not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", args.label):
        parser.error("Use a bounded filename-safe evidence label")
    env, report = desktop()
    if (
        args.action not in {"identity", "wm-diagnose"}
        and report.get("session_locked_hint") == "yes"
    ):
        raise RuntimeError("guest_graphical_session_locked")
    if args.action == "identity":
        print(json.dumps(report))
        return
    appdir, env = package_environment(env)
    if args.action == "native-preflight":
        if report["session_type"] != "wayland":
            raise RuntimeError("actual_wayland_session_required")
        result = subprocess.run(
            [str(appdir / "usr/bin/python3"), "-c", NATIVE_CHECK],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        (OUTPUT / "native-preflight-child.log").write_text(result.stderr)
        if result.returncode:
            report["native_check_exit"] = result.returncode
            report["native_preflight_completed"] = False
            (OUTPUT / "native-preflight-failed.json").write_text(
                json.dumps(report, indent=2) + "\n"
            )
            print(json.dumps(report))
            raise SystemExit(1)
        report.update(json.loads(result.stdout))
    elif args.action.startswith("pipeline"):
        if report["session_type"] != "x11":
            raise RuntimeError("actual_xorg_session_required")
        label = args.action + (f"-{args.label}" if args.label else "")
        command = [
            str(appdir / "usr/bin/python3"),
            str(
                INPUT / "validation-r3/scripts/validation/performance_package_probe.py"
            ),
            "--package-root",
            str(appdir / "packages"),
            "--owned-ubuntu24-vm-x11",
            "--xdotool",
            "/usr/bin/xdotool",
            "--output",
            str(OUTPUT / f"{label}.json"),
        ]
        if args.action == "pipeline40":
            command.extend(["--pacing", "0.04"])
        with (OUTPUT / f"{label}.log").open("x") as log:
            checked(
                command,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=60,
            )
        report["pipeline_completed"] = True
    elif args.action == "wm-diagnose":
        client_env = dict(env)
        for key in ("PYTHONHOME", "PYTHONPATH", "LD_LIBRARY_PATH", "QT_PLUGIN_PATH"):
            client_env.pop(key, None)
        queries = {
            "root_window_properties": [
                "xprop",
                "-root",
                "_NET_SUPPORTING_WM_CHECK",
                "_NET_ACTIVE_WINDOW",
                "_NET_CLIENT_LIST",
            ],
            "x_input_focus": ["xdotool", "getwindowfocus"],
            "xorg_process": ["pgrep", "-a", "-x", "Xorg"],
            "gnome_process": [
                "ps",
                "-p",
                str(report["gnome_shell_pid"]),
                "-o",
                "pid=,stat=,etime=,comm=",
            ],
            "screensaver_active": [
                "gdbus",
                "call",
                "--session",
                "--dest",
                "org.gnome.ScreenSaver",
                "--object-path",
                "/org/gnome/ScreenSaver",
                "--method",
                "org.gnome.ScreenSaver.GetActive",
            ],
            "idle_milliseconds": [
                "gdbus",
                "call",
                "--session",
                "--dest",
                "org.gnome.Mutter.IdleMonitor",
                "--object-path",
                "/org/gnome/Mutter/IdleMonitor/Core",
                "--method",
                "org.gnome.Mutter.IdleMonitor.GetIdletime",
            ],
        }
        report["diagnostics"] = {}
        for name, command in queries.items():
            result = subprocess.run(
                command, env=client_env, capture_output=True, text=True, timeout=5
            )
            report["diagnostics"][name] = {
                "exit": result.returncode,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
            }
    elif args.action == "fixture-diagnose":
        client_env = dict(env)
        for key in ("PYTHONHOME", "PYTHONPATH", "LD_LIBRARY_PATH", "QT_PLUGIN_PATH"):
            client_env.pop(key, None)
        report["fixtures"] = []
        for target in ["gtk", "vte"]:
            with tempfile.TemporaryDirectory(prefix="inkecho-vm-diagnostic-") as name:
                output = Path(name) / "state.json"
                with (OUTPUT / f"fixture-{target}-stderr.log").open("w") as log:
                    process = subprocess.Popen(
                        [
                            "/usr/bin/python3",
                            str(
                                INPUT
                                / "scripts/validation/keyboard_latency_probe_vm.py"
                            ),
                            "--fixture",
                            target,
                            "--output",
                            str(output),
                        ],
                        env=client_env,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                    )
                    began = time.monotonic()
                    windows = []
                    try:
                        while time.monotonic() - began < 10:
                            result = subprocess.run(
                                [
                                    "xdotool",
                                    "search",
                                    "--onlyvisible",
                                    "--pid",
                                    str(process.pid),
                                ],
                                env=client_env,
                                capture_output=True,
                                text=True,
                                timeout=3,
                            )
                            windows = result.stdout.splitlines()
                            if process.poll() is not None or (
                                windows and output.exists()
                            ):
                                break
                            time.sleep(0.1)
                        report["fixtures"].append(
                            {
                                "target": target,
                                "pid": process.pid,
                                "exit_before_cleanup": process.poll(),
                                "visible_windows": windows,
                                "ready_file": output.exists(),
                                "seconds_to_observation": round(
                                    time.monotonic() - began, 3
                                ),
                                "no_text_requested": True,
                            }
                        )
                    finally:
                        if process.poll() is None:
                            process.terminate()
                            try:
                                process.wait(timeout=3)
                            except subprocess.TimeoutExpired:
                                process.kill()
                                process.wait()
    elif args.action.startswith("keyboard"):
        if report["session_type"] != "x11":
            raise RuntimeError("actual_xorg_session_required")
        probe = INPUT / (
            f"scripts/validation/keyboard_latency_probe_vm_{args.probe_generation}.py"
        )
        command = [
            str(appdir / "usr/bin/python3"),
            str(probe),
            "--environment",
            "ubuntu24-vm-x11",
            "--qt-loop",
            "--xdotool",
            "/usr/bin/xdotool",
            "--repeat",
            "1"
            if args.action in {"keyboard-phase0", "keyboard-browser-phase0"}
            else "5",
            "--targets",
            "gtk",
        ]
        if args.action.startswith("keyboard-browser"):
            command[-1] = "chrome-textarea"
            command.append("chrome-contenteditable")
        elif args.target:
            command[-1] = args.target
        elif args.action != "keyboard-cancel":
            command.append("vte")
        if args.action in {
            "keyboard-phase0",
            "keyboard40",
            "keyboard-browser-phase0",
            "keyboard-browser40",
        }:
            command.extend(["--pacing", "0.04", "0.04", "0.04"])
        elif args.action == "keyboard-cancel":
            command.extend(["--cancel-after", "12"])
        label = args.action + (f"-{args.target}" if args.target else "")
        if args.label:
            label += f"-{args.label}"
        command.extend(["--output", str(OUTPUT / f"{label}.json")])
        with (OUTPUT / f"{label}.log").open("x") as log:
            checked(
                command,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=150,
            )
        with probe.open("rb") as stream:
            report["probe_sha256"] = hashlib.file_digest(stream, "sha256").hexdigest()
        report["benchmark_completed"] = True
    else:
        screenshots = OUTPUT / f"ui-{report['session_type']}"
        profile = Path.home() / f"ui-profile-{report['session_type']}"
        with (OUTPUT / f"ui-{report['session_type']}.log").open("w") as log:
            checked(
                [
                    str(appdir / "AppRun"),
                    "--config-dir",
                    str(profile / "config"),
                    "--data-dir",
                    str(profile / "data"),
                    "--screenshot-dir",
                    str(screenshots),
                    "--quit-after",
                    "3",
                ],
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=30,
            )
        report["screenshots"] = len(list(screenshots.glob("page-*.png")))
        report["normal_exit"] = True
    report["artifact_sha256"] = EXPECTED_SHA256
    label = args.action + (f"-{args.target}" if args.target else "")
    if args.label:
        label += f"-{args.label}"
    (OUTPUT / f"{label}-{report['session_type']}.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(json.dumps(report))


if __name__ == "__main__":
    main()
