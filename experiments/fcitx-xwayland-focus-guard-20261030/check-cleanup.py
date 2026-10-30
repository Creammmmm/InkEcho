import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

base = Path(__file__).resolve().parent
mode = sys.argv[1]
assert mode in ('different', 'same')
script = 'run.sh' if mode == 'different' else 'run-samepid.sh'
with tempfile.TemporaryDirectory(prefix='inkecho-cleanup-check-', dir='/var/tmp') as tmp:
    tmp = Path(tmp)
    info, log = tmp / 'info.json', tmp / 'probe.log'
    env = os.environ.copy()
    env.update(INKECHO_INFO_PATH=str(info), INKECHO_STALE_FAULT='1')
    with log.open('w') as output:
        run = subprocess.Popen(['bash', str(base / script)], env=env, stdout=output, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline and 'FAULT_AFTER_STOP' not in log.read_text(errors='replace'):
                if run.poll() is not None:
                    raise RuntimeError('experiment exited before injection')
                time.sleep(.05)
            if 'FAULT_AFTER_STOP' not in log.read_text(errors='replace'):
                run.kill(); run.wait(); raise RuntimeError('fault injection timed out')
            pidns = json.loads(info.read_text())['pid-namespace']
            def processes():
                found=[]
                for item in Path('/proc').iterdir():
                    if not item.name.isdecimal():continue
                    try:
                        if os.readlink(item / 'ns/pid') == f'pid:[{pidns}]':
                            name=(item / 'comm').read_text().strip()
                            state=(item / 'status').read_text().split('State:')[1].strip()[0]
                            found.append((int(item.name),name,state))
                    except (FileNotFoundError,PermissionError,ProcessLookupError):pass
                return sorted(found)
            before=processes();print('namespace_before:',before,flush=True)
            if not {'weston','fcitx5','Xwayland'}.issubset({name for _,name,_ in before}) or not any(name=='python3' and state=='T' for _,name,state in before):
                run.kill();run.wait();raise RuntimeError('expected stopped target and services not observed')
            result=run.wait(timeout=20);print('injected_exit:',result,flush=True)
            if result != 1:raise RuntimeError('unexpected fault exit status')
            time.sleep(.2);after=processes();print('namespace_after:',after,flush=True)
            if after:raise RuntimeError('private processes remain')
            dirs=[line.split()[1:] for line in log.read_text(errors='replace').splitlines() if line.startswith('TEST_TEMP_DIRS ')]
            if len(dirs)!=1 or len(dirs[0])!=2:raise RuntimeError('temporary paths unavailable')
            remaining=[p for p in dirs[0] if Path(p).exists()]
            print('temporary_dirs_remaining:',remaining,flush=True)
            if remaining:raise RuntimeError('temporary directories remain')
            print('cleanup_check: PASS',flush=True)
            if os.environ.get('INKECHO_FAULT_LOG_DIR'):
                (Path(os.environ['INKECHO_FAULT_LOG_DIR']) / f'fault-{mode}.log').write_bytes(log.read_bytes())
        finally:
            if run.poll() is None:
                run.terminate()
                try:
                    run.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    run.kill()
                    run.wait()
