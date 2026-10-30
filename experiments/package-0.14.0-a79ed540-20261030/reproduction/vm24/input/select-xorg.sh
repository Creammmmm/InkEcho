set -eu
umask 077
mkdir -p /mnt/output/xorg-transition-r2
sudo cat /etc/gdm3/custom.conf > /mnt/output/xorg-transition-r2/gdm-before.conf
sudo cat /var/lib/AccountsService/users/inkecho > /mnt/output/xorg-transition-r2/accounts-before.ini
test -f /usr/share/xsessions/ubuntu-xorg.desktop
sudo sed -i '/^\[daemon\]/a WaylandEnable=false' /etc/gdm3/custom.conf
sudo gdbus call --system --dest org.freedesktop.Accounts --object-path /org/freedesktop/Accounts/User1000 --method org.freedesktop.Accounts.User.SetSession ubuntu-xorg
sudo gdbus call --system --dest org.freedesktop.Accounts --object-path /org/freedesktop/Accounts/User1000 --method org.freedesktop.Accounts.User.SetSessionType x11
sudo systemctl restart gdm3
