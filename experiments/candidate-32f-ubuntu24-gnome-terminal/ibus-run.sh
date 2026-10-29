set -eu
root=/tmp/inkecho-r4-test
export XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus DISPLAY=:0 XDG_SESSION_TYPE=wayland XDG_CURRENT_DESKTOP=ubuntu:GNOME XMODIFIERS=@im=ibus GTK_IM_MODULE=ibus QT_IM_MODULE=ibus GDK_BACKEND=wayland WAYLAND_DISPLAY=wayland-0
export XAUTHORITY="$(systemctl --user show-environment | sed -n 's/^XAUTHORITY=//p')"
sha256sum "$root/InkEcho-0.10.2-x86_64.AppImage"
gnome-extensions enable inkecho-ibus-v2-prototype@local.invalid
sleep 2
gnome-extensions info inkecho-ibus-v2-prototype@local.invalid
systemctl --user show-environment | sed -n '/^XMODIFIERS=/p; /^GTK_IM_MODULE=/p; /^QT_IM_MODULE=/p' > /tmp/inkecho-ibus-oldenv
cleanup() { systemctl --user unset-environment XMODIFIERS GTK_IM_MODULE QT_IM_MODULE || true; while IFS= read -r entry; do systemctl --user set-environment "$entry" || true; done < /tmp/inkecho-ibus-oldenv; }
trap cleanup EXIT
systemctl --user set-environment XMODIFIERS=@im=ibus GTK_IM_MODULE=ibus QT_IM_MODULE=ibus
pkill -f '[g]nome-terminal-server' || true
sleep 2
timeout 70 /usr/bin/python3 "$root/probes/terminal_driver_ibus.py" full || printf 'ibus_terminal_timeout_or_error\n'
