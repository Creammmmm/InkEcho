"""Validate a frozen source snapshot using the old AppImage's dependencies.

This separate runner leaves historical R5 tools and artifacts unchanged.
Preparation copies only repository source, the reviewed probe and its license.
Running requires the existing isolated guest's actual, unlocked Xorg session.
"""

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from ubuntu24_vm import LAB, ROOT

BACKEND_SHA = "1aff28ceab124e9745f2afda5ac8fec084d71be3185719a73556ad0b755f60f3"
PROBE_SHA = "f0cb80b62727f9c03c26af8c929255bf99c41c349c8afe3769dc38b49d897344"
SNAPSHOT = LAB / "input/source-r6"

GUEST = r"""
env, identity = desktop()
if identity["session_type"] != "x11" or identity["session_locked_hint"] != "no":
    raise RuntimeError("unlocked_actual_xorg_session_required")
snapshot = INPUT / "source-r6"
manifest_path = snapshot / "manifest.json"
if hashlib.sha256(manifest_path.read_bytes()).hexdigest() != SNAPSHOT_SHA:
    raise RuntimeError("unexpected_snapshot_manifest")
manifest = json.loads(manifest_path.read_text())
if len(manifest["source_files"]) != 43:
    raise RuntimeError("unexpected_source_file_count")
for group in ["source_files", "tool_files"]:
    for relative, checksum in manifest[group].items():
        path = (snapshot / relative).resolve(strict=True)
        if not path.is_relative_to(snapshot):
            raise RuntimeError("snapshot_path_escape")
        if hashlib.sha256(path.read_bytes()).hexdigest() != checksum:
            raise RuntimeError("snapshot_hash_mismatch")
if manifest["source_files"]["src/inkecho/platform/keyboard.py"] != BACKEND_SHA:
    raise RuntimeError("unexpected_keyboard_source")
probe_relative = "scripts/validation/keyboard_latency_probe.py"
if manifest["tool_files"][probe_relative] != PROBE_SHA:
    raise RuntimeError("unexpected_keyboard_probe")
appdir, env = package_environment(env)
source_root = snapshot / "src"
env["PYTHONPATH"] = str(source_root) + os.pathsep + env["PYTHONPATH"]
env["PYTHONDONTWRITEBYTECODE"] = "1"
stem = "source-r6-" + SETTINGS["label"]
probe_output = OUTPUT / f"{stem}.json"
summary_output = OUTPUT / f"{stem}-acceptance.json"
if probe_output.exists() or summary_output.exists():
    raise RuntimeError("evidence_already_exists")


def screensaver():
    began = time.monotonic()
    native_env = dict(env)
    for name in ["PYTHONHOME", "PYTHONPATH", "LD_LIBRARY_PATH", "QT_PLUGIN_PATH"]:
        native_env.pop(name, None)
    try:
        result = subprocess.run([
            "gdbus", "call", "--session", "--dest", "org.gnome.ScreenSaver",
            "--object-path", "/org/gnome/ScreenSaver", "--method",
            "org.gnome.ScreenSaver.GetActive",
        ], env=native_env, capture_output=True, text=True, timeout=2)
        return {
            "exit": result.returncode,
            "active": {"(true,)": True, "(false,)": False}.get(result.stdout.strip()),
            "duration_seconds": round(time.monotonic() - began, 4),
        }
    except subprocess.TimeoutExpired:
        return {
            "code": "timeout", "duration_seconds": round(time.monotonic() - began, 4)
        }


targets = ["chrome-textarea", "chrome-contenteditable", "gtk", "vte"]
if SETTINGS["mode"] == "cancel12":
    targets = ["gtk"]
command = [
    str(appdir / "usr/bin/python3"), str(snapshot / probe_relative),
    "--source-root", str(source_root), "--environment", "ubuntu24-vm-x11",
    "--qt-loop", "--xdotool", "/usr/bin/xdotool", "--repeat", "5",
    "--targets", *targets, "--output", str(probe_output),
]
if SETTINGS["mode"] == "control40":
    command.extend(["--pacing", ".04", ".04", ".04"])
if SETTINGS["mode"] == "cancel12":
    command.extend(["--cancel-after", "12"])
before = screensaver()
with (OUTPUT / f"{stem}.log").open("x") as log:
    process = subprocess.Popen(
        command, env=env, stdout=log, stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    fields = Path(f"/proc/{process.pid}/stat").read_text().rsplit(")", 1)[1].split()
    start_ticks = int(fields[19])
    print(json.dumps({"probe_pid": process.pid, "start_ticks": start_ticks}),
          flush=True)
    try:
        process.wait(timeout=120)
    except subprocess.TimeoutExpired:
        pass  # Observation timeout never interrupts the probe's key/map cleanup.
status = process.poll()
summary = {
    **identity,
    "runtime_kind": "source",
    "dependency_artifact_sha256": EXPECTED_SHA256,
    "snapshot_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
    "source_files_checked": len(manifest["source_files"]),
    "probe_pid": process.pid,
    "probe_start_ticks": start_ticks,
    "probe_exit": status,
    "probe_running": status is None,
    "settings": SETTINGS,
    "screensaver_before": before,
    "passed": False,
    "cloud_requests": 0,
    "credential_store_read": False,
    "microphone_used": False,
}
if status is not None:
    summary["screensaver_after"] = screensaver()
    if probe_output.exists():
        report = json.loads(probe_output.read_text())
        origin_matches = {}
        for name, relative in {
            "inkecho": "src/inkecho/__init__.py",
            "inkecho.platform.keyboard": "src/inkecho/platform/keyboard.py",
            "inkecho.runtime": "src/inkecho/runtime.py",
        }.items():
            origin = report.get("runtime_origins", {}).get(name, {})
            origin_matches[name] = (
                origin.get("path") == str(snapshot / relative)
                and origin.get("sha256") == manifest["source_files"][relative]
            )
        rows = report.get("targets", [])
        expected_writes = 13 if SETTINGS["mode"] == "cancel12" else 136
        summary["origins_match_snapshot"] = origin_matches
        summary["mapping_counts_match"] = len(rows) == len(targets) and all(
            row.get("mapping_counts") == {
                "mapping_writes": expected_writes,
                "restore_calls": 1,
                "successful_restore_calls": 1,
            } for row in rows
        )
        summary["passed"] = (
            status == 0 and report.get("passed") is True
            and report.get("runtime_kind") == "source"
            and report.get("production_behavior_modified") is False
            and "candidate_policy" not in report
            and report.get("restore_policy") == "production"
            and report.get("expected_source_root") == str(source_root)
            and [row.get("target") for row in rows] == targets
            and all(origin_matches.values()) and summary["mapping_counts_match"]
        )
summary_output.write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary))
if not summary["passed"]:
    raise SystemExit(1)
"""


