#!/usr/bin/env python3
"""Prepare a Noble cloud comparison; a plan or --live is never human consent.

Only the separately reviewed execution commands may contact SSH, Docker or the
credential backend. Default host plan is stdlib/read-only; offline handoff sends
only generated silence and fake keys, with no SDK/Qt/desktop invocation.
"""

import argparse
import asyncio
import hashlib
import importlib
import io
import json
import os
import resource
import shlex
import shutil
import struct
import subprocess
import sys
import time
import wave
from pathlib import Path

import performance_live_comparison as core
import performance_live_handoff as handoff
import performance_noble_comparison as noble
from performance_memory_target import RunHandle, digest, process_start, write_metadata

ROOT = Path(__file__).resolve().parents[2]
NAME = "live-comparison-noble-cloud-r1"
LAB = ROOT / "build/ubuntu24-perf-vm"
HOST_SNAPSHOT = LAB / "input" / NAME
HOST_OUTPUT = LAB / "output" / NAME
GUEST_ROOT = Path("/mnt/input") / NAME
GUEST_OUTPUT = Path("/mnt/output") / NAME
SCRIPT = "scripts/validation/performance_noble_live.py"
SOURCES = (*noble.SOURCES, "scripts/validation/performance_live_handoff.py", SCRIPT)
CONTAINER = "inkecho-ubuntu24-perf-vm"
CONTAINER_ID = "0582fbea0288c17e40759c823892d60c750f51b43d1de17722cabf33bd136a2f"
CONTAINER_STARTED = "2026-10-15T17:00:26.9984176Z"
QEMU_START = "26717597"
BRIDGE_ID = "946c8b2d57de6eb9a62c60c209e9415f63881999afc389655be6cabe5b603a9f"
MODES = ("offline-handoff", "live")
FAILURES = frozenset(
    {
        "plan_changed",
        "plan_required",
        "path_mismatch",
        "identity_mismatch",
        "producer_present",
        "network_state",
        "control_failed",
        "handoff_failed",
        "pending",
        "execution_failed",
        "offline_mismatch",
        "mode_mismatch",
    }
)


class ControlError(ValueError):
    def __init__(self, code):
        super().__init__(code if code in FAILURES else "control_failed")


class Parser(argparse.ArgumentParser):
    def error(self, _message):
        raise ControlError("mode_mismatch")


def error_code(error):
    if type(error) is ControlError:
        return error.args[0]
    if type(error) is handoff.HandoffError:
        return "handoff_failed"
    return "execution_failed"


def load(path):
    return json.loads(path.read_bytes())


def synthetic_audio():
    output = io.BytesIO()
    with wave.open(output, "wb") as recording:
        recording.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        recording.writeframes(b"\0\0" * 3200)
    audio = output.getvalue()
    return audio, handoff.AudioConstraints(
        hashlib.sha256(audio).hexdigest(), len(audio), 3200
    )


def audio_metadata(mode):
    if mode == "offline-handoff":
        _audio, constraints = synthetic_audio()
    else:
        constraints = handoff.PUBLIC_AUDIO
    return {
        "sha256": constraints.sha256,
        "bytes": constraints.size,
        "frames": constraints.frames,
        "sample_rate": 16000,
        "channels": 1,
        "sample_width": 2,
        "seconds": constraints.frames / 16000,
    }


def source_hashes(root):
    return {name: digest(root / name) for name in SOURCES}


