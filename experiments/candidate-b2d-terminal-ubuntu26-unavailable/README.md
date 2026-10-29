# Candidate b2d: Ubuntu 26 GNOME Terminal unavailable

An externally network-isolated Ubuntu 26.04.1 QEMU snapshot used read-only original disk/base/seed and input share; the real GNOME session was Wayland, active and unlocked (`inventory.log`). The exact candidate AppImage visible in the guest had SHA-256 `b2d47dee9295dadbbbff644e0f9553875ef7ac8971a97c56eec7de68d603c5d2` (`package-hash.log`). The host desktop, real user data, credentials, input method and clipboard were not accessed; the test SSH key stayed on the host.

The guest had no `gnome-terminal` executable or installed package and no matching `.deb` in its apt cache (`inventory.log`). `alternatives.log` records read-only checks of other common terminal executables and the offline package-cache listing; none of the checked terminal executables was found. The guest had no external network. Therefore no GNOME Terminal input, cancellation or focus test was run. The candidate was not launched, and no IBus or Fcitx service was started for this check. This cannot be counted as package acceptance or evidence of failure/success on an Ubuntu 26 installation that does have GNOME Terminal.

To reproduce the inventory only, provision an equivalent isolated guest, confirm its graphical session with `loginctl`, check `command -v gnome-terminal`, `dpkg-query -W gnome-terminal`, and look for matching files under `/var/cache/apt/archives`; independently verify the AppImage SHA. This record is an environment limitation, not an application compatibility claim.

The guest powered off normally, Docker wait returned 0 and the container was removed (`shutdown.log`).
