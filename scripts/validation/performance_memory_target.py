"""Owned GTK parent controls: memory-only readback and non-destructive observation."""

import asyncio
import hashlib
import json
import os
import socket
import struct
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHILD = ROOT / "scripts/feasibility/owned_memory_text_fixture.py"
CHILD_SHA = "ce73be70846dfa3725156c7e7710ec21b500fce492f7ada8765ce77c5abf8849"
NATIVE = ROOT / "build/a13-host-r3/native"
NATIVE_HASHES = {
    "xdotool": "c91f9c829951e18000e54aa654e6d20c4e456aaa37816238ccc4ea346e49dfbb",
    "bin/xdotool": "9c14c28ba0b6f5a2a84aac70bfdfb411728b28f3682807b44925ebeab2046d9f",
    "lib/libxdo.so.3": (
        "4a97e3fcddc94e5c818f5684416f71a38d523d657b4bf62afa4d0946f6187cb2"
    ),
}
MAX_FRAME = 65536
MAX_TEXT = 32768
FAILURE_CODES = frozenset(
    {
        "comparison_acceptance_failed",
        "comparison_budget_failed",
        "comparison_outcome_failed",
        "comparison_transcript_not_forwarded",
        "comparison_current_cursor_failed",
        "comparison_late_response_not_exercised",
        "comparison_output_order_failed",
        "owned_target_not_cleanly_closed",
        "observation_timeout_no_next_arm",
        "fixture_session_not_started",
        "session_producer_still_running",
        "local_fixture_failed",
        "memory_target_identity_failed",
        "memory_target_exit_failed",
        "memory_channel_closed",
        "memory_frame_size",
        "memory_frame_invalid",
        "memory_close_failed",
        "memory_read_failed",
        "delivery_outside_owned_targets",
        "host_preflight_failed",
        "reviewed_plan_sha_required",
        "native_activation_failed",
        "comparison_unexpected_failure",
    }
)
GUARD_FLAGS = (
    "active_top_owned",
    "target_running",
    "start_matches",
    "active_pid_matches",
    "focus_matches_dispatch",
    "dispatch_equals_owned_top",
)
ARM_FLAGS = (
    "audio_matches",
    "polish_input_exact",
    "exact_expected",
    "no_tail_or_replay",
    "recording_without_focus_reads",
    "matched_releases",
    "late_response_attempted",
    "first_timestamp_from_press",
    "driver_closed_and_mapping_released",
    "target_owner_observed_exit_zero",
    "mapping_unchanged_during_target_startup",
    "mapping_restored_before_close",
    "keyboard_connected_before_close",
    "keyboard_closed_after_close",
)
DIAGNOSTIC_CODES = frozenset(
    {
        "other",
        "injection_failed",
        "unsupported_target",
        "mapping_changed",
        "input_cancelled",
        "session_closed",
        "unsupported_text",
        "display_unavailable",
        "cleanup_pending",
        "keys_held",
        "caps_lock",
        "unsupported_layout",
        "audio_failed",
        "transcription_failed",
        "polishing_failed",
        "task_timed_out",
        "empty_result",
        "configuration_invalid",
        "credentials_unavailable",
        "network",
        "response",
        "timeout",
        "empty",
        "audio",
        "configuration",
        "authentication",
        "rate_limit",
        "model",
        "unavailable",
        "protocol",
    }
)


def diagnostic_code(value):
    return value if type(value) is str and value in DIAGNOSTIC_CODES else "other"


