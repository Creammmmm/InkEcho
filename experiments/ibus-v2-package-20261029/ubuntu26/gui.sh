set -eu
umask 077
root=/tmp/inkecho-v2-package-acceptance
mkdir -p "$root" /mnt/output/ui26
cp /mnt/input/InkEcho.AppImage "$root/InkEcho.AppImage"
chmod +x "$root/InkEcho.AppImage"
printf '%s  %s\n' 42118031876729529974e6c20d746638d5d09611f4bb34b4ae189fb4717ada7b "$root/InkEcho.AppImage" | sha256sum -c -
export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus XDG_RUNTIME_DIR=/run/user/1000 DISPLAY=:0
export XAUTHORITY="$(systemctl --user show-environment | sed -n 's/^XAUTHORITY=//p')"
export XDG_SESSION_TYPE=wayland XDG_CURRENT_DESKTOP=ubuntu:GNOME WAYLAND_DISPLAY=wayland-0 QT_QPA_PLATFORM=wayland
loginctl show-session 1 -p Type -p Desktop
"$root/InkEcho.AppImage" --config-dir "$root/config" --data-dir "$root/data" --screenshot-dir /mnt/output/ui26 --quit-after 8 > /mnt/output/gui26.log 2>&1 & pid=$!
for n in $(seq 1 40); do
 if grep -q 'fuse.InkEcho.AppImage' /proc/$pid/mountinfo 2>/dev/null; then grep 'fuse.InkEcho.AppImage' /proc/$pid/mountinfo > /mnt/output/mount26.txt; break; fi
 sleep .1
done
wait "$pid"
printf 'gui_exit=0\n'
