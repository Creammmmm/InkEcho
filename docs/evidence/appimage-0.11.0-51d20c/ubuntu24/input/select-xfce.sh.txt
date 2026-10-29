set -eu
umask 077
mkdir -p /mnt/output/xfce-transition
sudo cat /var/lib/AccountsService/users/inkecho > /mnt/output/xfce-transition/accounts-before.ini
sudo gdbus call --system --dest org.freedesktop.Accounts --object-path /org/freedesktop/Accounts/User1000 --method org.freedesktop.Accounts.User.SetSession xfce
sudo gdbus call --system --dest org.freedesktop.Accounts --object-path /org/freedesktop/Accounts/User1000 --method org.freedesktop.Accounts.User.SetSessionType x11
sudo systemctl restart gdm3
