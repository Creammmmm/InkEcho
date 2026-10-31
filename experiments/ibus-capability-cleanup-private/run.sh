#!/bin/bash
set -eu
repo=$(git rev-parse --show-toplevel)
base=$(mktemp -d /var/tmp/inkecho-ibus-private.XXXXXX)
chmod 700 "$base"
trap 'rm -rf "$base"' EXIT
mkdir "$base/service" "$base/runtime"
chmod 700 "$base/runtime"
cp "$repo"/src/inkecho/platform/ibus_owned_candidate/{capability.js,delivery_gate.js,owned_gate.js,identity.js} "$base/service/"
cp "$repo/experiments/ibus-capability-cleanup-private/service.js" "$base/service/"
export XDG_RUNTIME_DIR="$base/runtime" PYTHONPATH="$repo/src" GIO_USE_VFS=local
export INKECHO_SERVICE_DIR="$base/service" INKECHO_REPO="$repo"
dbus-run-session -- bash -c 'set -eu; gjs -m "$INKECHO_SERVICE_DIR/service.js" > "$XDG_RUNTIME_DIR/service.log" 2>&1 & pid=$!; trap "kill $pid 2>/dev/null || true" EXIT; for i in $(seq 1 100); do grep -q READY "$XDG_RUNTIME_DIR/service.log" && break; sleep .05; done; "$INKECHO_REPO/.venv/bin/python" "$INKECHO_REPO/experiments/ibus-capability-cleanup-private/probe.py"'
