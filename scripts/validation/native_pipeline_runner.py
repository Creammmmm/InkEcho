"""Reviewed two-phase native receiver for the frozen full audio pipeline sender.

Preparation opens only a private owned native Chrome fixture. Text is not sent
until the root reviewer creates output/send-request containing 'send'. The
fixture then receives only the fixed public nine-character sample. Browser.close
and the original Popen wait provide normal cleanup; no forced signal exists.
"""

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

SAMPLE = "本地完整链路测试。"


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    temporary.replace(path)


def parse():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    roots = parser.add_mutually_exclusive_group(required=True)
    roots.add_argument("--source-root", type=Path)
    roots.add_argument("--package-root", type=Path)
    parser.add_argument("--frozen-source-root", type=Path)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--artifact", type=Path)
    parser.add_argument("--artifact-sha256")
    parser.add_argument("--inventory-sha256")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-reviewed", action="store_true")
    parser.add_argument("--audit-only", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args()


def stage_check(args):
    stage = args.stage.resolve(strict=True)
    assert re.fullmatch(r"[a-f0-9]{64}", args.manifest_sha256)
    assert digest(stage / "manifest.json") == args.manifest_sha256
    manifest = json.loads((stage / "manifest.json").read_text())
    for name, pin in manifest["files"].items():
        path = stage / name
        assert not path.is_symlink() and path.resolve().is_relative_to(stage)
        assert path.is_file() and digest(path) == pin
    source = (args.source_root or args.frozen_source_root).resolve(strict=True)
    assert source.is_relative_to(stage)
    prefix = str(source.relative_to(stage)) + "/"
    actual = {
        str(path.relative_to(stage))
        for path in source.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }
    assert actual == {name for name in manifest["files"] if name.startswith(prefix)}
    text = (source / "inkecho/__init__.py").read_text()
    assert re.search(r'__version__ = "([^"]+)"', text).group(1) == args.expected_version
    return stage, source, manifest


def sender_environment(args, stage, root):
    allowed = (
        "LANG LC_ALL DISPLAY WAYLAND_DISPLAY XAUTHORITY DBUS_SESSION_BUS_ADDRESS "
        "XDG_RUNTIME_DIR XDG_SESSION_TYPE XDG_CURRENT_DESKTOP GTK_IM_MODULE "
        "QT_IM_MODULE XMODIFIERS PULSE_SERVER"
    ).split()
    env = {key: os.environ[key] for key in allowed if key in os.environ}
    env["PATH"] = str(stage / "pulse-bin") + ":/usr/bin:/bin"
    for name in ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
        folder = root / name.lower()
        folder.mkdir(mode=0o700)
        env[name] = str(folder)
    selected = (args.package_root or args.source_root).resolve(strict=True)
    env["PYTHONPATH"] = str(selected)
    env["PYTHONNOUSERSITE"] = "1"
    if args.package_root:
        appdir = selected.parent
        assert args.python.resolve().is_relative_to(appdir / "usr")
        env.update(
            APPDIR=str(appdir),
            PYTHONHOME=str(appdir / "usr"),
            LD_LIBRARY_PATH=str(appdir / "usr/lib/inkecho"),
        )
    return env


def package_audit(args, source, helpers):
    sys.path.insert(0, str(helpers))
    from artifact_scope import audit_package, selected_artifact

    assert args.artifact and args.artifact_sha256 and args.inventory_sha256
    inventory = args.package_root.parent / "usr/share/doc/inkecho/inventory.json"
    assert digest(inventory) == args.inventory_sha256
    return {
        "artifact": selected_artifact(args.artifact, args.artifact_sha256),
        "runtime": audit_package(args.package_root, source, args.expected_version),
    }


class PageReader:
    def __init__(self, fixture, endpoint):
        from websockets.sync.client import connect

        self.channel = connect(
            endpoint,
            open_timeout=3,
            close_timeout=1,
            max_size=8 * 1024 * 1024,
            ping_interval=None,
            proxy=None,
        )
        self.serial = 0
        self.session = None
        target_url = fixture.argv[-1].removeprefix("--app=")
        targets = self.call("Target.getTargets")["targetInfos"]
        choices = [
            t for t in targets if t.get("type") == "page" and t.get("url") == target_url
        ]
        assert len(choices) == 1
        self.session = self.call(
            "Target.attachToTarget",
            {"targetId": choices[0]["targetId"], "flatten": True},
        )["sessionId"]
        self.call("Page.enable", session=True)

    def call(self, method, params=None, session=False):
        assert method in {
            "Target.getTargets",
            "Target.attachToTarget",
            "Page.enable",
            "Runtime.evaluate",
            "Page.captureScreenshot",
        }
        self.serial += 1
        command = {"id": self.serial, "method": method, "params": params or {}}
        if session:
            command["sessionId"] = self.session
        self.channel.send(json.dumps(command))
        while True:
            value = json.loads(self.channel.recv(timeout=3))
            if value.get("id") == self.serial:
                assert "error" not in value
                return value.get("result", {})

    def state(self):
        expression = """(() => ({
          text: document.getElementById('field').value,
          history: window.inkechoPublicHistory || [],
          documentFocused: document.hasFocus(),
          fieldFocused: document.activeElement === document.getElementById('field')
        }))()"""
        response = self.call(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True},
            session=True,
        )
        assert "exceptionDetails" not in response
        return response["result"]["value"]

    def screenshot(self, path):
        response = self.call(
            "Page.captureScreenshot",
            {"format": "png", "fromSurface": True, "captureBeyondViewport": False},
            session=True,
        )
        image = base64.b64decode(response["data"], validate=True)
        assert image.startswith(b"\x89PNG\r\n\x1a\n")
        with Path(path).open("xb") as stream:
            stream.write(image)

    def close(self):
        self.channel.close()


