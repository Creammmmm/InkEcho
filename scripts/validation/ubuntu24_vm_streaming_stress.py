"""Keep the long one-character SSE stress evidence separate from a11 R1."""

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
SNAPSHOT = LAB / "input/a11-r2-long"

GUEST = r"""
env, identity = desktop()
if identity["session_type"] != "x11" or identity["session_locked_hint"] != "no":
    raise RuntimeError("unlocked_actual_xorg_session_required")
snapshot = INPUT / "a11-r2-long"
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
artifact = snapshot / "InkEcho-0.1.0a11-x86_64.AppImage"
with artifact.open("rb") as stream:
    if hashlib.file_digest(stream, "sha256").hexdigest() != ARTIFACT_SHA:
        raise RuntimeError("unexpected_a11_artifact")
runtime = Path.home() / "inkecho-a11-runtime-r2"
appdir = runtime / "squashfs-root"
if not appdir.exists():
    runtime.mkdir(mode=0o700, exist_ok=True)
    with (OUTPUT / "a11-r2-long-extract.log").open("x") as log:
        checked(
            [str(artifact), "--appimage-extract"],
            cwd=runtime,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
env = dict(
    env,
    APPDIR=str(appdir),
    PYTHONHOME=str(appdir / "usr"),
    PYTHONPATH=str(appdir / "packages"),
    PYTHONNOUSERSITE="1",
    PYTHONDONTWRITEBYTECODE="1",
    QT_PLUGIN_PATH=str(appdir / "packages/PySide6/Qt/plugins"),
    LD_LIBRARY_PATH=str(appdir / "usr/lib/inkecho"),
)
tools = snapshot / "scripts/validation"
python = str(appdir / "usr/bin/python3")
pipeline_output = OUTPUT / "a11-r2-long-pipeline.json"
readiness_output = OUTPUT / "a11-r2-long-next-window.json"
summary_output = OUTPUT / "a11-r2-long-acceptance.json"
if any(path.exists() for path in [pipeline_output, readiness_output, summary_output]):
    raise RuntimeError("evidence_already_exists")
command = [
    python,
    str(tools / "performance_package_probe.py"),
    "--package-root",
    str(appdir / "packages"),
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


first_full_readback = None
with (OUTPUT / "a11-r2-long-pipeline.log").open("x") as log:
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
    "runtime_kind": "package",
    "artifact_sha256": ARTIFACT_SHA,
    "source_commit": PRODUCT_COMMIT,
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
    audit = report.get("package_inventory", {})
    summary["keyboard_mapping_counts"] = report.get("keyboard_mapping_counts")
    summary["pipeline_passed"] = (
        status == 0
        and report.get("passed") is True
        and report.get("runtime_kind") == "package"
        and report.get("version") == "0.1.0a11"
        and report.get("runtime_modules_verified") == 10
        and report.get("fixture_sse_profile") == "one-character-fast-long"
        and report.get("fixture_final_codepoints") == 150
        and report.get("fixture_final_printable_codepoints") == 144
        and report.get("real_desktop_input") is True
        and report.get("real_microphone") is False
        and report.get("cloud_requests") == 0
        and report.get("user_credentials_read") is False
        and audit.get("inventory_application") == "0.1.0a11"
        and audit.get("inventory_files_verified") == 3958
        and audit.get("inventory_links_verified") == 1048
        and audit.get("application_files_match_source") == 43
        and audit.get("websockets_license_copies_verified") == 2
    )
    if summary["pipeline_passed"]:
        command = [
            python,
            str(tools / "package_next_window_probe.py"),
            "--package-root",
            str(appdir / "packages"),
            "--xdotool",
            "/usr/bin/xdotool",
            "--pipeline-exited-at",
            str(pipeline_exited_at),
            "--output",
            str(readiness_output),
        ]
        with (OUTPUT / "a11-r2-long-next-window.log").open("x") as log:
            next_process = subprocess.Popen(
                command,
                env=env,
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
    previous = LAB / "input/a11-r1"
    old_manifest = json.loads((previous / "manifest.json").read_text())
    tools = [
        "scripts/validation/keyboard_latency_probe.py",
        "scripts/validation/performance_package_probe.py",
        "scripts/validation/package_next_window_probe.py",
        "assets/licenses/websockets-LICENSE.txt",
    ]
    if digest(ROOT / tools[1]) != PROBE_SHA:
        raise RuntimeError("stress_probe_not_frozen_revision")
    manifest = {
        "source_commit": PRODUCT_COMMIT,
        "artifact_sha256": ARTIFACT_SHA,
        "source_files": old_manifest["source_files"],
        "tool_files": {name: digest(ROOT / name) for name in tools},
    }
    with tempfile.TemporaryDirectory(
        prefix=".a11-r2-long-", dir=SNAPSHOT.parent
    ) as name:
        directory = Path(name)
        for relative, checksum in manifest["source_files"].items():
            if digest(previous / relative) != checksum:
                raise RuntimeError("historical_source_snapshot_changed")
            destination = directory / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(previous / relative, destination)
        for relative in tools:
            destination = directory / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, destination)
        artifact = previous / "InkEcho-0.1.0a11-x86_64.AppImage"
        if digest(artifact) != ARTIFACT_SHA:
            raise RuntimeError("unexpected_a11_artifact")
        shutil.copy2(artifact, directory / artifact.name)
        (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        os.rename(directory, SNAPSHOT)
    record = {
        "snapshot": str(SNAPSHOT),
        "manifest_sha256": digest(SNAPSHOT / "manifest.json"),
    }
    with (LAB / "output/a11-r2-long-snapshot.json").open("x") as stream:
        json.dump(record, stream, indent=2)
    print(json.dumps(record))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "preview", "run"])
    args = parser.parse_args()
    if args.action == "prepare":
        prepare()
        return
    helper = (ROOT / "scripts/validation/ubuntu24_vm_guest.py").read_text()
    definitions = helper.rsplit('if __name__ == "__main__":', 1)[0]
    record = json.loads((LAB / "output/a11-r2-long-snapshot.json").read_text())
    checksum = record["manifest_sha256"]
    if digest(SNAPSHOT / "manifest.json") != checksum:
        raise RuntimeError("stress_manifest_changed")
    payload = (
        definitions
        + f"\nARTIFACT_SHA={ARTIFACT_SHA!r}\nPRODUCT_COMMIT={PRODUCT_COMMIT!r}\n"
        + f"SNAPSHOT_SHA={checksum!r}\n"
        + GUEST
    )
    compile(payload, "isolated-a11-long-stress", "exec")
    suffix = "preview" if args.action == "preview" else "payload"
    path = LAB / f"output/a11-r2-long-{suffix}.py"
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