def spec(mode, configuration, package, sources):
    return {
        "schema_version": 1,
        "mode": mode,
        "comparison": "configuration_A_B_same_a13_not_version_baseline",
        "configuration": configuration,
        "package": package,
        "sources": sources,
        "audio": audio_metadata(mode),
        "canonical_refs": list(handoff.REFS),
        "A": {"asr_url": core.ASR_URL, "model": "qwen3-asr-flash", "stream": False},
        "B": {
            "asr_url": core.previous.ASR_WS,
            "model": "qwen3-asr-flash-realtime",
            "stream": True,
        },
        "polishing": {
            "url": core.POLISH_URL,
            "model": "deepseek-flash",
            "max_tokens": 128,
            "thinking": {"type": "disabled"},
            "prompt": core.previous.PROMPT,
        },
        "budget": {"per_arm_asr": 1, "per_arm_polishing": 1, "total": 4},
        "retries": 0,
        "warmup": 0,
        "discovery": 0,
        "cold_client_per_arm": True,
        "native": noble.NATIVE_HASHES,
        "desktop": noble.DESKTOP,
        "guest_root": str(GUEST_ROOT),
        "guest_appdir": str(noble.GUEST_APPDIR),
        "guest_artifact": str(noble.GUEST_ARTIFACT),
        "container": {
            "id": CONTAINER_ID,
            "name": CONTAINER,
            "started_at": CONTAINER_STARTED,
            "qemu_start": QEMU_START,
            "initial_networks": [],
        },
        "network": "existing_bridge_temporarily_connected"
        if mode == "live"
        else "unchanged_none",
        "bridge_id": BRIDGE_ID,
        "background_guest_network_possible": mode == "live",
        "four_call_budget_covers_only_tool_API_requests": True,
        "real_microphone": False,
        "current_cursor_semantics": True,
        "separate_human_authorization_required": True,
        "plan_is_authorization": False,
    }


def fingerprint(value):
    return {**value, "plan_sha256": core.previous.fingerprint(value)}


def host_plan(args, mode):
    configuration = core.read_metadata(args.config_root)
    package = core.previous.verify_package(args.appimage, args.package_root)
    if mode == "live":
        observed = core.previous.verify_wave(core.previous.WAV)
        if observed["bytes"] != handoff.PUBLIC_AUDIO.size:
            raise ControlError("plan_changed")
    return fingerprint(spec(mode, configuration, package, source_hashes(ROOT)))


def validate_configuration(value):
    if (
        type(value) is not dict
        or set(value) != {"hashes", "references", "selected_models"}
        or value["references"] != core.REFS
        or type(value["hashes"]) is not dict
        or set(value["hashes"])
        != {"config.json", "providers/qwen.json", "providers/deepseek.json"}
        or any(not handoff._sha(checksum) for checksum in value["hashes"].values())
        or type(value["selected_models"]) is not dict
        or set(value["selected_models"]) != {"qwen", "deepseek"}
        or value["selected_models"]["qwen"]
        not in {"qwen3-asr-flash", "qwen3-asr-flash-realtime"}
        or value["selected_models"]["deepseek"] != "deepseek-flash"
    ):
        raise ControlError("plan_changed")


def plan_path(root, mode):
    return root / "plans" / f"{mode}.json"


def node_plan(mode, *, allowed=()):
    if Path(__file__).resolve() != GUEST_ROOT / SCRIPT:
        raise ControlError("path_mismatch")
    reviewed = load(plan_path(GUEST_ROOT, mode))
    validate_configuration(reviewed.get("configuration"))
    package = core.previous.verify_package(
        noble.GUEST_ARTIFACT, noble.GUEST_APPDIR / "packages"
    )
    current = fingerprint(
        spec(mode, reviewed["configuration"], package, source_hashes(ROOT))
    )
    if current != reviewed:
        raise ControlError("plan_changed")
    noble.preflight()
    noble.verify_controls(noble.XDOTOOL)
    no_producers(allowed)
    return current


def no_producers(allowed=()):
    for directory in Path("/proc").iterdir():
        if not directory.name.isdecimal() or int(directory.name) in {
            os.getpid(),
            *allowed,
        }:
            continue
        try:
            if directory.stat().st_uid != os.getuid():
                continue
            arguments = (directory / "cmdline").read_bytes().split(b"\0")
            executable = Path(os.fsdecode(arguments[0])).name
            if (
                executable.startswith("python")
                and any(
                    b"performance_" in argument
                    or b"owned_memory_text_fixture.py" in argument
                    for argument in arguments[1:]
                )
            ) or executable in {"inkecho", "AppRun"}:
                raise ControlError("producer_present")
        except (OSError, IndexError):
            continue


