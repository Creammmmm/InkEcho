#!/bin/bash
set -eu
root=$(mktemp -d /tmp/inkecho-ibus-v2-private.XXXXXX)
chmod 700 "$root"
trap 'rm -rf "$root"' EXIT
export XDG_RUNTIME_DIR="$root"
export GIO_USE_VFS=local
cd "$(dirname "$0")"
dbus-run-session -- bash -c 'set -eu; gjs -m isolated_service.js > "$XDG_RUNTIME_DIR/service.log" 2>&1 & pid=$!; trap "kill $pid 2>/dev/null || true" EXIT; for i in $(seq 1 100); do grep -q ready "$XDG_RUNTIME_DIR/service.log" && break; sleep .05; done; rm "$XDG_RUNTIME_DIR/service.log"; exec_python="${VIRTUAL_ENV:?}/bin/python"; "$exec_python" isolated_bus_test.py'
