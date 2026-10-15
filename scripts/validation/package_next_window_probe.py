"""Observe fresh owned GTK/VTE readiness after a long local pipeline; no input."""

import argparse
import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

from keyboard_latency_probe import (
    fixture_environment,
    readiness_scene,
    runtime_origins,
    start_time,
    verify_ubuntu24_vm_x11,
)


async def run(args):
    metadata = verify_ubuntu24_vm_x11()
    appdir = args.package_root.parent
    if not Path(sys.executable).resolve().is_relative_to(appdir / "usr"):
        raise RuntimeError("selected_package_interpreter_required")
    origins = runtime_origins(None)["runtime_origins"]
    if not all(
        Path(row["path"]).is_relative_to(args.package_root) for row in origins.values()
    ):
        raise RuntimeError("module_escaped_selected_package")
    report = {
        "passed": False,
        "runtime_kind": "package",
        "runtime_origins": origins,
        "environment_metadata": metadata,
        "text_input_requested": False,
        "cloud_requests": 0,
        "user_credentials_read": False,
        "targets": [],
    }
    for target in ["gtk", "vte"]:
        with tempfile.TemporaryDirectory(prefix="inkecho-next-owned-") as name:
            output = Path(name) / "ready.json"
            with args.output.with_name(f"{args.output.stem}-{target}.log").open(
                "xb"
            ) as log:
                process = subprocess.Popen(
                    [
                        "/usr/bin/python3",
                        str(Path(__file__).with_name("keyboard_latency_probe.py")),
                        "--fixture",
                        target,
                        "--output",
                        str(output),
                    ],
                    env=fixture_environment(),
                    stdout=log,
                    stderr=subprocess.STDOUT,
                )
                identity = start_time(process.pid)
                began = time.monotonic()
                visible = []
                ready = False
                try:
                    for _ in range(120):
                        if process.poll() is not None:
                            break
                        query = subprocess.run(
                            [
                                args.xdotool,
                                "search",
                                "--onlyvisible",
                                "--pid",
                                str(process.pid),
                            ],
                            env=fixture_environment(),
                            capture_output=True,
                            text=True,
                            timeout=3,
                        )
                        visible = (
                            query.stdout.splitlines() if query.returncode == 0 else []
                        )
                        if visible and output.exists():
                            window = int(visible[0])
                            owner = subprocess.check_output(
                                [args.xdotool, "getwindowpid", str(window)],
                                env=fixture_environment(),
                                text=True,
                                timeout=3,
                            ).strip()
                            ready = (
                                process.poll() is None
                                and start_time(process.pid) == identity
                                and owner == str(process.pid)
                            )
                            if ready:
                                break
                        await asyncio.sleep(0.05)
                    row = {
                        "target": target,
                        "ready": ready,
                        "process_alive": process.poll() is None,
                        "readyfile_exists": output.exists(),
                        "visible_window_count": len(visible),
                        "elapsed_seconds": round(time.monotonic() - began, 4),
                        "started_after_pipeline_ms": round(
                            (began - args.pipeline_exited_at) * 1000, 3
                        ),
                        "pid": process.pid,
                        "start_ticks": identity,
                    }
                    if not ready:
                        gate = SimpleNamespace(
                            environment="ubuntu24-vm-x11",
                            verified_session_id=os.environ["XDG_SESSION_ID"],
                            xdotool=args.xdotool,
                        )
                        row["scene"] = readiness_scene(gate, process, identity)
                    report["targets"].append(row)
                finally:
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()
                if not ready:
                    break
    report["passed"] = len(report["targets"]) == 2 and all(
        row["ready"] for row in report["targets"]
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--xdotool", required=True)
    parser.add_argument("--pipeline-exited-at", type=float, required=True)
    args = parser.parse_args()
    args.package_root = args.package_root.resolve(strict=True)
    sys.path.insert(0, str(args.package_root))
    from PySide6.QtWidgets import QApplication

    from inkecho.runtime import ManagedQtEventLoop

    application = QApplication([])
    application.setQuitOnLastWindowClosed(False)
    if application.platformName() != "xcb":
        raise RuntimeError("actual_xorg_qt_platform_required")
    with ManagedQtEventLoop(application) as loop:
        report = loop.run_until_complete(run(args))
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
