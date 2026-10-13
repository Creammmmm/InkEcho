#!/usr/bin/env python3
"""Fresh XWayland Chromium fixture; only this blank local page writes its text."""

import json
import signal
import subprocess
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

PAGE = b"""<!doctype html><meta charset="utf-8">
<title>InkEcho owned input fixture</title>
<textarea autofocus rows="12" cols="60"></textarea><script>
const field=document.querySelector('textarea');
function record(){fetch('/result',{method:'POST',body:JSON.stringify(field.value)})}
field.addEventListener('input',record);window.addEventListener('load',record);
</script>"""
output = Path(sys.argv[1])


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(PAGE)

    def do_POST(self):
        if self.path != "/result":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length > 4096:
            self.send_error(413)
            return
        value = json.loads(self.rfile.read(length))
        if not isinstance(value, str):
            self.send_error(400)
            return
        output.write_text(json.dumps(value))
        self.send_response(204)
        self.end_headers()

    def log_message(self, *_):
        pass


def terminate(*_):
    raise KeyboardInterrupt


signal.signal(signal.SIGTERM, terminate)
with tempfile.TemporaryDirectory(prefix="inkecho-owned-chrome-") as profile:
    server = HTTPServer(("127.0.0.1", 0), Handler)
    browser = subprocess.Popen(
        [
            "google-chrome",
            "--ozone-platform=x11",
            f"--user-data-dir={profile}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            "--disable-component-update",
            "--force-renderer-accessibility",
            f"http://127.0.0.1:{server.server_port}",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    output.with_suffix(".pid").write_text(str(browser.pid))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        browser.terminate()
        try:
            browser.wait(timeout=3)
        except subprocess.TimeoutExpired:
            browser.kill()
            browser.wait()
        server.server_close()