def expected_origins(package_root):
    inventory = load(package_root.parent / "usr/share/doc/inkecho/inventory.json")
    return {
        name: inventory["files"]["packages/" + name.replace(".", "/") + ".py"]
        for name in handoff.ORIGINS
    }


def node_command(
    mode, *, worker=False, accepted=None, credential_fd=None, ready_fd=None
):
    command = [
        str(noble.GUEST_APPDIR / "usr/bin/python3") if worker else "/usr/bin/python3",
        "-B",
        str(GUEST_ROOT / SCRIPT),
        "--role",
        "worker" if worker else "node",
        "--mode",
        mode,
    ]
    if accepted:
        command += [
            "--offline-handoff" if mode == "offline-handoff" else "--live",
            "--accept-plan-sha",
            accepted,
        ]
    else:
        command += ["--plan"]
    if worker:
        command += ["--credential-fd", str(credential_fd), "--ready-fd", str(ready_fd)]
    return command


def ssh_command(mode, accepted):
    return [
        "docker",
        "exec",
        "--interactive",
        CONTAINER,
        "ssh",
        "-T",
        "-i",
        "/secrets/testkey",
        "-p",
        "2222",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=20",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        "UserKnownHostsFile=/state/known_hosts",
        "inkecho@127.0.0.1",
        shlex.join(node_command(mode, accepted=accepted)),
    ]


def prepare(args):
    plans = {mode: host_plan(args, mode) for mode in MODES}
    HOST_SNAPSHOT.mkdir(mode=0o700, parents=True, exist_ok=False)
    HOST_OUTPUT.mkdir(mode=0o700, parents=True, exist_ok=False)
    for relative in SOURCES:
        target = HOST_SNAPSHOT / relative
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    (HOST_SNAPSHOT / "plans").mkdir(mode=0o700)
    for mode, reviewed in plans.items():
        write_metadata(plan_path(HOST_SNAPSHOT, mode), reviewed)
    preview = {
        mode: {
            "plan_sha256": reviewed["plan_sha256"],
            "argv": ssh_command(mode, reviewed["plan_sha256"]),
        }
        for mode, reviewed in plans.items()
    }
    write_metadata(HOST_SNAPSHOT / "preview.json", preview)
    return preview


def ready_message(reviewed, origins):
    return {
        "version": 1,
        "kind": "ready",
        "plan_sha256": reviewed["plan_sha256"],
        "origins": origins,
        "producer": {"pid": os.getpid(), "start_ticks": process_start(os.getpid())},
        "budget": {arm: {"asr": 0, "polishing": 0} for arm in ("A", "B")},
    }


def send_ready(fd, value):
    encoded = json.dumps(value, separators=(",", ":")).encode()
    if len(encoded) > handoff.MAX_METADATA:
        raise ControlError("handoff_failed")
    handoff.write_exact(fd, struct.pack("!I", len(encoded)))
    handoff.write_exact(fd, encoded)


def attach_worker(handle_path):
    for _ in range(200):
        handle = RunHandle(handle_path)
        item = handle.record["producer"]
        if (
            item
            and item["pid"] == os.getpid()
            and item["start_ticks"] == process_start(os.getpid())
        ):
            return handle
        time.sleep(0.005)
    raise ControlError("identity_mismatch")


def cleaned(handle):
    return handle.record.get("current_arm_cleanup_verified") is True and all(
        target.get("owner_observed_terminal") is True
        and target.get("exit_code") is not None
        for target in handle.record["targets"]
    )


