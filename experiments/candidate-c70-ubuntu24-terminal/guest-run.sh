set -eu
cat /etc/os-release | head -3
gnome-shell --version
fcitx5 --version
dpkg-query -W gnome-terminal
id=$(loginctl show-user inkecho -p Display --value)
loginctl show-session "$id" -p Type -p Active -p LockedHint
[ "$(loginctl show-session "$id" -p Type --value)" = wayland ]
[ "$(loginctl show-session "$id" -p Active --value)" = yes ]
[ "$(loginctl show-session "$id" -p LockedHint --value)" = no ]
mkdir -p /tmp/term-share /tmp/inkecho-r4-test/probes
sudo mount -t 9p -o trans=virtio,version=9p2000.L,ro inkecho_input /tmp/term-share
cp /tmp/term-share/InkEcho-0.10.2-x86_64.AppImage /tmp/inkecho-r4-test/
cp /tmp/term-share/probes/* /tmp/inkecho-r4-test/probes/
sudo umount /tmp/term-share
cd /tmp/inkecho-r4-test
bash probes/run.sh c70d9bb224fbfbc9955a379e43d67df2967a4a0e80731dc4a3247c41a092b65f wayland
