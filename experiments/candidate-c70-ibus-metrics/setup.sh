set -eu
export XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus DISPLAY=:0
mkdir -p /tmp/share /tmp/inkecho-r4-test
sudo mount -t 9p -o trans=virtio,version=9p2000.L,ro inkecho_input /tmp/share
cp /tmp/share/InkEcho-0.10.2-x86_64.AppImage /tmp/inkecho-r4-test/
cd /tmp/inkecho-r4-test
printf '%s  %s\n' c70d9bb224fbfbc9955a379e43d67df2967a4a0e80731dc4a3247c41a092b65f InkEcho-0.10.2-x86_64.AppImage | sha256sum -c -
chmod +x InkEcho-0.10.2-x86_64.AppImage
./InkEcho-0.10.2-x86_64.AppImage --appimage-extract >/dev/null
mkdir -p "$HOME/.local/share/gnome-shell/extensions/inkecho-ibus-v2-prototype@local.invalid" "$HOME/.local/share/gnome-shell/extensions/inkecho-presend-fault@local.invalid"
cp squashfs-root/packages/inkecho/platform/ibus_candidate/* "$HOME/.local/share/gnome-shell/extensions/inkecho-ibus-v2-prototype@local.invalid/"
cp /tmp/share/fault/* "$HOME/.local/share/gnome-shell/extensions/inkecho-presend-fault@local.invalid/"
sha256sum squashfs-root/packages/inkecho/platform/ibus_candidate/* "$HOME/.local/share/gnome-shell/extensions/inkecho-ibus-v2-prototype@local.invalid/"* /tmp/share/fault/*
sudo umount /tmp/share
gsettings set org.gnome.shell disable-user-extensions false
sudo systemctl mask systemd-networkd-wait-online.service
sudo reboot