def safe_arm_metadata(result):
    """Whitelist metadata before writing it; never accept text/error/body fields."""
    from inkecho.performance import validate_snapshot

    if (
        result.get("configuration") not in {"A", "B"}
        or result.get("scenario") != "normal"
    ):
        raise ValueError("arm_metadata_invalid")
    metadata = {"configuration": result["configuration"], "scenario": "normal"}
    snapshot = result.get("performance")
    metadata["performance"] = (
        validate_snapshot(snapshot) if snapshot is not None else None
    )
    metadata["flags"] = {}
    for name in ARM_FLAGS:
        value = result.get(name)
        if value is not None and type(value) is not bool:
            raise ValueError("arm_metadata_invalid")
        metadata["flags"][name] = value
    for name in ("characters_sent", "presses_sent", "releases_sent"):
        value = result.get(name)
        if value is not None and (type(value) is not int or not 0 <= value <= 100000):
            raise ValueError("arm_metadata_invalid")
        metadata[name] = value
    calls = result.get("calls", {})
    roles = ("http_asr", "wss_asr", "polishing")
    if set(calls) != set(roles) or any(
        type(calls[name]) is not int or not 0 <= calls[name] <= 100 for name in roles
    ):
        raise ValueError("arm_metadata_invalid")
    metadata["calls"] = calls.copy()
    checks = result.get("guard_checks")
    if checks is not None and (
        set(checks) != set(GUARD_FLAGS)
        or any(type(value) is not bool for value in checks.values())
    ):
        raise ValueError("arm_metadata_invalid")
    metadata["guard_checks"] = checks.copy() if checks is not None else None
    metadata["session_diagnostics"] = [
        diagnostic_code(value) for value in result.get("session_diagnostics", [])[:32]
    ]
    return metadata


def failure_code(error):
    if (
        type(error) is ValueError
        and len(error.args) == 1
        and type(error.args[0]) is str
        and error.args[0] in FAILURE_CODES
    ):
        return error.args[0]
    if isinstance(error, subprocess.CalledProcessError):
        return "native_activation_failed"
    return "comparison_unexpected_failure"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify_controls(xdotool):
    if xdotool.resolve(strict=True) != (NATIVE / "xdotool").resolve(strict=True):
        raise ValueError("reviewed_native_wrapper_required")
    for relative, checksum in NATIVE_HASHES.items():
        if digest(NATIVE / relative) != checksum:
            raise ValueError("native_control_hash_mismatch")
    if digest(CHILD) != CHILD_SHA:
        raise ValueError("memory_child_hash_mismatch")
    return {
        "root": str(NATIVE),
        "sha256": NATIVE_HASHES.copy(),
        "child_sha256": CHILD_SHA,
    }


def process_start(pid):
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]
    except (OSError, IndexError):
        return None


def process_record(process, argv):
    return {
        "pid": process.pid,
        "start_ticks": process_start(process.pid),
        "argv": list(argv),
        "exit_code": None,
        "owner_observed_terminal": False,
    }


def write_metadata(path, record):
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as output:
        os.chmod(temporary, 0o600)
        json.dump(record, output, ensure_ascii=True, allow_nan=False)
        output.write("\n")
    temporary.replace(path)


def observe_handle(path):
    record = json.loads(path.read_text())
    for item in [record.get("producer"), *record["targets"]]:
        if item is not None:
            start = process_start(item["pid"])
            item["identity_alive"] = start is not None and start == item["start_ticks"]
    # Missing PID is never evidence of a successful exit. Only its Popen owner
    # records a real return code and owner_observed_terminal.
    return record


