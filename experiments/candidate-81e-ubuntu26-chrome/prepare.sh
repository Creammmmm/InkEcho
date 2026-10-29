set -eu
mkdir -p /tmp/share /tmp/inkecho-r4-test/probes /tmp/inkecho-browser/chrome
sudo mount -t 9p -o trans=virtio,version=9p2000.L,ro inkecho_input /tmp/share
cp /tmp/share/InkEcho-0.10.2-x86_64.AppImage /tmp/inkecho-r4-test/; cp /tmp/share/probes/* /tmp/inkecho-r4-test/probes/; sudo umount /tmp/share
sudo mount -t 9p -o trans=virtio,version=9p2000.L,ro chrome_input /tmp/inkecho-browser/chrome
/tmp/inkecho-browser/chrome/chrome --version
cd /tmp/inkecho-r4-test
printf '%s  %s\n' 81eefc17f810f1a3fd22b911b8109ba1b6921db8bc8adc9abba371371aaa6527 InkEcho-0.10.2-x86_64.AppImage | sha256sum -c -
chmod +x InkEcho-0.10.2-x86_64.AppImage
./InkEcho-0.10.2-x86_64.AppImage --appimage-extract >/dev/null
sha256sum squashfs-root/packages/inkecho/platform/{output_router.py,ibus.py,fcitx5.py}
bash probes/browser-run.sh 81eefc17f810f1a3fd22b911b8109ba1b6921db8bc8adc9abba371371aaa6527 wayland