def digest(content):
    return hashlib.sha256(content).hexdigest()


def prepare():
    if SNAPSHOT.exists():
        raise RuntimeError("source_snapshot_already_exists")
    paths = [
        path
        for path in (ROOT / "src/inkecho").rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    ]
    if len(paths) != 43 or any(path.is_symlink() for path in paths):
        raise RuntimeError("unexpected_source_inventory")
    backend = (ROOT / "src/inkecho/platform/keyboard.py").read_bytes()
    probe = (ROOT / "scripts/validation/keyboard_latency_probe.py").read_bytes()
    if digest(backend) != BACKEND_SHA or digest(probe) != PROBE_SHA:
        raise RuntimeError("source_or_probe_not_frozen_revision")
    manifest = {"source_files": {}, "tool_files": {}}
    with tempfile.TemporaryDirectory(
        prefix=".source-r6-", dir=SNAPSHOT.parent
    ) as temporary:
        directory = Path(temporary)
        for path in paths + [
            ROOT / "scripts/validation/keyboard_latency_probe.py",
            ROOT / "assets/licenses/websockets-LICENSE.txt",
        ]:
            relative = str(path.relative_to(ROOT))
            content = path.read_bytes()
            destination = directory / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
            group = "source_files" if path in paths else "tool_files"
            manifest[group][relative] = digest(content)
        (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        os.rename(directory, SNAPSHOT)
    record = {
        "snapshot": str(SNAPSHOT),
        "manifest_sha256": digest((SNAPSHOT / "manifest.json").read_bytes()),
    }
    with (LAB / "output/source-r6-snapshot.json").open("x") as stream:
        json.dump(record, stream, indent=2)
    print(json.dumps(record))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "run"])
    parser.add_argument("--mode", choices=["control40", "default20", "cancel12"])
    parser.add_argument("--label", choices=["control40", "default20", "cancel12"])
    args = parser.parse_args()
    if args.action == "prepare":
        if args.mode or args.label:
            parser.error("prepare takes no run options")
        prepare()
        return
    if not args.mode or args.label != args.mode:
        parser.error("run requires a matching fixed mode and evidence label")
    helper = (ROOT / "scripts/validation/ubuntu24_vm_guest.py").read_text()
    definitions = helper.rsplit('if __name__ == "__main__":', 1)[0]
    snapshot_record = json.loads((LAB / "output/source-r6-snapshot.json").read_text())
    snapshot_sha = snapshot_record["manifest_sha256"]
    if digest((SNAPSHOT / "manifest.json").read_bytes()) != snapshot_sha:
        raise RuntimeError("snapshot_manifest_changed")
    payload = (
        definitions
        + f"\nBACKEND_SHA={BACKEND_SHA!r}\nPROBE_SHA={PROBE_SHA!r}\n"
        + f"SNAPSHOT_SHA={snapshot_sha!r}\n"
        + f"SETTINGS={vars(args)!r}\n"
        + GUEST
    )
    compile(payload, "isolated-source-r6", "exec")
    path = LAB / f"output/source-r6-{args.label}-payload.py"
    with path.open("x") as stream:
        stream.write(payload)
    with path.with_suffix(".manifest.json").open("x") as stream:
        json.dump(
            {"payload_file": path.name, "sha256": digest(payload.encode())},
            stream,
            indent=2,
        )
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
