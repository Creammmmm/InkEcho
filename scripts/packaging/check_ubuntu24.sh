#!/bin/sh
# Tests Ubuntu 24.04 userspace startup, not a Wayland/X11 desktop session.
set -eu
repo=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
artifact=${1:-InkEcho-0.1.0a6-x86_64.AppImage}
test -x "$repo/dist/$artifact"
output=$(mktemp -d "$repo/build/ubuntu24-qa.XXXXXX")
# Only this newly created screenshot directory is writable by container UID 65532.
chmod 0777 "$output"
docker build --file "$repo/scripts/packaging/ubuntu24.Dockerfile" \
    --tag inkecho-ubuntu24-alpha "$repo/scripts/packaging"
docker run --rm --network none --read-only --security-opt no-new-privileges \
    --tmpfs /tmp:exec,size=1200m --volume "$repo/dist:/input:ro" \
    --volume "$output:/output" inkecho-ubuntu24-alpha "/input/$artifact" \
    --appimage-extract-and-run --config-dir /tmp/config --data-dir /tmp/data \
    --screenshot-dir /output --quit-after 1
test "$(find "$output" -name 'page-*.png' -type f | wc -l)" -eq 9
printf 'Full application exited successfully; nine page screenshots: %s\n' "$output"
