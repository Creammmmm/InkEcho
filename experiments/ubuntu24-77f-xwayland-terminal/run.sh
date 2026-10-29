set -eu
export XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus DISPLAY=:0 XDG_SESSION_TYPE=wayland WAYLAND_DISPLAY=wayland-0 XDG_CURRENT_DESKTOP=ubuntu:GNOME
export XAUTHORITY="$(systemctl --user show-environment | sed -n 's/^XAUTHORITY=//p')"
id=$(loginctl show-user inkecho -p Display --value); loginctl show-session "$id" -p Type -p Active -p LockedHint
[ "$(loginctl show-session "$id" -p Type --value)" = wayland ]
[ "$(loginctl show-session "$id" -p LockedHint --value)" = no ]
mkdir -p /tmp/share /tmp/xwtest
sudo mount -t 9p -o trans=virtio,version=9p2000.L,ro inkecho_input /tmp/share
cp /tmp/share/{InkEcho.AppImage,sender.py,terminal_capture.py,observer.py} /tmp/xwtest/
sudo umount /tmp/share
cd /tmp/xwtest
printf '%s  %s\n' 77f252509097fe550188122acbe912783e9ad4b4ea33296fe23a2d64da3729ef InkEcho.AppImage | sha256sum -c -
chmod +x InkEcho.AppImage; ./InkEcho.AppImage --appimage-extract >/dev/null
printf 'Original candidate, no source overlay\n'
gnome-extensions enable inkecho-wayland-focus-probe@local.invalid
for i in $(seq 1 20); do gnome-extensions info inkecho-wayland-focus-probe@local.invalid > /tmp/xw-ext-info; grep -q 'State: ACTIVE' /tmp/xw-ext-info && break; sleep 1; done
cat /tmp/xw-ext-info; grep -q 'State: ACTIVE' /tmp/xw-ext-info
gnome-terminal --version
systemctl --user set-environment GDK_BACKEND=x11 DISPLAY=:0 XAUTHORITY="$XAUTHORITY"
pkill -f '[g]nome-terminal-server' || true
rm -f /tmp/xw-terminal-received /tmp/xw-tty-error /tmp/xw-tty-stderr
sleep 1
gnome-terminal --title='InkEcho isolated terminal' -- /bin/sh -c '/usr/bin/python3 /tmp/xwtest/terminal_capture.py 2>/tmp/xw-tty-stderr'
trap 'pkill -f "[g]nome-terminal-server" || true' EXIT
for i in $(seq 1 25); do test -e /tmp/xw-terminal-received && break; sleep .2; done
for file in /tmp/xw-tty-error /tmp/xw-tty-stderr; do test ! -f "$file" || { echo "${file}:"; cat "$file"; }; done
if [ ! -e /tmp/xw-terminal-received ]; then echo RECEIVER_START_FAILED; exit 1; fi
for mode in full cancel; do
 echo ACTIVATE
 gdbus call --session --dest io.github.Creammmmm.InkEcho.WaylandFocusProbe --object-path /io/github/Creammmmm/InkEcho/WaylandFocusProbe --method io.github.Creammmmm.InkEcho.WaylandFocusProbe1.Activate 'InkEcho isolated terminal'
 sleep .5
 gdbus call --session --dest io.github.Creammmmm.InkEcho.WaylandFocusProbe --object-path /io/github/Creammmmm/InkEcho/WaylandFocusProbe --method io.github.Creammmmm.InkEcho.WaylandFocusProbe1.Read
 PYTHONHOME="$PWD/squashfs-root/usr" PYTHONPATH="$PWD/squashfs-root/packages" LD_LIBRARY_PATH="$PWD/squashfs-root/usr/lib/inkecho" "$PWD/squashfs-root/usr/bin/python3" observer.py
 echo TERMINAL=$mode
 PYTHONHOME="$PWD/squashfs-root/usr" PYTHONPATH="$PWD/squashfs-root/packages" LD_LIBRARY_PATH="$PWD/squashfs-root/usr/lib/inkecho" "$PWD/squashfs-root/usr/bin/python3" sender.py "$mode"
 sleep .5
 /usr/bin/python3 -c 'print("terminal_bytes=",repr(open("/tmp/xw-terminal-received","rb").read()))'
done
