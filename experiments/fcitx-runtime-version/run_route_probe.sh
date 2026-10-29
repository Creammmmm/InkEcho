#!/bin/sh
# Disposable logged-in guest only; expects the frozen tree under /tmp/inkecho-route.
set -eu
root=/tmp/inkecho-route
export XDG_DATA_HOME="$root/data"
export PYTHONPATH="$root"
export INK_TEST_TARGET="$root/target-text"
rm -f "$INK_TEST_TARGET" "$INK_TEST_TARGET.module"
mkdir -p "$XDG_DATA_HOME/fcitx5/addon" "$XDG_DATA_HOME/inkecho/fcitx5/532ef632385bfe9ae3b76312b74874a7cc562c58435bb07f430e704179ebd139"
dir="$XDG_DATA_HOME/inkecho/fcitx5/532ef632385bfe9ae3b76312b74874a7cc562c58435bb07f430e704179ebd139"
cp "$root/libinkecho.so" "$dir/libinkecho.so"
version=$(fcitx5 --version)
/usr/bin/python3 -c 'from inkecho.platform.fcitx5_staging import _conf; import os,sys; open(sys.argv[1],"wb").write(_conf(sys.argv[2],sys.argv[3]))' \
  "$XDG_DATA_HOME/fcitx5/addon/inkecho.conf" "$dir/libinkecho" "$version"
chmod -R go-w "$XDG_DATA_HOME"
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
window=$(xdotool search --pid "$actor" --name '^InkEcho isolated fcitx$' | tail -1)
xdotool windowfocus --sync "$window"
sleep 1
/usr/bin/python3 "$root/route_probe.py"
