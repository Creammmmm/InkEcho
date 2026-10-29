set -eu
export XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus DISPLAY=:0 XDG_SESSION_TYPE=wayland WAYLAND_DISPLAY=wayland-0 XDG_CURRENT_DESKTOP=ubuntu:GNOME
export XAUTHORITY="$(systemctl --user show-environment | sed -n 's/^XAUTHORITY=//p')"
id=$(loginctl show-user inkecho -p Display --value); loginctl show-session "$id" -p Type -p Active -p LockedHint
[ "$(loginctl show-session "$id" -p LockedHint --value)" = no ]
mkdir -p /tmp/share /tmp/inkecho-wayland-focus /tmp/xwtest
sudo mount -t 9p -o trans=virtio,version=9p2000.L,ro inkecho_input /tmp/share
cp /tmp/share/InkEcho.AppImage /tmp/xwtest/; cp /tmp/share/extension/actor.py /tmp/inkecho-wayland-focus/; cp /tmp/share/observer.py /tmp/xwtest/; sudo umount /tmp/share
cd /tmp/xwtest
printf '%s  %s\n' 222c017a4f9e10bf4d6422cf402a2b7ea57245adb267a4409cce87ca74551694 InkEcho.AppImage | sha256sum -c -
chmod +x InkEcho.AppImage; ./InkEcho.AppImage --appimage-extract >/dev/null
gnome-extensions enable inkecho-wayland-focus-probe@local.invalid
for i in $(seq 1 20); do gnome-extensions info inkecho-wayland-focus-probe@local.invalid > /tmp/xw-extension-info; grep -q 'State: ACTIVE' /tmp/xw-extension-info && break; sleep 1; done
cat /tmp/xw-extension-info; grep -q 'State: ACTIVE' /tmp/xw-extension-info
GDK_BACKEND=x11 GTK_IM_MODULE=gtk-im-context-simple /usr/bin/python3 /tmp/inkecho-wayland-focus/actor.py simple > /tmp/xw-simple.log 2>&1 & a=$!
GDK_BACKEND=wayland GTK_IM_MODULE=gtk-im-context-simple /usr/bin/python3 /tmp/inkecho-wayland-focus/actor.py wayland > /tmp/xw-wayland.log 2>&1 & b=$!
cleanup() { kill "$a" "$b" 2>/dev/null || true; wait "$a" "$b" 2>/dev/null || true; }
trap cleanup EXIT
sleep 3
for name in simple wayland simple wayland; do
 printf 'ACTIVATE=%s\n' "$name"
 gdbus call --session --dest io.github.Creammmmm.InkEcho.WaylandFocusProbe --object-path /io/github/Creammmmm/InkEcho/WaylandFocusProbe --method io.github.Creammmmm.InkEcho.WaylandFocusProbe1.Activate "InkEcho isolated $name"
 sleep 0.5
 gdbus call --session --dest io.github.Creammmmm.InkEcho.WaylandFocusProbe --object-path /io/github/Creammmmm/InkEcho/WaylandFocusProbe --method io.github.Creammmmm.InkEcho.WaylandFocusProbe1.Read
 PYTHONHOME="$PWD/squashfs-root/usr" PYTHONPATH="$PWD/squashfs-root/packages" LD_LIBRARY_PATH="$PWD/squashfs-root/usr/lib/inkecho" "$PWD/squashfs-root/usr/bin/python3" observer.py
done