class RunHandle:
    def __init__(self, path):
        self.path = path
        self.record = json.loads(path.read_text())
        self.timed_out = False

    @classmethod
    def create(cls, path):
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with path.open("x") as output:
            os.chmod(path, 0o600)
            json.dump(
                {
                    "schema_version": 1,
                    "producer": None,
                    "targets": [],
                    "phase": "launching",
                    "observation_timed_out": False,
                },
                output,
            )
        return cls(path)

    def save(self):
        write_metadata(self.path, self.record)

    def phase(self, value):
        self.record["phase"] = value
        self.save()

    def failure(self, error):
        if "failure_code" not in self.record:
            self.record["failure_code"] = failure_code(error)
            self.record["failed_phase"] = self.record["phase"]
            self.save()

    def arm(self, metadata):
        metadata = safe_arm_metadata(metadata)
        rows = self.record.setdefault("arm_metadata", [])
        rows[:] = [
            row for row in rows if row["configuration"] != metadata["configuration"]
        ]
        rows.append(metadata)
        self.save()

    def add_process(self, process, argv, *, producer=False):
        item = process_record(process, argv)
        if producer:
            self.record["producer"] = item
        else:
            self.record["targets"].append(item)
        self.save()
        return item

    def terminal(self, process, item):
        code = process.poll()
        if code is None:
            raise ValueError("producer_not_terminal")
        item.update(exit_code=code, owner_observed_terminal=True)
        self.save()
        return code

    async def observe(self, operation, phase, seconds=8):
        """A timeout changes observation state, never cancels the producer."""
        self.phase(phase)
        task = asyncio.ensure_future(operation)
        try:
            return await asyncio.wait_for(asyncio.shield(task), seconds)
        except TimeoutError:
            self.timed_out = True
            self.record["observation_timed_out"] = True
            self.phase("observation_pending")
            return await task  # Same task/PID/FD remains observable; no restart.

    async def until(self, predicate, phase):
        async def waiting():
            while not predicate():
                await asyncio.sleep(0.005)

        return await self.observe(waiting(), phase)


class PrivateChannel:
    def __init__(self, channel):
        self.channel = channel
        channel.setblocking(False)
        self.lock = asyncio.Lock()

    async def exact(self, count):
        result = bytearray()
        while len(result) < count:
            part = await asyncio.get_running_loop().sock_recv(
                self.channel, count - len(result)
            )
            if not part:
                raise ValueError("memory_channel_closed")
            result.extend(part)
        return bytes(result)

    async def receive(self):
        size = struct.unpack("!I", await self.exact(4))[0]
        if not 0 < size <= MAX_FRAME:
            raise ValueError("memory_frame_size")
        try:

            def unique(pairs):
                values = {}
                for key, value in pairs:
                    if key in values:
                        raise ValueError("memory_duplicate_field")
                    values[key] = value
                return values

            result = json.loads(
                (await self.exact(size)).decode("utf-8"), object_pairs_hook=unique
            )
        except (ValueError, UnicodeError, RecursionError):
            raise ValueError("memory_frame_invalid") from None
        if not isinstance(result, dict):
            raise ValueError("memory_frame_invalid")
        return result

    async def command(self, command):
        if command not in {"read", "close"}:
            raise ValueError("memory_command_invalid")
        async with self.lock:
            payload = json.dumps({"command": command}).encode()
            await asyncio.get_running_loop().sock_sendall(
                self.channel, struct.pack("!I", len(payload)) + payload
            )
            result = await self.receive()
            if command == "close":
                if (
                    set(result) != {"ok", "closed"}
                    or result["ok"] is not True
                    or result["closed"] is not True
                ):
                    raise ValueError("memory_close_failed")
                return None
            if (
                set(result) != {"ok", "text"}
                or result["ok"] is not True
                or not isinstance(result["text"], str)
                or len(result["text"].encode("utf-8")) > MAX_TEXT
            ):
                raise ValueError("memory_read_failed")
            return result["text"]


def child_environment(environment):
    names = (
        "PATH",
        "HOME",
        "TMPDIR",
        "DISPLAY",
        "XAUTHORITY",
        "XDG_RUNTIME_DIR",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
        "XDG_CACHE_HOME",
        "XDG_STATE_HOME",
    )
    return {
        **{name: environment[name] for name in names if name in environment},
        "GDK_BACKEND": "x11",
        "GTK_IM_MODULE": "gtk-im-context-simple",
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    }


