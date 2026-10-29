set -eu
cat /etc/os-release | head -3; gnome-shell --version; fcitx5 --version; dpkg-query -W gnome-terminal coreutils bash
id=$(loginctl show-user inkecho -p Display --value);loginctl show-session "$id" -p Type -p Active -p LockedHint
[ "$(loginctl show-session "$id" -p Type --value)" = x11 ]
mkdir -p /tmp/share /tmp/inkecho-r4-test/probes
sudo mount -t 9p -o trans=virtio,version=9p2000.L,ro inkecho_input /tmp/share
cp /tmp/share/InkEcho-0.10.2-x86_64.AppImage /tmp/inkecho-r4-test/; cp /tmp/share/probes/* /tmp/inkecho-r4-test/probes/; sudo umount /tmp/share
cd /tmp/inkecho-r4-test
bash probes/fcitx-run.sh 81eefc17f810f1a3fd22b911b8109ba1b6921db8bc8adc9abba371371aaa6527 x11
