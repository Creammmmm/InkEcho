set -eu
export XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus DISPLAY=:0
export XAUTHORITY="$(systemctl --user show-environment | sed -n 's/^XAUTHORITY=//p')"
gsettings set org.gnome.desktop.input-sources xkb-options '[]'
sleep 2
xkbcomp -xkb "$DISPLAY" /tmp/inkecho-xkb-before.xkb 2>/tmp/inkecho-xkb-before.err
gdbus call --session --dest org.example.InkEchoXkbProbe --object-path /org/example/InkEchoXkbProbe --method org.example.InkEchoXkbProbe.Apply
sleep 1
xkbcomp -xkb "$DISPLAY" /tmp/inkecho-xkb-during.xkb 2>/tmp/inkecho-xkb-during.err
gdbus call --session --dest org.example.InkEchoXkbProbe --object-path /org/example/InkEchoXkbProbe --method org.example.InkEchoXkbProbe.Restore
sleep 1
xkbcomp -xkb "$DISPLAY" /tmp/inkecho-xkb-after.xkb 2>/tmp/inkecho-xkb-after.err
sha256sum /tmp/inkecho-xkb-{before,during,after}.xkb
cmp /tmp/inkecho-xkb-before.xkb /tmp/inkecho-xkb-after.xkb && echo XWAYLAND_RESTORE_IDENTICAL
cmp /tmp/inkecho-xkb-before.xkb /tmp/inkecho-xkb-during.xkb || echo XWAYLAND_APPLY_DIFFERS
cp /tmp/inkecho-xkb-{before,during,after}.xkb /mnt/output/runtime/
cp /tmp/inkecho-xkb-{before,during,after}.err /mnt/output/runtime/
