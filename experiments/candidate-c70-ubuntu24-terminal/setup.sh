set -eu
cat /etc/os-release | head -3
sudo systemctl mask systemd-networkd-wait-online.service
sudo sed -i 's/^WaylandEnable=false/WaylandEnable=true/' /etc/gdm3/custom.conf
sudo sed -i 's/^Session=ubuntu$/Session=ubuntu-wayland/' /var/lib/AccountsService/users/inkecho
mkdir -p /tmp/share /tmp/product-prepare
sudo mount -t 9p -o trans=virtio,version=9p2000.L,ro inkecho_input /tmp/share
cp /tmp/share/InkEcho-0.10.2-x86_64.AppImage /tmp/product-prepare/
sudo umount /tmp/share
cd /tmp/product-prepare
printf '%s  %s\n' c70d9bb224fbfbc9955a379e43d67df2967a4a0e80731dc4a3247c41a092b65f InkEcho-0.10.2-x86_64.AppImage | sha256sum -c -
chmod +x InkEcho-0.10.2-x86_64.AppImage
./InkEcho-0.10.2-x86_64.AppImage --appimage-extract >/dev/null
mkdir -p "$HOME/.local/share/gnome-shell/extensions/inkecho-ibus-v2-prototype@local.invalid"
cp squashfs-root/packages/inkecho/platform/ibus_candidate/* "$HOME/.local/share/gnome-shell/extensions/inkecho-ibus-v2-prototype@local.invalid/"
sha256sum "$HOME/.local/share/gnome-shell/extensions/inkecho-ibus-v2-prototype@local.invalid/"*
sudo reboot
