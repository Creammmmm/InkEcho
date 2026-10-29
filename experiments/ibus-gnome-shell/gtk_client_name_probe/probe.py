"""Test names from two owned GTK clients on private Broadway and IBus."""

import os
import re
import subprocess
import time
from pathlib import Path

runtime = Path(os.environ["XDG_RUNTIME_DIR"])
assert str(runtime).startswith("/tmp/inkecho-ibus-lab.")
display = subprocess.Popen(
    ["broadwayd", "--unixsocket", str(runtime / "broadway5.socket"), ":5"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)
monitor = None
actors = []
try:
    time.sleep(0.5)
    assert display.poll() is None
    rule = (
        "type='method_call',interface='org.freedesktop.IBus',"
        "member='CreateInputContext',eavesdrop='true'"
    )
    monitor = subprocess.Popen(
        [
            "stdbuf",
            "-oL",
            "dbus-monitor",
            "--address",
            os.environ["IBUS_ADDRESS"],
            rule,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    time.sleep(0.5)
    env = os.environ.copy()
    env.update(GDK_BACKEND="broadway", BROADWAY_DISPLAY=":5", GTK_IM_MODULE="ibus")
    actors = [
        subprocess.Popen(
            ["/usr/bin/python3", str(Path(__file__).with_name("actor.py"))],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(2)
    ]
    for actor in actors:
        out, err = actor.communicate(timeout=8)
        print("actor", actor.pid, "exit", actor.returncode, out, err, flush=True)
        assert actor.returncode == 0
    monitor.terminate()
    out, err = monitor.communicate(timeout=3)
    print("context-creation metadata:\n" + out, flush=True)
    print("monitor diagnostic:\n" + err, flush=True)
    assert out.count('string "gtk3-im:inkecho-synthetic-same-name"') == 2
    assert len(set(re.findall(r"sender=(:\d+\.\d+)", out))) == 2
finally:
    for process in (*actors, monitor, display):
        if process is not None and process.poll() is None:
            process.terminate()
            process.wait(timeout=3)
