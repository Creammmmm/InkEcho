set -eu
mode=$1
export XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus DISPLAY=:0 XDG_SESSION_TYPE="$mode" XDG_CURRENT_DESKTOP=ubuntu:GNOME GTK_IM_MODULE=ibus XMODIFIERS=@im=ibus QT_IM_MODULE=ibus
if [ "$mode" = wayland ]; then export GDK_BACKEND=wayland WAYLAND_DISPLAY=wayland-0; else export GDK_BACKEND=x11; fi
export XAUTHORITY="$(systemctl --user show-environment | sed -n 's/^XAUTHORITY=//p')"
id=$(loginctl show-user inkecho -p Display --value);loginctl show-session "$id" -p Type -p Active -p LockedHint
[ "$(loginctl show-session "$id" -p Type --value)" = "$mode" ]
mkdir -p /tmp/share /tmp/inkecho-r4-test/probes
sudo mount -t 9p -o trans=virtio,version=9p2000.L,ro inkecho_input /tmp/share
cp /tmp/share/InkEcho-0.10.2-x86_64.AppImage /tmp/inkecho-r4-test/
cp /tmp/share/probes/* /tmp/inkecho-r4-test/probes/
sudo umount /tmp/share
cd /tmp/inkecho-r4-test
printf '%s  %s\n' 81eefc17f810f1a3fd22b911b8109ba1b6921db8bc8adc9abba371371aaa6527 InkEcho-0.10.2-x86_64.AppImage | sha256sum -c -
chmod +x InkEcho-0.10.2-x86_64.AppImage
./InkEcho-0.10.2-x86_64.AppImage --appimage-extract >/dev/null
sha256sum squashfs-root/packages/inkecho/platform/{ibus.py,output_router.py,ibus_candidate/delivery_gate.js,ibus_candidate/extension.js}
gnome-extensions enable inkecho-ibus-v2-prototype@local.invalid
gnome-extensions enable inkecho-presend-fault@local.invalid
sleep 3
gnome-extensions info inkecho-ibus-v2-prototype@local.invalid
gnome-extensions info inkecho-presend-fault@local.invalid
ibus engine
printf 'CASE=polish_fail_ibus\n';INK_PROBE_MODE=ibus timeout 65 /usr/bin/python3 probes/target-focus.py full || true
