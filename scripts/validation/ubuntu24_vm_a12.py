"""Run the separately built a12 artifact in the existing isolated Noble VM."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from ubuntu24_vm import LAB, ROOT

ARTIFACT_SHA = "e31dbc6301318ab10632c12a7437ae7cd01482f2b1ee39655a82e43b6900eae9"
PRODUCT_COMMIT = "06f5600a57402335e97b3975afc38009d6233e58"
SNAPSHOT = LAB / "input/a12-r1"
MODES = [
    "control40",
    "default20",
    "cancel12",
    "pipeline40",
    "pipeline20",
    "pipeline-long",
    "focus-stream",
    "ui",
]

GUEST = r"""
env, identity = desktop()
if identity["session_type"] != "x11" or identity["session_locked_hint"] != "no":
    raise RuntimeError("unlocked_actual_xorg_session_required")
snapshot = INPUT / "a12-r1"
manifest_path = snapshot / "manifest.json"
if hashlib.sha256(manifest_path.read_bytes()).hexdigest() != SNAPSHOT_SHA:
    raise RuntimeError("unexpected_a12_snapshot_manifest")
manifest = json.loads(manifest_path.read_text())
for group in ["source_files", "tool_files"]:
    for relative, checksum in manifest[group].items():
        path = (snapshot / relative).resolve(strict=True)
        if not path.is_relative_to(snapshot):
            raise RuntimeError("snapshot_path_escape")
        if hashlib.sha256(path.read_bytes()).hexdigest() != checksum:
            raise RuntimeError("snapshot_hash_mismatch")
artifact = snapshot / "InkEcho-0.1.0a12-x86_64.AppImage"
with artifact.open("rb") as stream:
    if hashlib.file_digest(stream, "sha256").hexdigest() != ARTIFACT_SHA:
        raise RuntimeError("unexpected_a12_artifact")
runtime = Path.home() / "inkecho-a12-runtime-r1"
appdir = runtime / "squashfs-root"
if not appdir.exists():
    runtime.mkdir(mode=0o700, exist_ok=True)
    with (OUTPUT / "a12-r1-extract.log").open("x") as log:
        checked([str(artifact), "--appimage-extract"], cwd=runtime,
                stdout=log, stderr=subprocess.STDOUT)
inventory = json.loads((appdir / "usr/share/doc/inkecho/inventory.json").read_text())
if inventory["application"] != "0.1.0a12" or len(manifest["source_files"]) != 43:
    raise RuntimeError("unexpected_application_inventory")
for relative, checksum in inventory["files"].items():
    path = (appdir / relative).resolve(strict=True)
    if not path.is_relative_to(appdir):
        raise RuntimeError("inventory_path_escape")
    with path.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != checksum:
            raise RuntimeError("inventory_file_mismatch")
for relative, target in inventory["symlinks"].items():
    path = appdir / relative
    if str(path.readlink()) != target or not path.resolve().is_relative_to(appdir):
        raise RuntimeError("inventory_symlink_mismatch")
for relative, checksum in manifest["source_files"].items():
    path = appdir / "packages" / Path(relative).relative_to("src")
    if hashlib.sha256(path.read_bytes()).hexdigest() != checksum:
        raise RuntimeError("packaged_source_mismatch")
license_hash = manifest["tool_files"]["assets/licenses/websockets-LICENSE.txt"]
for path in [appdir / "packages/websockets-15.0.1.dist-info/LICENSE",
             appdir / "usr/share/doc/inkecho/licenses/websockets-LICENSE.txt"]:
    if hashlib.sha256(path.read_bytes()).hexdigest() != license_hash:
        raise RuntimeError("packaged_websocket_license_mismatch")
env = dict(env, APPDIR=str(appdir), PYTHONHOME=str(appdir / "usr"),
           PYTHONPATH=str(appdir / "packages"), PYTHONNOUSERSITE="1",
           PYTHONDONTWRITEBYTECODE="1",
           QT_PLUGIN_PATH=str(appdir / "packages/PySide6/Qt/plugins"),
           LD_LIBRARY_PATH=str(appdir / "usr/lib/inkecho"))
stem = "a12-r1-" + SETTINGS["mode"]
output = OUTPUT / f"{stem}.json"
summary_output = OUTPUT / f"{stem}-acceptance.json"
if output.exists() or summary_output.exists():
    raise RuntimeError("evidence_already_exists")
tools = snapshot / "scripts/validation"
python = str(appdir / "usr/bin/python3")
mode = SETTINGS["mode"]
targets = ["chrome-textarea", "chrome-contenteditable", "gtk", "vte"]
if mode == "cancel12":
    targets = ["gtk"]
origins_output = OUTPUT / f"{stem}-origins.json"
if origins_output.exists():
    raise RuntimeError("origins_evidence_already_exists")