async def live_pair(handle, reviewed, credentials, audio):
    with wave.open(io.BytesIO(audio), "rb") as recording:
        pcm = recording.readframes(recording.getnframes())

    def checkpoint(_arm, _role, counts):
        handle.record["reserved_calls"] = counts
        handle.phase("request_reserved")

    budget, rows = core.Budget(checkpoint), []
    desktop = {
        "handle": handle,
        "xdotool": noble.XDOTOOL,
        "target_options": {
            "verifier": noble.verify_controls,
            "child_path": ROOT / noble.SOURCES[-1],
        },
    }
    for arm in ("A", "B"):
        handle.record["current_arm_cleanup_verified"] = False
        handle.save()
        if node_plan("live", allowed=(os.getppid(),)) != reviewed or handle.timed_out:
            raise ControlError("plan_changed")
        row = core.safe_result(
            await core.run_arm(arm, budget, audio, pcm, credentials, desktop=desktop)
        )
        # Session.close can report an input error via a diagnostic instead of
        # raising. Only run_arm's actual post-HTTP-context resource witnesses
        # establish cleanup, independently from experiment acceptance.
        handle.record["current_arm_cleanup_verified"] = all(
            row.get(field) is True
            for field in (
                "mapping_restored_and_driver_closed",
                "matched_releases",
                "target_exit_zero",
            )
        )
        handle.record.setdefault("live_arm_metadata", []).append(row)
        handle.phase("arm_acceptance")
        core.accept(row)
        if handle.timed_out:
            raise ControlError("pending")
        rows.append(row)
    return rows


def worker(args):
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    handle_path = GUEST_OUTPUT / args.mode / "handle.json"
    handle = attach_worker(handle_path)
    credentials, started = None, False
    try:
        reviewed = node_plan(args.mode, allowed=(os.getppid(),))
        require_plan(args, reviewed)
        origins = core.audit_runtime(noble.GUEST_APPDIR / "packages")
        core.previous.verify_production_profiles()
        send_ready(args.ready_fd, ready_message(reviewed, origins))
        os.close(args.ready_fd)
        args.ready_fd = None
        constraints = (
            synthetic_audio()[1]
            if args.mode == "offline-handoff"
            else handoff.PUBLIC_AUDIO
        )
        credentials, audio = handoff.Receiver().receive(
            args.credential_fd, reviewed["plan_sha256"], constraints=constraints
        )
        os.close(args.credential_fd)
        args.credential_fd = None
        if args.mode == "offline-handoff":
            if audio != synthetic_audio()[0] or any(
                credentials.get(ref) != "synthetic-offline-only" for ref in handoff.REFS
            ):
                raise ControlError("offline_mismatch")
            rows = []
        else:
            # Imports stay after the authenticated RAM handoff; offline never
            # constructs Qt, SDK clients or an owned target.
            from PySide6.QtWidgets import QApplication

            from inkecho.runtime import ManagedQtEventLoop

            application = QApplication.instance() or QApplication([])
            application.setQuitOnLastWindowClosed(False)
            started = True
            with ManagedQtEventLoop(application) as loop:
                asyncio.set_event_loop(loop)
                rows = loop.run_until_complete(
                    live_pair(handle, reviewed, credentials, audio)
                )
        handle.record.update(
            cleanup_complete=not started or cleaned(handle),
            mode=args.mode,
            runtime_origins=origins,
            plan_sha256=reviewed["plan_sha256"],
            results=rows,
            offline_handoff_verified=args.mode == "offline-handoff",
        )
        handle.phase("worker_clean")
        return 0
    except Exception as error:
        if "live_failure_code" not in handle.record:
            handle.record.setdefault("failure_code", error_code(error))
        handle.record.setdefault("failed_phase", handle.record["phase"])
        handle.record["cleanup_complete"] = not started or cleaned(handle)
        handle.phase("worker_failed")
        return 1
    finally:
        if credentials:
            credentials.close()
        for fd in (args.ready_fd, args.credential_fd):
            if fd is None:
                continue
            try:
                os.close(fd)
            except OSError:
                pass


def require_plan(args, reviewed):
    if args.accept_plan_sha != reviewed["plan_sha256"]:
        raise ControlError("plan_required")


def private_log(path):
    return os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb")


