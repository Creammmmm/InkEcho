# GNOME input focus object identity experiment

The preliminary Ubuntu 26.04 GNOME Wayland trial installed a temporary local
extension and created two owned GTK entry windows. The extension retained the
Shell's current `ClutterInputFocus` reference from the first activation and
compared it after activation requests for the second and first windows. No text
was entered or read. It reported the same focus object and same Shell IBus
context path both times, but **the preliminary extension returned success when
it requested activation without independently reporting the active window**.
Consequently, actual focus transfer was not proven and these observations do
not prove object reuse. The exact preliminary input archive remains in ignored
`build/focus-object-evidence/first-run.tar`, SHA-256
`96aad3177bfeeedbfd404cb4bcf0007d0a2e0477dcb6477ba9a6b5ff5ffcbcfc`.

The extension and probe were subsequently amended to return and assert active
window titles only for the two synthetic windows. On a fresh Ubuntu 26.04 GNOME
Wayland VM run, the first attempt failed before making a comparison: the local
extension was INITIALIZED but not yet enabled, so its D-Bus service was absent.
After explicitly enabling it in the isolated guest, the repeat exited 0. The
active titles were confirmed in order `one`, `two`, `one`. In all three cases
the Shell input focus object had the same identity and the Shell IBus context
path was the same. This establishes object/path reuse for these two windows in
that tested session; it does not confirm delivery, remove the existing queue
race, or establish other desktops or Ubuntu 24.04. No production code uses this
probe.

The amended trial archive is retained in ignored
`build/focus-object-evidence/second-run.tar`, SHA-256
`7ed02adbc434b49dcb8ba75b198453756059328f4a6230e8a127eb7192627bc8`.
Its extension, probe, actor, and metadata SHA-256 values were respectively
`d43970fd0588242d8969cb603ade2e6dee99ee3c0163c706c4554e84db0e62e5`,
`c3e20b7d7ff8ae1478dcb8d89761405474181edae0e680e511d117224c77ca38`,
`2cd60ba3e8e5fb9b9208176565a3c0241fc7416a89254374644f9a83873d6582`, and
`2d16bb51aff9aba1e2f88ee160e4e17eeadf6b7f411ac6a7fa9d2cee13010e35`.

After the preliminary trial, the extension was disabled and removed, enabled
extensions restored to empty, temporary guest files removed, and the three IBus
test packages removed. The virtual machine was then handed to the other test
agent while running. Following the amended trial, the extension was again
disabled and removed, enabled extensions verified empty, temporary files and
the same three packages removed, and the guest shut down normally with container
exit 0. Package history and cache remain in the disposable guest. The host user
session and text were not accessed.
