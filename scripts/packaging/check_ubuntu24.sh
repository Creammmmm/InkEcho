#!/bin/sh
# Tests Ubuntu 24.04 userspace startup, not a Wayland/X11 desktop session.
set -eu
repo=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
artifact=InkEcho-0.1.0-stage0-x86_64.AppImage
test -x "$repo/dist/$artifact"
docker build --file "$repo/scripts/packaging/ubuntu24.Dockerfile" \
    --tag inkecho-ubuntu24-probe "$repo/scripts/packaging"
docker run --rm --network none --read-only --security-opt no-new-privileges \
    --tmpfs /tmp:exec,size=1200m --volume "$repo/dist:/input:ro" \
    inkecho-ubuntu24-probe "/input/$artifact" \
    --appimage-extract-and-run --smoke-test
