set -eu
umask 077
root=/tmp/inkecho-native-test
cd "$root"
printf '%s  %s\n' f6378650f230215a0ff0a7196a80ddc48e9429e2546b55afe40105d8a5889d05 "$root/InkEcho-0.10.2-x86_64.AppImage" | sha256sum -c -
export XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus DISPLAY=:0 XDG_SESSION_TYPE=x11 GDK_BACKEND=x11 GTK_IM_MODULE=gtk-im-context-simple INK_PROBE_MODE=auto
export XAUTHORITY="$(systemctl --user show-environment | sed -n 's/^XAUTHORITY=//p')"
test -n "$XAUTHORITY" && test -r "$XAUTHORITY"
! pgrep -x fcitx5 >/dev/null
base=$(mktemp -d /tmp/inkecho-keyboard-fallback.XXXXXX)
trap 'rm -rf "$base"' EXIT
export XDG_DATA_HOME="$base/share" XDG_CONFIG_HOME="$base/config" XDG_CACHE_HOME="$base/cache"
mkdir -p "$XDG_DATA_HOME" "$XDG_CONFIG_HOME" "$XDG_CACHE_HOME"
unset PYTHONHOME PYTHONPATH LD_LIBRARY_PATH QT_QPA_PLATFORM
chmod +x "$root/InkEcho-0.10.2-x86_64.AppImage"
"$root/InkEcho-0.10.2-x86_64.AppImage" --help > "$root/probes/fuse-help.log" 2>&1 && echo 'direct_appimage_help_exit=0' || echo 'direct_appimage_help_failed'
"$root/InkEcho-0.10.2-x86_64.AppImage" --appimage-extract >/dev/null
for mode in full switch switch cancel; do /usr/bin/python3 "$root/probes/target-focus.py" "$mode"; done
