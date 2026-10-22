"""Exercise task-only Escape against an owned, separate Xorg Qt window.

No microphone, cloud, credentials, clipboard, input method, or user document is
used. Run only in an unlocked, dedicated Xorg desktop with no held keys.
"""

import argparse
import ctypes as c
import hashlib
import json
import os
import select
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def target(path):
    from PySide6.QtCore import QSocketNotifier, Qt
    from PySide6.QtWidgets import QApplication, QLineEdit

    class Target(QLineEdit):
        escapes = 0

        def keyPressEvent(self, event):
            if event.key() == Qt.Key.Key_Escape:
                self.escapes += 1
            super().keyPressEvent(event)
            temporary = Path(path).with_suffix(".pending")
            temporary.write_text(
                json.dumps({"escapes": self.escapes, "text": self.text()})
            )
            temporary.replace(path)

    app = QApplication([])
    control = QSocketNotifier(sys.stdin.fileno(), QSocketNotifier.Type.Read)
    control.activated.connect(
        lambda *_args: app.quit() if sys.stdin.readline() else None
    )
    window = Target()
    window.setWindowTitle("InkEcho isolated Escape acceptance")
    window.show()
    window.activateWindow()
    window.setFocus()
    app.processEvents()
    print(json.dumps({"window": int(window.winId())}), flush=True)
    return app.exec()


def run(args):
    report = args.report
    if os.environ.get("XDG_SESSION_TYPE") != "x11":
        raise RuntimeError("This global Escape acceptance requires actual Xorg")
    sys.path.insert(0, str(args.package_root.resolve(strict=True)))
    from PySide6.QtWidgets import QApplication

    import inkecho.platform.escape as module

    if not Path(module.__file__).resolve().is_relative_to(args.package_root.resolve()):
        raise RuntimeError("Escape module escaped selected runtime")
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    cancelled = []
    guard = module.TaskEscape(lambda: cancelled.append(time.monotonic()))

    def spin(seconds):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.005)

    with tempfile.TemporaryDirectory(prefix="inkecho-escape-owned-") as directory:
        state = Path(directory) / "state.json"
        child = subprocess.Popen(
            [sys.executable, __file__, "--target", str(state)],
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            text=True,
        )
        report.update(
            module=str(module.__file__),
            module_sha256=hashlib.sha256(
                Path(module.__file__).read_bytes()
            ).hexdigest(),
            owned_target_pid=child.pid,
        )
        try:
            readable, _, _ = select.select([child.stdout], [], [], 10)
            if not readable:
                raise RuntimeError("Owned target did not start")
            window = json.loads(child.stdout.readline())["window"]
            guard.set_active(True)
            spin(0.1)
            if guard.backend is None:
                raise RuntimeError("Escape grab unavailable or conflicting")
            lib, display = guard.backend.lib, guard.backend.display
            lib.XSetInputFocus.argtypes = [c.c_void_p, c.c_ulong, c.c_int, c.c_ulong]
            lib.XGetInputFocus.argtypes = [
                c.c_void_p,
                c.POINTER(c.c_ulong),
                c.POINTER(c.c_int),
            ]
            # The target is owned by this probe, never a discovered user window.
            lib.XSetInputFocus(display, window, 1, 0)
            lib.XSync(display, False)
            focus, revert = c.c_ulong(), c.c_int()
            lib.XGetInputFocus(display, c.byref(focus), c.byref(revert))
            if focus.value != window:
                raise RuntimeError("Owned target did not receive focus")
            xtest = c.CDLL("libXtst.so.6")
            xtest.XTestFakeKeyEvent.argtypes = [
                c.c_void_p,
                c.c_uint,
                c.c_int,
                c.c_ulong,
            ]
            # Keep a separate connection because cancellation closes its own grab.
            sender = lib.XOpenDisplay(None)
            if not sender:
                raise RuntimeError("No sender display")
            try:

                def key(keysym):
                    code = lib.XKeysymToKeycode(sender, keysym)
                    xtest.XTestFakeKeyEvent(sender, code, True, 0)
                    xtest.XTestFakeKeyEvent(sender, code, False, 0)
                    lib.XSync(sender, False)
                    spin(0.15)

                key(ord("a"))
                before = json.loads(state.read_text())
                if before != {"escapes": 0, "text": "a"}:
                    raise RuntimeError("Ordinary input was intercepted")
                key(0xFF1B)
                after_active = json.loads(state.read_text())
                if len(cancelled) != 1 or guard.active or guard.backend is not None:
                    raise RuntimeError("Active Escape did not cancel and release")
                if after_active["escapes"] != 0:
                    raise RuntimeError("Active Escape leaked to target")
                key(0xFF1B)
                after_idle = json.loads(state.read_text())
                if after_idle != {"escapes": 1, "text": "a"}:
                    raise RuntimeError("Idle Escape was swallowed")
                lib.XGetInputFocus(sender, c.byref(focus), c.byref(revert))
                if focus.value != window:
                    raise RuntimeError("Escape cancellation changed focus")
                report.update(
                    active_escape_cancelled=True,
                    ordinary_input_delivered=True,
                    idle_escape_delivered=True,
                    focus_unchanged=True,
                    released=True,
                )
            finally:
                lib.XCloseDisplay(sender)
        finally:
            guard.close()
            if child.poll() is None:
                child.stdin.write("close\n")
                child.stdin.flush()
            child.wait(timeout=5)
            report["owned_target_exit"] = child.returncode
            if child.returncode != 0:
                raise RuntimeError("Owned target did not exit normally")
        report["ok"] = True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target")
    parser.add_argument("--package-root", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if arguments.target:
        raise SystemExit(target(arguments.target))
    if arguments.package_root is None or arguments.output is None:
        parser.error("--package-root and --output are required")
    arguments.report = {"ok": False, "session": os.environ.get("XDG_SESSION_TYPE")}
    try:
        run(arguments)
    except BaseException as error:
        arguments.report["error_type"] = type(error).__name__
        if isinstance(error, RuntimeError):
            arguments.report["error"] = str(error)
        raise
    finally:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(json.dumps(arguments.report, indent=2) + "\n")
        print(json.dumps(arguments.report), flush=True)
