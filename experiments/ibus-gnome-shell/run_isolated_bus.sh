#!/usr/bin/env bash
set -eu
dbus-run-session -- bash -c '
set -eu
lab_dir=$(mktemp -d /tmp/inkecho-ibus-proto.XXXXXX)
chmod 700 "$lab_dir"
export XDG_RUNTIME_DIR="$lab_dir"
gjs -m experiments/ibus-gnome-shell/isolated_service.js >"$lab_dir/service.log" 2>&1 &
service_pid=$!
trap "kill $service_pid 2>/dev/null || true; wait $service_pid 2>/dev/null || true; rm -rf $lab_dir" EXIT
for i in {1..50}; do if grep -q ready "$lab_dir/service.log"; then break; fi; sleep 0.1; done
.venv/bin/python experiments/ibus-gnome-shell/isolated_bus_test.py
'
