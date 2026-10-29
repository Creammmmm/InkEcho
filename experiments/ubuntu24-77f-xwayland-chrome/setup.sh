set -eu
export XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus DISPLAY=:0
sudo systemctl mask systemd-networkd-wait-online.service
sudo sed -i 's/^WaylandEnable=false/WaylandEnable=true/' /etc/gdm3/custom.conf
sudo sed -i 's/^Session=ubuntu$/Session=ubuntu-wayland/' /var/lib/AccountsService/users/inkecho
mkdir -p /tmp/share "$HOME/.local/share/gnome-shell/extensions/inkecho-wayland-focus-probe@local.invalid"
sudo mount -t 9p -o trans=virtio,version=9p2000.L,ro inkecho_input /tmp/share
cp /tmp/share/extension/{extension.js,metadata.json} "$HOME/.local/share/gnome-shell/extensions/inkecho-wayland-focus-probe@local.invalid/"
sudo umount /tmp/share
gsettings set org.gnome.shell disable-user-extensions false
gsettings set org.gnome.desktop.session idle-delay 0
gsettings set org.gnome.desktop.screensaver lock-enabled false
sudo reboot
