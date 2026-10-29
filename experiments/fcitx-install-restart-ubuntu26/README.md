# Fcitx installation, restart and disable: isolated Ubuntu 26

Ubuntu 26.04 GNOME native Wayland ran in an externally network-isolated KVM container with original and backing disks read-only and a temporary QEMU snapshot. Candidate AppImage SHA-256 `602dab02b4837bb8d30c864dbe50d0413d58d53afb53d9695c7f96f50cdfb756` was verified in the guest; packaged code was not overlaid. The Fcitx process and XDG configuration were private to the test; host user credentials were not mounted. The actual packaged FcitxInstaller, framework collector/detector, and live `RuntimeVersion` endpoint were queried. No characters or surrounding text were read or sent.

`run.log` records four states using consistent Fcitx user-manager hints:

1. Before installation, a Fcitx owner existed but the product detector returned null; `/inkecho` was unavailable.
2. After `install()` but **without** calling `enable()`, detection still returned null and the live endpoint remained unavailable while the original Fcitx process was already running.
3. After terminating that test Fcitx and starting a new instance, still without calling `enable()`, `/inkecho` reported runtime `5.1.19`, and the detector selected the new Fcitx owner `:1.110`. Thus installing publishes a config that a later service start may load; the old UI message saying to manually enable omitted this possibility.
4. After `disable()`, the already loaded `/inkecho` endpoint still reported `5.1.19`, but product auto detection returned null because the published config had been removed. This matches the expected conservative disable behavior; it does not assert instant unload.

`run.stderr` preserves the two expected UnknownObject errors before the plugin was loaded. Exact runner and probe bytes are saved with `.txt` suffix; reproduce with the AppImage in `/tmp/inkecho-r4-test/`, scripts under `probes/` without suffixes, and `bash probes/run.sh 602dab02b4837bb8d30c864dbe50d0413d58d53afb53d9695c7f96f50cdfb756 wayland` in a disposable GNOME session. The runner restores its user-manager hint values, stops the test Fcitx process, and deletes its private profile. QMP system_powerdown was issued; docker wait returned 0 and the temporary container was removed.

This is one controlled service restart, not a real-user change of system input framework, arbitrary daemon crash, runtime text delivery, or complete package acceptance. It establishes the old UI message could mislead; it does not establish a route error. Other session combinations and races remain untested.
