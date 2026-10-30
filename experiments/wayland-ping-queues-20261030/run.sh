#!/usr/bin/env bash
set -euo pipefail
experiment_dir=$(cd "$(dirname "$0")" && pwd)
repo_dir=$(cd "$experiment_dir/../.." && pwd)
lab_dir=${INKECHO_WAYLAND_LAB_DIR:-"$repo_dir/dist/wayland-ping-queues-20261030"}
cd "$lab_dir"
tmpdir=$(mktemp -d /var/tmp/inkecho-wayland-queues.XXXXXX)
trap 'rm -rf "$tmpdir"' EXIT
for spec in 'xdg root/usr/share/wayland-protocols/stable/xdg-shell/xdg-shell.xml' 'text root/usr/share/wayland-protocols/unstable/text-input/text-input-unstable-v3.xml'; do
    read -r name xml <<< "$spec"
    root/usr/bin/wayland-scanner client-header "$xml" "$tmpdir/$name-client.h"
    root/usr/bin/wayland-scanner server-header "$xml" "$tmpdir/$name-server.h"
    root/usr/bin/wayland-scanner private-code "$xml" "$tmpdir/$name-protocol.c"
done
TMPDIR="$tmpdir" gcc -std=c11 -Wall -Wextra -Iroot/usr/include -I"$tmpdir" "$experiment_dir/inkecho-wayland-server.c" "$tmpdir/xdg-protocol.c" "$tmpdir/text-protocol.c" /usr/lib/x86_64-linux-gnu/libwayland-server.so.0 -o "$tmpdir/server"
TMPDIR="$tmpdir" gcc -std=c11 -Wall -Wextra -Iroot/usr/include -I"$tmpdir" "$experiment_dir/inkecho-wayland-client.c" "$tmpdir/xdg-protocol.c" "$tmpdir/text-protocol.c" /usr/lib/x86_64-linux-gnu/libwayland-client.so.0 -o "$tmpdir/client"
timeout 10 "$tmpdir/server" "$tmpdir/client"
