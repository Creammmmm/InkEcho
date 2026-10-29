set -eu
export XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus DISPLAY=:0
mkdir -p /tmp/share /tmp/inkecho-r4-test
sudo mount -t 9p -o trans=virtio,version=9p2000.L,ro inkecho_input /tmp/share
cp /tmp/share/InkEcho-0.10.2-x86_64.AppImage /tmp/inkecho-r4-test/
cd /tmp/inkecho-r4-test
printf '%s  %s\n' 32f20808a0143d61bf24b2809a11d47344688a7e7edb690684f9e47cfd50bfa5 InkEcho-0.10.2-x86_64.AppImage | sha256sum -c -
chmod +x InkEcho-0.10.2-x86_64.AppImage
./InkEcho-0.10.2-x86_64.AppImage --appimage-extract >/dev/null
python3 - <<'PY'
import zipfile
from pathlib import Path
for source, dest in [(Path('squashfs-root/packages/inkecho/platform/ibus_candidate'), 'product.zip'),(Path('/tmp/share/fault'), 'fault.zip')]:
 with zipfile.ZipFile(dest,'w') as archive:
  for item in source.iterdir():
   if item.is_file(): archive.writestr(item.name,item.read_bytes())
PY
sudo umount /tmp/share
gsettings set org.gnome.shell disable-user-extensions false
gnome-extensions install product.zip
gnome-extensions install fault.zip
gnome-extensions enable inkecho-ibus-v2-prototype@local.invalid
gnome-extensions enable inkecho-presend-fault@local.invalid
sleep 3
gnome-extensions info inkecho-ibus-v2-prototype@local.invalid
gnome-extensions info inkecho-presend-fault@local.invalid
