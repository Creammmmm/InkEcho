#!/usr/bin/env bash
set -euo pipefail
experiment_dir=$(cd "$(dirname "$0")" && pwd)
repo_dir=$(cd "$experiment_dir/../.." && pwd)
xres_dir=${INKECHO_XRES_LAB_DIR:-"$repo_dir/dist/fcitx-stale-xres-deps-20261030"}
if [ -e "$xres_dir/root" ]; then printf 'Refusing to overwrite existing root\n' >&2; exit 1; fi
mkdir -p "$xres_dir/debs"
xres_dir=$(cd "$xres_dir" && pwd)
cd "$xres_dir/debs"
export TMPDIR=${TMPDIR:-/var/tmp}
apt-get download libxcb-res0-dev=1.17.0-2ubuntu1
printf '%s  %s\n' 7f08271ca6d34de2c3782d31c099bd19dff20a1ffa0543547a3a013cb73f9a25 libxcb-res0-dev_1.17.0-2ubuntu1_amd64.deb | sha256sum -c
mkdir "$xres_dir/root"
dpkg-deb -x libxcb-res0-dev_1.17.0-2ubuntu1_amd64.deb "$xres_dir/root"
printf 'Verified XRes headers extracted to %s\n' "$xres_dir/root"
