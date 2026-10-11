import os
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

page = b"""<!doctype html><html><head><meta charset="utf-8">
<title>InkEcho isolated browser</title></head><body>
<textarea autofocus rows="12" cols="60"
oninput="fetch('/result',{method:'POST',body:JSON.stringify(this.value)})">
</textarea></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(page)

    def do_POST(self):
        data = self.rfile.read(int(self.headers["Content-Length"]))
        Path("/tmp/inkecho-x11-browser.json").write_bytes(data)
        self.send_response(204)
        self.end_headers()

    def log_message(self, *_):
        pass


server = HTTPServer(("127.0.0.1", 0), Handler)
print(f"Browser probe listening on port {server.server_port}", flush=True)
process = subprocess.Popen(
    [
        "google-chrome",
        "--ozone-platform=x11",
        "--user-data-dir=/tmp/inkecho-chrome-x11",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-networking",
        "--disable-component-update",
        f"http://127.0.0.1:{server.server_port}",
    ],
    env=dict(os.environ, DISPLAY=":91"),
)
try:
    server.serve_forever()
finally:
    process.terminate()
    server.server_close()
