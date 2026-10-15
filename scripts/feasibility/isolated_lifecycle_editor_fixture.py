"""Owned private native editor plus a temporary XWayland window; no input calls."""

import argparse
import json
import os
import signal
import subprocess
import tempfile
import time
from pathlib import Path

from isolated_browser_fixture import write_json
from private_xwayland_environment import private_xwayland_environment


def coordinate(args, folder):
    native_environment = dict(os.environ, GDK_BACKEND="wayland")
    evidence = private_xwayland_environment(args.compositor_pid)
    xwayland_environment = dict(os.environ, GTK_IM_MODULE="simple")
    if os.environ.get("INKECHO_MIXED_XMAP_DIAGNOSTIC"):
        write_json(args.state_output.parent / "x-server.json", evidence)
    children = {}
    last = {}
    serial = None

    def launch(kind):
        child = subprocess.Popen(
            [
                "/usr/bin/python3",
                str(Path(__file__).with_name("isolated_mixed_editor_fixture.py")),
                "--child",
                kind,
                "--text-output",
                str(folder / f"{kind}-text.json"),
                "--state-output",
                str(folder / f"{kind}-state.json"),
                "--seconds",
                "120",
                "--activate-file",
                str(folder / "child-activation.json"),
            ],
            env=native_environment if kind == "native" else xwayland_environment,
        )
        children[kind] = child
        deadline = time.monotonic() + 5
        while not (folder / f"{kind}-state.json").exists():
            if child.poll() is not None or time.monotonic() >= deadline:
                raise RuntimeError("Owned lifecycle editor failed to start")
            time.sleep(0.025)

    def snapshot(kind):
        state = json.loads((folder / f"{kind}-state.json").read_text())
        if (
            state["target_pid"] != children[kind].pid
            or state["target_parent_pid"] != os.getpid()
        ):
            raise RuntimeError("Owned lifecycle editor identity mismatch")
        return state, json.loads((folder / f"{kind}-text.json").read_text())

    try:
        launch("native")
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            if args.activate_file.exists():
                request = json.loads(args.activate_file.read_text())
                if request["serial"] != serial:
                    serial = request["serial"]
                    if request["target"] == "xwayland" and "xwayland" not in children:
                        launch("xwayland")
                    elif request["target"] == "native" and "xwayland" in children:
                        child = children["xwayland"]
                        if child.poll() is None:
                            last["xwayland"] = snapshot("xwayland")
                            child.terminate()
                            child.wait(timeout=3)
                            last["xwayland"][0].update(active=False, focused=False)
                            write_json(
                                folder / "child-activation.json",
                                {"target": "native", "serial": serial},
                            )
            states, texts = {}, {}
            for kind, child in children.items():
                if child.poll() is None:
                    states[kind], texts[kind] = snapshot(kind)
                elif kind in last:
                    states[kind], texts[kind] = last[kind]
                else:
                    raise RuntimeError("Owned lifecycle editor exited unexpectedly")
            states["xwayland_pid"] = evidence["pid"]
            write_json(args.state_output, states)
            write_json(args.text_output, texts)
            time.sleep(0.025)
    finally:
        for child in children.values():
            if child.poll() is None:
                child.terminate()
            try:
                child.wait(timeout=3)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=3)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compositor-pid", type=int, required=True)
    parser.add_argument("--text-output", type=Path, required=True)
    parser.add_argument("--state-output", type=Path, required=True)
    parser.add_argument("--activate-file", type=Path, required=True)
    args = parser.parse_args()

    def terminate(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, terminate)
    try:
        with tempfile.TemporaryDirectory(prefix="inkecho-private-lifecycle-") as folder:
            coordinate(args, Path(folder))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
