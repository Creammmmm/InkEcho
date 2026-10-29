set -eu
export XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus DISPLAY=:0 XDG_SESSION_TYPE=wayland XDG_CURRENT_DESKTOP=ubuntu:GNOME XMODIFIERS=@im=ibus GTK_IM_MODULE=ibus QT_IM_MODULE=ibus GDK_BACKEND=wayland WAYLAND_DISPLAY=wayland-0
export XAUTHORITY="$(systemctl --user show-environment | sed -n 's/^XAUTHORITY=//p')"
pkill -f '[/]tmp/inkecho-browser/chrome/chrome' || true
mkdir -p /tmp/share; sudo mount -t 9p -o trans=virtio,version=9p2000.L,ro inkecho_input /tmp/share; cp /tmp/share/probes/browser-simple.py /tmp/inkecho-r4-test/probes/; sudo umount /tmp/share
systemctl --user show-environment | sed -n '/^XMODIFIERS=/p; /^GTK_IM_MODULE=/p; /^QT_IM_MODULE=/p' >/tmp/inkecho-ibus-oldenv
cleanup() { systemctl --user unset-environment XMODIFIERS GTK_IM_MODULE QT_IM_MODULE || true; while IFS= read -r e; do systemctl --user set-environment "$e" || true; done </tmp/inkecho-ibus-oldenv; pkill -f '[/]tmp/inkecho-browser/chrome/chrome' || true; }
trap cleanup EXIT
systemctl --user set-environment XMODIFIERS=@im=ibus GTK_IM_MODULE=ibus QT_IM_MODULE=ibus
gnome-extensions info inkecho-ibus-v2-prototype@local.invalid
for mode in full cancel switch; do printf 'CASE=%s\n' "$mode"; timeout 55 /usr/bin/python3 /tmp/inkecho-r4-test/probes/browser-simple.py "$mode" || echo fixture_failed; done
