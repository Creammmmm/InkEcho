#!/bin/bash
# Private X socket, authorization and network namespace. No user desktop access.
set -eu
repo_root=$(cd "$(dirname "$0")/../.." && pwd)
sdk_root="$repo_root/dist/xim-sync-stage0-20261030/root"
lab_dir=$(mktemp -d /var/tmp/inkecho-xim-sync.XXXXXX)
chmod 700 "$lab_dir"
trap 'rm -rf "$lab_dir"' EXIT
TMPDIR="$lab_dir" cc -std=c11 -Wall -Wextra -Werror -I"$sdk_root/usr/include" \
  "$repo_root/experiments/xim-sync-private-20261030/probe.c" \
  -L"$sdk_root/usr/lib/x86_64-linux-gnu" -lxcb-imdkit \
  /usr/lib/x86_64-linux-gnu/libxcb.so.1 -o "$lab_dir/probe"
bwrap --unshare-net --ro-bind / / --bind "$lab_dir" /tmp --dev /dev --proc /proc \
  --setenv INKECHO_SDK_ROOT "$sdk_root" --chdir /tmp /bin/bash -c '
set -eu
export XAUTHORITY=/tmp/auth
: > "$XAUTHORITY"; chmod 600 "$XAUTHORITY"
xauth add :88 MIT-MAGIC-COOKIE-1 "$(od -An -N16 -tx1 /dev/urandom | tr -d " \n")"
export LD_LIBRARY_PATH="$INKECHO_SDK_ROOT/usr/lib/x86_64-linux-gnu" LIBGL_ALWAYS_SOFTWARE=1
"$INKECHO_SDK_ROOT/usr/bin/Xvfb" :88 -screen 0 800x600x24 -extension GLX -nolisten tcp -auth "$XAUTHORITY" >/tmp/xvfb.log 2>&1 &
p=$!; trap '\''kill "$p" 2>/dev/null || :; wait "$p" 2>/dev/null || :'\'' EXIT
for i in $(seq 1 100); do
  test -S /tmp/.X11-unix/X88 && break
  if ! kill -0 "$p" 2>/dev/null; then cat /tmp/xvfb.log; exit 1; fi
  sleep .05
done
DISPLAY=:88 timeout 10 /tmp/probe
'
