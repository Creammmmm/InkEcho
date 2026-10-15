"""Validate frozen R7 source with a11 dependencies; never classify it as a package."""

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from ubuntu24_vm import LAB, ROOT
from ubuntu24_vm_package import ARTIFACT_SHA, PRODUCT_COMMIT, digest

PROBE_SHA = "2122ea8dfb59808c23a72b07caab0f059550140b4fc199e37fe4612f42a17a12"
STREAMING_SHA = "c46eb6e13627067d9c918415defe57eb93898f30e3e57795ed9c828edab89ce1"
SNAPSHOT = LAB / "input/source-r7-streaming"

GUEST = r"""
env, identity = desktop()
if identity["session_type"] != "x11" or identity["session_locked_hint"] != "no":
    raise RuntimeError("unlocked_actual_xorg_session_required")
snapshot = INPUT / "source-r7-streaming"
manifest_path = snapshot / "manifest.json"
if hashlib.sha256(manifest_path.read_bytes()).hexdigest() != SNAPSHOT_SHA:
    raise RuntimeError("unexpected_stress_manifest")
manifest = json.loads(manifest_path.read_text())
for group in ["source_files", "tool_files"]:
    for relative, checksum in manifest[group].items():
        path = (snapshot / relative).resolve(strict=True)
        if not path.is_relative_to(snapshot):
            raise RuntimeError("snapshot_path_escape")
        if hashlib.sha256(path.read_bytes()).hexdigest() != checksum:
            raise RuntimeError("snapshot_file_mismatch")
dependency_snapshot = INPUT / "a11-r2-long"
artifact = dependency_snapshot / "InkEcho-0.1.0a11-x86_64.AppImage"
with artifact.open("rb") as stream:
    if hashlib.file_digest(stream, "sha256").hexdigest() != ARTIFACT_SHA:
        raise RuntimeError("unexpected_a11_artifact")
runtime = Path.home() / "inkecho-a11-runtime-r2"
appdir = runtime / "squashfs-root"
if not appdir.exists():
    raise RuntimeError("existing_a11_dependency_runtime_required")
source_root = snapshot / "src"
env = dict(
    env,
    APPDIR=str(appdir),
    PYTHONHOME=str(appdir / "usr"),
    PYTHONPATH=str(source_root) + os.pathsep + str(appdir / "packages"),
    PYTHONNOUSERSITE="1",
    PYTHONDONTWRITEBYTECODE="1",
    QT_PLUGIN_PATH=str(appdir / "packages/PySide6/Qt/plugins"),
    LD_LIBRARY_PATH=str(appdir / "usr/lib/inkecho"),
)
tools = snapshot / "scripts/validation"
python = str(appdir / "usr/bin/python3")
origins_output = OUTPUT / "source-r7-streaming-origins.json"
readiness_tool = dependency_snapshot / "scripts/validation/package_next_window_probe.py"
if (
    hashlib.sha256(readiness_tool.read_bytes()).hexdigest()
    != manifest["readiness_tool_sha256"]
):
    raise RuntimeError("historical_readiness_tool_changed")
pipeline_output = OUTPUT / "source-r7-streaming-pipeline.json"
readiness_output = OUTPUT / "source-r7-streaming-next-window.json"
summary_output = OUTPUT / "source-r7-streaming-acceptance.json"
if MODE == "long" and any(
    path.exists()
    for path in [pipeline_output, readiness_output, summary_output, origins_output]
):
    raise RuntimeError("evidence_already_exists")
command = [
    python,
    str(tools / "source_pipeline_probe.py"),
    "--source-root",
    str(source_root),
    "--dependency-root",
    str(appdir / "packages"),
    "--snapshot-manifest",
    str(manifest_path),
    "--origins-output",
    str(origins_output),
    "--package-root",
    str(source_root),
    "--owned-ubuntu24-vm-x11",
    "--xdotool",
    "/usr/bin/xdotool",
    "--fixture-sse-profile",
    "one-character-fast-long",
    "--output",
    str(pipeline_output),
]


def process_start(pid):
    return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]


def owned_count(probe_pid):
    children = Path(f"/proc/{probe_pid}/task/{probe_pid}/children")
    try:
        pids = children.read_text().split()
    except FileNotFoundError:
        return None
    for pid in pids:
        try:
            started = process_start(pid)
            argv = Path(f"/proc/{pid}/cmdline").read_bytes().decode().split("\0")
            if (
                len(argv) < 6
                or argv[1] != str(tools / "keyboard_latency_probe.py")
                or argv[2:5] != ["--fixture", "gtk", "--output"]
            ):
                continue
            path = Path(argv[5]).resolve(strict=True)
            if (
                path.name != "owned-text.json"
                or path.parent.parent != Path("/tmp")
                or not path.parent.name.startswith("inkecho-package-performance-")
            ):
                raise RuntimeError("unexpected_owned_readback_path")
            if path.stat().st_size > 32000:
                raise RuntimeError("owned_readback_size_cap")
            state = json.loads(path.read_text())
            if process_start(pid) != started:
                continue
            text = state.get("text")
            if not isinstance(text, str):
                raise RuntimeError("unexpected_owned_readback_shape")
            return len(text)
        except (FileNotFoundError, ProcessLookupError):
            continue
    return None


def source_audit_valid(audit):
    origins = audit.get("origins", {})
    if (
        audit.get("runtime_kind") != "source"
        or audit.get("application_modules_verified") != 10
        or len(origins) != 11
        or audit.get("source_root") != str(source_root)
    ):
        return False
    inventory = json.loads(
        (appdir / "usr/share/doc/inkecho/inventory.json").read_text()
    )
    for name, origin in origins.items():
        path = Path(origin["path"])
        if name == "websockets":
            if not path.is_relative_to(appdir / "packages"):
                return False
            relative = str(path.relative_to(appdir))
            if origin["sha256"] != inventory["files"][relative]:
                return False
        else:
            if not path.is_relative_to(source_root):
                return False
            relative = "src/" + str(path.relative_to(source_root))
            if origin["sha256"] != manifest["source_files"][relative]:
                return False
    return True


if MODE == "focus":
    focus_output = OUTPUT / "source-r7-streaming-focus.json"
    focus_summary = OUTPUT / "source-r7-streaming-focus-acceptance.json"
    if focus_output.exists() or focus_summary.exists():
        raise RuntimeError("focus_evidence_already_exists")
    command = [
        python,
        str(tools / "source_streaming_cursor_probe.py"),
        "--source-root",
        str(source_root),
        "--dependency-root",
        str(appdir / "packages"),
        "--snapshot-manifest",
        str(manifest_path),
        "--xdotool",
        "/usr/bin/xdotool",
        "--output",
        str(focus_output),
    ]
    with (OUTPUT / "source-r7-streaming-focus.log").open("x") as log:
        focus_process = subprocess.Popen(
            command,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        focus_started = process_start(focus_process.pid)
        print(
            json.dumps({"focus_pid": focus_process.pid, "start_ticks": focus_started}),
            flush=True,
        )
        try:
            focus_process.wait(timeout=120)
        except subprocess.TimeoutExpired:
            pass
    status = focus_process.poll()
    summary = {
        **identity,
        "runtime_kind": "source",
        "dependency_artifact_sha256": ARTIFACT_SHA,
        "snapshot_manifest_sha256": SNAPSHOT_SHA,
        "source_streaming_sha256": STREAMING_SHA,
        "source_files_verified": len(manifest["source_files"]),
        "passed": False,
        "focus_pid": focus_process.pid,
        "focus_start_ticks": focus_started,
        "focus_exit": status,
        "focus_running": status is None,
        "cloud_requests": 0,
        "user_credentials_read": False,
        "microphone_used": False,
    }
    if status is not None and focus_output.exists():
        report = json.loads(focus_output.read_text())
        summary["source_origins_verified"] = source_audit_valid(
            report.get("runtime_metadata", {})
        )
        summary["passed"] = (
            status == 0
            and report.get("passed") is True
            and report.get("runtime_kind") == "source"
            and summary["source_origins_verified"]
            and report.get("lone_first_character_sent_before_remaining_queued") is True
        )
    focus_summary.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary))
    raise SystemExit(0 if summary["passed"] else 1)


first_full_readback = None
with (OUTPUT / "source-r7-streaming-pipeline.log").open("x") as log:
    process = subprocess.Popen(
        command, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True
    )
    started = process_start(process.pid)
    began = time.monotonic()
    print(json.dumps({"pipeline_pid": process.pid, "start_ticks": started}), flush=True)
    while process.poll() is None and time.monotonic() - began < 120:
        count = owned_count(process.pid)
        if count == 150 and first_full_readback is None:
            first_full_readback = time.monotonic()
        time.sleep(0.05)
status = process.poll()
pipeline_exited_at = time.monotonic() if status is not None else None
summary = {
    **identity,
    "runtime_kind": "source",
    "dependency_artifact_sha256": ARTIFACT_SHA,
    "dependency_product_commit": PRODUCT_COMMIT,
    "source_streaming_sha256": STREAMING_SHA,
    "snapshot_manifest_sha256": SNAPSHOT_SHA,
    "pipeline_pid": process.pid,
    "pipeline_start_ticks": started,
    "pipeline_exit": status,
    "pipeline_running": status is None,
    "first_150_readback_seen_at": first_full_readback,
    "first_150_readback_observed": first_full_readback is not None,
    "pipeline_exited_observed_at": pipeline_exited_at,
    "readback_poll_seconds": 0.05,
    "readiness_scope": "after_both_tasks_and_cleanup",
    "cloud_requests": 0,
    "user_credentials_read": False,
    "microphone_used": False,
    "passed": False,
}
if first_full_readback is not None and pipeline_exited_at is not None:
    summary["readback_150_to_pipeline_exit_ms"] = round(
        (pipeline_exited_at - first_full_readback) * 1000, 3
    )
if status is not None and pipeline_output.exists():
    report = json.loads(pipeline_output.read_text())
    audit = json.loads(origins_output.read_text()) if origins_output.exists() else {}
    summary["source_origins_verified"] = source_audit_valid(audit)
    summary["keyboard_mapping_counts"] = report.get("keyboard_mapping_counts")
    summary["pipeline_passed"] = (
        status == 0
        and report.get("passed") is True
        and report.get("runtime_kind") == "source"
        and report.get("version") == "0.1.0a11"
        and report.get("runtime_modules_verified") == 10
        and report.get("fixture_sse_profile") == "one-character-fast-long"
        and report.get("fixture_final_codepoints") == 150
        and report.get("fixture_final_printable_codepoints") == 144
        and report.get("real_desktop_input") is True
        and report.get("real_microphone") is False
        and report.get("cloud_requests") == 0
        and report.get("user_credentials_read") is False
        and summary["source_origins_verified"]
    )
    if summary["pipeline_passed"]:
        command = [
            python,
            str(readiness_tool),
            "--package-root",
            str(appdir / "packages"),
            "--xdotool",
            "/usr/bin/xdotool",
            "--pipeline-exited-at",
            str(pipeline_exited_at),
            "--output",
            str(readiness_output),
        ]
        with (OUTPUT / "source-r7-streaming-next-window.log").open("x") as log:
            next_process = subprocess.Popen(
                command,
                env=dict(env, PYTHONPATH=str(appdir / "packages")),
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            next_started = process_start(next_process.pid)
            summary["readiness_spawn_after_pipeline_exit_ms"] = round(
                (time.monotonic() - pipeline_exited_at) * 1000, 3
            )
            try:
                next_process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                pass
        next_status = next_process.poll()
        summary.update(
            readiness_fixture_runtime_kind="package",
            readiness_pid=next_process.pid,
            readiness_start_ticks=next_started,
            readiness_exit=next_status,
            readiness_running=next_status is None,
        )
        if next_status is not None and readiness_output.exists():
            ready = json.loads(readiness_output.read_text())
            matches = {}
            for name, relative in {
                "inkecho": "src/inkecho/__init__.py",
                "inkecho.platform.keyboard": "src/inkecho/platform/keyboard.py",
                "inkecho.runtime": "src/inkecho/runtime.py",
            }.items():
                origin = ready.get("runtime_origins", {}).get(name, {})
                matches[name] = (
                    origin.get("path")
                    == str(appdir / "packages" / Path(relative).relative_to("src"))
                    and origin.get("sha256") == manifest["source_files"][relative]
                )
            summary["readiness_origins_match_package"] = matches
            summary["passed"] = (
                next_status == 0
                and ready.get("passed") is True
                and ready.get("runtime_kind") == "package"
                and all(matches.values())
                and ready.get("text_input_requested") is False
                and first_full_readback is not None
            )
summary_output.write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary))
if not summary["passed"]:
    raise SystemExit(1)
"""


