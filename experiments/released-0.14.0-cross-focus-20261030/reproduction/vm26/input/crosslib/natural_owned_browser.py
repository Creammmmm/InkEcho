"""Owned local Chrome fixture with RAM text and Browser.close/natural wait only.

No browser/server starts on import. Call start(reviewed=True) only after the
complete artifact, desktop and exact command review. It never removes profiles
or terminates a process; failed close preserves the same identity for diagnosis.
"""

import json
import os
import re
import secrets
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

MAX_STATE_BYTES = 65536


def process_start(pid: int) -> str | None:
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]
    except (OSError, IndexError):
        return None


def parent_pid(pid: int) -> int | None:
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("PPid:"):
                return int(line.split()[1])
    except (OSError, ValueError):
        pass
    return None


def debugger_endpoint(path: Path, profile: Path) -> str:
    """Accept only Chrome's own bounded loopback debugging metadata."""
    if path.is_symlink() or not path.resolve(strict=True).is_relative_to(profile):
        raise ValueError("owned_debugger_metadata_invalid")
    if path.stat().st_uid != os.getuid() or path.stat().st_size > 256:
        raise ValueError("owned_debugger_metadata_invalid")
    lines = path.read_text().splitlines()
    if (
        len(lines) != 2
        or not re.fullmatch(r"[0-9]{1,5}", lines[0])
        or not 0 < int(lines[0]) < 65536
        or not re.fullmatch(r"/devtools/browser/[A-Za-z0-9-]{1,80}", lines[1])
    ):
        raise ValueError("owned_debugger_metadata_invalid")
    return f"ws://127.0.0.1:{int(lines[0])}{lines[1]}"


def browser_environment(root: Path, platform: str) -> dict:
    if platform not in {"wayland", "x11"}:
        raise ValueError("owned_platform_invalid")
    session = os.environ.get("XDG_SESSION_TYPE")
    if (platform == "wayland" and session != "wayland") or (
        platform == "x11" and session not in {"x11", "wayland"}
    ):
        raise ValueError("actual_graphical_session_required")
    allowed = ["PATH", "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS", "XAUTHORITY"]
    allowed.append("WAYLAND_DISPLAY" if platform == "wayland" else "DISPLAY")
    result = {key: os.environ[key] for key in allowed if key in os.environ}
    result["XDG_SESSION_TYPE"] = session
    display_key = "WAYLAND_DISPLAY" if platform == "wayland" else "DISPLAY"
    if not result.get(display_key):
        raise ValueError("owned_display_missing")
    for key in ["HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"]:
        path = root / key.lower()
        path.mkdir(mode=0o700)
        result[key] = str(path)
    result.update(
        GTK_IM_MODULE="ibus",
        QT_IM_MODULE="ibus",
        XMODIFIERS="@im=ibus",
        WAYLAND_DEBUG="client",
    )
    return result


class StateServer(ThreadingHTTPServer):
    daemon_threads = False
    block_on_close = True

    def handle_error(self, _request, _client_address):
        self.errors.append("owned_http_unexpected_failure")


