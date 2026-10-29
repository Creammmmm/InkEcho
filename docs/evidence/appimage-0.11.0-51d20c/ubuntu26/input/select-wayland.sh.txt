set -eu
umask 077
export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus XDG_RUNTIME_DIR=/run/user/1000
mkdir -p /mnt/output/wayland-transition
sudo cat /etc/gdm3/custom.conf > /mnt/output/wayland-transition/gdm-before.conf
sudo cat /var/lib/AccountsService/users/inkecho > /mnt/output/wayland-transition/accounts-before.ini
sudo sed -i '/^[[:space:]]*WaylandEnable=false/d' /etc/gdm3/custom.conf
sudo gdbus call --system --dest org.freedesktop.Accounts --object-path /org/freedesktop/Accounts/User1000 --method org.freedesktop.Accounts.User.SetSession ubuntu-wayland
sudo gdbus call --system --dest org.freedesktop.Accounts --object-path /org/freedesktop/Accounts/User1000 --method org.freedesktop.Accounts.User.SetSessionType wayland
sudo systemctl restart gdm3
