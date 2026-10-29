set -eu
export XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus DISPLAY=:0 XDG_SESSION_TYPE=wayland WAYLAND_DISPLAY=wayland-0 XDG_CURRENT_DESKTOP=ubuntu:GNOME
export XAUTHORITY="$(systemctl --user show-environment | sed -n 's/^XAUTHORITY=//p')"
id=$(loginctl show-user inkecho -p Display --value); loginctl show-session "$id" -p Type -p Active -p LockedHint
[ "$(loginctl show-session "$id" -p Type --value)" = wayland ]; [ "$(loginctl show-session "$id" -p LockedHint --value)" = no ]
mkdir -p /tmp/share /tmp/xwtest /tmp/inkecho-browser/chrome
sudo mount -t 9p -o trans=virtio,version=9p2000.L,ro inkecho_input /tmp/share
cp /tmp/share/{InkEcho.AppImage,sender.py,browser.py} /tmp/xwtest/; sudo umount /tmp/share
sudo mount -t 9p -o trans=virtio,version=9p2000.L,ro chrome_input /tmp/inkecho-browser/chrome
cd /tmp/xwtest
printf '%s  %s\n' 77f252509097fe550188122acbe912783e9ad4b4ea33296fe23a2d64da3729ef InkEcho.AppImage | sha256sum -c -
chmod +x InkEcho.AppImage; ./InkEcho.AppImage --appimage-extract >/dev/null
printf 'Original candidate, no source overlay\n'
gnome-extensions enable inkecho-wayland-focus-probe@local.invalid
for i in $(seq 1 20); do gnome-extensions info inkecho-wayland-focus-probe@local.invalid > /tmp/xw-ext-info; grep -q 'State: ACTIVE' /tmp/xw-ext-info && break; sleep 1; done
cat /tmp/xw-ext-info; grep -q 'State: ACTIVE' /tmp/xw-ext-info
/tmp/inkecho-browser/chrome/chrome --version
for mode in full cancel; do
 echo BROWSER="$mode"
 /usr/bin/python3 browser.py "$mode" || { echo BROWSER_FAILED="$mode"; cat "/tmp/xw-chrome-$mode.log"; }
done
