#!/bin/sh
# Independent disposable D-Bus session, no text is sent.
set -eu
work=$(mktemp -d)
export XDG_DATA_HOME="$work/data" XDG_CONFIG_HOME="$work/config"
export XDG_RUNTIME_DIR="$work/runtime"
mkdir -p "$XDG_DATA_HOME/fcitx5/addon" "$XDG_CONFIG_HOME" "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"
sed "s|Library=libinkecho|Library=/tmp/inkecho-runtime-version/build/libinkecho|" \
  /tmp/inkecho-runtime-version/build/inkecho.conf > "$XDG_DATA_HOME/fcitx5/addon/inkecho.conf"
pid=''
actor=''
trap '[ -z "$actor" ] || kill "$actor" 2>/dev/null || :; [ -z "$pid" ] || kill "$pid" 2>/dev/null || :; [ -z "$pid" ] || wait "$pid" 2>/dev/null || :; rm -rf "$work"' EXIT
start() {
  fcitx5 -D --keep --disable=wayland,xcb,notificationitem,classicui,clipboard >"$work/fcitx.log" 2>&1 &
  pid=$!
  count=0
  while [ "$count" -lt 50 ]; do
    if gdbus call --session --dest org.freedesktop.DBus --object-path /org/freedesktop/DBus \
      --method org.freedesktop.DBus.NameHasOwner org.fcitx.Fcitx5 | grep -q true; then return; fi
    count=$((count+1))
    sleep 0.1
  done
  cat "$work/fcitx.log" >&2
  return 1
}
owner() {
  gdbus call --session --dest org.freedesktop.DBus --object-path /org/freedesktop/DBus \
    --method org.freedesktop.DBus.GetNameOwner org.fcitx.Fcitx5
}
version() {
  gdbus call --session --dest "$1" --object-path /inkecho \
    --method org.fcitx.Fcitx.InkEcho1.RuntimeVersion
}
start
old=$(owner | sed "s/['(), ]//g")
old_version=$(version "$old")
if [ -n "${DISPLAY:-}" ]; then
  GTK_IM_MODULE=fcitx /usr/bin/python3 /tmp/inkecho-runtime-version/target.py fcitx "$work/text" &
  actor=$!
  count=0
  while [ ! -f "$work/text.module" ] && [ "$count" -lt 50 ]; do
    count=$((count+1)); sleep 0.1
  done
  window=$(xdotool search --pid "$actor" --name '^InkEcho isolated fcitx$' | tail -1)
  xdotool windowfocus --sync "$window"
  sleep 0.5
  /usr/bin/python3 /tmp/inkecho-runtime-version/protocol_probe.py "$work/text"
  kill "$actor"; wait "$actor" || :; actor=''
else
  /usr/bin/python3 /tmp/inkecho-runtime-version/protocol_probe.py
fi
kill "$pid"
wait "$pid" || :
pid=''
start
new=$(owner | sed "s/['(), ]//g")
new_version=$(version "$new")
test "$old" != "$new"
if version "$old" >/dev/null 2>&1; then exit 1; fi
printf 'old_owner=%s old_version=%s new_owner=%s new_version=%s old_owner_unreachable=true\n' \
  "$old" "$old_version" "$new" "$new_version"
