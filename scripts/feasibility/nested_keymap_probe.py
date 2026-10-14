"""Opt-in isolated GNOME experiment: temporary Unicode map and snapshot restore.

Never attach to the caller's bus/display. The outer process creates private XDG
roots and dbus-run-session; the inner helper owns the only compositor it may
mutate. This is a feasibility experiment, not a production permission mechanism.
No clipboard, input method, network, microphone, credentials or user window is used.
The first experiment configures a single US source (plus GNOME locale group)
and does not establish full
modifier-state, concurrent-layout, helper-crash or production restoration safety.
"""

import argparse
import asyncio
import ctypes as c
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

from dbus_next import Message, MessageType, Variant
from dbus_next.aio import MessageBus
from eis_modifier_snapshot import EISModifierObserver, ObserverError
from production_keymap_workflow import run_worker
from wayland_keymap_snapshot import snapshot

SAMPLE = "你好 InkEcho，世界！ café Ω 😀\n第二行。"
DESTINATION = "org.gnome.Mutter.RemoteDesktop"
SOCKET = "inkecho-isolated-keymap"


class GuardStop(Exception):
    pass


def augmented_map(original, sample=None, preferred_code=None, force_empty=False):
    """Append symbols only for unassigned named keycodes; retain all other text."""
    lib = c.CDLL("libxkbcommon.so.0")
    p, u = c.c_void_p, c.c_uint32
    signatures = {
        "xkb_context_new": ([u], p),
        "xkb_context_unref": ([p], None),
        "xkb_keymap_new_from_string": ([p, c.c_char_p, u, u], p),
        "xkb_keymap_unref": ([p], None),
        "xkb_keymap_num_layouts": ([p], u),
        "xkb_keymap_mod_get_index": ([p, c.c_char_p], u),
        "xkb_keymap_min_keycode": ([p], u),
        "xkb_keymap_max_keycode": ([p], u),
        "xkb_keymap_key_get_name": ([p, u], c.c_char_p),
        "xkb_keymap_num_layouts_for_key": ([p, u], u),
        "xkb_keymap_num_levels_for_key": ([p, u, u], u),
        "xkb_keymap_key_get_syms_by_level": ([p, u, u, u, c.POINTER(p)], c.c_int),
    }
    for name, (args, result) in signatures.items():
        function = getattr(lib, name)
        function.argtypes, function.restype = args, result
    context = lib.xkb_context_new(0)
    keymap = lib.xkb_keymap_new_from_string(context, original, 1, 0)
    candidate = None
    try:
        if not keymap:
            raise RuntimeError("original_map_invalid")
        groups = lib.xkb_keymap_num_layouts(keymap)
        # Shell appends the UI-locale group even for the sole configured source.
        # This experiment seeds that sole source at group zero before startup.
        if groups not in (1, 2, 3):
            raise RuntimeError("unexpected_baseline_group_count")
        available, mapped = [], set()
        first = lib.xkb_keymap_min_keycode(keymap)
        last = min(lib.xkb_keymap_max_keycode(keymap), 255)
        for code in range(first, last + 1):
            symbols = []
            for group in range(lib.xkb_keymap_num_layouts_for_key(keymap, code)):
                for level in range(
                    lib.xkb_keymap_num_levels_for_key(keymap, code, group)
                ):
                    values = p()
                    count = lib.xkb_keymap_key_get_syms_by_level(
                        keymap, code, group, level, c.byref(values)
                    )
                    symbols.extend(c.cast(values, c.POINTER(u))[:count])
            mapped.update(symbols)
            name = lib.xkb_keymap_key_get_name(keymap, code)
            if name and not any(symbols):
                available.append((name.decode("ascii"), code))
        if preferred_code is not None:
            available = [item for item in available if item[1] == preferred_code]
        requested = {
            (ord(char) if ord(char) < 256 else 0x01000000 | ord(char))
            for char in (SAMPLE if sample is None else sample)
            if char != "\n"
        }
        missing = sorted(requested if force_empty else requested - mapped)
        if len(available) < len(missing):
            raise RuntimeError("insufficient_empty_keycodes")
        text = original.rstrip(b"\0").decode("utf-8")
        # Generated XKB text uses balanced sections. Do not edit existing entries.
        start = text.index("{", text.index("xkb_symbols"))
        depth, end = 1, start + 1
        while depth:
            depth += (text[end] == "{") - (text[end] == "}")
            end += 1
        additions, allocations = [], []
        for (name, code), keysym in zip(available, missing, strict=False):
            if not re.fullmatch(r"[A-Za-z0-9_]+", name):
                raise RuntimeError("unexpected_key_name")
            additions.append(
                f'    key <{name}> {{ type[Group1]="ONE_LEVEL", '
                f"symbols[Group1]=[ 0x{keysym:08x} ] }};\n"
            )
            allocations.append({"xkb_code": code, "name": name, "keysym": keysym})
        result = (
            text[: end - 1] + "".join(additions) + text[end - 1 :]
        ).encode() + b"\0"
        candidate = lib.xkb_keymap_new_from_string(context, result, 1, 0)
        if not candidate or lib.xkb_keymap_num_layouts(candidate) != groups:
            raise RuntimeError("augmented_map_invalid")
        return (
            result,
            len(missing),
            groups,
            allocations,
            1 << lib.xkb_keymap_mod_get_index(keymap, b"Lock"),
        )
    finally:
        if candidate:
            lib.xkb_keymap_unref(candidate)
        if keymap:
            lib.xkb_keymap_unref(keymap)
        lib.xkb_context_unref(context)


