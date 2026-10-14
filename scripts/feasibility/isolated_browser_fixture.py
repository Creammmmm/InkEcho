#!/usr/bin/env python3
"""Native Chrome fixture adapter for the private nested-keymap compositor only.

Produces a JSON text string and separate owned-PID/focus metadata. It sends no
input and cannot attach to the user's Wayland socket or inherit an X display.
"""

import argparse
import json
import os
import signal
import time
from pathlib import Path

from owned_wayland_browser_fixture import OwnedWaylandBrowser


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value))
    temporary.replace(path)


def parent_pid(pid):
    for line in (Path("/proc") / str(pid) / "status").read_text().splitlines():
        if line.startswith("PPid:"):
            return int(line.split()[1])
    raise RuntimeError("Owned browser parent PID unavailable")


def private_environment():
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", "/")).resolve()
    root = runtime.parent
    if (
        runtime.name != "runtime"
        or root.parent != Path("/tmp")
        or not root.name.startswith("inkecho-isolated-keymap-")
        or os.environ.get("WAYLAND_DISPLAY") != "inkecho-isolated-keymap"
        or not (runtime / "inkecho-isolated-keymap").is_socket()
        or os.environ.get("DISPLAY")
        or not os.environ.get("DBUS_SESSION_BUS_ADDRESS")
    ):
        raise RuntimeError("Private compositor environment required")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target", choices=("chrome-textarea", "chrome-contenteditable"), required=True
    )
    parser.add_argument("--text-output", type=Path, required=True)
    parser.add_argument("--state-output", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=120)
    parser.add_argument("--switch-after", type=int, default=0)
    args = parser.parse_args()
    if not 0 < args.seconds <= 300:
        parser.error("seconds must be within (0, 300]")
    private_environment()

    def terminate(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, terminate)
    try:
        with OwnedWaylandBrowser(
            args.target.removeprefix("chrome-"), args.switch_after
        ) as fixture:
            pid = fixture.process.pid
            actual_parent = parent_pid(pid)
            if actual_parent != os.getpid():
                raise RuntimeError("Browser is not the wrapper's direct child")
            deadline = time.monotonic() + args.seconds
            native = None
            while time.monotonic() < deadline:
                if fixture.process.poll() is not None:
                    raise RuntimeError("Owned browser exited")
                snapshot = fixture.snapshot()
                if snapshot is not None and native is None:
                    evidence = fixture.native_evidence()
                    if all(
                        value is True
                        for key, value in evidence.items()
                        if key != "ozone_platform"
                    ):
                        native = evidence
                fresh = bool(
                    snapshot is not None
                    and time.monotonic() - snapshot["sampled_at"] < 0.5
                    and native is not None
                )
                state = {
                    "active": bool(fresh and snapshot["document_focused"]),
                    "focused": bool(
                        fresh
                        and snapshot["document_focused"]
                        and snapshot["field_focused"]
                    ),
                    "target_pid": pid,
                    "target_parent_pid": actual_parent,
                    "sampled_at": snapshot["sampled_at"] if snapshot else None,
                    "native_evidence": native,
                }
                if snapshot is not None:
                    state.update(
                        {
                            key: snapshot[key]
                            for key in ("first_count", "second_count", "switch_done")
                        }
                    )
                    write_json(args.text_output, snapshot["text"])
                write_json(args.state_output, state)
                time.sleep(0.05)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
