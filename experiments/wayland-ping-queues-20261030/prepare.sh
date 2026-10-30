#!/usr/bin/env bash
set -euo pipefail
experiment_dir=$(cd "$(dirname "$0")" && pwd)
repo_dir=$(cd "$experiment_dir/../.." && pwd)
lab_dir=${INKECHO_WAYLAND_LAB_DIR:-"$repo_dir/dist/wayland-ping-queues-20261030"}
if [ -e "$lab_dir/root" ]; then
    printf 'Refusing to extract over an existing root: %s\n' "$lab_dir/root" >&2
    exit 1
fi
mkdir -p "$lab_dir/debs"
lab_dir=$(cd "$lab_dir" && pwd)
cd "$lab_dir/debs"
export TMPDIR=${TMPDIR:-/var/tmp}
while IFS= read -r package; do apt-get download "$package"; done < "$experiment_dir/packages.txt"
sha256sum --check "$experiment_dir/debs.sha256"
mkdir "$lab_dir/root"
while read -r hash filename; do dpkg-deb -x "$filename" "$lab_dir/root"; done < "$experiment_dir/debs.sha256"
printf 'Verified dependencies extracted to %s\n' "$lab_dir/root"
