import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

base = Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix='inkecho-check-', dir='/var/tmp') as tmp:
    tmp = Path(tmp)
    info, log = tmp / 'info.json', tmp / 'fault.log'
    env = os.environ.copy()
    mode = sys.argv[1] if len(sys.argv) > 1 else '1'
    assert mode in ('1', '2')
    marker = 'INJECTED_FAILURE_AFTER_FCITX' if mode == '1' else 'INJECTED_FAILURE_IN_CLIENT'
    env.update(INKECHO_INFO_PATH=str(info), INKECHO_FAULT_AFTER_FCITX=mode)
    with log.open('w') as output:
        run = subprocess.Popen(['bash', str(base / 'run.sh')], env=env, stdout=output, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and not (log.exists() and marker in log.read_text(errors='replace')):
            if run.poll() is not None:
                raise RuntimeError('experiment exited before fault injection')
            time.sleep(0.05)
        if not info.exists() or marker not in log.read_text(errors='replace'):
            run.kill(); run.wait(); raise RuntimeError('fault injection timed out')
        pidns = json.loads(info.read_text())['pid-namespace']
        def processes():
            found = []
            for item in Path('/proc').iterdir():
                if not item.name.isdecimal(): continue
                try:
                    if os.readlink(item / 'ns/pid') == f'pid:[{pidns}]':
                        found.append((int(item.name), (item / 'comm').read_text().strip()))
                except (FileNotFoundError, PermissionError, ProcessLookupError): pass
            return sorted(found)
        before = processes()
        print('namespace_before:', before, flush=True)
        if not {'weston', 'fcitx5'}.issubset({name for _, name in before}):
            run.kill(); run.wait(); raise RuntimeError('expected private processes not observed')
        result = run.wait(timeout=20)
        print('injected_exit:', result, flush=True)
        if result != (42 if mode == '1' else 43): raise RuntimeError('wrong injected failure exit status')
        time.sleep(0.2)
        after = processes()
        print('namespace_after:', after, flush=True)
        if after: raise RuntimeError('private processes remain after failure')
        print('cleanup_check: PASS', flush=True)
        print('failure_marker:', marker in log.read_text(errors='replace'), flush=True)