def launcher(args):
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    handoff._pipe(0, writing=False)
    handoff._pipe(1, writing=True)
    reviewed = node_plan(args.mode)
    require_plan(args, reviewed)
    folder = GUEST_OUTPUT / args.mode
    profile = core.persistent_profile(folder / "handle.json")
    handle = RunHandle.create(folder / "handle.json")
    environment = noble.worker_environment(noble.GUEST_APPDIR / "packages", profile)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    credential_read, credential_write = os.pipe()
    ready_read, ready_write = os.pipe()
    process = None
    try:
        command = node_command(
            args.mode,
            worker=True,
            accepted=reviewed["plan_sha256"],
            credential_fd=credential_read,
            ready_fd=ready_write,
        )
        with private_log(folder / "worker.log") as log:
            process = subprocess.Popen(
                command,
                env=environment,
                pass_fds=(credential_read, ready_write),
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
        item = handle.add_process(process, command, producer=True)
        os.close(credential_read)
        credential_read = None
        os.close(ready_write)
        ready_write = None
        expected = handoff.ReadyExpected(
            reviewed["plan_sha256"],
            expected_origins(noble.GUEST_APPDIR / "packages"),
            item["pid"],
            item["start_ticks"],
        )
        message = handoff.receive_ready(ready_read, expected)
        send_ready(1, message)
        # Only opaque bounded bytes traverse the launcher. Neither argv nor its
        # parent-owned durable handle ever contains credential/audio content.
        total = 0
        while True:
            block = os.read(0, 32768)
            if not block:
                break
            total += len(block)
            if total > 4 + handoff.MAX_METADATA + handoff.MAX_AUDIO:
                raise ControlError("handoff_failed")
            handoff.write_exact(credential_write, block)
        os.close(credential_write)
        credential_write = None
        return process.wait()
    finally:
        for fd in (credential_read, credential_write, ready_read, ready_write):
            if fd is not None:
                os.close(fd)
        if process:
            # Natural terminal only; no observation timeout kills the producer.
            process.wait()
            terminal_worker(handle.path, process)


def terminal_worker(path, process):
    handle = RunHandle(path)  # Preserve worker results, never overwrite stale state.
    if handle.record["producer"]["pid"] != process.pid:
        raise ControlError("identity_mismatch")
    return handle.terminal(process, handle.record["producer"])


def command_json(argv):
    try:
        completed = subprocess.run(argv, capture_output=True, check=False, timeout=15)
        if completed.returncode:
            raise ValueError
        return json.loads(completed.stdout)
    except Exception:
        raise ControlError("control_failed") from None


def container_state():
    template = (
        '{"id":{{json .Id}},"name":{{json .Name}},'
        '"started_at":{{json .State.StartedAt}},"running":{{json .State.Running}},'
        '"paused":{{json .State.Paused}},"restarting":{{json .State.Restarting}},'
        '"pid":{{json .State.Pid}},"networks":{{json .NetworkSettings.Networks}}}'
    )
    row = command_json(["docker", "inspect", "--format", template, CONTAINER])
    if (
        row["id"] != CONTAINER_ID
        or row["name"] != "/" + CONTAINER
        or row["started_at"] != CONTAINER_STARTED
        or row["running"] is not True
        or row["paused"] is not False
        or row["restarting"] is not False
        or row["pid"] != 517799
    ):
        raise ControlError("identity_mismatch")
    query = (
        "import json,os;from pathlib import Path;"
        "print(json.dumps({'exe':os.readlink('/proc/1/exe'),"
        "'start':Path('/proc/1/stat').read_text().rsplit(')',1)[1].split()[19]}))"
    )
    qemu = command_json(["docker", "exec", CONTAINER, "python3", "-B", "-c", query])
    if qemu != {"exe": "/usr/bin/qemu-system-x86_64", "start": QEMU_START}:
        raise ControlError("identity_mismatch")
    return {
        "id": row["id"],
        "started_at": row["started_at"],
        "qemu_start": qemu["start"],
        "networks": sorted(row["networks"]),
    }


class ScopedBridge:
    """Only the existing bridge/container; no generic networking API or retry."""

    def __init__(self, record, save):
        self.record, self.save = record, save
        self.requested = False

    def before(self):
        state = container_state()
        if state["networks"] != []:
            raise ControlError("network_state")
        self.record["network_before"] = state
        self.save()

    def connect(self):
        self.before()
        template = (
            '{"id":{{json .Id}},"name":{{json .Name}},'
            '"driver":{{json .Driver}},"internal":{{json .Internal}}}'
        )
        network = command_json(
            ["docker", "network", "inspect", "--format", template, "bridge"]
        )
        if network != {
            "id": BRIDGE_ID,
            "name": "bridge",
            "driver": "bridge",
            "internal": False,
        }:
            raise ControlError("network_state")
        self.requested = True
        self.record["network_phase"] = "connect_requested"
        self.save()
        # A failed CLI return doesn't prove whether Docker applied the request.
        # The saved requested state survives and prevents automatic re-execution.
        result = subprocess.run(
            ["docker", "network", "connect", "bridge", CONTAINER_ID],
            capture_output=True,
            check=False,
        )
        if result.returncode or container_state()["networks"] != ["bridge"]:
            raise ControlError("network_state")
        self.record["network_phase"] = "connected"
        self.save()

    def finish(self, terminal_and_clean):
        if not self.requested:
            return
        if not terminal_and_clean:
            self.record["network_phase"] = "pending_producer_or_cleanup"
            self.save()
            return
        state = container_state()
        if state["networks"] == ["bridge"]:
            self.record["network_phase"] = "disconnect_requested"
            self.save()
            result = subprocess.run(
                ["docker", "network", "disconnect", "bridge", CONTAINER_ID],
                capture_output=True,
                check=False,
            )
            if result.returncode:
                raise ControlError("network_state")
        elif state["networks"] != []:
            raise ControlError("network_state")
        after = container_state()
        if after["networks"] != []:
            raise ControlError("network_state")
        self.record.update(network_phase="restored_none", network_after=after)
        self.save()


def host_expected(path, reviewed, origins):
    record = load(path)
    item = record["producer"]
    argv = item["argv"]
    # PIDs originate in the authenticated launcher's actual Popen record, not
    # in worker READY. FD numbers are nonsecret and checked against the template.
    try:
        cfd = int(argv[argv.index("--credential-fd") + 1])
        rfd = int(argv[argv.index("--ready-fd") + 1])
    except (ValueError, IndexError):
        raise ControlError("identity_mismatch") from None
    if (
        cfd < 3
        or rfd < 3
        or cfd == rfd
        or item["owner_observed_terminal"] is not False
        or item["exit_code"] is not None
        or record["targets"]
        or argv
        != node_command(
            reviewed["mode"],
            worker=True,
            accepted=reviewed["plan_sha256"],
            credential_fd=cfd,
            ready_fd=rfd,
        )
    ):
        raise ControlError("identity_mismatch")
    return handoff.ReadyExpected(
        reviewed["plan_sha256"], origins, item["pid"], item["start_ticks"]
    )


def terminal_and_clean(path):
    try:
        record = load(path)
        producer = record["producer"]
        return (
            producer["owner_observed_terminal"] is True
            and type(producer["exit_code"]) is int
            and record.get("cleanup_complete") is True
            and all(
                target["owner_observed_terminal"] is True
                and type(target["exit_code"]) is int
                for target in record["targets"]
            )
        )
    except Exception:
        return False


def execute_host(args, reviewed):
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    require_plan(args, reviewed)
    frozen = load(plan_path(HOST_SNAPSHOT, args.mode))
    if frozen != reviewed or source_hashes(HOST_SNAPSHOT) != reviewed["sources"]:
        raise ControlError("plan_changed")
    folder = HOST_OUTPUT / args.mode
    folder.mkdir(mode=0o700, exist_ok=False)
    record = {
        "mode": args.mode,
        "plan_sha256": reviewed["plan_sha256"],
        "ssh": None,
        "phase": "starting",
        "passed": False,
    }

    def save():
        write_metadata(folder / "controller.json", record)

    bridge = ScopedBridge(record, save)
    bridge.before()  # Read-only even in offline; require this isolated container.
    process, backend, experiment_passed = None, None, False

    def first_failure(error):
        record.setdefault("failure_code", error_code(error))
        record.setdefault("host_failed_phase", record["phase"])

    def cleanup_failure(error):
        record.setdefault("cleanup_failure_code", error_code(error))
        record.setdefault("cleanup_failed_phase", record["phase"])
        first_failure(error)

    def revalidate():
        if (
            host_plan(args, args.mode) != reviewed
            or load(plan_path(HOST_SNAPSHOT, args.mode)) != reviewed
        ):
            raise ControlError("plan_changed")
        if source_hashes(HOST_SNAPSHOT) != reviewed["sources"]:
            raise ControlError("plan_changed")

    def read_key(reference):
        nonlocal backend
        revalidate()
        if reference not in handoff.REFS:
            raise ControlError("handoff_failed")
        if args.mode == "offline-handoff":
            return "synthetic-offline-only"
        if backend is None:
            sys.path.insert(0, str(args.package_root))
            security = importlib.import_module("inkecho.security")
            origin = Path(security.__file__).resolve()
            if (
                origin != (args.package_root / "inkecho/security.py").resolve()
                or digest(origin)
                != expected_origins(args.package_root)["inkecho.security"]
            ):
                raise ControlError("identity_mismatch")
            backend = security.FileCredentialStore(args.config_root)
        return backend.get(reference)

    def read_audio():
        revalidate()
        return (
            synthetic_audio()[0]
            if args.mode == "offline-handoff"
            else core.previous.WAV.read_bytes()
        )

    try:
        argv = ssh_command(args.mode, reviewed["plan_sha256"])
        with private_log(folder / "ssh.log") as log:
            process = subprocess.Popen(
                argv,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=log,
                start_new_session=True,
            )
        record["ssh"] = {
            "pid": process.pid,
            "start_ticks": process_start(process.pid),
            "argv": argv,
            "exit_code": None,
            "owner_observed_terminal": False,
        }
        save()
        # READY cannot be consumed until its independent parent-owned identity
        # exists. The launcher writes that record before forwarding READY.
        while not (folder / "handle.json").exists():
            if process.poll() is not None:
                raise ControlError("execution_failed")
            time.sleep(0.02)
        # The file can exist briefly with producer=None before Popen is recorded.
        while load(folder / "handle.json")["producer"] is None:
            if process.poll() is not None:
                raise ControlError("execution_failed")
            time.sleep(0.02)
        expected = host_expected(
            folder / "handle.json", reviewed, expected_origins(args.package_root)
        )
        ready = handoff.receive_ready(process.stdout.fileno(), expected)
        revalidate()
        record["phase"] = "ready_verified"
        save()
        if args.mode == "live":
            record["phase"] = "network_connect"
            save()
            bridge.connect()
        constraints = (
            synthetic_audio()[1]
            if args.mode == "offline-handoff"
            else handoff.PUBLIC_AUDIO
        )
        record["phase"] = "handoff"
        save()
        handoff.Sender().send(
            process.stdin.fileno(),
            ready,
            expected,
            revalidate=revalidate,
            read_key=read_key,
            read_audio=read_audio,
            constraints=constraints,
        )
        process.stdin.close()  # Critical: no other writer may keep worker EOF open.
        record["phase"] = "running"
        save()
        code = process.wait()
        record["ssh"].update(exit_code=code, owner_observed_terminal=True)
        clean = terminal_and_clean(folder / "handle.json")
        child = load(folder / "handle.json")
        passed = (
            code == 0 and clean and child.get("plan_sha256") == reviewed["plan_sha256"]
        )
        if args.mode == "offline-handoff":
            passed = passed and child.get("offline_handoff_verified") is True
        else:
            passed = (
                passed
                and len(child.get("results", [])) == 2
                and not child.get("failure_code")
            )
        experiment_passed = passed
        record.update(
            experiment_passed=passed,
            phase="experiment_terminal",
            producer_terminal_and_clean=clean,
        )
        save()
        if not passed:
            raise ControlError("execution_failed")
    except BaseException as error:
        first_failure(error)
        record["phase"] = "failed_or_pending"
        save()
    finally:
        backend = None
        record["phase"] = "producer_cleanup"
        if process:
            try:
                if process.stdin and not process.stdin.closed:
                    process.stdin.close()
            except BaseException as error:
                cleanup_failure(error)
            try:
                code = process.wait()  # Never kill/restart on an observation limit.
                record["ssh"].update(exit_code=code, owner_observed_terminal=True)
            except BaseException:
                cleanup_failure(ControlError("pending"))
            try:
                if process.stdout:
                    process.stdout.close()
            except BaseException as error:
                cleanup_failure(error)
        clean = (
            process is not None
            and process.poll() is not None
            and terminal_and_clean(folder / "handle.json")
        )
        record["phase"] = "network_cleanup"
        save()
        try:
            bridge.finish(clean)
        except BaseException as error:
            cleanup_failure(error)
        record["producer_terminal_and_clean"] = clean
        if not clean:
            first_failure(ControlError("pending"))
        record["passed"] = experiment_passed and clean and "failure_code" not in record
        record["phase"] = (
            "terminal" if record["passed"] else "failed" if clean else "pending"
        )
        save()
    if not record["passed"]:
        raise ControlError(record["failure_code"]) from None
    return record


def arguments(argv=None):
    parser = Parser(description=__doc__)
    parser.add_argument("--role", choices=("host", "node", "worker"), default="host")
    parser.add_argument("--mode", choices=MODES, default="live")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--plan", action="store_true")
    action.add_argument("--prepare", action="store_true")
    action.add_argument("--offline-handoff", action="store_true")
    action.add_argument("--live", action="store_true")
    parser.add_argument("--accept-plan-sha")
    parser.add_argument(
        "--config-root", type=Path, default=Path.home() / ".config/inkecho"
    )
    parser.add_argument(
        "--appimage", type=Path, default=ROOT / "dist/InkEcho-0.1.0a13-x86_64.AppImage"
    )
    parser.add_argument(
        "--package-root",
        type=Path,
        default=ROOT
        / "build/performance-a13-extracted-iwmzy2mn/squashfs-root/packages",
    )
    parser.add_argument("--credential-fd", type=int)
    parser.add_argument("--ready-fd", type=int)
    args = parser.parse_args(argv)
    if (
        (args.live and args.mode != "live")
        or (args.offline_handoff and args.mode != "offline-handoff")
        or (args.prepare and args.role != "host")
        or (
            args.role == "worker"
            and (args.credential_fd is None or args.ready_fd is None)
        )
        or (
            args.role != "worker"
            and (args.credential_fd is not None or args.ready_fd is not None)
        )
    ):
        raise ControlError("mode_mismatch")
    return args


def main(argv=None):
    args = None
    try:
        args = arguments(argv)
        executing = args.live or args.offline_handoff
        if args.role == "host":
            if args.prepare:
                result = prepare(args)
            else:
                result = host_plan(args, args.mode)
                if executing:
                    result = execute_host(args, result)
        elif args.role == "worker":
            if not executing:
                raise ControlError("mode_mismatch")
            return worker(args)
        else:
            if executing:
                return launcher(args)
            result = node_plan(args.mode)
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0
    except Exception as error:
        # Node stdout is a private binary READY channel during execution.
        output = sys.stderr if args and args.role == "node" else sys.stdout
        print(json.dumps({"status": "failed", "code": error_code(error)}), file=output)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
