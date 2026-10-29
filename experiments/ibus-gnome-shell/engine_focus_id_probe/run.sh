#!/bin/bash
# Create a private session bus even when invoked from a normal desktop session.
set -eu
if [ "${INKECHO_ISOLATED_BUS:-}" != 1 ]; then
    exec dbus-run-session -- env INKECHO_ISOLATED_BUS=1 bash "$0" "$@"
fi
probe_dir=$(mktemp -d /tmp/inkecho-ibus-lab.XXXXXX)
ibus_pid=
cleanup() {
    if [ -n "$ibus_pid" ]; then
        kill "$ibus_pid" 2>/dev/null || true
        wait "$ibus_pid" 2>/dev/null || true
    fi
    if [ -f "$probe_dir/ibus.log" ]; then
        tail -n 40 "$probe_dir/ibus.log"
    fi
    rm -rf "$probe_dir"
}
trap cleanup EXIT
export HOME="$probe_dir" XDG_CONFIG_HOME="$probe_dir/config"
export XDG_CACHE_HOME="$probe_dir/cache" XDG_RUNTIME_DIR="$probe_dir/runtime"
export GIO_USE_VFS=local
mkdir -m 700 "$XDG_RUNTIME_DIR" "$XDG_CONFIG_HOME" "$XDG_CACHE_HOME"
export IBUS_ADDRESS="unix:path=$probe_dir/ibus.sock"
ibus-daemon --single --panel=disable --config=disable --emoji-extension=disable \
    --address="$IBUS_ADDRESS" >"$probe_dir/ibus.log" 2>&1 &
ibus_pid=$!
for _ in $(seq 1 50); do
    [ -S "$probe_dir/ibus.sock" ] && break
    sleep .1
done
test -S "$probe_dir/ibus.sock"
/usr/bin/python3 "$(dirname "$0")/probe.py"
