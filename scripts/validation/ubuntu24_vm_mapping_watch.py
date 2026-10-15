"""Observe the frozen, owned keyboard probe without changing its acceptance."""

import argparse
import hashlib
import json
import re
import subprocess

from ubuntu24_vm import ROOT

WATCH = r"""
import threading
from collections import Counter

env, identity = desktop()
if identity["session_type"] != "x11" or identity["session_locked_hint"] != "no":
    raise RuntimeError("unlocked_actual_xorg_session_required")
appdir, package_env = package_environment(env)
probe_name = f"keyboard_latency_probe_vm_{SETTINGS['generation']}.py"
probe = INPUT / "scripts/validation" / probe_name
expected_probe = {
    "r4": "09163aec2b2e4a5b625b18f6064b9f67cd311e8cf8d79b0bed73ac2f566910b7",
    "r5": "e3f4e17e8ce3fd4fd70199d7359c0199a5b65d198fb093a35eddc5ceec1341c6",
}[SETTINGS["generation"]]
if hashlib.sha256(probe.read_bytes()).hexdigest() != expected_probe:
    raise RuntimeError("frozen_probe_hash_mismatch")
stem = ("keyboard40-" if SETTINGS["control40"] else "keyboard20-") + SETTINGS["label"]
output = OUTPUT / f"{stem}.json"
watch_output = OUTPUT / f"mapping-watch-{SETTINGS['label']}.json"
if output.exists() or watch_output.exists():
    raise RuntimeError("evidence_already_exists")


def query(command, timeout=0.2):
    began = time.monotonic()
    try:
        result = subprocess.run(
            command, env=env, capture_output=True, text=True, timeout=timeout
        )
        return {
            "exit": result.returncode,
            "value": result.stdout.strip(),
            "duration": round(time.monotonic() - began, 4),
        }
    except subprocess.TimeoutExpired:
        return {"code": "timeout", "duration": round(time.monotonic() - began, 4)}


def process_state(pid):
    try:
        directory = Path(f"/proc/{pid}")
        fields = (directory / "stat").read_text().rsplit(")", 1)[1].split()
        states = Counter()
        for thread in (directory / "task").iterdir():
            try:
                state = (thread / "stat").read_text().rsplit(")", 1)[1].split()[0]
                states[state] += 1
            except FileNotFoundError:
                pass
        channel = (directory / "wchan").read_text().strip()
        return {
            "pid": pid,
            "start_ticks": int(fields[19]),
            "state": fields[0],
            "utime_ticks": int(fields[11]),
            "stime_ticks": int(fields[12]),
            "threads": dict(states),
            "wchan": channel
            if re.fullmatch(r"[A-Za-z0-9_.]{1,100}", channel) else None,
        }
    except (FileNotFoundError, ProcessLookupError):
        return {"pid": pid, "alive": False}


def frame_clients():
    result = []
    for directory in Path("/proc").iterdir():
        if not directory.name.isdigit():
            continue
        try:
            if directory.stat().st_uid != os.getuid():
                continue
            executable = (directory / "exe").resolve(strict=True)
            if executable.name == "mutter-x11-frames":
                result.append({
                    "comm": (directory / "comm").read_text().strip(),
                    "exe": str(executable),
                    **process_state(int(directory.name)),
                })
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
    return result


def property_number(source, name):
    match = re.search(
        rf"^{re.escape(name)}(?:\([^\n)]*\))?[ \t]*(?:=|:[ \t]*window id #)[ \t]*"
        r"(0x[0-9a-fA-F]+|[0-9]+)[ \t]*$",
        source,
        re.MULTILINE,
    )
    if match:
        value = match[1]
        return int(value, 16 if value.startswith("0x") else 10)
    return None


def owned_windows(pid):
    search = query(["xdotool", "search", "--limit", "8", "--pid", str(pid)])
    result = []
    for window in search.get("value", "").splitlines():
        if not window.isdigit():
            continue
        properties = query([
            "xprop", "-id", window, "_NET_WM_PID", "_MUTTER_NEEDS_FRAME",
            "WM_STATE", "_NET_WM_DESKTOP",
        ]).get("value", "")
        if property_number(properties, "_NET_WM_PID") != pid:
            continue
        info = query(["xwininfo", "-id", window, "-tree"]).get("value", "")
        map_info = query(["xwininfo", "-id", window]).get("value", "")
        mapping = re.search(r"Map State: (\w+)", map_info)
        parent = re.search(r"Parent window id: (0x[0-9a-fA-F]+)", info)
        root = re.search(r"Root window id: (0x[0-9a-fA-F]+)", info)
        parent_id = int(parent[1], 16) if parent else None
        root_id = int(root[1], 16) if root else None
        parent_properties = query([
            "xprop", "-id", str(parent_id), "_NET_WM_PID"
        ]).get("value", "") if parent_id is not None else ""
        result.append({
            "window": int(window),
            "map_state": mapping[1] if mapping and mapping[1] in {
                "IsUnMapped", "IsUnviewable", "IsViewable"
            } else None,
            "needs_frame": property_number(properties, "_MUTTER_NEEDS_FRAME"),
            "desktop": property_number(properties, "_NET_WM_DESKTOP"),
            "parent_window": parent_id,
            "parent_is_root": parent_id == root_id if root_id is not None else None,
            "parent_pid": property_number(parent_properties, "_NET_WM_PID"),
        })
    return result


def fixtures(probe_pid):
    children = Path(f"/proc/{probe_pid}/task/{probe_pid}/children")
    try:
        pids = children.read_text().split()
    except FileNotFoundError:
        return []
    result = []
    for value in pids:
        child = Path(f"/proc/{value}")
        try:
            argv = (child / "cmdline").read_bytes().decode().split("\0")
            if len(argv) < 4 or argv[1] != str(probe) or argv[2] != "--fixture":
                continue
            if argv[3] not in {"gtk", "vte"}:
                continue
            pid = int(value)
            before = process_state(pid)
            windows = owned_windows(pid)
            after = process_state(pid)
            if before.get("start_ticks") != after.get("start_ticks"):
                continue
            result.append({"target": argv[3], **after, "windows": windows})
        except (FileNotFoundError, ProcessLookupError):
            continue
    return result


stop = threading.Event()
screensaver = []
began = time.monotonic()


def screensaver_watch():
    while not stop.is_set():
        row = query([
            "gdbus", "call", "--session", "--dest", "org.gnome.ScreenSaver",
            "--object-path", "/org/gnome/ScreenSaver", "--method",
            "org.gnome.ScreenSaver.GetActive",
        ], timeout=2)
        value = row.pop("value", None)
        row["active"] = {"(true,)": True, "(false,)": False}.get(value)
        row["elapsed"] = round(time.monotonic() - began, 3)
        screensaver.append(row)
        stop.wait(2)


thread = threading.Thread(target=screensaver_watch)
samples = []
with (OUTPUT / f"{stem}.log").open("x") as log:
    command = [
        str(appdir / "usr/bin/python3"), str(probe), "--environment", "ubuntu24-vm-x11",
        "--qt-loop", "--xdotool", "/usr/bin/xdotool", "--repeat", "5",
        "--targets", *SETTINGS.get("targets", ["gtk", "vte"]),
        "--output", str(output),
    ]
    if SETTINGS["control40"]:
        command.extend(["--pacing", ".04", ".04", ".04"])
    if SETTINGS["restore_policy"] == "end-of-insertion-candidate":
        command.extend(["--restore-policy", SETTINGS["restore_policy"]])
    if SETTINGS.get("cancel_after") is not None:
        command.extend(["--cancel-after", str(SETTINGS["cancel_after"])])
    process = subprocess.Popen(
        command, env=package_env, stdout=log, stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    probe_identity = process_state(process.pid)
    thread.start()
    completed_at = None
    try:
        while time.monotonic() - began < 70:
            row = {
                "elapsed": round(time.monotonic() - began, 3),
                "gnome": process_state(identity["gnome_shell_pid"]),
                "frame_clients": frame_clients(),
                "fixtures": fixtures(process.pid),
            }
            properties = query([
                "xprop", "-root", "_NET_ACTIVE_WINDOW", "_NET_CURRENT_DESKTOP",
                "_NET_CLIENT_LIST",
            ])
            source = properties.pop("value", "")
            row["root"] = {
                **properties,
                "active_window": property_number(source, "_NET_ACTIVE_WINDOW"),
                "desktop": property_number(source, "_NET_CURRENT_DESKTOP"),
                "client_count": len(re.findall(r"0x[0-9a-fA-F]+", next((
                    line for line in source.splitlines()
                    if line.startswith("_NET_CLIENT_LIST")
                ), ""))),
            }
            samples.append(row)
            if process.poll() is not None:
                if completed_at is None:
                    completed_at = time.monotonic()
                elif time.monotonic() - completed_at >= 2:
                    break
            stop.wait(0.5)
    finally:
        stop.set()
        thread.join(timeout=3)
status = process.poll()
report = {
    **identity, "measurement": "diagnostic_sidecar_not_performance_score",
    "probe_sha256": hashlib.sha256(probe.read_bytes()).hexdigest(),
    "settings": SETTINGS,
    "probe_exit": status,
    "probe_running": status is None,
    "probe_pid": process.pid,
    "probe_start_ticks": probe_identity.get("start_ticks"),
    "clock_ticks_per_second": os.sysconf("SC_CLK_TCK"),
    "samples": samples, "screensaver": screensaver,
    "screensaver_thread_joined": not thread.is_alive(), "cloud_requests": 0,
}
watch_output.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({"probe_exit": process.returncode, "samples": len(samples)}))
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", default="monitored-r4")
    parser.add_argument("--generation", choices=["r4", "r5"], default="r4")
    parser.add_argument("--control40", action="store_true")
    parser.add_argument(
        "--targets",
        nargs="+",
        choices=["gtk", "vte", "chrome-textarea", "chrome-contenteditable"],
        default=["gtk", "vte"],
    )
    parser.add_argument("--cancel-after", type=int, choices=[12])
    parser.add_argument(
        "--restore-policy",
        choices=["per-character-production", "end-of-insertion-candidate"],
        default="per-character-production",
    )
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", args.label):
        parser.error("bounded filename-safe label required")
    if args.generation == "r4" and args.restore_policy != "per-character-production":
        parser.error("candidate restoration requires the reviewed r5 probe")
    if args.cancel_after is not None and args.targets != ["gtk"]:
        parser.error("partial cancellation requires only the owned GTK target")
    helper = (ROOT / "scripts/validation/ubuntu24_vm_guest.py").read_text()
    definitions = helper.rsplit('if __name__ == "__main__":', 1)[0]
    payload = definitions + f"\nSETTINGS = {vars(args)!r}\n" + WATCH
    compile(payload, "isolated-guest-mapping-watch", "exec")
    path = (
        ROOT
        / "build/ubuntu24-perf-vm/output"
        / f"mapping-watch-{args.label}-payload.py"
    )
    with path.open("x") as stream:
        stream.write(payload)
    with path.with_suffix(".manifest.json").open("x") as stream:
        json.dump(
            {
                "payload_file": path.name,
                "sha256": hashlib.sha256(payload.encode()).hexdigest(),
                "saved_after_run": False,
            },
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
