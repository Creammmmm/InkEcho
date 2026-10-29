#!/bin/bash
set -eu
root=$(mktemp -d /tmp/inkecho-ibus-product-private.XXXXXX)
chmod 700 "$root"
trap 'rm -rf "$root"' EXIT
export XDG_RUNTIME_DIR="$root" GIO_USE_VFS=local
repo=$(git rev-parse --show-toplevel)
export PYTHONPATH="$repo/src"
cd "$(dirname "$0")"
dbus-run-session -- bash -c 'set -eu; gjs -m isolated_service.js > "$XDG_RUNTIME_DIR/service.log" 2>&1 & pid=$!; trap "kill $pid 2>/dev/null || true" EXIT; for i in $(seq 1 100); do grep -q ready "$XDG_RUNTIME_DIR/service.log" && break; sleep .05; done; "${VIRTUAL_ENV:?}/bin/python" product_bus_test.py'
