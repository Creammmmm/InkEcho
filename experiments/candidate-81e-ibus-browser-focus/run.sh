set -eu
export XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus DISPLAY=:0 XDG_SESSION_TYPE=wayland XDG_CURRENT_DESKTOP=ubuntu:GNOME XMODIFIERS=@im=ibus GTK_IM_MODULE=ibus QT_IM_MODULE=ibus GDK_BACKEND=wayland WAYLAND_DISPLAY=wayland-0
export XAUTHORITY="$(systemctl --user show-environment | sed -n 's/^XAUTHORITY=//p')"
mkdir -p /tmp/share /tmp/inkecho-r4-test/probes /tmp/inkecho-browser/chrome
sudo mount -t 9p -o trans=virtio,version=9p2000.L,ro inkecho_input /tmp/share
cp /tmp/share/InkEcho-0.10.2-x86_64.AppImage /tmp/inkecho-r4-test/; cp /tmp/share/probes/* /tmp/inkecho-r4-test/probes/; sudo umount /tmp/share
sudo mount -t 9p -o trans=virtio,version=9p2000.L,ro chrome_input /tmp/inkecho-browser/chrome
/tmp/inkecho-browser/chrome/chrome --version
cd /tmp/inkecho-r4-test
printf '%s  %s\n' 81eefc17f810f1a3fd22b911b8109ba1b6921db8bc8adc9abba371371aaa6527 InkEcho-0.10.2-x86_64.AppImage | sha256sum -c -
chmod +x InkEcho-0.10.2-x86_64.AppImage; ./InkEcho-0.10.2-x86_64.AppImage --appimage-extract >/dev/null
gsettings set org.gnome.shell disable-user-extensions false
gnome-extensions enable inkecho-ibus-v2-prototype@local.invalid
for i in $(seq 1 20); do gnome-extensions info inkecho-ibus-v2-prototype@local.invalid > /tmp/inkecho-ext-info; grep -q 'State: ACTIVE' /tmp/inkecho-ext-info && break; sleep 1; done
cat /tmp/inkecho-ext-info
grep -q 'State: ACTIVE' /tmp/inkecho-ext-info || { echo extension_not_active; exit 1; }
systemctl --user show-environment | sed -n '/^XMODIFIERS=/p; /^GTK_IM_MODULE=/p; /^QT_IM_MODULE=/p' >/tmp/inkecho-ibus-oldenv
cleanup() { systemctl --user unset-environment XMODIFIERS GTK_IM_MODULE QT_IM_MODULE || true; while IFS= read -r e; do systemctl --user set-environment "$e" || true; done </tmp/inkecho-ibus-oldenv; }
trap cleanup EXIT
systemctl --user set-environment XMODIFIERS=@im=ibus GTK_IM_MODULE=ibus QT_IM_MODULE=ibus
for mode in full cancel switch; do printf 'CASE=%s\n' "$mode"; timeout 55 /usr/bin/python3 probes/browser.py "$mode" || echo fixture_failed; done
