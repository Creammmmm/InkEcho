set -eu
umask 077
root=/tmp/wayland-lifecycle
export XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus WAYLAND_DISPLAY=wayland-0 DISPLAY=:0 XDG_SESSION_TYPE=wayland XDG_CURRENT_DESKTOP=ubuntu:GNOME GDK_BACKEND=wayland GTK_IM_MODULE=fcitx XMODIFIERS=@im=fcitx QT_IM_MODULE=fcitx
export XAUTHORITY=/run/user/1000/gdm/Xauthority
export APPDIR="$root/squashfs-root"
! pgrep -x fcitx5 >/dev/null
base=$(mktemp -d /tmp/inkecho-wayland-cross.XXXXXX)
mkdir -p "$base/share" "$base/config" "$base/cache"
export XDG_DATA_HOME="$base/share" XDG_CONFIG_HOME="$base/config" XDG_CACHE_HOME="$base/cache"
cp "$root/fcitx5.py" "$APPDIR/packages/inkecho/platform/fcitx5.py"
sha256sum "$APPDIR/packages/inkecho/platform/fcitx5.py"
systemctl --user show-environment | sed -n '/^XMODIFIERS=/p; /^GTK_IM_MODULE=/p; /^QT_IM_MODULE=/p' > "$base/oldenv"
cleanup() {
 systemctl --user unset-environment XMODIFIERS GTK_IM_MODULE QT_IM_MODULE || true
 while IFS= read -r entry; do systemctl --user set-environment "$entry" || true; done < "$base/oldenv"
 test -z "${pid:-}" || kill "$pid" 2>/dev/null || true
 test -z "${pid:-}" || wait "$pid" 2>/dev/null || true
 rm -rf "$base"
}
trap cleanup EXIT
systemctl --user set-environment XMODIFIERS=@im=fcitx GTK_IM_MODULE=fcitx QT_IM_MODULE=fcitx
fcitx5 --disable xim -D > "$root/fcitx.log" 2>&1 & pid=$!
sleep 3
kill -0 "$pid"
env PYTHONHOME="$APPDIR/usr" PYTHONPATH="$APPDIR/packages" LD_LIBRARY_PATH="$APPDIR/usr/lib/inkecho" "$APPDIR/usr/bin/python3" -c 'from inkecho.platform.fcitx5_install import FcitxInstaller; m=FcitxInstaller(); m.install(); m.enable(); print(m.status())'
sleep 2
env PYTHONHOME="$APPDIR/usr" PYTHONPATH="$APPDIR/packages" LD_LIBRARY_PATH="$APPDIR/usr/lib/inkecho" "$APPDIR/usr/bin/python3" "$root/cross.py"
env PYTHONHOME="$APPDIR/usr" PYTHONPATH="$APPDIR/packages" LD_LIBRARY_PATH="$APPDIR/usr/lib/inkecho" "$APPDIR/usr/bin/python3" -c 'from inkecho.platform.fcitx5_install import FcitxInstaller; m=FcitxInstaller(); m.disable(); print(m.status())'
