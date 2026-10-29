#!/bin/sh
set -eu
root=/tmp/inkecho-fuse-test
printf '%s  %s\n' f6378650f230215a0ff0a7196a80ddc48e9429e2546b55afe40105d8a5889d05 "$root/InkEcho.AppImage" | sha256sum -c -
chmod 700 "$root/InkEcho.AppImage"
mkdir -p "$root/data-home" "$root/cache-home"
export XDG_DATA_HOME="$root/data-home" XDG_CACHE_HOME="$root/cache-home"
unset APPIMAGE_EXTRACT_AND_RUN
"$root/InkEcho.AppImage" --config-dir "$root/config" --data-dir "$root/data" \
  --screenshot-dir "$root/screens" --quit-after 8 > "$root/app.log" 2>&1 &
pid=$!
trap 'kill "$pid" 2>/dev/null || :; wait "$pid" 2>/dev/null || :' EXIT
count=0
while [ "$count" -lt 30 ]; do
  if grep -q '/tmp/.mount_' "/proc/$pid/mountinfo" 2>/dev/null; then break; fi
  kill -0 "$pid" 2>/dev/null || break
  count=$((count+1)); sleep 0.2
done
grep '/tmp/.mount_' "/proc/$pid/mountinfo" > "$root/mountinfo.log" || :
wait "$pid"
code=$?
trap - EXIT
cat "$root/mountinfo.log"
cat "$root/app.log"
test "$code" -eq 0
test -s "$root/mountinfo.log"
