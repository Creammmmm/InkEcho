"""Private actual-AppImage FUSE parent-death probe; explicit artifact SHA required."""

import asyncio
import hashlib
import json
import os
import select
import signal
import subprocess
import sys
import time
from pathlib import Path

import nested_keymap_probe as launcher
from isolated_browser_fixture import parent_pid
from mixed_keymap_workflow_probe import PrivateDesktop, metadata


def descendant(pid, ancestor):
    for _ in range(8):
        if pid == ancestor:
            return True
        if pid <= 1:
            return False
        pid = parent_pid(pid)
    return False


async def inner(root, *_args, **_kwargs):
    from inkecho.platform.wayland_worker import MutterSession

    artifact = Path(os.environ["INKECHO_TEST_FUSE_ARTIFACT"]).resolve()
    expected_hash = os.environ["INKECHO_TEST_FUSE_SHA256"]
    report = {
        "passed": False,
        "isolated": True,
        "host_desktop_used": False,
        "test_entry_replaces_gui_main": True,
        "fuse_parent_death_tested": False,
    }
    desktop = PrivateDesktop(root)
    observer = fixture = application = None
    guardian_fd = None
    try:
        actual_hash = hashlib.sha256(artifact.read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            raise RuntimeError("artifact_hash_mismatch")
        report.update(artifact=str(artifact), artifact_sha256=actual_hash)
        await desktop.start()
        output, focus = root / "fuse-owned-text.json", root / "fuse-owned-focus.json"
        environment = dict(os.environ, GDK_BACKEND="wayland", NO_AT_BRIDGE="1")
        for key in ("PYTHONHOME", "PYTHONPATH", "LD_LIBRARY_PATH"):
            environment.pop(key, None)
        observer = MutterSession()
        await observer.connect()
        await observer.authorize()
        report["before"] = await metadata(observer)
        shim = root / "entry-shim"
        shim.mkdir()
        entry = (
            Path(__file__).resolve().parents[1] / "validation/fuse_guardian_entry.py"
        )
        (shim / "inkecho.py").write_bytes(entry.read_bytes())
        app_environment = dict(
            os.environ,
            INKECHO_FUSE_PROBE="private-parent-death-v1",
            INKECHO_FUSE_PROBE_ROOT=str(root),
        )
        with (root / "appimage.log").open("wb") as log:
            application = subprocess.Popen(
                [str(artifact)],
                cwd=shim,
                env=app_environment,
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
        authorized_path = root / "fuse-parent-authorized.json"
        for _ in range(160):
            if authorized_path.exists():
                break
            if application.poll() is not None:
                raise RuntimeError("appimage_exited_before_authorization")
            await asyncio.sleep(0.05)
        else:
            raise RuntimeError("appimage_authorization_timeout")
        authorized = json.loads(authorized_path.read_text())
        if not descendant(authorized["parent_pid"], application.pid):
            raise RuntimeError("appimage_authorized_parent_mismatch")
        with (root / "fixture.log").open("wb") as log:
            fixture = subprocess.Popen(
                [
                    "/usr/bin/python3",
                    str(Path(__file__).with_name("wayland_editor_fixture.py")),
                    str(output),
                    str(root / "owned-events.jsonl"),
                    str(focus),
                ],
                env=environment,
                stdout=log,
                stderr=log,
            )
        for _ in range(100):
            if focus.exists():
                break
            if fixture.poll() is not None:
                raise RuntimeError("owned_fixture_exited")
            await asyncio.sleep(0.05)
        await desktop.tap(0xFF1B)
        for _ in range(100):
            if focus.exists():
                state = json.loads(focus.read_text())
                if state["active"] and state["focused"]:
                    break
            await asyncio.sleep(0.05)
        else:
            raise RuntimeError("owned_fixture_not_focused")
        if (
            parent_pid(fixture.pid) != os.getpid()
            or json.loads(output.read_text()) != ""
        ):
            raise RuntimeError("owned_fixture_precondition_failed")
        (root / "fuse-parent-go.json").write_text("true")
        ready_path = root / "fuse-parent-ready.json"
        for _ in range(200):
            if ready_path.exists():
                break
            if application.poll() is not None:
                raise RuntimeError("appimage_exited_before_owned_ack")
            await asyncio.sleep(0.05)
        else:
            raise RuntimeError("appimage_ack_timeout")
        ready = json.loads(ready_path.read_text())
        if (
            not descendant(ready["parent_pid"], application.pid)
            or parent_pid(ready["guardian_pid"]) != ready["parent_pid"]
        ):
            raise RuntimeError("appimage_process_ownership_mismatch")
        parent_fd = os.pidfd_open(ready["parent_pid"])
        guardian_fd = os.pidfd_open(ready["guardian_pid"])
        report["mounted_runtime"] = ready
        report["during"] = await metadata(observer)
        if report["during"]["map_sha256"] == report["before"]["map_sha256"]:
            raise RuntimeError("no_owned_map_to_restore")
        for _ in range(40):
            prefix = json.loads(output.read_text())
            if prefix == "中":
                break
            await asyncio.sleep(0.025)
        report["owned_prefix_codepoints"] = [ord(char) for char in prefix]
        report["owned_focus_before_parent_death"] = json.loads(focus.read_text())
        report["owned_key_events"] = (
            [
                json.loads(line)
                for line in (root / "owned-events.jsonl").read_text().splitlines()
            ]
            if (root / "owned-events.jsonl").exists()
            else []
        )
        if prefix != "中":
            raise RuntimeError("owned_prefix_not_exact")
        try:
            signal.pidfd_send_signal(parent_fd, signal.SIGKILL)
        finally:
            os.close(parent_fd)
        report["fuse_parent_death_tested"] = True
        deadline = time.monotonic() + 12
        while (
            time.monotonic() < deadline
            and not select.select([guardian_fd], [], [], 0)[0]
        ):
            await asyncio.sleep(0.05)
        report["guardian_exited"] = bool(select.select([guardian_fd], [], [], 0)[0])
        report["after"] = await metadata(observer)
        report["map_and_modifiers_restored"] = report["before"] == report["after"]
        await asyncio.sleep(0.2)
        report["no_late_text"] = json.loads(output.read_text()) == prefix
        await asyncio.to_thread(application.wait, 5)
        appdir = ready["appdir"]
        report["fuse_mount_remaining"] = any(
            line.split()[4] == appdir
            for line in Path("/proc/self/mountinfo").read_text().splitlines()
        )
        report["passed"] = (
            report["guardian_exited"]
            and report["no_late_text"]
            and report["map_and_modifiers_restored"]
            and not report["fuse_mount_remaining"]
        )
    except Exception as error:
        report["error"] = str(error)
    finally:
        if application and application.poll() is None:
            application.terminate()
            await asyncio.to_thread(application.wait, 5)
        if observer:
            await observer.close()
        if fixture and fixture.poll() is None:
            fixture.terminate()
            await asyncio.to_thread(fixture.wait, 5)
        await desktop.close()
        if guardian_fd is not None:
            # Only the pidfd captured while it was this owned parent's child.
            # The private compositor's exit releases an unfinished guardian;
            # never scan or kill unrelated processes to make the check pass.
            deadline = time.monotonic() + 5
            while (
                time.monotonic() < deadline
                and not select.select([guardian_fd], [], [], 0)[0]
            ):
                await asyncio.sleep(0.05)
            report["guardian_exited_after_private_cleanup"] = bool(
                select.select([guardian_fd], [], [], 0)[0]
            )
            os.close(guardian_fd)
        print(json.dumps(report, sort_keys=True), flush=True)
    return report["passed"]


if __name__ == "__main__":
    if "--inner" not in sys.argv:
        for option, variable in (
            ("--appimage", "INKECHO_TEST_FUSE_ARTIFACT"),
            ("--sha256", "INKECHO_TEST_FUSE_SHA256"),
        ):
            if option not in sys.argv:
                raise SystemExit("Explicit --appimage and --sha256 required")
            index = sys.argv.index(option)
            os.environ[variable] = sys.argv[index + 1]
            del sys.argv[index : index + 2]
        os.environ["INKECHO_TEST_FUSE_ARTIFACT"] = str(
            Path(os.environ["INKECHO_TEST_FUSE_ARTIFACT"]).resolve(strict=True)
        )
    launcher.inner = inner
    launcher.__file__ = __file__
    launcher.main()