entry = [python, str(tools / "artifact_runtime_probe.py"), "--package-root",
         str(appdir / "packages"), "--origins-output", str(origins_output)]
if mode in ["control40", "default20", "cancel12"]:
    command = [*entry, "--tool", "keyboard_latency_probe", "--",
               "--environment", "ubuntu24-vm-x11", "--qt-loop", "--xdotool",
               "/usr/bin/xdotool", "--repeat", "5", "--targets", *targets,
               "--output", str(output)]
    if mode == "control40":
        command.extend(["--pacing", ".04", ".04", ".04"])
    if mode == "cancel12":
        command.extend(["--cancel-after", "12"])
elif mode.startswith("pipeline"):
    command = [*entry, "--tool", "performance_package_probe", "--",
               "--owned-ubuntu24-vm-x11", "--xdotool", "/usr/bin/xdotool",
               "--output", str(output)]
    if mode == "pipeline40":
        command.extend(["--pacing", ".04"])
    if mode == "pipeline-long":
        command.extend(["--fixture-sse-profile", "one-character-fast-long"])
elif mode == "focus-stream":
    command = [*entry, "--tool", "artifact_streaming_cursor_probe", "--",
               "--xdotool", "/usr/bin/xdotool", "--output", str(output)]
else:
    profile = Path.home() / "a12-r1-ui-profile"
    screenshots = OUTPUT / "a12-r1-ui-pages"
    if profile.exists() or screenshots.exists():
        raise RuntimeError("ui_profile_or_screenshots_already_exist")
    command = [str(appdir / "AppRun"), "--config-dir", str(profile / "config"),
               "--data-dir", str(profile / "data"), "--screenshot-dir",
               str(screenshots), "--quit-after", "3"]


def screensaver():
    native_env = dict(env)
    for key in ["PYTHONHOME", "PYTHONPATH", "LD_LIBRARY_PATH", "QT_PLUGIN_PATH"]:
        native_env.pop(key, None)
    began = time.monotonic()
    try:
        result = subprocess.run([
            "gdbus", "call", "--session", "--dest", "org.gnome.ScreenSaver",
            "--object-path", "/org/gnome/ScreenSaver", "--method",
            "org.gnome.ScreenSaver.GetActive",
        ], env=native_env, capture_output=True, text=True, timeout=2)
        return {"exit": result.returncode,
                "active": {"(true,)": True, "(false,)": False}.get(
                    result.stdout.strip()),
                "duration_seconds": round(time.monotonic() - began, 4)}
    except subprocess.TimeoutExpired:
        return {"code": "timeout"}


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
            if (len(argv) < 6
                or argv[1] != str(tools / "keyboard_latency_probe.py")
                or argv[2:5] != ["--fixture", "gtk", "--output"]):
                continue
            path = Path(argv[5]).resolve(strict=True)
            if (path.name != "owned-text.json"
                or path.parent.parent != Path("/tmp")
                or not path.parent.name.startswith("inkecho-package-performance-")):
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


def package_audit_valid(audit):
    origins = audit.get("origins", {})
    if (audit.get("runtime_kind") != "package"
        or audit.get("version") != "0.1.0a12"
        or audit.get("application_modules_verified") != 10
        or len(origins) != 11):
        return False
    for name, origin in origins.items():
        path = Path(origin.get("path", ""))
        if not path.is_relative_to(appdir / "packages"):
            return False
        if origin.get("sha256") != inventory["files"].get(
            str(path.relative_to(appdir))):
            return False
        if name != "websockets":
            relative = "src/" + str(path.relative_to(appdir / "packages"))
            if origin.get("sha256") != manifest["source_files"].get(relative):
                return False
    return True


before = screensaver()
first_full_readback = None
with (OUTPUT / f"{stem}.log").open("x") as log:
    process = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT,
                               start_new_session=True)
    start_ticks = process_start(process.pid)
    print(json.dumps({"probe_pid": process.pid, "start_ticks": start_ticks}),
          flush=True)
    if mode == "pipeline-long":
        began = time.monotonic()
        while process.poll() is None and time.monotonic() - began < 120:
            count = owned_count(process.pid)
            if count == 150 and first_full_readback is None:
                first_full_readback = time.monotonic()
            time.sleep(0.05)
    else:
        try:
            process.wait(timeout=120)
        except subprocess.TimeoutExpired:
            pass  # Never interrupt a producer's pending key/map cleanup.
