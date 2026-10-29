set -eu
export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus XDG_RUNTIME_DIR=/run/user/1000 DISPLAY=:0 XAUTHORITY="$(systemctl --user show-environment | sed -n 's/^XAUTHORITY=//p')" GDK_BACKEND=wayland WAYLAND_DISPLAY=wayland-0
root=/tmp/inkecho-v2-package-acceptance/squashfs-root
env APPDIR="$root" PYTHONHOME="$root/usr" PYTHONPATH="$root/packages" LD_LIBRARY_PATH="$root/usr/lib/inkecho" "$root/usr/bin/python3" -c 'from inkecho.platform.ibus_extension import ExtensionManager; m=ExtensionManager(); m.enable(); print(m.status())'
sleep 2
PYTHONPATH="$root/packages" /usr/bin/python3 /mnt/input/input_probe.py
