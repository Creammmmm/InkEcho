# Ubuntu 24.04 GNOME Wayland EIS diagnostic (2026-10-28)

This is an isolated desktop experiment, not package acceptance or a claim of
production support. A keyboard-only RemoteDesktop portal request was approved
through the standard dialog's Allow Remote Interaction checkbox and Share
button. No clipboard or system input method was used. The only injected key was
ASCII `b`, sent to the test-owned GTK3 Wayland editor after verifying its PID.

The candidate runtime was `InkEcho-0.10.2-x86_64.AppImage`, SHA-256
`e4f2c6de3450cd997607baaeba41dd1764f8365c0bda73d9b9dd7c4ac395db54`.
It supplies Python, libei and the app's EIS observer; this is not a package test.

* `eis_probe.py.txt` SHA-256 `06c97cf4b323775e7bb2e2a860904ae9c5398026f7a068454b1e90c1968bd009`:
  authorization and ConnectToEIS succeeded, but the observer timed out waiting
  for modifier state (`wayland24-r6-portal.log`). No key was sent.
* `eis_probe_r2.py.txt` SHA-256 `b3177fc7fb368759b60578cde00e142f439c5bfabfffcf09ed41d2523db950c2`:
  after the same timeout it inspected the resumed device's keymap. Scanning
  all 9–708 XKB keycodes, groups and levels found `b` at keycode 56, but no
  `中` or `😀`. Sending `b` via libei reached the test editor as `b`.
  The two Unicode samples were **not sent**: an absent mapping is evidence
  about this keymap, not a negative injection test of arbitrary Unicode.
  The script then raised a `TypeError` during cleanup and exited 1; its cause
  was not captured. Thus the run must not be represented as a full pass.
* `keymap.xkb` SHA-256 `7f05616da2b8268871bb8b0a45fce919615a260e8bd307016db9e217514fcfe3`
  is the observer's canonicalized copy of the server keymap (one terminating
  NUL), 68,405 bytes. No inference is made for other layouts or compositors.

To reproduce, copy the `.py.txt` files to a private test directory with `.py`
extensions, expand the candidate AppImage there, run the probe using its
bundled Python with `PYTHONHOME`, `PYTHONPATH` and `LD_LIBRARY_PATH` pointing to
its `usr`, `packages`, and `usr/lib/inkecho`; set the test user's Wayland and
D-Bus session variables. When `waiting_for_standard_keyboard_consent` appears,
use `portal_ui_action.py` to activate the exact checkbox and button above in
that isolated session. The retained portal and action logs contain the command
and result. A new standard authorization is needed for each probe. The editor
and accessibility fixture copies are the actual tested inputs.

Before changing the isolated VM, GDM and the account session files were backed
up. After testing, both were copied back and compared byte-for-byte, and the
private guest test directory was removed (`wayland24-r6-restore.log`). A normal
QMP powerdown was requested. No real user desktop was operated.
