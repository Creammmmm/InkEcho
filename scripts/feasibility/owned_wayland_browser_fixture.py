#!/usr/bin/env python3
"""Disposable native Wayland Chrome and a local empty chat-style input fixture.

This helper never sends keys. Only its own fixed page reports input/focus state.
The temporary profile, server and owned browser are cleaned on context exit.
"""

import argparse
import json
import os
import secrets
import signal
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class OwnedWaylandBrowser:
    def __init__(self, field="textarea", switch_after=0, class_name=None):
        if field not in {"textarea", "contenteditable"}:
            raise ValueError("Unknown owned field")
        self.field = field
        if not isinstance(switch_after, int) or not 0 <= switch_after <= 8192:
            raise ValueError("Switch position must be within [0, 8192]")
        self.switch_after = switch_after
        self.class_name = class_name
        self.process = None
        self.server = None
        self.thread = None
        self.temporary = None
        self.log = None
        self.state = None
        self.requests = {"page": 0, "state": 0}
        self.lock = threading.Lock()

    def snapshot(self):
        with self.lock:
            return dict(self.state) if self.state is not None else None

    def __enter__(self):
        if os.environ.get("XDG_SESSION_TYPE") != "wayland" or not os.environ.get(
            "WAYLAND_DISPLAY"
        ):
            raise RuntimeError(
                "An explicitly coordinated native Wayland session is needed"
            )
        self.temporary = tempfile.TemporaryDirectory(prefix="inkecho-wayland-chrome-")
        self.root = Path(self.temporary.name)
        token = secrets.token_urlsafe(24)
        route = f"/{token}"
        field = (
            '<textarea id="field" autofocus rows="8" cols="65"></textarea>'
            if self.field == "textarea"
            else '<div id="field" contenteditable="true" role="textbox" '
            'aria-multiline="true" tabindex="0" style="min-height:160px"></div>'
        )
        second = (
            field.replace('id="field"', 'id="second"').replace("autofocus", "")
            if self.switch_after
            else ""
        )
        page = (
            '<!doctype html><meta charset="utf-8">'
            "<title>InkEcho owned native Wayland fixture</title>"
            "<h1>Owned local chat input fixture</h1>"
            "<p>No account, external website or message submission.</p>"
            + field
            + second
            + "<script>const field=document.querySelector('#field');"
            "const second=document.querySelector('#second');"
            f"const switchAfter={self.switch_after};"
            "let switched=false,sequence=0;"
            "const value=e=>e?(e.value??e.innerText):'';"
            "function record(){const first=value(field),last=value(second);"
            "fetch(location.pathname+'/state',{method:'POST',"
            "body:JSON.stringify({text:first+last,sequence:++sequence,"
            "first_count:Array.from(first).length,"
            "second_count:Array.from(last).length,switch_done:switched,"
            "document_focused:document.hasFocus(),"
            "field_focused:document.activeElement===(switched?second:field)})})}"
            "field.addEventListener('input',()=>{"
            "if(second&&!switched&&Array.from(value(field)).length>=switchAfter){"
            "second.focus();switched=document.activeElement===second;}record()});"
            "if(second)second.addEventListener('input',record);"
            "for(const e of [window,field,second].filter(Boolean)){"
            "e.addEventListener('blur',record);e.addEventListener('focus',record);}"
            "window.addEventListener('load',()=>{field.focus();record()});"
            "setInterval(record,100);</script>"
        ).encode()
        fixture = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path != route:
                    self.send_error(404)
                    return
                with fixture.lock:
                    fixture.requests["page"] += 1
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header(
                    "Content-Security-Policy",
                    "default-src 'none'; script-src 'unsafe-inline'; "
                    "style-src 'unsafe-inline'; connect-src 'self'; form-action 'none'",
                )
                self.end_headers()
                self.wfile.write(page)

            def do_POST(self):
                if self.path != route + "/state":
                    self.send_error(404)
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 < length <= 8192:
                        raise ValueError
                    state = json.loads(self.rfile.read(length))
                    if (
                        type(state.get("sequence")) is not int
                        or not isinstance(state.get("text"), str)
                        or any(
                            not isinstance(state.get(key), bool)
                            for key in ("document_focused", "field_focused")
                        )
                    ):
                        raise ValueError
                except (ValueError, TypeError, AttributeError):
                    self.send_error(400)
                    return
                state["sampled_at"] = time.monotonic()
                with fixture.lock:
                    if (
                        fixture.state is None
                        or state["sequence"] > fixture.state["sequence"]
                    ):
                        fixture.state = state
                    fixture.requests["state"] += 1
                self.send_response(204)
                self.end_headers()

            def log_message(self, *_):
                pass

        try:
            self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            self.thread = threading.Thread(
                target=self.server.serve_forever, daemon=True
            )
            self.thread.start()
            env = dict(os.environ, WAYLAND_DEBUG="client")
            for key in ("DISPLAY", "PYTHONHOME", "PYTHONPATH", "LD_LIBRARY_PATH"):
                env.pop(key, None)
            for key in ("XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME"):
                directory = self.root / key.lower()
                directory.mkdir()
                env[key] = str(directory)
            self.log = (self.root / "wayland.log").open("w")
            self.process = subprocess.Popen(
                [
                    "google-chrome",
                    "--ozone-platform=wayland",
                    *([f"--class={self.class_name}"] if self.class_name else []),
                    f"--user-data-dir={self.root / 'profile'}",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-background-networking",
                    "--disable-component-update",
                    "--disable-sync",
                    "--password-store=basic",
                    "--force-renderer-accessibility",
                    "--no-proxy-server",
                    "--host-resolver-rules=MAP * ~NOTFOUND, "
                    "EXCLUDE localhost, EXCLUDE 127.0.0.1",
                    f"--app=http://127.0.0.1:{self.server.server_port}{route}",
                ],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=self.log,
            )
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def native_evidence(self):
        data = (self.root / "wayland.log").read_text(errors="replace")
        environment = (Path("/proc") / str(self.process.pid) / "environ").read_bytes()
        return {
            "ozone_platform": "wayland",
            "display_unset_in_owned_process": not any(
                value.startswith(b"DISPLAY=") for value in environment.split(b"\0")
            ),
            "wayland_surface_observed": "wl_compositor" in data
            and "create_surface" in data,
            "xdg_toplevel_observed": "xdg_toplevel" in data,
        }

    def __exit__(self, *_):
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        if self.server is not None:
            if self.thread is not None:
                self.server.shutdown()
                self.thread.join(timeout=3)
            self.server.server_close()
        if self.log is not None:
            self.log.close()
        if self.temporary is not None:
            self.temporary.cleanup()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--field", choices=("textarea", "contenteditable"), default="textarea"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=30)
    parser.add_argument("--switch-after", type=int, default=0)
    args = parser.parse_args()
    if not 0 < args.seconds <= 120:
        parser.error("seconds must be within (0, 120]")

    def terminate(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, terminate)
    try:
        with OwnedWaylandBrowser(args.field, args.switch_after) as fixture:
            deadline = time.monotonic() + args.seconds
            while time.monotonic() < deadline:
                if fixture.process.poll() is not None:
                    raise RuntimeError("Owned Chrome exited")
                state = fixture.snapshot()
                if state is not None:
                    temporary = args.output.with_suffix(".tmp")
                    temporary.write_text(
                        json.dumps(
                            {"pid": fixture.process.pid, "field": args.field, **state}
                        )
                    )
                    temporary.replace(args.output)
                time.sleep(0.1)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
