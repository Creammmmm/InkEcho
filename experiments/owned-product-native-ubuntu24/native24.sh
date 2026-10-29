#!/bin/bash
set -eu
mkdir -p /tmp/probe-out /tmp/inkecho-r4-test/probes /tmp/inkecho-package
sudo mount -t 9p -o trans=virtio,version=9p2000.L inkoutput /tmp/probe-out
sudo mount -t 9p -o trans=virtio,version=9p2000.L inkpackage /tmp/inkecho-package
exec > /tmp/probe-out/native24.log 2>&1
session="$(loginctl show-user inkecho -p Display --value)"
loginctl show-session "$session" -p Type -p Active -p LockedHint
loginctl show-session "$session" -p Type --value | grep -qx wayland
/usr/bin/gnome-shell --version
export XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus DISPLAY=:0 WAYLAND_DISPLAY=wayland-0 XDG_SESSION_TYPE=wayland XDG_CURRENT_DESKTOP=ubuntu:GNOME GDK_BACKEND=wayland XMODIFIERS=@im=ibus QT_IM_MODULE=ibus
export XAUTHORITY="$(systemctl --user show-environment | sed -n 's/^XAUTHORITY=//p')"
cd /tmp/inkecho-r4-test
cp /tmp/inkecho-package/InkEcho-0.10.2-x86_64.AppImage .
chmod +x InkEcho-0.10.2-x86_64.AppImage
./InkEcho-0.10.2-x86_64.AppImage --appimage-extract >/dev/null
tar -xf /mnt/source.tar -C squashfs-root/packages
cp /mnt/{sender.py,target-focus.py} probes/
sha256sum /mnt/source.tar squashfs-root/packages/inkecho/{app.py,platform/ibus_owned_auto.py,platform/ibus_owned_extension.py,ui/information.py}
root=/tmp/inkecho-r4-test/squashfs-root
PYTHONHOME="$root/usr" PYTHONPATH="$root/packages" LD_LIBRARY_PATH="$root/usr/lib/inkecho" QT_QPA_PLATFORM=offscreen "$root/usr/bin/python3" /mnt/ui-enable.py
sleep 3
gnome-extensions info inkecho-ibus-owned-v4-prototype@local.invalid || true
for mode in full cancel no-target; do echo CASE="$mode"; timeout 55 /usr/bin/python3 probes/target-focus.py "$mode" || true; done
PYTHONHOME="$root/usr" PYTHONPATH="$root/packages" LD_LIBRARY_PATH="$root/usr/lib/inkecho" QT_QPA_PLATFORM=offscreen "$root/usr/bin/python3" /mnt/ui-disable.py
gnome-extensions info inkecho-ibus-owned-v4-prototype@local.invalid || true
echo RUN_DONE
sync
sudo poweroff
