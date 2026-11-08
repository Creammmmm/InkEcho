#!/bin/bash
set -euo pipefail
probe=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
case "$probe" in /tmp/inkecho-ibus-stock-key-*) ;; *) exit 2 ;; esac
mkdir -m 700 -p "$probe/home" "$probe/run" "$probe/config" "$probe/cache"
private_env=(
    -u DISPLAY -u WAYLAND_DISPLAY -u XAUTHORITY
    -u DBUS_SESSION_BUS_ADDRESS -u DBUS_SYSTEM_BUS_ADDRESS
    HOME="$probe/home" XDG_RUNTIME_DIR="$probe/run"
    XDG_CONFIG_HOME="$probe/config" XDG_CACHE_HOME="$probe/cache"
    GSETTINGS_BACKEND=memory IBUS_ADDRESS="unix:path=$probe/run/ibus.sock"
    PROBE_DIR="$probe"
)
env "${private_env[@]}" timeout --kill-after=2 15 dbus-run-session -- bash -c '
set -eu
/usr/bin/ibus-daemon -s -E disable -a "$IBUS_ADDRESS" >"$PROBE_DIR/daemon.log" 2>&1 &
pid=$!
trap "kill $pid 2>/dev/null || :; wait $pid 2>/dev/null || :" EXIT
/usr/bin/python3 "$PROBE_DIR/probe.py"
' | tee "$probe/result.json"
