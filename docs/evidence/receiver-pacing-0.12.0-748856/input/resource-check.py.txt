from pathlib import Path
import os,json,subprocess,fcntl,ctypes as C,ctypes.util
O=Path('/mnt/output')/os.environ.get('INKECHO_OUTPUT_STAGE','');m=json.loads((O/'mount.json').read_text());matches=[]
for p in Path('/proc').glob('[0-9]*/environ'):
 try:
  if int(p.parent.name)==os.getpid()or p.stat().st_uid!=os.getuid():continue
  env=p.read_bytes().split(b'\0')
  if any(v==('APPDIR='+m['appdir']).encode()for v in env):matches.append(int(p.parent.name))
 except OSError:pass
caps=[p.name for p in Path('/run/user/1000').glob('*inkecho*.cap')];lock_rows=[]
for p in Path('/run/user/1000').glob('*inkecho*.lock'):
 fd=os.open(p,os.O_RDWR|os.O_NOFOLLOW|os.O_NONBLOCK)
 try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);lock_rows.append({'name':p.name,'lock_free':True});fcntl.flock(fd,fcntl.LOCK_UN)
 finally:os.close(fd)
module_lines=subprocess.check_output(['pactl','list','short','modules'],text=True).splitlines();owned_audio=[l.split()[1]for l in module_lines if 'inkecho' in l.lower()]
owner=subprocess.check_output(['gdbus','call','--session','--dest','org.freedesktop.DBus','--object-path','/org/freedesktop/DBus','--method','org.freedesktop.DBus.NameHasOwner','org.fcitx.Fcitx5'],text=True).strip()
x=C.CDLL(ctypes.util.find_library('X11'));x.XOpenDisplay.argtypes=[C.c_char_p];x.XOpenDisplay.restype=C.c_void_p;x.XKeysymToKeycode.argtypes=[C.c_void_p,C.c_ulong];x.XKeysymToKeycode.restype=C.c_ubyte;x.XQueryKeymap.argtypes=[C.c_void_p,C.c_void_p];x.XCloseDisplay.argtypes=[C.c_void_p];d=x.XOpenDisplay(None);assert d;state=C.create_string_buffer(32);x.XQueryKeymap(d,state);held=[]
for sym in [97,110,105,32,65307,65505,65507,65513]:
 code=x.XKeysymToKeycode(d,sym)
 if code and state.raw[code//8]&(1<<(code%8)):held.append(sym)
x.XCloseDisplay(d)
r={'candidate_processes_after_tests':matches,'capabilities_remaining':caps,'lock_states':lock_rows,'owned_virtual_audio_remaining':owned_audio,'fcitx_service_owner':owner,'generated_keys_or_modifiers_held':held,'mount_gone':not Path(m['appdir']).exists()};r['passed']=not(matches or caps or owned_audio or held)and owner=='(false,)'and r['mount_gone'];(O/'final-resource-check.json').write_text(json.dumps(r,indent=2));print(json.dumps(r));assert r['passed']
