set -eu
umask 077
root=/tmp/inkecho-v2-protocol-acceptance
mkdir -p "$root"
cp /mnt/input/InkEcho.AppImage "$root/InkEcho.AppImage"
printf '%s  %s\n' 42118031876729529974e6c20d746638d5d09611f4bb34b4ae189fb4717ada7b "$root/InkEcho.AppImage" | sha256sum -c -
chmod 700 "$root/InkEcho.AppImage"
cd "$root"; ./InkEcho.AppImage --appimage-extract > /mnt/output/protocol-extract.log
cp /mnt/input/pipeline-tests/*.py "$root/"
export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus XDG_RUNTIME_DIR=/run/user/1000
export APPDIR="$root/squashfs-root" PYTHONHOME="$root/squashfs-root/usr" PYTHONPATH="$root/squashfs-root/packages" LD_LIBRARY_PATH="$root/squashfs-root/usr/lib/inkecho"
"$APPDIR/usr/bin/python3" -c 'from inkecho.platform.ibus_extension import ExtensionManager; m=ExtensionManager(); m.install(); print(m.status())'
