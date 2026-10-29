#!/bin/sh
# Run only in a disposable guest, under dbus-run-session.
set -eu
work=$(mktemp -d)
export XDG_DATA_HOME="$work/data" XDG_CONFIG_HOME="$work/config"
mkdir -p "$XDG_DATA_HOME/fcitx5/addon" "$XDG_CONFIG_HOME"
sed "s|Library=libinkecho|Library=/tmp/inkecho-runtime-version/build/libinkecho|" \
  /tmp/inkecho-runtime-version/build/inkecho.conf > "$XDG_DATA_HOME/fcitx5/addon/inkecho.conf"
fcitx5 -D --keep --disable=wayland,xcb,notificationitem,classicui,clipboard >"$work/fcitx.log" 2>&1 &
pid=$!
trap 'kill "$pid" 2>/dev/null || :; wait "$pid" 2>/dev/null || :; rm -rf "$work"' EXIT
attempt=0
while [ "$attempt" -lt 50 ]; do
  if gdbus call --session --dest org.freedesktop.DBus \
    --object-path /org/freedesktop/DBus --method org.freedesktop.DBus.NameHasOwner \
    org.fcitx.Fcitx5 | grep -q true && \
    gdbus call --session --dest org.fcitx.Fcitx5 --object-path /inkecho \
    --method org.fcitx.Fcitx.InkEcho1.RuntimeVersion 2>/dev/null; then
    exit 0
  fi
  attempt=$((attempt + 1))
  sleep 0.1
done
cat "$work/fcitx.log" >&2
exit 1
