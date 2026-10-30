import os,subprocess,json,pathlib
e=dict(os.environ,DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/1000/bus",XDG_RUNTIME_DIR="/run/user/1000")
for line in subprocess.check_output(["systemctl","--user","show-environment"],env=e,text=True).splitlines():
 k,sep,v=line.partition("=")
 if sep and k in {"DISPLAY","XAUTHORITY","WAYLAND_DISPLAY","XDG_SESSION_TYPE","XDG_CURRENT_DESKTOP"}:e[k]=v
p=subprocess.run(["ibus","engine"],env=e,capture_output=True,text=True)
pathlib.Path("/mnt/output/engine-final-check.json").write_text(json.dumps({"returncode":p.returncode,"stdout":p.stdout,"stderr":p.stderr},indent=2))
assert p.returncode==0 and p.stdout.strip()=="xkb:us::eng"
