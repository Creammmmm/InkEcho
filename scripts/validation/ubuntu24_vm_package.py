"""Run the separately built a11 artifact in the existing isolated Noble VM."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from ubuntu24_vm import LAB, ROOT

ARTIFACT_SHA = "a61b2a036863d9c2ea1515055c7fadb7c9905e9a0139aa05e94936b32a67cb97"
PRODUCT_COMMIT = "004b054eb324d6c54b622db6df4d0e2ede106b57"
SNAPSHOT = LAB / "input/a11-r1"
MODES = [
    "control40",
    "default20",
    "cancel12",
    "pipeline40",
    "pipeline20",
    "pipeline-character-fast",
    "focus-switch",
    "ui",
]

GUEST = r"""
env, identity = desktop()
if identity["session_type"] != "x11" or identity["session_locked_hint"] != "no":
    raise RuntimeError("unlocked_actual_xorg_session_required")
snapshot = INPUT / "a11-r1"
manifest_path = snapshot / "manifest.json"
if hashlib.sha256(manifest_path.read_bytes()).hexdigest() != SNAPSHOT_SHA:
    raise RuntimeError("unexpected_a11_snapshot_manifest")
manifest = json.loads(manifest_path.read_text())
for group in ["source_files", "tool_files"]:
    for relative, checksum in manifest[group].items():
        path = (snapshot / relative).resolve(strict=True)
        if not path.is_relative_to(snapshot):
            raise RuntimeError("snapshot_path_escape")
        if hashlib.sha256(path.read_bytes()).hexdigest() != checksum:
            raise RuntimeError("snapshot_hash_mismatch")
artifact = snapshot / "InkEcho-0.1.0a11-x86_64.AppImage"
with artifact.open("rb") as stream:
    if hashlib.file_digest(stream, "sha256").hexdigest() != ARTIFACT_SHA:
        raise RuntimeError("unexpected_a11_artifact")
runtime = Path.home() / "inkecho-a11-runtime-r1"
appdir = runtime / "squashfs-root"
if not appdir.exists():
    runtime.mkdir(mode=0o700, exist_ok=True)
    with (OUTPUT / "a11-r1-extract.log").open("x") as log:
        checked([str(artifact), "--appimage-extract"], cwd=runtime,
                stdout=log, stderr=subprocess.STDOUT)
inventory = json.loads((appdir / "usr/share/doc/inkecho/inventory.json").read_text())
if inventory["application"] != "0.1.0a11" or len(manifest["source_files"]) != 43:
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
stem = "a11-r1-" + SETTINGS["mode"]
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
if mode in ["control40", "default20", "cancel12"]:
    command = [python, str(tools / "keyboard_latency_probe.py"),
               "--environment", "ubuntu24-vm-x11", "--qt-loop", "--xdotool",
               "/usr/bin/xdotool", "--repeat", "5", "--targets", *targets,
               "--output", str(output)]
    if mode == "control40":
        command.extend(["--pacing", ".04", ".04", ".04"])
    if mode == "cancel12":
        command.extend(["--cancel-after", "12"])
elif mode.startswith("pipeline"):
    command = [python, str(tools / "performance_package_probe.py"),
               "--package-root", str(appdir / "packages"),
               "--owned-ubuntu24-vm-x11", "--xdotool", "/usr/bin/xdotool",
               "--output", str(output)]
    if mode == "pipeline40":
        command.extend(["--pacing", ".04"])
    if mode == "pipeline-character-fast":
        command.extend(["--fixture-sse-profile", "one-character-fast"])
elif mode == "focus-switch":
    command = [python, str(tools / "package_cursor_switch_probe.py"),
               "--package-root", str(appdir / "packages"), "--xdotool",
               "/usr/bin/xdotool", "--output", str(output)]
else:
    profile = Path.home() / "a11-r1-ui-profile"
    screenshots = OUTPUT / "a11-r1-ui-pages"
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


before = screensaver()
with (OUTPUT / f"{stem}.log").open("x") as log:
    process = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT,
                               start_new_session=True)
    fields = Path(f"/proc/{process.pid}/stat").read_text().rsplit(")", 1)[1].split()
    start_ticks = int(fields[19])
    print(json.dumps({"probe_pid": process.pid, "start_ticks": start_ticks}),
          flush=True)
    try:
        process.wait(timeout=120)
    except subprocess.TimeoutExpired:
        pass  # Never interrupt a producer's pending key/map cleanup.
