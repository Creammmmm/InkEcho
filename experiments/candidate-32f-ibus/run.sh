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
printf '%s  %s\n' 32f20808a0143d61bf24b2809a11d47344688a7e7edb690684f9e47cfd50bfa5 InkEcho-0.10.2-x86_64.AppImage | sha256sum -c -
chmod +x InkEcho-0.10.2-x86_64.AppImage
./InkEcho-0.10.2-x86_64.AppImage --appimage-extract >/dev/null
sha256sum squashfs-root/packages/inkecho/platform/{ibus.py,output_router.py,ibus_candidate/delivery_gate.js,ibus_candidate/extension.js}
gnome-extensions enable inkecho-ibus-v2-prototype@local.invalid
gnome-extensions enable inkecho-presend-fault@local.invalid
sleep 3
gnome-extensions info inkecho-ibus-v2-prototype@local.invalid
gnome-extensions info inkecho-presend-fault@local.invalid
ibus engine
fault() { gdbus call --session --dest io.github.Creammmmm.InkEcho.PresendFault --object-path /io/github/Creammmmm/InkEcho/PresendFault --method "io.github.Creammmmm.InkEcho.PresendFault1.$@"; }
if [ "$mode" = x11 ]; then xdotool key Escape; fi
printf 'PRESENT_BEFORE=';fault Present
printf 'CASE=normal\n';timeout 65 /usr/bin/python3 probes/target-focus.py full || true
printf 'SET_UNAVAILABLE=';fault 'SetUnavailable' true
printf 'PRESENT_FORCED=';fault Present
printf 'CASE=no_service\n';timeout 65 /usr/bin/python3 probes/target-focus.py full || true
printf 'RESTORE=';fault 'SetUnavailable' false
printf 'PRESENT_AFTER=';fault Present
printf 'CASE=lost_reply\n';INK_LOST=1 timeout 65 /usr/bin/python3 probes/target-focus.py full || true
