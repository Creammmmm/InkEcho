set -u
export XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus DISPLAY=:0 XDG_SESSION_TYPE=wayland WAYLAND_DISPLAY=wayland-0 XDG_CURRENT_DESKTOP=ubuntu:GNOME
export XAUTHORITY="$(systemctl --user show-environment | sed -n 's/^XAUTHORITY=//p')"
mkdir -p /tmp/share
sudo mount -t 9p -o trans=virtio,version=9p2000.L,ro inkecho_input /tmp/share
rm -f /tmp/xwtest/tty.py; cp /tmp/share/{browser.py,terminal_capture.py} /tmp/xwtest/; sudo umount /tmp/share
cd /tmp/xwtest
GDK_BACKEND=wayland GTK_IM_MODULE=gtk-im-context-simple /usr/bin/python3 /tmp/inkecho-wayland-focus/actor.py wayland >/tmp/xw-native.log 2>&1 & actor=$!
trap 'kill "$actor" 2>/dev/null || true; pkill -f "[g]nome-terminal-server" || true' EXIT
sleep 2
echo BROWSER_SKIPPED_ALREADY_RECORDED
systemctl --user set-environment GDK_BACKEND=x11
pkill -f '[g]nome-terminal-server' || true
rm -f /tmp/xw-terminal-received /tmp/xw-tty-error
sleep 1
gnome-terminal --title='InkEcho isolated terminal' -- /bin/sh -c '/usr/bin/python3 /tmp/xwtest/terminal_capture.py 2>/tmp/xw-tty-stderr'
sleep 4
for file in /tmp/xw-tty-error /tmp/xw-tty-stderr; do test ! -f "$file" || { echo "${file}:"; cat "$file"; }; done
for mode in full cancel switch; do
 gdbus call --session --dest io.github.Creammmmm.InkEcho.WaylandFocusProbe --object-path /io/github/Creammmmm/InkEcho/WaylandFocusProbe --method io.github.Creammmmm.InkEcho.WaylandFocusProbe1.Activate 'InkEcho isolated terminal'
 sleep .5
 echo TERMINAL=$mode
 PYTHONHOME="$PWD/squashfs-root/usr" PYTHONPATH="$PWD/squashfs-root/packages" LD_LIBRARY_PATH="$PWD/squashfs-root/usr/lib/inkecho" "$PWD/squashfs-root/usr/bin/python3" sender.py "$mode"
 sleep .5
 /usr/bin/python3 -c 'import os; p="/tmp/xw-terminal-received"; print("terminal_bytes=",repr(open(p,"rb").read()) if os.path.exists(p) else "FILE_MISSING")'
done