def prepare():
    if SNAPSHOT.exists():
        raise RuntimeError("long_snapshot_already_exists")
    previous = LAB / "input/a11-r2-long"
    sources = {
        str(path.relative_to(ROOT)): digest(path)
        for path in (ROOT / "src/inkecho").rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }
    if (
        len(sources) != 43
        or sources["src/inkecho/streaming_output.py"] != STREAMING_SHA
    ):
        raise RuntimeError("source_not_frozen_r7_revision")
    if (
        sources["src/inkecho/platform/keyboard.py"]
        != "1aff28ceab124e9745f2afda5ac8fec084d71be3185719a73556ad0b755f60f3"
    ):
        raise RuntimeError("unexpected_keyboard_source")
    tools = [
        "scripts/validation/keyboard_latency_probe.py",
        "scripts/validation/performance_package_probe.py",
        "scripts/validation/source_pipeline_probe.py",
        "scripts/validation/source_streaming_cursor_probe.py",
        "assets/licenses/websockets-LICENSE.txt",
    ]
    if digest(ROOT / tools[1]) != PROBE_SHA:
        raise RuntimeError("stress_probe_not_frozen_revision")
    manifest = {
        "dependency_product_commit": PRODUCT_COMMIT,
        "dependency_artifact_sha256": ARTIFACT_SHA,
        "source_files": sources,
        "tool_files": {name: digest(ROOT / name) for name in tools},
        "readiness_tool_sha256": digest(
            previous / "scripts/validation/package_next_window_probe.py"
        ),
    }
    with tempfile.TemporaryDirectory(
        prefix=".source-r7-streaming-", dir=SNAPSHOT.parent
    ) as name:
        directory = Path(name)
        for relative, checksum in manifest["source_files"].items():
            if digest(ROOT / relative) != checksum:
                raise RuntimeError("frozen_source_changed_during_copy")
            destination = directory / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, destination)
        for relative in tools:
            destination = directory / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, destination)
        artifact = previous / "InkEcho-0.1.0a11-x86_64.AppImage"
        if digest(artifact) != ARTIFACT_SHA:
            raise RuntimeError("unexpected_a11_artifact")
        (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        os.rename(directory, SNAPSHOT)
    record = {
        "snapshot": str(SNAPSHOT),
        "manifest_sha256": digest(SNAPSHOT / "manifest.json"),
    }
    with (LAB / "output/source-r7-streaming-snapshot.json").open("x") as stream:
        json.dump(record, stream, indent=2)
    print(json.dumps(record))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "preview", "run"])
    parser.add_argument("--mode", choices=["long", "focus"])
    args = parser.parse_args()
    if args.action == "prepare":
        if args.mode:
            parser.error("prepare takes no mode")
        prepare()
        return
    if args.mode is None:
        parser.error("preview/run requires a mode")
    helper = (ROOT / "scripts/validation/ubuntu24_vm_guest.py").read_text()
    definitions = helper.rsplit('if __name__ == "__main__":', 1)[0]
    record = json.loads((LAB / "output/source-r7-streaming-snapshot.json").read_text())
    checksum = record["manifest_sha256"]
    if digest(SNAPSHOT / "manifest.json") != checksum:
        raise RuntimeError("stress_manifest_changed")
    payload = (
        definitions
        + f"\nARTIFACT_SHA={ARTIFACT_SHA!r}\nPRODUCT_COMMIT={PRODUCT_COMMIT!r}\n"
        + f"STREAMING_SHA={STREAMING_SHA!r}\nMODE={args.mode!r}\n"
        + f"SNAPSHOT_SHA={checksum!r}\n"
        + GUEST
    )
    compile(payload, "isolated-source-r7-streaming", "exec")
    suffix = "preview" if args.action == "preview" else "payload"
    path = LAB / f"output/source-r7-streaming-{args.mode}-{suffix}.py"
    with path.open("x") as stream:
        stream.write(payload)
    with path.with_suffix(".manifest.json").open("x") as stream:
        json.dump({"payload_file": path.name, "sha256": digest(path)}, stream, indent=2)
    if args.action == "preview":
        print(json.dumps({"payload": str(path), "sha256": digest(path)}))
        return
    subprocess.run(
        [
            str(ROOT / ".venv/bin/python"),
            str(ROOT / "scripts/validation/ubuntu24_vm.py"),
            "ssh",
            "--",
            "python3",
            "-",
        ],
        input=payload,
        text=True,
        check=True,
    )


if __name__ == "__main__":
    main()
