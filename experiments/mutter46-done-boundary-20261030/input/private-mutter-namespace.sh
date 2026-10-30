#!/bin/sh
set -eu
[ "$(id -u)" = 0 ]
[ "${XDG_RUNTIME_DIR-}" = /run/user/1000 ]
[ "${XDG_SESSION_TYPE-}" = wayland ]
grep -q 'inkecho_output /mnt/output 9p' /proc/mounts
if [ "${1-}" != --inside ]; then
 exec unshare --mount --propagation private -- "$0" --inside
fi
mount --make-rprivate /
mount --bind /mnt/output/mutter-active/lib/x86_64-linux-gnu/mutter-14 /usr/lib/x86_64-linux-gnu/mutter-14
mount -o remount,bind,ro /usr/lib/x86_64-linux-gnu/mutter-14
set --
if [ -n "${XDG_SESSION_ID-}" ]; then set -- "$@" "XDG_SESSION_ID=$XDG_SESSION_ID"; fi
exec setpriv --reuid 1000 --regid 1000 --init-groups --reset-env /usr/bin/env \
 XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus \
 NOTIFY_SOCKET="${NOTIFY_SOCKET-}" XDG_SESSION_TYPE=wayland \
 GNOME_SHELL_SESSION_MODE=ubuntu XDG_CURRENT_DESKTOP=ubuntu:GNOME \
 LD_LIBRARY_PATH=/mnt/output/mutter-active/lib/x86_64-linux-gnu:/mnt/output/mutter-active/lib/x86_64-linux-gnu/mutter-14 \
 GI_TYPELIB_PATH=/mnt/output/mutter-active/lib/x86_64-linux-gnu/mutter-14 \
 "$@" /usr/bin/gnome-shell