status = process.poll()
summary = {**identity, "runtime_kind": "package", "version": "0.1.0a11",
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
if status is not None:
    summary["screensaver_after"] = screensaver()
    if mode == "ui":
        summary["screenshots"] = len(list(screenshots.glob("page-*.png")))
        summary["passed"] = status == 0 and summary["screenshots"] == 9
    elif output.exists():
        report = json.loads(output.read_text())
        if mode in ["control40", "default20", "cancel12", "focus-switch"]:
            origin_matches = {}
            for name, relative in {
                "inkecho": "src/inkecho/__init__.py",
                "inkecho.platform.keyboard": "src/inkecho/platform/keyboard.py",
                "inkecho.runtime": "src/inkecho/runtime.py",
            }.items():
                expected_path = appdir / "packages" / Path(relative).relative_to("src")
                origin = report.get("runtime_origins", {}).get(name, {})
                origin_matches[name] = (
                    origin.get("path") == str(expected_path)
                    and origin.get("sha256") == manifest["source_files"][relative])
            summary["origins_match_package"] = origin_matches
            origin_ok = all(origin_matches.values())
            flags_ok = report.get("production_behavior_modified") is False
            if mode != "focus-switch":
                rows = report.get("targets", [])
                writes = 13 if mode == "cancel12" else 136
                summary["mapping_counts_match"] = len(rows) == len(targets) and all(
                    row.get("mapping_counts") == {"mapping_writes": writes,
                        "restore_calls": 1, "successful_restore_calls": 1}
                    for row in rows)
                flags_ok = (flags_ok and report.get("runtime_kind") == "unclassified"
                    and report.get("expected_source_root") is None
                    and report.get("restore_policy") == "production"
                    and "candidate_policy" not in report
                    and [row.get("target") for row in rows] == targets
                    and summary["mapping_counts_match"])
            else:
                flags_ok = flags_ok and report.get("runtime_kind") == "package"
        else:
            origin_ok = (report.get("runtime_modules_verified") == 10
                and report.get("runtime_kind") == "package")
            expected_profile = (
                "one-character-fast" if mode == "pipeline-character-fast" else "normal"
            )
            flags_ok = (report.get("version") == "0.1.0a11"
                and report.get("cloud_requests") == 0
                and report.get("user_credentials_read") is False
                and report.get("real_microphone") is False
                and report.get("real_desktop_input") is True
                and report.get("fixture_sse_profile") == expected_profile)
        summary["passed"] = (status == 0 and report.get("passed") is True
                             and origin_ok and flags_ok)
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
        raise RuntimeError("a11_snapshot_already_exists")
    baseline = json.loads(
        (ROOT / "build/performance-a11-source-before-build.json").read_text()
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
        "scripts/validation/package_cursor_switch_probe.py",
        "assets/licenses/websockets-LICENSE.txt",
    ]
    artifact = ROOT / "dist/InkEcho-0.1.0a11-x86_64.AppImage"
    if digest(artifact) != ARTIFACT_SHA:
        raise RuntimeError("unexpected_a11_artifact")
    manifest = {
        "source_commit": PRODUCT_COMMIT,
        "artifact_sha256": ARTIFACT_SHA,
        "source_files": sources,
        "tool_files": {name: digest(ROOT / name) for name in tools},
    }
    with tempfile.TemporaryDirectory(prefix=".a11-r1-", dir=SNAPSHOT.parent) as name:
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
    with (LAB / "output/a11-r1-snapshot.json").open("x") as stream:
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
    record = json.loads((LAB / "output/a11-r1-snapshot.json").read_text())
    snapshot_sha = record["manifest_sha256"]
    if digest(SNAPSHOT / "manifest.json") != snapshot_sha:
        raise RuntimeError("a11_manifest_changed")
    payload = (
        definitions
        + f"\nARTIFACT_SHA={ARTIFACT_SHA!r}\nPRODUCT_COMMIT={PRODUCT_COMMIT!r}\n"
        + f"SNAPSHOT_SHA={snapshot_sha!r}\nSETTINGS={{'mode': {args.mode!r}}}\n"
        + GUEST
    )
    compile(payload, "isolated-a11-package", "exec")
    suffix = "preview" if args.action == "preview" else "payload"
    path = LAB / f"output/a11-r1-{args.mode}-{suffix}.py"
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
