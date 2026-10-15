"""Bounded read-only WM sampling and an owned, no-input VTE observation."""

import argparse
import subprocess

from ubuntu24_vm import ROOT

DIAGNOSTIC = r"""
from collections import Counter

env, identity = desktop()
pid = identity["gnome_shell_pid"]
began = time.monotonic()


def process_state():
    fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    states = Counter()
    for thread in Path(f"/proc/{pid}/task").iterdir():
        try:
            state = (thread / "stat").read_text().rsplit(")", 1)[1].split()[0]
            states[state] += 1
        except FileNotFoundError:
            pass
    return {
        "state": fields[0],
        "utime_ticks": int(fields[11]),
        "stime_ticks": int(fields[12]),
        "threads": dict(states),
    }


def query(command, timeout=2):
    try:
        result = subprocess.run(
            command, env=env, capture_output=True, text=True, timeout=timeout
        )
        return {
            "exit": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }
    except subprocess.TimeoutExpired:
        return {"code": "timeout"}


def wait_until(offset):
    while time.monotonic() - began < offset:
        time.sleep(0.1)


samples = []
for offset in [0, 2, 5]:
    wait_until(offset)
    row = {
        "elapsed_seconds": round(time.monotonic() - began, 3),
        "gnome": process_state(),
    }
    row["screensaver"] = query(
        [
            "gdbus",
            "call",
            "--session",
            "--dest",
            "org.gnome.ScreenSaver",
            "--object-path",
            "/org/gnome/ScreenSaver",
            "--method",
            "org.gnome.ScreenSaver.GetActive",
        ]
    )
    row["root"] = query(
        [
            "xprop",
            "-root",
            "_NET_SUPPORTING_WM_CHECK",
            "_NET_ACTIVE_WINDOW",
            "_NET_CLIENT_LIST",
            "_NET_CURRENT_DESKTOP",
        ]
    )
    samples.append(row)
journal = query(
    [
        "journalctl",
        "--user",
        "--boot",
        "--no-pager",
        "--output=json",
        "_COMM=gnome-shell",
        "-n",
        "100",
    ]
)
messages = []
if journal.get("exit") == 0:
    for line in journal["stdout"].splitlines():
        try:
            record = json.loads(line)
        except ValueError:
            continue
        message = record.get("MESSAGE", "")
        if isinstance(message, str) and any(
            word in message.lower() for word in ["keymap", "xkb", "window", "error"]
        ):
            messages.append(
                {
                    "timestamp_us": record.get("__REALTIME_TIMESTAMP"),
                    "message": message[:600],
                }
            )
report = {
    **identity,
    "clock_ticks_per_second": os.sysconf("SC_CLK_TCK"),
    "samples": samples,
    "relevant_guest_gnome_messages": messages[-15:],
    "text_requested": False,
    "cloud_requests": 0,
}
if OBSERVE:
    client_env = dict(env, GDK_BACKEND="x11")
    for name in ["PYTHONHOME", "PYTHONPATH", "LD_LIBRARY_PATH", "QT_PLUGIN_PATH"]:
        client_env.pop(name, None)
    with tempfile.TemporaryDirectory(prefix="inkecho-owned-vte-observe-") as name:
        state = Path(name) / "ready.json"
        with (OUTPUT / "wm-backlog-owned-vte-stderr.log").open("x") as log:
            process = subprocess.Popen(
                [
                    "/usr/bin/python3",
                    str(INPUT / "scripts/validation/keyboard_latency_probe_vm_r4.py"),
                    "--fixture",
                    "vte",
                    "--output",
                    str(state),
                ],
                env=client_env,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            began = time.monotonic()
            observations = []
            try:
                for offset in [0.2, 2, 5, 15]:
                    wait_until(offset)
                    windows = query(
                        ["xdotool", "search", "--limit", "8", "--pid", str(process.pid)]
                    )
                    owned = []
                    for window in windows.get("stdout", "").splitlines():
                        if not window.isdigit():
                            continue
                        info = query(["xwininfo", "-id", window])
                        mapping = next(
                            (
                                line.split(":", 1)[1].strip()
                                for line in info.get("stdout", "").splitlines()
                                if "Map State:" in line
                            ),
                            None,
                        )
                        properties = query(
                            [
                                "xprop",
                                "-id",
                                window,
                                "_NET_WM_PID",
                                "WM_STATE",
                                "_NET_WM_STATE",
                                "_NET_WM_DESKTOP",
                            ]
                        )
                        owned.append(
                            {
                                "window": int(window),
                                "map_state": mapping,
                                "properties": properties,
                            }
                        )
                    observations.append(
                        {
                            "elapsed_seconds": round(time.monotonic() - began, 3),
                            "pid": process.pid,
                            "alive": process.poll() is None,
                            "ready_file": state.exists(),
                            "owned_windows": owned,
                            "root": query(
                                [
                                    "xprop",
                                    "-root",
                                    "_NET_ACTIVE_WINDOW",
                                    "_NET_CURRENT_DESKTOP",
                                ]
                            ),
                            "gnome": process_state(),
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
            report["owned_vte_observations"] = observations
            report["owned_vte_exit"] = process.returncode
output = OUTPUT / (
    "wm-backlog-vte-observation.json" if OBSERVE else "wm-backlog-cpu.json"
)
output.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report))
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observe-vte", action="store_true")
    args = parser.parse_args()
    helper = (ROOT / "scripts/validation/ubuntu24_vm_guest.py").read_text()
    definitions = helper.rsplit('if __name__ == "__main__":', 1)[0]
    program = definitions + f"\nOBSERVE={args.observe_vte!r}\n" + DIAGNOSTIC
    subprocess.run(
        [
            str(ROOT / ".venv/bin/python"),
            str(ROOT / "scripts/validation/ubuntu24_vm.py"),
            "ssh",
            "--",
            "python3",
            "-",
        ],
        input=program,
        text=True,
        check=True,
    )


if __name__ == "__main__":
    main()