def main():
    args = parse()
    stage, source, manifest = stage_check(args)
    helpers = stage / "frozen/scripts/validation"
    if args.audit_only:
        save(args.output, package_audit(args, source, helpers))
        return
    assert args.run_reviewed and not args.output.exists()
    assert os.environ.get("XDG_SESSION_TYPE") == "wayland"
    assert "GNOME" in os.environ.get("XDG_CURRENT_DESKTOP", "").upper().split(":")
    args.output.mkdir(mode=0o700, parents=True)
    sender_home = args.output / "sender-private"
    sender_home.mkdir(mode=0o700)
    env = sender_environment(args, stage, sender_home)
    sys.path.insert(0, str(helpers))
    import natural_owned_browser as browser_module
    from native_guard import save as guard_save

    assert Path(browser_module.__file__).resolve().is_relative_to(helpers)

    class Receiver(browser_module.NaturalOwnedBrowser):
        def page(self):
            return (
                super().page()
                + b"""<script>
              window.inkechoPublicHistory = [];
              document.getElementById('field').addEventListener('input', event => {
                if (window.inkechoPublicHistory.length < 256)
                  window.inkechoPublicHistory.push({
                    text: event.target.value, trusted: event.isTrusted,
                    inputType: event.inputType, at: performance.now()});
              });
            </script>"""
            )

    report = {
        "scope": "actual native owned receiver, virtual audio, local ASR/SSE",
        "manifest_sha256": args.manifest_sha256,
        "stage_provenance": manifest.get("provenance"),
        "source_or_package": "package" if args.package_root else "source",
        "expected_version": args.expected_version,
        "sender_started": False,
        "forced_signals": [],
        "cleanup_errors": [],
    }
    if args.package_root:
        audit_args = [
            str(args.python),
            str(Path(__file__).resolve()),
            "--audit-only",
            "--stage",
            str(stage),
            "--manifest-sha256",
            args.manifest_sha256,
            "--package-root",
            str(args.package_root),
            "--frozen-source-root",
            str(source),
            "--python",
            str(args.python),
            "--expected-version",
            args.expected_version,
            "--artifact",
            str(args.artifact),
            "--artifact-sha256",
            args.artifact_sha256,
            "--inventory-sha256",
            args.inventory_sha256,
            "--output",
            str(args.output / "package-audit.json"),
        ]
        subprocess.run(audit_args, env=env, check=True)
    fixture = reader = sender = None
    guard_path = args.output / "native-focus-guard.json"
    stop = threading.Event()
    publisher = None
    try:
        fixture = Receiver(args.output / "browser", platform="wayland")
        original_environment = browser_module.browser_environment

        def actual_environment(root, platform):
            owned = original_environment(root, platform)
            # Preserve actual receiver IM configuration; this remains a direct
            # simulated-keyboard transport and does not submit via an input method.
            for key in ("GTK_IM_MODULE", "QT_IM_MODULE", "XMODIFIERS"):
                owned.pop(key, None)
                if key in os.environ:
                    owned[key] = os.environ[key]
            return owned

        browser_module.browser_environment = actual_environment
        try:
            fixture.start(reviewed=True)
        finally:
            browser_module.browser_environment = original_environment
        until = time.monotonic() + 20
        while time.monotonic() < until:
            fixture.assert_owned()
            state = fixture.snapshot()
            native = fixture.native_evidence()
            if (
                state
                and native["wayland_surface_observed"]
                and native["xdg_toplevel_observed"]
            ):
                break
            time.sleep(0.05)
        else:
            raise RuntimeError("owned_native_fixture_not_ready")
        assert native["display_unset_in_owned_process"]
        endpoint = browser_module.debugger_endpoint(
            fixture.profile / "DevToolsActivePort", fixture.profile
        )
        reader = PageReader(fixture, endpoint)

        def publish():
            while not stop.is_set():
                try:
                    fixture.assert_owned()
                    state = fixture.snapshot()
                    fresh = bool(
                        state
                        and state["document_focused"]
                        and state["field_focused"]
                        and 0 <= time.monotonic() - state["sampled_at"] <= 0.25
                    )
                    guard_save(
                        guard_path,
                        {
                            "allowed": fresh,
                            "backend_confirmed": True,
                            "owner_pid": os.getpid(),
                            "pid": fixture.process.pid,
                            "start_ticks": fixture.started,
                            "sampled_at": state["sampled_at"] if state else 0,
                        },
                    )
                except BaseException as error:
                    report["guard_publish_error"] = type(error).__name__
                    guard_save(guard_path, {"allowed": False})
                    return
                stop.wait(0.02)

        publisher = threading.Thread(target=publish)
        publisher.start()
        initial = reader.state()
        assert initial["text"] == "" and initial["history"] == []
        reader.screenshot(args.output / "ready.png")
        save(
            args.output / "ready.json",
            {
                "native": native,
                "page": reader.state(),
                "browser_pid": fixture.process.pid,
                "start_ticks": fixture.started,
                "review_required": (
                    "Write send to send-request after reviewing ready.png/json."
                ),
            },
        )
        print("owned_native_ready_waiting_for_root_release", flush=True)
        while True:
            fixture.assert_owned()
            if (args.output / "close-request").exists():
                report["closed_before_send"] = True
                return
            trigger = args.output / "send-request"
            if trigger.exists():
                assert (
                    not trigger.is_symlink() and trigger.read_text().strip() == "send"
                )
                break
            time.sleep(0.05)
        stage_check(args)
        command = [
            str(args.python),
            str(stage / "audio_pipeline_keyboard.py"),
            "--package-root" if args.package_root else "--source-root",
            str(args.package_root or args.source_root),
            "--native-guard",
            str(guard_path),
            "--native-owner",
            str(os.getpid()),
            "--native-helper-root",
            str(helpers),
            "--native-work-root",
            str(args.output / "native-worker"),
            "--output",
            str(args.output / "delivery.json"),
        ]
        with (
            (args.output / "sender.stdout").open("xb") as out,
            (args.output / "sender.stderr").open("xb") as err,
        ):
            sender = subprocess.Popen(
                command, env=env, stdout=out, stderr=err, stdin=subprocess.DEVNULL
            )
            report.update(
                sender_started=True, sender_pid=sender.pid, sender_argv=command
            )
            save(args.output / "live-owner.json", report)
            partial = False
            while sender.poll() is None:
                state = reader.state()
                if 0 < len(state["text"]) < len(SAMPLE) and not partial:
                    reader.screenshot(args.output / "partial.png")
                    after_image = reader.state()
                    save(
                        args.output / "partial.json",
                        {
                            "at_monotonic": time.monotonic(),
                            "before_image": state,
                            "after_image": after_image,
                        },
                    )
                    partial = 0 < len(after_image["text"]) < len(SAMPLE)
                time.sleep(0.01)
            report["sender_exit_code"] = sender.wait()
            report["sender_original_wait_completed"] = True
        final = reader.state()
        reader.screenshot(args.output / "final.png")
        save(args.output / "receiver-final.json", final)
        lengths = [len(row["text"]) for row in final["history"]]
        report["visible_prefix_lengths"] = lengths
        report["exact_all_prefixes"] = [row["text"] for row in final["history"]] == [
            SAMPLE[:i] for i in range(1, len(SAMPLE) + 1)
        ]
        report["success"] = bool(
            report["sender_exit_code"] == 0
            and final["text"] == SAMPLE
            and report["exact_all_prefixes"]
            and partial
            and all(row["trusted"] for row in final["history"])
        )
        assert report["success"], "native_full_pipeline_acceptance_failed"
    finally:
        # Stop the publisher before the final false write, so an in-flight
        # publisher cannot overwrite it with an older allowed=True snapshot.
        stop.set()
        guard_disabled = True
        if publisher is not None:
            publisher.join(timeout=3)
            if publisher.is_alive():
                guard_disabled = False
                report["cleanup_errors"].append("guard_thread_pending")
        try:
            guard_save(guard_path, {"allowed": False})
        except BaseException as error:
            guard_disabled = False
            report["cleanup_errors"].append("guard_close:" + type(error).__name__)
        if sender is not None and sender.poll() is None:
            try:
                report["sender_exit_code"] = sender.wait(timeout=10)
                report["sender_original_wait_completed"] = True
            except subprocess.TimeoutExpired:
                report["sender_still_running"] = True
                report["cleanup_errors"].append("sender_original_handle_still_live")
        if reader is not None:
            try:
                reader.close()
            except BaseException as error:
                report["cleanup_errors"].append(
                    "page_reader_close:" + type(error).__name__
                )
        if (
            fixture is not None
            and fixture.process is not None
            and not report.get("sender_still_running")
            and guard_disabled
        ):
            try:
                report["browser_natural_exit_code"] = fixture.close()
                report["browser_original_wait_completed"] = True
            except BaseException as error:
                report["cleanup_errors"].append("browser_close:" + type(error).__name__)
        if sender is not None and sender.poll() is None:
            report["sender_still_running"] = True
        report["accepted"] = bool(
            report.get("success")
            and not report["cleanup_errors"]
            and report.get("browser_natural_exit_code") == 0
            and not report.get("sender_still_running")
        )
        save(args.output / "terminal.json", report)
    if report["cleanup_errors"]:
        raise RuntimeError("native_pipeline_cleanup_failed")


if __name__ == "__main__":
    main()