class MemoryTarget:
    def __init__(self, handle, xdotool):
        self.handle, self.xdotool = handle, xdotool
        self.window = None

    async def open(self, environment):
        verify_controls(self.xdotool)
        parent, child = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        argv = ["/usr/bin/python3", str(CHILD), "--fd", str(child.fileno())]
        try:
            self.process = subprocess.Popen(
                argv,
                pass_fds=(child.fileno(),),
                start_new_session=True,
                env=child_environment(environment),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            parent.close()
            raise
        finally:
            child.close()
        self.item = self.handle.add_process(self.process, argv)
        self.item["ready_verified"] = False
        self.handle.save()
        self.channel = PrivateChannel(parent)
        ready = await self.handle.observe(self.channel.receive(), "target_ready")
        if (
            set(ready) != {"ready", "pid", "window_id"}
            or ready["ready"] is not True
            or type(ready["pid"]) is not int
            or ready["pid"] != self.process.pid
            or type(ready["window_id"]) is not int
            or ready["window_id"] <= 0
            or self.item["start_ticks"] is None
        ):
            raise ValueError("memory_target_identity_failed")
        self.window = ready["window_id"]
        self.item["window_id"] = self.window
        self.item["ready_verified"] = True
        self.handle.save()

    async def activate(self):
        verify_controls(self.xdotool)
        await self.handle.observe(
            asyncio.to_thread(
                subprocess.run,
                [str(self.xdotool), "windowactivate", "--sync", str(self.window)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            ),
            "target_activation",
        )

    async def text(self):
        return await self.handle.observe(
            self.channel.command("read"), "target_readback"
        )

    async def close(self):
        protocol_closed = False
        if self.process.poll() is None:
            try:
                await self.handle.observe(self.channel.command("close"), "target_close")
                protocol_closed = True
            except (ValueError, ConnectionError):
                # EOF makes this owned fixture exit normally; never terminate/kill.
                self.channel.channel.close()
        await self.handle.observe(asyncio.to_thread(self.process.wait), "target_exit")
        self.item["protocol_close_ack"] = protocol_closed
        code = self.handle.terminal(self.process, self.item)
        self.channel.channel.close()
        if code != 0 or not protocol_closed:
            raise ValueError("memory_target_exit_failed")


class DeliveryGuard:
    """Fixture-only press guard; production KeyboardInput retains current focus."""

    def __init__(self, inputs, targets):
        self.inputs, self.targets = inputs, targets
        self.focus_reads = 0
        self.presses = self.releases = 0
        self.first_press_at = None
        self.last_check = None
        self.original_send = inputs._send
        self.original_focus = inputs._driver.focus

        def focus():
            self.focus_reads += 1
            return self.original_focus()

        inputs._driver.focus = focus
        inputs._send = self.send

    def send(self, window, code, pressed):
        if pressed:
            driver = self.inputs._driver
            self.last_check = dict.fromkeys(GUARD_FLAGS, False)
            # KeyboardInput dispatches to the actual focused child. Its focus()
            # already verifies that child's ancestry under the active top-level.
            active = driver._property(driver.root, driver.active_atom)
            target = next(
                (target for target in self.targets if target.window == active), None
            )
            check = self.last_check
            check["active_top_owned"] = target is not None
            if target is not None:
                check["target_running"] = target.process.poll() is None
                check["start_matches"] = (
                    target.item["start_ticks"] is not None
                    and process_start(target.process.pid) == target.item["start_ticks"]
                )
                check["active_pid_matches"] = (
                    driver._property(active, driver.pid_atom) == target.process.pid
                )
                check["dispatch_equals_owned_top"] = window == active
                check["focus_matches_dispatch"] = self.original_focus() == window
            if not all(
                check[name]
                for name in GUARD_FLAGS
                if name != "dispatch_equals_owned_top"
            ):
                raise ValueError("delivery_outside_owned_targets")
        self.original_send(window, code, pressed)
        if pressed:
            self.presses += 1
            if self.first_press_at is None:
                self.first_press_at = time.monotonic()
        else:
            self.releases += 1
