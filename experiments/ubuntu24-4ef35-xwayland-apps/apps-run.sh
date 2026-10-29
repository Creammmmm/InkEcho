set -eu
export XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus DISPLAY=:0 XDG_SESSION_TYPE=wayland WAYLAND_DISPLAY=wayland-0 XDG_CURRENT_DESKTOP=ubuntu:GNOME
export XAUTHORITY="$(systemctl --user show-environment | sed -n 's/^XAUTHORITY=//p')"
id=$(loginctl show-user inkecho -p Display --value); loginctl show-session "$id" -p Type -p Active -p LockedHint
[ "$(loginctl show-session "$id" -p LockedHint --value)" = no ]
mkdir -p /tmp/share /tmp/inkecho-wayland-focus /tmp/xwtest /tmp/inkecho-browser/chrome
sudo mount -t 9p -o trans=virtio,version=9p2000.L,ro inkecho_input /tmp/share
cp /tmp/share/InkEcho.AppImage /tmp/share/{hybrid_keyboard.py,sender.py,browser.py,tty.py} /tmp/xwtest/
cp /tmp/share/extension/actor.py /tmp/inkecho-wayland-focus/; sudo umount /tmp/share
mountpoint -q /tmp/inkecho-browser/chrome || sudo mount -t 9p -o trans=virtio,version=9p2000.L,ro chrome_input /tmp/inkecho-browser/chrome
cd /tmp/xwtest
printf '%s  %s\n' 4ef35afaf863562a38bd90646cc6d4337d20c22545aa080876ddaab0a5d667e5 InkEcho.AppImage | sha256sum -c -
chmod +x InkEcho.AppImage; ./InkEcho.AppImage --appimage-extract >/dev/null
printf "Original package; no source overlay\n"
gnome-extensions enable inkecho-wayland-focus-probe@local.invalid
for i in $(seq 1 20); do gnome-extensions info inkecho-wayland-focus-probe@local.invalid > /tmp/xw-apps-ext; grep -q 'State: ACTIVE' /tmp/xw-apps-ext && break; sleep 1; done
cat /tmp/xw-apps-ext; grep -q 'State: ACTIVE' /tmp/xw-apps-ext
GDK_BACKEND=wayland GTK_IM_MODULE=gtk-im-context-simple /usr/bin/python3 /tmp/inkecho-wayland-focus/actor.py wayland >/tmp/xw-native.log 2>&1 & actor=$!
cleanup() { kill "$actor" 2>/dev/null || true; pkill -f '[g]nome-terminal-server' || true; }
trap cleanup EXIT
sleep 2
printf 'Chrome version: '; /tmp/inkecho-browser/chrome/chrome --version

printf 'terminal version: '; gnome-terminal --version
systemctl --user set-environment GDK_BACKEND=x11
pkill -f '[g]nome-terminal-server' || true
sleep 1
rm -f /tmp/xw-terminal-received
gnome-terminal --title='InkEcho isolated terminal' -- /usr/bin/python3 /tmp/xwtest/tty.py
sleep 2
for mode in full cancel switch; do
 gdbus call --session --dest io.github.Creammmmm.InkEcho.WaylandFocusProbe --object-path /io/github/Creammmmm/InkEcho/WaylandFocusProbe --method io.github.Creammmmm.InkEcho.WaylandFocusProbe1.Activate 'InkEcho isolated terminal'
 sleep .5
 echo TERMINAL=$mode
 PYTHONHOME="$PWD/squashfs-root/usr" PYTHONPATH="$PWD/squashfs-root/packages" LD_LIBRARY_PATH="$PWD/squashfs-root/usr/lib/inkecho" "$PWD/squashfs-root/usr/bin/python3" sender.py "$mode"
 sleep .5
 /usr/bin/python3 -c 'print("terminal_bytes=",repr(open("/tmp/xw-terminal-received","rb").read()))'
done

for mode in full cancel switch; do echo BROWSER=$mode; /usr/bin/python3 browser.py "$mode" || { echo "BROWSER_FAILED=$mode"; cat "/tmp/xw-chrome-error-$mode.log"; }; done
