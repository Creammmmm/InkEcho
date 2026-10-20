#!/usr/bin/env python3
"""Launch five settings pages and verify same-user IPC in disposable directories.

This checks desktop lifecycle, not cloud speech quality or native input support.
Run under a private display/session, never against an existing user instance.
"""

import argparse
import hashlib
import json
import os
import struct
import subprocess
import sys
import time
from pathlib import Path


def probe(output: Path, artifact: Path | None) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    prefix = [str(artifact)] if artifact else [sys.executable, "-m", "inkecho"]
    result = {
        "kind": "appimage" if artifact else "source",
        "session": os.environ.get("XDG_SESSION_TYPE", "unknown"),
        "qt_platform": os.environ.get("QT_QPA_PLATFORM", "default"),
        "voice_end_to_end": False,
        "clipboard_accessed": False,
    }
    if artifact:
        with artifact.open("rb") as stream:
            result["artifact_sha256"] = hashlib.file_digest(
                stream, "sha256"
            ).hexdigest()
    root = output / "private"
    root.mkdir(mode=0o700)
    environment = os.environ.copy()
    for name in ("CONFIG", "DATA", "STATE", "CACHE"):
        path = root / name.lower()
        path.mkdir(mode=0o700)
        environment[f"XDG_{name}_HOME"] = str(path)
    (root / "home").mkdir(mode=0o700)
    environment["HOME"] = str(root / "home")
    environment["APPIMAGE_EXTRACT_AND_RUN"] = "1"
    base = [
        *prefix,
        "--config-dir",
        str(root / "config" / "inkecho"),
        "--data-dir",
        str(root / "data" / "inkecho"),
    ]
    with (output / "process.log").open("w") as log:
        process = subprocess.Popen(
            [*base, "--screenshot-dir", str(output), "--quit-after", "20"],
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + 15
            while not (output / "page-05.png").exists():
                if process.poll() is not None:
                    raise RuntimeError("Application exited before rendering all pages.")
                if time.monotonic() > deadline:
                    raise TimeoutError("Settings screenshot generation timed out.")
                time.sleep(0.1)
            pages = []
            for index in range(1, 6):
                path = output / f"page-{index:02}.png"
                data = path.read_bytes()
                if data[:8] != b"\x89PNG\r\n\x1a\n":
                    raise RuntimeError("Invalid screenshot output.")
                width, height = struct.unpack(">II", data[16:24])
                if width < 600 or height < 400:
                    raise RuntimeError("Settings screenshot is unexpectedly small.")
                pages.append({"file": path.name, "width": width, "height": height})
            result["pages"] = pages
            for command in ("show", "quit"):
                subprocess.run(
                    [*base, f"--{command}"],
                    env=environment,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    check=True,
                    timeout=30,
                )
                if command != "quit" and process.poll() is not None:
                    raise RuntimeError("Secondary instance terminated the primary.")
            result["primary_exit_code"] = process.wait(timeout=15)
            if result["primary_exit_code"] != 0:
                raise RuntimeError("Application did not shut down cleanly.")
            result["ipc_show_quit"] = True
            config = root / "config" / "inkecho" / "config.json"
            before = config.read_bytes() if config.exists() else None
            for command in ("toggle", "cancel", "quit"):
                subprocess.run(
                    [*base, f"--{command}"],
                    env=environment,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    check=True,
                    timeout=30,
                )
                if (config.read_bytes() if config.exists() else None) != before:
                    raise RuntimeError("Cold control changed configuration.")
            result["cold_controls_exit_0_config_unchanged"] = True
            # Only our disposable profile is damaged; no recovery may overwrite it.
            config = root / "config" / "inkecho" / "config.json"
            damaged = b'{"schema_version":'
            config.write_bytes(damaged)
            broken = subprocess.run(
                [*base, "--quit-after", "0.1"],
                env=environment,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=30,
            )
            if broken.returncode != 1 or config.read_bytes() != damaged:
                raise RuntimeError("Damaged configuration recovery check failed.")
            result["damaged_config_exit_1_preserved"] = True
        finally:
            # The application's own timer bounds its lifetime. Keep the original
            # owner wait and profile even on failure; never kill or replay input.
            try:
                exit_code = process.wait(timeout=25)
                terminal = {
                    "pid": process.pid,
                    "returncode": exit_code,
                    "signals_sent": [],
                }
            except subprocess.TimeoutExpired:
                terminal = {"pid": process.pid, "running": True, "signals_sent": []}
                raise
            finally:
                (output / "terminal.json").write_text(
                    json.dumps(terminal, indent=2) + "\n"
                )
    result["passed"] = True
    (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--appimage", type=Path)
    args = parser.parse_args()
    result = probe(
        args.output.resolve(), args.appimage.resolve() if args.appimage else None
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