async def inner(
    root,
    restore_policy=False,
    cancel_after=None,
    terminate_after=None,
    target="gtk",
    modifier=None,
    single_slot_bmp=False,
    producer_crash_after=None,
    direct_keycode=False,
    external_map_after=None,
    switch_after=None,
    cancel_during_map=False,
    nonzero_group=False,
    guard_modifiers=False,
    production_worker=False,
    worker_eof_after=None,
):
    root = root.resolve()
    if (
        root.parent != Path("/tmp")
        or not root.name.startswith("inkecho-isolated-keymap-")
        or os.environ.get("XDG_RUNTIME_DIR") != str(root / "runtime")
        or not os.environ.get("DBUS_SESSION_BUS_ADDRESS")
        or os.environ.get("DISPLAY")
        or os.environ.get("WAYLAND_DISPLAY")
    ):
        raise RuntimeError("isolation_precondition_failed")
    stop_requested = asyncio.Event()
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGTERM, stop_requested.set)
    loop.add_signal_handler(signal.SIGINT, stop_requested.set)
    bus = await MessageBus(negotiate_unix_fd=True).connect()
    shell = fixture = observer = producer = None
    held_modifier = None
    before_map_state = None
    baseline_group = 0
    map_applied = False
    modifier_release_task = None
    session_path = foreign_session = None
    foreign_map = None
    report = {
        "target": target,
        "single_slot_bmp": single_slot_bmp,
        "direct_keycode": direct_keycode,
        "modifier_case": modifier,
        "restore_mode": "shell_policy" if restore_policy else "snapshot_fd",
        "isolated": True,
        "real_desktop_mutated": False,
        "input_calls": 0,
        "single_configured_source": not nonzero_group,
        "modifier_restoration_tested": False,
        "concurrent_layout_tested": False,
        "helper_crash_tested": False,
    }

    async def call(path, interface, member, signature="", body=None, fds=None):
        response = await asyncio.wait_for(
            bus.call(
                Message(
                    destination=DESTINATION,
                    path=path,
                    interface=interface,
                    member=member,
                    signature=signature,
                    body=body or [],
                    unix_fds=fds or [],
                )
            ),
            5,
        )
        if response.message_type == MessageType.ERROR:
            raise RuntimeError(f"isolated_{member}_failed")
        return response.body

    async def verify_owner():
        response = await asyncio.wait_for(
            bus.call(
                Message(
                    destination="org.freedesktop.DBus",
                    path="/org/freedesktop/DBus",
                    interface="org.freedesktop.DBus",
                    member="GetConnectionUnixProcessID",
                    signature="s",
                    body=[DESTINATION],
                )
            ),
            2,
        )
        if response.message_type == MessageType.ERROR or response.body != [shell.pid]:
            raise RuntimeError("compositor_owner_mismatch")

    async def map_source():
        result = await call(
            session_path,
            "org.freedesktop.DBus.Properties",
            "Get",
            "ss",
            [DESTINATION + ".Session", "CurrentKeymap"],
        )
        return result[0].value["source"].value

    async def next_map_state(previous):
        # Mutter does not always resend unchanged modifiers when replacing a map.
        # Rebind this metadata-only EIS keyboard to request its actual current state.
        state = await observer.refresh_snapshot(timeout=3)
        if state["device_generation"] <= previous["device_generation"]:
            raise ObserverError("snapshot_timeout")
        return state

    async def set_map(data, target_session=None):
        await verify_owner()
        fd = os.memfd_create("isolated-keymap", os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING)
        try:
            os.write(fd, data)
            os.lseek(fd, 0, os.SEEK_SET)
            await call(
                target_session or session_path,
                DESTINATION + ".Session",
                "SetKeymap",
                "a{sv}",
                [
                    {
                        "keymap-type": Variant("u", 0),
                        "xkb-keymap-format": Variant("u", 1),
                        "xkb-keymap": Variant("h", 0),
                        "xkb-keymap-layout-index": Variant("u", baseline_group),
                        "lock-keymap": Variant("b", False),
                    }
                ],
                [fd],
            )
        finally:
            os.close(fd)

    original = changed = None
    try:
        # Only this private XDG_CONFIG_HOME keyfile is configured. Avoid inherited
        # distribution defaults adding another group to the single-group baseline.
        subprocess.run(
            [
                "gsettings",
                "set",
                "org.gnome.desktop.input-sources",
                "sources",
                "[('xkb', 'us'), ('xkb', 'de')]"
                if nonzero_group
                else "[('xkb', 'us')]",
            ],
            check=True,
            timeout=3,
        )
        with (root / "shell.log").open("wb") as log:
            shell = subprocess.Popen(
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
            if shell.poll() is not None:
                raise RuntimeError("isolated_compositor_exited")
            if (root / "runtime" / SOCKET).exists():
                try:
                    await verify_owner()
                    break
                except RuntimeError:
                    pass
            await asyncio.sleep(0.1)
        else:
            raise RuntimeError("isolated_compositor_timeout")
        session_path = (
            await call("/org/gnome/Mutter/RemoteDesktop", DESTINATION, "CreateSession")
        )[0]
        await call(session_path, DESTINATION + ".Session", "Start")
        # Headless has no physical keyboard. Establish one before any window
        # exists, then release Shift; this never delivers text to a target.
        for pressed in (True, False):
            await verify_owner()
            await call(
                session_path,
                DESTINATION + ".Session",
                "NotifyKeyboardKeysym",
                "ub",
                [0xFFE1, pressed],
            )
        report["bootstrap_key_events"] = 2
        await asyncio.sleep(1.0)
        if modifier is not None:
            response = await bus.call(
                Message(
                    destination=DESTINATION,
                    path=session_path,
                    interface=DESTINATION + ".Session",
                    member="ConnectToEIS",
                    signature="a{sv}",
                    body=[{"device-types": Variant("u", 1)}],
                )
            )
            if response.message_type == MessageType.ERROR:
                raise RuntimeError("isolated_eis_connection_failed")
            fd = response.unix_fds[response.body[0]]
            try:
                observer = EISModifierObserver(fd)
            finally:
                os.close(fd)
            report["initial_modifiers"] = await observer.wait_snapshot()
        original = snapshot(SOCKET)
        if nonzero_group:
            baseline_group = 1
            await set_map(original)
            report["initial_modifiers"] = await next_map_state(
                report["initial_modifiers"]
            )
        changed, slots, groups, allocations, caps_mask = augmented_map(
            original,
            SAMPLE[0] if single_slot_bmp else None,
            132 if single_slot_bmp else None,
            direct_keycode,
        )
        report["synthetic_slot_allocations"] = allocations
        report["xkb_layout_groups"] = groups
        report["baseline_group"] = baseline_group
        report["caps_lock_mask"] = caps_mask
        report["original_sha256"] = hashlib.sha256(original).hexdigest()
        report["added_empty_slots"] = slots
        output = root / "owned-text.json"
        focus_state = root / "owned-state.json"
        env = dict(
            os.environ, WAYLAND_DISPLAY=SOCKET, GDK_BACKEND="wayland", NO_AT_BRIDGE="1"
        )
        for name in ("PYTHONHOME", "PYTHONPATH", "LD_LIBRARY_PATH"):
            env.pop(name, None)
        if target == "gtk":
            fixture_command = [
                "/usr/bin/python3",
                str(Path(__file__).with_name("wayland_editor_fixture.py")),
                str(output),
                str(root / "owned-events.jsonl"),
                str(focus_state),
            ]
        else:
            fixture_command = [
                "/usr/bin/python3",
                str(
                    Path(__file__).with_name(
                        "isolated_browser_fixture.py"
                        if target.startswith("chrome-")
                        else "isolated_terminal_fixture.py"
                    )
                ),
                "--target",
                target,
                "--text-output",
                str(output),
                "--state-output",
                str(focus_state),
            ]
        if target == "vte-xwayland":
            fixture_command.extend(["--compositor-pid", str(shell.pid)])
        if switch_after is not None:
            fixture_command.extend(["--switch-after", str(switch_after)])
        fixture = subprocess.Popen(
            fixture_command,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(100):
            if output.exists():
                break
            await asyncio.sleep(0.05)
        else:
            raise RuntimeError("owned_fixture_unavailable")
        # New Shell sessions start in overview. Escape only on our isolated bus.
        await asyncio.sleep(0.5)
        for pressed in (True, False):
            await verify_owner()
            await call(
                session_path,
                DESTINATION + ".Session",
                "NotifyKeyboardKeysym",
                "ub",
                [0xFF1B, pressed],
            )
        for _ in range(100):
            if focus_state.exists():
                state = json.loads(focus_state.read_text())
                if state.get("active") and state.get("focused"):
                    if target != "gtk":
                        child_pid = state["target_pid"]
                        process_stat = Path(f"/proc/{child_pid}/stat").read_text()
                        parent_pid = int(
                            process_stat[process_stat.rindex(")") + 2 :].split()[1]
                        )
                        expected_parent = (
                            fixture.pid if target.startswith("chrome-") else os.getpid()
                        )
                        if (
                            parent_pid != expected_parent
                            or state["target_parent_pid"] != expected_parent
                            or (target.startswith("vte-") and child_pid != fixture.pid)
                        ):
                            raise RuntimeError("fixture_process_ownership_mismatch")
                        report["native_protocol_evidence"] = state.get(
                            "native_evidence",
                            {
                                "display_type": state.get("native_display"),
                                "target_backend": state.get("target_backend"),
                            },
                        )
                    report["owned_fixture_active_focused"] = True
                    break
            await asyncio.sleep(0.05)
        else:
            raise RuntimeError("isolated_fixture_not_focused")
        if production_worker:
            report.pop("input_calls", None)
            count = await run_worker(
                SAMPLE,
                cancel_after=cancel_after,
                eof_after=worker_eof_after,
            )
            await asyncio.sleep(0.3)
            received = json.loads(output.read_text())
            expected_count = cancel_after or worker_eof_after or len(SAMPLE)
            prefix = SAMPLE[:expected_count]
            expected = (
                prefix.replace("\n", "\r") if target.startswith("vte-") else prefix
            )
            await asyncio.sleep(0.2)
            no_late = json.loads(output.read_text()) == received
            report.update(
                production_worker=True,
                stop_reason=(
                    "explicit_cancel"
                    if cancel_after
                    else "requester_eof"
                    if worker_eof_after
                    else None
                ),
                no_late_output=no_late,
                remaining_characters_not_sent=len(SAMPLE) - count,
                characters=len(received),
                sent_characters=count,
                exact_unicode=received == expected,
                output_matches_expected=received == expected,
                snapshot_restored=snapshot(SOCKET) == original,
            )
            return (
                received == expected
                and count == expected_count
                and no_late
                and report["snapshot_restored"]
            )
        if observer:
            if modifier not in ("none", "mid-shift"):
                held_modifier = {
                    "shift": 0xFFE1,
                    "control": 0xFFE3,
                    "caps": 0xFFE5,
                    "num": 0xFF7F,
                }[modifier]
                await verify_owner()
                await call(
                    session_path,
                    DESTINATION + ".Session",
                    "NotifyKeyboardKeysym",
                    "ub",
                    [held_modifier, True],
                )
                if modifier in ("caps", "num"):
                    await call(
                        session_path,
                        DESTINATION + ".Session",
                        "NotifyKeyboardKeysym",
                        "ub",
                        [held_modifier, False],
                    )
                before_map_state = await observer.wait_snapshot(
                    after_revision=report["initial_modifiers"]["revision"]
                )
            else:
                before_map_state = await observer.wait_snapshot()
            report["before_map_modifiers"] = before_map_state
            if guard_modifiers and (
                before_map_state["depressed"]
                or before_map_state["latched"]
                or before_map_state["locked"] & caps_mask
            ):
                report["stop_reason"] = (
                    "keys_held"
                    if before_map_state["depressed"] or before_map_state["latched"]
                    else "caps_lock"
                )
                report["guard_refused"] = True
                raise GuardStop()
        await set_map(changed)
        map_applied = True
        # Retain the compositor's canonical map for later ownership comparison.
        changed = snapshot(SOCKET)
        report["temporary_map_source"] = await map_source()
        if observer:
            report["temporary_modifiers"] = await next_map_state(before_map_state)
        await asyncio.sleep(0.3)
        report["map_settle_seconds"] = 0.3
        if producer_crash_after is not None:
            producer = await asyncio.create_subprocess_exec(
                sys.executable,
                str(Path(__file__).with_name("keymap_text_producer.py")),
                SAMPLE,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
        sent = 0
        for character in SAMPLE:
            if producer:
                request = await asyncio.wait_for(producer.stdout.readline(), 2)
                if not request:
                    report["stop_reason"] = "requester_eof"
                    report["producer_exit_code"] = await asyncio.wait_for(
                        producer.wait(), 2
                    )
                    break
                if json.loads(request) != character:
                    raise RuntimeError("unexpected_owned_producer_request")
            if stop_requested.is_set():
                report["stop_reason"] = "sigterm"
                break
            if cancel_after is not None and sent >= cancel_after:
                report["stop_reason"] = "explicit_cancel"
                break
            if observer and guard_modifiers:
                current = await observer.wait_snapshot()
                if current["depressed"] or current["latched"]:
                    started = loop.time()
                    report["stop_reason"] = "keys_held"
                    while current["depressed"] or current["latched"]:
                        current = await observer.wait_snapshot(
                            timeout=max(0.01, 3 - (loop.time() - started)),
                            after_revision=current["revision"],
                        )
                    report["waited_for_release_seconds"] = loop.time() - started
                    break
            if await map_source() != 1 or snapshot(SOCKET) != changed:
                report["stop_reason"] = "external_map_changed"
                break
            if (
                single_slot_bmp
                and character != "\n"
                and (direct_keycode or ord(character) > 127)
            ):
                changed, _, _, allocations, _ = augmented_map(
                    original, character, 132, direct_keycode
                )
                if cancel_during_map and sent == 0:
                    loop.call_soon(stop_requested.set)
                await set_map(changed)
                changed = snapshot(SOCKET)
                if observer:
                    report["temporary_modifiers"] = await observer.refresh_snapshot()
                await asyncio.sleep(0.05)
            await verify_owner()
            keysym = (
                0xFF0D
                if character == "\n"
                else (
                    ord(character)
                    if ord(character) < 256
                    else 0x01000000 | ord(character)
                )
            )
            if stop_requested.is_set():
                report["stop_reason"] = (
                    "cancel_during_map" if cancel_during_map else "sigterm"
                )
                break
            method = (
                "NotifyKeyboardKeycode"
                if direct_keycode and character != "\n"
                else "NotifyKeyboardKeysym"
            )
            key = 124 if direct_keycode and character != "\n" else keysym
            # Mark attempted press before awaiting. Even an ambiguous failure must
            # attempt its matching release; never replay or emit the remaining tail.
            try:
                report["input_calls"] += 1
                await call(
                    session_path, DESTINATION + ".Session", method, "ub", [key, True]
                )
            finally:
                await call(
                    session_path, DESTINATION + ".Session", method, "ub", [key, False]
                )
                report["input_calls"] += 1
            sent += 1
            if modifier == "mid-shift" and sent == 5:
                held_modifier = 0xFFE1
                await call(
                    session_path,
                    DESTINATION + ".Session",
                    "NotifyKeyboardKeysym",
                    "ub",
                    [held_modifier, True],
                )
                await observer.wait_snapshot(
                    after_revision=report["temporary_modifiers"]["revision"]
                )

                async def release_owned_modifier():
                    nonlocal held_modifier
                    await asyncio.sleep(0.3)
                    await call(
                        session_path,
                        DESTINATION + ".Session",
                        "NotifyKeyboardKeysym",
                        "ub",
                        [held_modifier, False],
                    )
                    held_modifier = None

                modifier_release_task = asyncio.create_task(release_owned_modifier())
            if external_map_after is not None and sent == external_map_after:
                foreign_session = (
                    await call(
                        "/org/gnome/Mutter/RemoteDesktop", DESTINATION, "CreateSession"
                    )
                )[0]
                await call(foreign_session, DESTINATION + ".Session", "Start")
                foreign_map, _, _, _, _ = augmented_map(original, "Ж", 132)
                await set_map(foreign_map, foreign_session)
                foreign_map = snapshot(SOCKET)
                report["concurrent_layout_tested"] = True
            if producer:
                if sent == producer_crash_after:
                    producer.kill()
                    await asyncio.wait_for(producer.wait(), 2)
                else:
                    producer.stdin.write(b"ack\n")
                    await producer.stdin.drain()
            if terminate_after is not None and sent == terminate_after:
                # Exercise a real termination signal; the isolated controller
                # finishes releasing this key and restores before its exit.
                os.kill(os.getpid(), signal.SIGTERM)
            await asyncio.sleep(0.02)
        await asyncio.sleep(0.3)
        received = json.loads(output.read_text())
        report["characters"] = len(received)
        if switch_after is not None:
            final_state = json.loads(focus_state.read_text())
            report["cursor_switch"] = {
                key: final_state[key]
                for key in ("first_count", "second_count", "switch_done")
            }
        expected_sample = (
            SAMPLE.replace("\n", "\r") if target.startswith("vte-") else SAMPLE
        )
        report["exact_unicode"] = received == expected_sample
        if received != SAMPLE and cancel_after is None and terminate_after is None:
            # This is solely the owned fixed public test sample, never user text.
            report["received_sample_codepoints"] = [ord(char) for char in received]
        report["output_matches_expected"] = received == expected_sample[:sent]
        report["sent_characters"] = sent
        report["remaining_characters_not_sent"] = len(SAMPLE) - sent
        if (
            cancel_after is not None
            or terminate_after is not None
            or producer_crash_after is not None
            or cancel_during_map
            or external_map_after is not None
            or modifier == "mid-shift"
        ):
            await asyncio.sleep(0.2)
            report["no_late_output"] = json.loads(output.read_text()) == received
    except GuardStop:
        report.update(
            sent_characters=0,
            remaining_characters_not_sent=len(SAMPLE),
            output_matches_expected=json.loads(output.read_text()) == "",
            no_late_output=True,
        )
    finally:
        try:
            if not map_applied and original is not None:
                report["snapshot_restored"] = snapshot(SOCKET) == original
            if (
                original is not None
                and changed is not None
                and session_path
                and map_applied
            ):
                if observer and guard_modifiers:
                    current = await observer.wait_snapshot()
                    deadline = loop.time() + 3
                    while current["depressed"] or current["latched"]:
                        current = await observer.wait_snapshot(
                            timeout=max(0.01, deadline - loop.time()),
                            after_revision=current["revision"],
                        )
                # Best-effort identity/content check, NOT atomic CAS. This isolated
                # run has no external layout actor; concurrent tests remain pending.
                if await map_source() == 1 and snapshot(SOCKET) == changed:
                    if restore_policy:
                        await verify_owner()
                        await call(
                            session_path,
                            DESTINATION + ".Session",
                            "SetKeymap",
                            "a{sv}",
                            [{}],
                        )
                    else:
                        await set_map(original)
                    report["snapshot_restored"] = snapshot(SOCKET) == original
                    report["restored_map_source"] = await map_source()
                    if observer:
                        previous = report.get("temporary_modifiers", before_map_state)
                        try:
                            restored = await next_map_state(previous)
                            report["restored_modifiers"] = restored
                            report["modifier_restoration_tested"] = True
                            report["modifier_state_equal"] = all(
                                restored[name] == before_map_state[name]
                                for name in ("depressed", "latched", "locked", "group")
                            )
                        except ObserverError as error:
                            report["restored_modifier_error"] = error.code
                else:
                    report["external_map_preserved"] = (
                        foreign_map is not None and snapshot(SOCKET) == foreign_map
                    )
                    report["snapshot_restored"] = False
            if held_modifier is not None:
                # Undo only this experiment's synthetic modifier, never user keys.
                if modifier in ("caps", "num"):
                    await call(
                        session_path,
                        DESTINATION + ".Session",
                        "NotifyKeyboardKeysym",
                        "ub",
                        [held_modifier, True],
                    )
                await call(
                    session_path,
                    DESTINATION + ".Session",
                    "NotifyKeyboardKeysym",
                    "ub",
                    [held_modifier, False],
                )
            if observer:
                observer.close()
            if foreign_session:
                await call(foreign_session, DESTINATION + ".Session", "Stop")
            if session_path:
                await call(session_path, DESTINATION + ".Session", "Stop")
        finally:
            if modifier_release_task:
                await modifier_release_task
            if producer and producer.returncode is None:
                producer.terminate()
                try:
                    await asyncio.wait_for(producer.wait(), 2)
                except TimeoutError:
                    producer.kill()
                    await asyncio.wait_for(producer.wait(), 2)
            report["compositor_exit_before_cleanup"] = shell.poll() if shell else None
            for process in (fixture, shell):
                if process and process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=3)
            bus.disconnect()
            if not report.get("exact_unicode"):
                log_path = root / "shell.log"
                if log_path.exists():
                    print(log_path.read_text(errors="replace")[-6000:], file=sys.stderr)
            print(json.dumps(report, sort_keys=True), flush=True)
    expected_sent, expected_reason = len(SAMPLE), None
    for boundary, reason in (
        (cancel_after, "explicit_cancel"),
        (terminate_after, "sigterm"),
        (producer_crash_after, "requester_eof"),
        (external_map_after, "external_map_changed"),
    ):
        if boundary is not None:
            expected_sent, expected_reason = boundary, reason
    if cancel_during_map:
        expected_sent, expected_reason = 0, "cancel_during_map"
    if modifier == "mid-shift":
        expected_sent, expected_reason = 5, "keys_held"
    if report.get("guard_refused"):
        expected_sent = 0
        expected_reason = "caps_lock" if modifier == "caps" else "keys_held"
    accepted = bool(
        report.get("output_matches_expected")
        and report.get("sent_characters") == expected_sent
        and report.get("input_calls") == 2 * expected_sent
        and report.get("stop_reason") == expected_reason
        and (
            report.get("external_map_preserved")
            if external_map_after is not None
            else report.get("snapshot_restored")
        )
    )
    if expected_reason is not None:
        accepted = accepted and report.get("no_late_output", False)
    if observer and not report.get("guard_refused"):
        accepted = accepted and report.get("modifier_state_equal", False)
    if switch_after is not None:
        accepted = accepted and report.get("cursor_switch") == {
            "first_count": switch_after,
            "second_count": len(SAMPLE) - switch_after,
            "switch_done": True,
        }
    if producer_crash_after is not None:
        accepted = accepted and report.get("producer_exit_code") == -signal.SIGKILL
    return accepted


def main():
    global SAMPLE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-isolated", action="store_true")
    parser.add_argument("--restore-policy", action="store_true")
    parser.add_argument("--single-slot-bmp", action="store_true")
    parser.add_argument("--direct-keycode", action="store_true")
    parser.add_argument(
        "--target",
        choices=(
            "gtk",
            "chrome-textarea",
            "chrome-contenteditable",
            "vte-wayland",
            "vte-xwayland",
        ),
        default="gtk",
    )
    parser.add_argument(
        "--modifier", choices=("none", "shift", "control", "caps", "num", "mid-shift")
    )
    stop = parser.add_mutually_exclusive_group()
    stop.add_argument("--cancel-after", type=int, choices=range(1, len(SAMPLE)))
    stop.add_argument("--terminate-after", type=int, choices=range(1, len(SAMPLE)))
    stop.add_argument("--producer-crash-after", type=int, choices=range(1, len(SAMPLE)))
    stop.add_argument("--external-map-after", type=int, choices=range(1, len(SAMPLE)))
    parser.add_argument("--switch-after", type=int, choices=range(1, len(SAMPLE)))
    parser.add_argument("--cancel-during-map", action="store_true")
    parser.add_argument("--nonzero-group", action="store_true")
    parser.add_argument("--guard-modifiers", action="store_true")
    parser.add_argument("--production-worker", action="store_true")
    stop.add_argument("--worker-eof-after", type=int, choices=range(1, len(SAMPLE)))
    parser.add_argument("--inner", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker_eof_after and not args.production_worker:
        parser.error("--worker-eof-after requires --production-worker")
    if args.production_worker and not args.single_slot_bmp:
        parser.error("--production-worker requires the BMP fixed sample")
    if args.nonzero_group and args.modifier is None:
        args.modifier = "none"
    if args.cancel_during_map and not args.single_slot_bmp:
        parser.error("--cancel-during-map needs --single-slot-bmp")
    if args.switch_after is not None and not args.target.startswith("chrome-"):
        parser.error("--switch-after needs an owned Chrome fixture")
    if args.direct_keycode and not args.single_slot_bmp:
        parser.error("--direct-keycode requires --single-slot-bmp")
    if args.single_slot_bmp:
        SAMPLE = "你好 InkEcho，世界！ café Ω\n第二行。"
    if args.inner:
        raise SystemExit(
            0
            if asyncio.run(
                asyncio.wait_for(
                    inner(
                        args.inner,
                        args.restore_policy,
                        args.cancel_after,
                        args.terminate_after,
                        args.target,
                        args.modifier,
                        args.single_slot_bmp,
                        args.producer_crash_after,
                        args.direct_keycode,
                        args.external_map_after,
                        args.switch_after,
                        args.cancel_during_map,
                        args.nonzero_group,
                        args.guard_modifiers,
                        args.production_worker,
                        args.worker_eof_after,
                    ),
                    40,
                )
            )
            else 1
        )
    if not args.run_isolated:
        parser.error("Explicit --run-isolated is required; review before running")
    with tempfile.TemporaryDirectory(
        prefix="inkecho-isolated-keymap-", dir="/tmp"
    ) as folder:
        root = Path(folder)
        env = dict(os.environ)
        for name in (
            "DBUS_SESSION_BUS_ADDRESS",
            "DBUS_STARTER_ADDRESS",
            "DBUS_STARTER_BUS_TYPE",
            "DISPLAY",
            "WAYLAND_DISPLAY",
            "AT_SPI_BUS_ADDRESS",
            "SESSION_MANAGER",
        ):
            env.pop(name, None)
        for name, directory in (
            ("XDG_RUNTIME_DIR", "runtime"),
            ("XDG_CONFIG_HOME", "config"),
            ("XDG_DATA_HOME", "data"),
            ("XDG_STATE_HOME", "state"),
            ("XDG_CACHE_HOME", "cache"),
        ):
            path = root / directory
            path.mkdir(mode=0o700)
            env[name] = str(path)
        env.update(
            XDG_SESSION_TYPE="wayland",
            XDG_CURRENT_DESKTOP="GNOME",
            LIBGL_ALWAYS_SOFTWARE="1",
            GIO_USE_VFS="local",
            GVFS_DISABLE_FUSE="1",
            GTK_IM_MODULE="gtk-im-context-simple",
            GSETTINGS_BACKEND="keyfile",
        )
        process = subprocess.Popen(
            [
                "dbus-run-session",
                "--",
                sys.executable,
                str(Path(__file__).resolve()),
                "--inner",
                str(root),
                "--target",
                args.target,
                *(["--restore-policy"] if args.restore_policy else []),
                *(["--single-slot-bmp"] if args.single_slot_bmp else []),
                *(["--direct-keycode"] if args.direct_keycode else []),
                *(["--cancel-during-map"] if args.cancel_during_map else []),
                *(["--nonzero-group"] if args.nonzero_group else []),
                *(["--guard-modifiers"] if args.guard_modifiers else []),
                *(["--production-worker"] if args.production_worker else []),
                *(
                    ["--worker-eof-after", str(args.worker_eof_after)]
                    if args.worker_eof_after
                    else []
                ),
                *(
                    ["--external-map-after", str(args.external_map_after)]
                    if args.external_map_after
                    else []
                ),
                *(
                    ["--switch-after", str(args.switch_after)]
                    if args.switch_after
                    else []
                ),
                *(
                    ["--producer-crash-after", str(args.producer_crash_after)]
                    if args.producer_crash_after
                    else []
                ),
                *(["--modifier", args.modifier] if args.modifier else []),
                *(
                    ["--cancel-after", str(args.cancel_after)]
                    if args.cancel_after
                    else []
                ),
                *(
                    ["--terminate-after", str(args.terminate_after)]
                    if args.terminate_after
                    else []
                ),
            ],
            env=env,
            start_new_session=True,
        )
        try:
            result = process.wait(timeout=50)
        finally:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                # Only this start_new_session child owns the group being stopped.
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=3)
            # Private portal/GVFS services can leave a disconnected FUSE mount
            # after group termination. Only exact mounts inside this owned root
            # are detached; never inspect or act on the user's runtime mounts.
            allowed = {str(root / "runtime" / name) for name in ("doc", "gvfs")}
            for line in Path("/proc/self/mountinfo").read_text().splitlines():
                path = line.split()[4]
                if path in allowed:
                    subprocess.run(
                        ["fusermount3", "-u", "-z", path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=3,
                        check=True,
                    )
        raise SystemExit(result)


if __name__ == "__main__":
    main()
