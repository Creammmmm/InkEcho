set -eu
umask 077
root=/tmp/inkecho-native-test
printf '%s  %s\n' 852a9e53efd66c7a19806e2473726d1ae5cdae5306804992fbf7d925eb583a48 "$root/InkEcho-0.10.2-x86_64.AppImage" | sha256sum -c -
cd "$root"
test -d squashfs-root || ./InkEcho-0.10.2-x86_64.AppImage --appimage-extract >/dev/null
! pgrep -x fcitx5 >/dev/null
base=$(mktemp -d /tmp/inkecho-session-fcitx.XXXXXX)
export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus XDG_RUNTIME_DIR=/run/user/1000 DISPLAY=:0 XDG_SESSION_TYPE=x11 GDK_BACKEND=x11 GTK_IM_MODULE=fcitx XMODIFIERS=@im=fcitx QT_IM_MODULE=fcitx
export XAUTHORITY="$(systemctl --user show-environment | sed -n 's/^XAUTHORITY=//p')"
test -n "$XAUTHORITY" && test -r "$XAUTHORITY"
mkdir -p "$base/share" "$base/config" "$base/cache"
export XDG_DATA_HOME="$base/share" XDG_CONFIG_HOME="$base/config" XDG_CACHE_HOME="$base/cache"
export APPDIR="$root/squashfs-root"
unset FCITX_ADDON_DIRS PYTHONHOME PYTHONPATH LD_LIBRARY_PATH QT_QPA_PLATFORM
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
fcitx5 --disable xim -D > "$root/probes/fcitx.log" 2>&1 & pid=$!
sleep 3
kill -0 "$pid"
env PYTHONHOME="$APPDIR/usr" PYTHONPATH="$APPDIR/packages" LD_LIBRARY_PATH="$APPDIR/usr/lib/inkecho" "$APPDIR/usr/bin/python3" -c 'from inkecho.platform.fcitx5_install import FcitxInstaller; m=FcitxInstaller(); m.install(); m.enable(); print(m.status())'
sleep 2
for backend in auto fcitx; do
  export INK_PROBE_MODE="$backend"
  /usr/bin/python3 "$root/probes/target-focus.py" switch-ready
  /usr/bin/python3 "$root/probes/target-focus.py" cancel
done
env PYTHONHOME="$APPDIR/usr" PYTHONPATH="$APPDIR/packages" LD_LIBRARY_PATH="$APPDIR/usr/lib/inkecho" "$APPDIR/usr/bin/python3" -c 'from inkecho.platform.fcitx5_install import FcitxInstaller; m=FcitxInstaller(); m.disable(); print(m.status())'
