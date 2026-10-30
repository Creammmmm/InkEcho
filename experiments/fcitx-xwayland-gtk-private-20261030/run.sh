set -eu
experiment_dir=$(cd "$(dirname "$0")" && pwd)
repo_dir=$(cd "$experiment_dir/../.." && pwd)
lab_dir=${INKECHO_LAB_DIR:-"$repo_dir/dist/fcitx-xwayland-private-20261030"}
printf '%s  %s\n' f67c6b5f2cb7ecd7c915c8062efd3b70284c74b97ced4a597d942c4b39594e44 "$repo_dir/assets/native/fcitx5/x86_64/libinkecho.so" | sha256sum -c
cd "$lab_dir"
TMPDIR=/var/tmp PKG_CONFIG_PATH="$PWD/root/usr/lib/x86_64-linux-gnu/pkgconfig" PKG_CONFIG_SYSROOT_DIR="$PWD/root" g++ -std=c++20 -fPIC -shared "$experiment_dir/control.cpp" -o "$PWD/libinkecho_test.so" -I"$PWD/root/usr/include/Fcitx5/Module" $(PKG_CONFIG_PATH="$PWD/root/usr/lib/x86_64-linux-gnu/pkgconfig" PKG_CONFIG_SYSROOT_DIR="$PWD/root" pkg-config --cflags --libs Fcitx5Core)
lab_dir=$(mktemp -d /var/tmp/inkecho-weston.XXXXXX)
trap 'rm -rf "$lab_dir"' EXIT
bwrap --info-fd 3 --setenv INKECHO_EXPERIMENT_DIR "$experiment_dir" --setenv INKECHO_REPO_DIR "$repo_dir" --unshare-net --unshare-pid --die-with-parent --setenv INKECHO_FAULT_AFTER_FCITX "${INKECHO_FAULT_AFTER_FCITX:-0}" --ro-bind / / --bind "$lab_dir" /tmp --ro-bind "$PWD/root/usr/libexec" /usr/libexec --dev /dev --proc /proc --chdir "$PWD" /bin/bash -c '
set -eu
mkdir -p /tmp/run /tmp/.X11-unix; chmod 700 /tmp/run; chmod 1777 /tmp/.X11-unix
export HOME=/tmp XDG_RUNTIME_DIR=/tmp/run LIBGL_ALWAYS_SOFTWARE=1
export __EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/50_mesa.json __GLX_VENDOR_LIBRARY_NAME=mesa
unset DBUS_SESSION_BUS_ADDRESS DISPLAY WAYLAND_DISPLAY
export LD_LIBRARY_PATH="$PWD/root/usr/lib/x86_64-linux-gnu:$PWD/root/usr/lib/x86_64-linux-gnu/weston"
export WESTON_MODULE_MAP="headless-backend.so=$PWD/root/usr/lib/x86_64-linux-gnu/libweston-14/headless-backend.so;desktop-shell.so=$PWD/root/usr/lib/x86_64-linux-gnu/weston/desktop-shell.so;xwayland.so=$PWD/root/usr/lib/x86_64-linux-gnu/libweston-14/xwayland.so"
root/usr/bin/weston --backend=headless --renderer=pixman --shell=desktop-shell.so --xwayland --no-config --socket=wayland-test --log=/tmp/weston.log & wp=$!
trap "kill $wp 2>/dev/null || true; wait $wp 2>/dev/null || true" EXIT
sleep 3
cat /tmp/weston.log
ls -la /tmp/.X11-unix
DISPLAY=:0 timeout 8 xprop -root _NET_SUPPORTING_WM_CHECK || true
export DISPLAY=:0 WAYLAND_DISPLAY=wayland-test
export FCITX_DATA_DIRS="$PWD/root/usr/share/fcitx5" FCITX_ADDON_DIRS="$PWD/root/usr/lib/x86_64-linux-gnu/fcitx5" XDG_DATA_HOME=/tmp/data XDG_CONFIG_HOME=/tmp/config
mkdir -p /tmp/data/fcitx5/addon /tmp/data/fcitx5/inkecho
cp "$INKECHO_REPO_DIR/assets/native/fcitx5/x86_64/inkecho.conf" /tmp/data/fcitx5/addon/
cp "$INKECHO_REPO_DIR/assets/native/fcitx5/x86_64/libinkecho.so" /tmp/data/fcitx5/inkecho/
cp "$PWD/libinkecho_test.so" /tmp/data/fcitx5/inkecho/
printf "[Addon]\nName=TestOnly\nCategory=Module\nType=SharedLibrary\nLibrary=libinkecho_test\nVersion=1.0.0\nOnDemand=False\n[Addon/Dependencies]\n0=core:5.1.19\n1=dbus\n" > /tmp/data/fcitx5/addon/inkecho_test.conf
export FCITX_ADDON_DIRS="/tmp/data/fcitx5/inkecho:$FCITX_ADDON_DIRS"
sed "s@<busconfig>@<busconfig><apparmor mode=\"disabled\"/>@" /usr/share/dbus-1/session.conf > /tmp/session.conf
dbus-run-session --config-file=/tmp/session.conf -- bash -c "set -e; root/usr/bin/fcitx5 --disable=clipboard,classicui,notifications,notificationitem,wayland,waylandim -D > /tmp/fcitx.log 2>&1 & fp=\$!; trap \"kill \\\$fp 2>/dev/null || true; wait \\\$fp 2>/dev/null || true\" EXIT; sleep 2; if [ \"\$INKECHO_FAULT_AFTER_FCITX\" = 1 ]; then echo INJECTED_FAILURE_AFTER_FCITX; sleep 3; exit 42; fi; xprop -root XIM_SERVERS; GTK_CSD=0 NO_AT_BRIDGE=1 GIO_USE_VFS=local GTK_IM_MODULE=xim XMODIFIERS=@im=ibus GDK_BACKEND=x11 timeout 10 /usr/bin/python3 $INKECHO_EXPERIMENT_DIR/probe.py clean; GTK_CSD=0 NO_AT_BRIDGE=1 GIO_USE_VFS=local GTK_IM_MODULE=xim XMODIFIERS=@im=ibus GDK_BACKEND=x11 timeout 10 /usr/bin/python3 $INKECHO_EXPERIMENT_DIR/probe.py active; kill \$fp; wait \$fp || true; cat /tmp/fcitx.log"
tail -10 /tmp/weston.log
' 3>"${INKECHO_INFO_PATH:-/dev/null}"
