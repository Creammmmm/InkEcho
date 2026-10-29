set -eu
umask 077
root=/tmp/handoff-r7
cd "$root"
printf '%s  %s\n' e4f2c6de3450cd997607baaeba41dd1764f8365c0bda73d9b9dd7c4ac395db54 InkEcho-0.10.2-x86_64.AppImage | sha256sum -c -
./InkEcho-0.10.2-x86_64.AppImage --appimage-extract >/dev/null
cp fcitx5.py output_router.py squashfs-root/packages/inkecho/platform/
sha256sum squashfs-root/packages/inkecho/platform/fcitx5.py squashfs-root/packages/inkecho/platform/output_router.py
! pgrep -x fcitx5 >/dev/null
base=$(mktemp -d /tmp/inkecho-handoff-fcitx.XXXXXX)
export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus XDG_RUNTIME_DIR=/run/user/1000 DISPLAY=:0 XDG_SESSION_TYPE=x11 GDK_BACKEND=x11 GTK_IM_MODULE=fcitx XMODIFIERS=@im=fcitx QT_IM_MODULE=fcitx
mkdir -p "$base/share" "$base/config" "$base/cache"
export XDG_DATA_HOME="$base/share" XDG_CONFIG_HOME="$base/config" XDG_CACHE_HOME="$base/cache"
export XAUTHORITY="$(systemctl --user show-environment | sed -n 's/^XAUTHORITY=//p')"
export APPDIR="$root/squashfs-root"
unset FCITX_ADDON_DIRS PYTHONHOME PYTHONPATH LD_LIBRARY_PATH QT_QPA_PLATFORM WAYLAND_DISPLAY
systemctl --user show-environment | sed -n '/^XMODIFIERS=/p; /^GTK_IM_MODULE=/p; /^QT_IM_MODULE=/p' > "$base/oldenv"
cleanup() {
 systemctl --user unset-environment XMODIFIERS GTK_IM_MODULE QT_IM_MODULE || true
 while IFS= read -r entry; do systemctl --user set-environment "$entry" || true; done < "$base/oldenv"
 test -z "${pid:-}" || kill "$pid" 2>/dev/null || true
 test -z "${pid:-}" || wait "$pid" 2>/dev/null || true
 rm -rf "$base"
}
trap cleanup EXIT
loginctl show-session "$(loginctl list-sessions --no-legend | awk '$2 == 1000 && $4 == "seat0" {print $1; exit}')" -p Type -p State
systemctl --user set-environment XMODIFIERS=@im=fcitx GTK_IM_MODULE=fcitx QT_IM_MODULE=fcitx
fcitx5 --disable xim -D > "$root/fcitx.log" 2>&1 & pid=$!
sleep 3
kill -0 "$pid"
env PYTHONHOME="$APPDIR/usr" PYTHONPATH="$APPDIR/packages" LD_LIBRARY_PATH="$APPDIR/usr/lib/inkecho" "$APPDIR/usr/bin/python3" -c 'from inkecho.platform.fcitx5_install import FcitxInstaller; m=FcitxInstaller(); m.install(); m.enable(); print(m.status())'
sleep 2
env PYTHONHOME="$APPDIR/usr" PYTHONPATH="$APPDIR/packages" LD_LIBRARY_PATH="$APPDIR/usr/lib/inkecho" "$APPDIR/usr/bin/python3" "$root/no-remap.py"

env PYTHONHOME="$APPDIR/usr" PYTHONPATH="$APPDIR/packages" LD_LIBRARY_PATH="$APPDIR/usr/lib/inkecho" "$APPDIR/usr/bin/python3" -c 'from inkecho.platform.fcitx5_install import FcitxInstaller; m=FcitxInstaller(); m.disable(); print(m.status())'