status = process.poll()
exited_at = time.monotonic() if status is not None else None
summary = {**identity, "runtime_kind": "package", "version": "0.1.0a12",
           "artifact_sha256": ARTIFACT_SHA, "source_commit": PRODUCT_COMMIT,
           "snapshot_manifest_sha256": SNAPSHOT_SHA,
           "inventory_files_checked": len(inventory["files"]),
           "inventory_symlinks_checked": len(inventory["symlinks"]),
           "source_files_checked": 43, "websocket_license_copies_checked": 2,
           "probe_pid": process.pid, "probe_start_ticks": start_ticks,
           "probe_exit": status, "probe_running": status is None,
           "settings": SETTINGS, "screensaver_before": before,
           "cloud_requests": 0, "user_credentials_read": False,
           "microphone_used": False, "passed": False}
if mode == "pipeline-long":
    summary.update(first_150_readback_seen_at=first_full_readback,
        first_150_readback_observed=first_full_readback is not None,
        pipeline_exited_observed_at=exited_at, readback_poll_seconds=0.05,
        readiness_scope="after_both_tasks_and_cleanup")
    if first_full_readback is not None and exited_at is not None:
        summary["readback_150_to_pipeline_exit_ms"] = round(
            (exited_at - first_full_readback) * 1000, 3)
if status is not None:
    if mode == "ui":
        summary["screenshots"] = len(list(screenshots.glob("page-*.png")))
        summary["passed"] = status == 0 and summary["screenshots"] == 9
    elif output.exists():
        report = json.loads(output.read_text())
        audit = (json.loads(origins_output.read_text())
                 if origins_output.exists() else {})
        origin_ok = package_audit_valid(audit)
        summary["package_origins_verified"] = origin_ok
        if mode in ["control40", "default20", "cancel12"]:
            rows = report.get("targets", [])
            writes = 13 if mode == "cancel12" else 136
            summary["mapping_counts_match"] = len(rows) == len(targets) and all(
                row.get("mapping_counts") == {"mapping_writes": writes,
                    "restore_calls": 1, "successful_restore_calls": 1}
                for row in rows)
            flags_ok = (report.get("production_behavior_modified") is False
                and report.get("runtime_kind") == "unclassified"
                and report.get("expected_source_root") is None
                and report.get("restore_policy") == "production"
                and "candidate_policy" not in report
                and [row.get("target") for row in rows] == targets
                and summary["mapping_counts_match"])
        elif mode == "focus-stream":
            flags_ok = (report.get("runtime_kind") == "package"
                and report.get("version") == "0.1.0a12"
                and report.get("production_behavior_modified") is False
                and package_audit_valid(report.get("runtime_metadata", {}))
                and report.get("lone_first_character_sent_before_remaining_queued")
                is True)
        else:
            expected_profile = (
                "one-character-fast-long" if mode == "pipeline-long" else "normal")
            flags_ok = (report.get("version") == "0.1.0a12"
                and report.get("runtime_kind") == "package"
                and report.get("runtime_modules_verified") == 10
                and report.get("cloud_requests") == 0
                and report.get("user_credentials_read") is False
                and report.get("real_microphone") is False
                and report.get("real_desktop_input") is True
                and report.get("fixture_sse_profile") == expected_profile)
            if mode == "pipeline-long":
                flags_ok = (flags_ok
                    and report.get("fixture_final_codepoints") == 150
                    and report.get("fixture_final_printable_codepoints") == 144
                    and first_full_readback is not None)
            summary["keyboard_mapping_counts"] = report.get("keyboard_mapping_counts")
        summary["passed"] = (status == 0 and report.get("passed") is True
                             and origin_ok and flags_ok)
    if mode == "pipeline-long" and summary["passed"]:
        readiness_output = OUTPUT / f"{stem}-next-window.json"
        if readiness_output.exists():
            raise RuntimeError("readiness_evidence_already_exists")
        command = [python, str(tools / "package_next_window_probe.py"),
                   "--package-root", str(appdir / "packages"), "--xdotool",
                   "/usr/bin/xdotool", "--pipeline-exited-at", str(exited_at),
                   "--output", str(readiness_output)]
        with (OUTPUT / f"{stem}-next-window.log").open("x") as log:
            next_process = subprocess.Popen(command, env=env, stdout=log,
                stderr=subprocess.STDOUT, start_new_session=True)
            next_started = process_start(next_process.pid)
            summary["readiness_spawn_after_pipeline_exit_ms"] = round(
                (time.monotonic() - exited_at) * 1000, 3)
            try:
                next_process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                pass  # Observation budget never terminates the known live task.
        next_status = next_process.poll()
        summary.update(readiness_pid=next_process.pid,
            readiness_start_ticks=next_started,
            readiness_exit=next_status, readiness_running=next_status is None)
        summary["pipeline_passed"] = summary["passed"]
        summary["passed"] = False
        if next_status is not None and readiness_output.exists():
            ready = json.loads(readiness_output.read_text())
            matches = {}
            for name, relative in {
                "inkecho": "src/inkecho/__init__.py",
                "inkecho.platform.keyboard": "src/inkecho/platform/keyboard.py",
                "inkecho.runtime": "src/inkecho/runtime.py",
            }.items():
                origin = ready.get("runtime_origins", {}).get(name, {})
                matches[name] = (origin.get("path")
                    == str(appdir / "packages" / Path(relative).relative_to("src"))
                    and origin.get("sha256") == manifest["source_files"][relative])
            summary["readiness_origins_match_package"] = matches
            summary["passed"] = (next_status == 0 and ready.get("passed") is True
                and ready.get("runtime_kind") == "package" and all(matches.values())
                and ready.get("text_input_requested") is False)
    summary["screensaver_after"] = screensaver()
