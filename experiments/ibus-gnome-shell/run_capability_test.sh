#!/usr/bin/env bash
set -eu
lab_dir=$(mktemp -d /tmp/inkecho-ibus-captest.XXXXXX)
trap 'rm -rf "$lab_dir"' EXIT
chmod 700 "$lab_dir"
printf '%064d' 0 | tr '0' a > "$lab_dir/target"
chmod 600 "$lab_dir/target"
cp "$lab_dir/target" "$lab_dir/inkecho-ibus-candidate.cap"
chmod 600 "$lab_dir/inkecho-ibus-candidate.cap"
XDG_RUNTIME_DIR="$lab_dir" gjs -m experiments/ibus-gnome-shell/capability.test.js
rm "$lab_dir/inkecho-ibus-candidate.cap"
ln -s target "$lab_dir/inkecho-ibus-candidate.cap"
test "$(XDG_RUNTIME_DIR="$lab_dir" gjs -m experiments/ibus-gnome-shell/capability-check.js)" = no
rm "$lab_dir/inkecho-ibus-candidate.cap"
cp "$lab_dir/target" "$lab_dir/inkecho-ibus-candidate.cap"
chmod 644 "$lab_dir/inkecho-ibus-candidate.cap"
test "$(XDG_RUNTIME_DIR="$lab_dir" gjs -m experiments/ibus-gnome-shell/capability-check.js)" = no
printf 'symlink and broad permissions rejected\n'
