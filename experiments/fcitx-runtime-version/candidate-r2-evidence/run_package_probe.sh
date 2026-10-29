#!/bin/sh
# Disposable desktop guest only; uses the extracted verified candidate AppImage.
set -eu
root=/tmp/inkecho-package-test
app="$root/squashfs-root"
export XDG_DATA_HOME="$root/data" INK_TEST_TARGET="$root/target-text"
rm -f "$INK_TEST_TARGET" "$INK_TEST_TARGET.module"
rm -rf "$XDG_DATA_HOME" "$root/settings"
mkdir -p "$XDG_DATA_HOME"
chmod 700 "$XDG_DATA_HOME"
ink_python() {
  env APPDIR="$app" PYTHONHOME="$app/usr" PYTHONPATH="$app/packages" \
    LD_LIBRARY_PATH="$app/usr/lib/inkecho" "$app/usr/bin/python3" "$@"
}
ink_python -c 'from inkecho.platform.fcitx5_install import FcitxInstaller; FcitxInstaller().install(); print("package addon installed")'
ink_python -c 'from inkecho.config import ConfigStore; from pathlib import Path; s=ConfigStore(Path("/tmp/inkecho-package-test/settings")); s.initialize(); c=s.load_settings(); print("settings", c.output_method, c.x11_mapping_wait_ms, c.x11_feedback_timeout_ms)'
systemctl --user show-environment | grep -E '^(GTK_IM_MODULE|QT_IM_MODULE|XMODIFIERS)=' > "$root/old-environment" || :
pid=''; actor=''
cleanup() {
  [ -z "$actor" ] || kill "$actor" 2>/dev/null || :
  [ -z "$pid" ] || kill "$pid" 2>/dev/null || :
  [ -z "$pid" ] || wait "$pid" 2>/dev/null || :
  systemctl --user unset-environment GTK_IM_MODULE QT_IM_MODULE XMODIFIERS
  while IFS= read -r line; do [ -z "$line" ] || systemctl --user set-environment "$line"; done < "$root/old-environment"
}
trap cleanup EXIT
if gdbus call --session --dest org.freedesktop.DBus --object-path /org/freedesktop/DBus \
  --method org.freedesktop.DBus.NameHasOwner org.fcitx.Fcitx5 | grep -q true; then
  echo 'A Fcitx daemon is already running; refusing to replace it.' >&2; exit 1
fi
systemctl --user set-environment GTK_IM_MODULE=fcitx QT_IM_MODULE=fcitx XMODIFIERS=@im=fcitx
fcitx5 -D --keep --disable=clipboard > "$root/fcitx.log" 2>&1 &
pid=$!
export INK_TEST_FCITX_PID="$pid"
count=0
while [ "$count" -lt 50 ]; do
  if gdbus call --session --dest org.freedesktop.DBus --object-path /org/freedesktop/DBus \
    --method org.freedesktop.DBus.NameHasOwner org.fcitx.Fcitx5 | grep -q true; then break; fi
  count=$((count+1)); sleep 0.1
done
GTK_IM_MODULE=fcitx GDK_BACKEND=x11 /usr/bin/python3 "$root/target.py" fcitx "$INK_TEST_TARGET" &
actor=$!
count=0
while [ ! -f "$INK_TEST_TARGET.module" ] && [ "$count" -lt 50 ]; do count=$((count+1)); sleep 0.1; done
sleep 2
window=$(xdotool search --pid "$actor" --onlyvisible --name '^InkEcho isolated fcitx$' | tail -1)
xdotool windowfocus --sync "$window"
sleep 1
ink_python "$root/route_probe.py"