class NaturalOwnedBrowser:
    def __init__(self, root: Path, field="textarea", platform="wayland") -> None:
        if field not in {"textarea", "contenteditable"} or platform not in {
            "wayland",
            "x11",
        }:
            raise ValueError("owned_fixture_configuration")
        self.root, self.field, self.platform = root, field, platform
        self.process = self.server = self.thread = self.stderr_thread = None
        self.started = None
        self.argv = None
        self.state = None
        self.surface_seen = self.toplevel_seen = False
        self.errors = []
        self.lock = threading.Lock()
        self.closed = False
        self.close_attempted = False
        self.class_name = "inkecho-owned-" + secrets.token_hex(6)
        self.spawn_display = None

    def save_owner(self, phase: str, code=None) -> None:
        value = {
            "phase": phase,
            "pid": self.process.pid if self.process else None,
            "start_ticks": self.started,
            "argv": self.argv,
            "exit_code": code,
            "owner_observed_terminal": code is not None,
        }
        path = self.root / "owner.json"
        temporary = path.with_suffix(".tmp")
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as output:
            json.dump(value, output, indent=2)
        temporary.replace(path)

    def assert_owned(self) -> None:
        if (
            self.process is None
            or self.process.poll() is not None
            or process_start(self.process.pid) != self.started
            or parent_pid(self.process.pid) != os.getpid()
        ):
            raise ValueError("owned_browser_identity_changed")

    def snapshot(self) -> dict | None:
        with self.lock:
            return dict(self.state) if self.state else None

    def native_evidence(self) -> dict:
        self.assert_owned()
        return {
            "ozone_platform": self.platform,
            "display_unset_in_owned_process": self.platform == "wayland"
            and "DISPLAY" not in self.environment,
            "wayland_surface_observed": self.surface_seen,
            "xdg_toplevel_observed": self.toplevel_seen,
        }

    def page(self) -> bytes:
        field = (
            '<textarea id="field" autofocus></textarea>'
            if self.field == "textarea"
            else '<div id="field" contenteditable="true" tabindex="0" autofocus></div>'
        )
        return (
            '<!doctype html><meta charset="utf-8">'
            "<title>InkEcho owned acceptance</title>"
            + field
            + '<script>const f=document.getElementById("field");let seq=0;'
            'function record(){fetch(location.pathname+"/state",{method:"POST",'
            "body:JSON.stringify({sequence:++seq,text:f.value??f.innerText,"
            "document_focused:document.hasFocus(),field_focused:document.activeElement===f})})}"
            'window.addEventListener("load",()=>{f.focus();record()});'
            'window.addEventListener("focus",()=>{f.focus();record()});'
            'f.addEventListener("input",record);setInterval(record,50);</script>'
        ).encode()

    def start(self, *, reviewed=False):
        if not reviewed:
            raise ValueError("explicit_desktop_review_required")
        self.root.mkdir(mode=0o700, exist_ok=False)
        self.environment = browser_environment(self.root, self.platform)
        self.spawn_display = self.environment.get("DISPLAY")
        self.profile = self.root / "profile"
        token = "/" + secrets.token_urlsafe(24)
        page = self.page()
        fixture = self

        class Handler(BaseHTTPRequestHandler):
            def setup(self):
                super().setup()
                self.connection.settimeout(2)

            def do_GET(self):
                if self.path != token:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header(
                    "Content-Security-Policy",
                    "default-src 'none'; "
                    "script-src 'unsafe-inline'; connect-src 'self'; "
                    "form-action 'none'",
                )
                self.end_headers()
                try:
                    self.wfile.write(page)
                except (BrokenPipeError, ConnectionResetError, TimeoutError):
                    pass

            def do_POST(self):
                if self.path != token + "/state":
                    self.send_error(404)
                    return
                try:
                    size = int(self.headers.get("Content-Length", "0"))
                    if not 0 < size <= MAX_STATE_BYTES:
                        raise ValueError
                    state = json.loads(self.rfile.read(size))
                    if (
                        set(state)
                        != {"sequence", "text", "document_focused", "field_focused"}
                        or type(state["sequence"]) is not int
                        or state["sequence"] < 1
                        or not isinstance(state["text"], str)
                        or any(
                            type(state[key]) is not bool
                            for key in ["document_focused", "field_focused"]
                        )
                    ):
                        raise ValueError
                    state["sampled_at"] = time.monotonic()
                    with fixture.lock:
                        if (
                            fixture.state is None
                            or state["sequence"] > fixture.state["sequence"]
                        ):
                            fixture.state = state
                    self.send_response(204)
                    self.end_headers()
                except (ValueError, TypeError, KeyError, UnicodeError):
                    self.send_error(400)
                except (BrokenPipeError, ConnectionResetError, TimeoutError):
                    pass

            def log_message(self, *_args):
                pass

        self.server = StateServer(("127.0.0.1", 0), Handler)
        self.server.errors = self.errors
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()
        self.argv = [
            str(__import__("chrome_program").ROOT / "chrome"),
            f"--ozone-platform={self.platform}",
            f"--class={self.class_name}",
            f"--user-data-dir={self.profile}",
            "--remote-debugging-port=0",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            "--disable-component-update",
            "--disable-sync",
            "--gtk-version=3",
            "--password-store=basic",
            "--no-proxy-server",
            "--host-resolver-rules=MAP * ~NOTFOUND, "
            "EXCLUDE localhost, EXCLUDE 127.0.0.1",
            f"--app=http://127.0.0.1:{self.server.server_port}{token}",
        ]
        try:
            if self.platform == "wayland":
                self.argv.extend(["--enable-wayland-ime", "--wayland-text-input-version=3"])
            self.process = subprocess.Popen(
                self.argv,
                env=self.environment,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
            self.started = process_start(self.process.pid)
            self.save_owner("running")
        except Exception:
            if self.process is None:
                self.server.shutdown()
                self.server.server_close()
                self.thread.join()
            raise ValueError("owned_browser_start_failed") from None
        self.stderr_thread = threading.Thread(target=self.drain_stderr)
        self.stderr_thread.start()
        return self

    def drain_stderr(self) -> None:
        # Keep only protocol presence booleans. No free-form stderr or key/text
        # protocol payload is persisted or included in reports.
        stream = self.process.stderr
        try:
            while line := stream.readline(8193):
                if len(line) > 8192:
                    continue
                self.surface_seen |= (
                    b"wl_compositor" in line and b"create_surface" in line
                )
                self.toplevel_seen |= b"xdg_toplevel" in line
        except OSError:
            self.errors.append("owned_stderr_read_failed")
        finally:
            stream.close()

    def close(self) -> int:
        """Request Browser.close once, then let the original owner observe exit."""
        if self.closed:
            return self.process.returncode
        if self.close_attempted:
            raise ValueError("owned_close_already_attempted")
        self.close_attempted = True
        self.assert_owned()
        endpoint = debugger_endpoint(self.profile / "DevToolsActivePort", self.profile)
        self.save_owner("normal_close_requested")
        close_sent = False
        try:
            from websockets.sync.client import connect

            with connect(
                endpoint,
                open_timeout=3,
                close_timeout=1,
                max_size=4096,
                ping_interval=None,
                proxy=None,
            ) as channel:
                channel.send(json.dumps({"id": 1, "method": "Browser.close"}))
                close_sent = True
        except Exception:
            if not close_sent:
                self.save_owner("normal_close_unconfirmed")
                raise ValueError("owned_normal_close_unconfirmed") from None
        code = self.process.wait()  # No timeout, terminate, kill or profile removal.
        self.save_owner("terminal", code)
        self.stderr_thread.join(timeout=3)
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        if self.stderr_thread.is_alive() or self.thread.is_alive():
            raise ValueError("owned_fixture_cleanup_pending")
        self.closed = True
        return code