summary_output.write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary))
if not summary["passed"]:
    raise SystemExit(1)
"""


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def prepare():
    if SNAPSHOT.exists():
        raise RuntimeError("a12_snapshot_already_exists")
    baseline = json.loads(
        (ROOT / "build/performance-a12-source-before-build.json").read_text()
    )
    if baseline["source_commit"] != PRODUCT_COMMIT:
        raise RuntimeError("unexpected_product_commit")
    sources = {
        "src/" + name: checksum for name, checksum in baseline["source_files"].items()
    }
    if any(digest(ROOT / name) != checksum for name, checksum in sources.items()):
        raise RuntimeError("product_source_changed_since_build")
    tools = [
        "scripts/validation/keyboard_latency_probe.py",
        "scripts/validation/performance_package_probe.py",
        "scripts/validation/ubuntu24_vm_a12.py",
        "scripts/validation/artifact_runtime_probe.py",
        "scripts/validation/artifact_streaming_cursor_probe.py",
        "scripts/validation/package_next_window_probe.py",
        "assets/licenses/websockets-LICENSE.txt",
    ]
    frozen_tools = dict(
        zip(
            [
                "keyboard_latency_probe.py",
                "performance_package_probe.py",
                "package_next_window_probe.py",
            ],
            [
                "f0cb80b62727f9c03c26af8c929255bf99c41c349c8afe3769dc38b49d897344",
                "2122ea8dfb59808c23a72b07caab0f059550140b4fc199e37fe4612f42a17a12",
                "8ab688389f19aa9f7550b70d2163a81c55f40d773bd8d338c9e10ac574608434",
            ],
            strict=True,
        )
    )
    if any(
        digest(ROOT / "scripts/validation" / name) != checksum
        for name, checksum in frozen_tools.items()
    ):
        raise RuntimeError("historical_probe_not_frozen_revision")
    artifact = ROOT / "dist/InkEcho-0.1.0a12-x86_64.AppImage"
    if digest(artifact) != ARTIFACT_SHA:
        raise RuntimeError("unexpected_a12_artifact")
    manifest = {
        "source_commit": PRODUCT_COMMIT,
        "artifact_sha256": ARTIFACT_SHA,
        "source_files": sources,
        "tool_files": {name: digest(ROOT / name) for name in tools},
    }
    with tempfile.TemporaryDirectory(prefix=".a12-r1-", dir=SNAPSHOT.parent) as name:
        directory = Path(name)
        for relative in [*sources, *tools]:
            destination = directory / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, destination)
        shutil.copy2(artifact, directory / artifact.name)
        (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        os.rename(directory, SNAPSHOT)
    record = {
        "snapshot": str(SNAPSHOT),
        "manifest_sha256": digest(SNAPSHOT / "manifest.json"),
        "artifact_sha256": ARTIFACT_SHA,
        "source_commit": PRODUCT_COMMIT,
    }
    with (LAB / "output/a12-r1-snapshot.json").open("x") as stream:
        json.dump(record, stream, indent=2)
    print(json.dumps(record))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "preview", "run"])
    parser.add_argument("--mode", choices=MODES)
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
    record = json.loads((LAB / "output/a12-r1-snapshot.json").read_text())
    snapshot_sha = record["manifest_sha256"]
    if digest(SNAPSHOT / "manifest.json") != snapshot_sha:
        raise RuntimeError("a12_manifest_changed")
    payload = (
        definitions
        + f"\nARTIFACT_SHA={ARTIFACT_SHA!r}\nPRODUCT_COMMIT={PRODUCT_COMMIT!r}\n"
        + f"SNAPSHOT_SHA={snapshot_sha!r}\nSETTINGS={{'mode': {args.mode!r}}}\n"
        + GUEST
    )
    compile(payload, "isolated-a12-package", "exec")
    suffix = "preview" if args.action == "preview" else "payload"
    path = LAB / f"output/a12-r1-{args.mode}-{suffix}.py"
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
