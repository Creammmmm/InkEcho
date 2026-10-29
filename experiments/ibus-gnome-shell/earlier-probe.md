# GNOME Shell / IBus panel probe, 2026-10-28

Ubuntu 26.04.1 virtual guest, GNOME Shell 50.1, Wayland, own GTK3 window, `GTK_IM_MODULE=ibus`. Temporary extension uses existing GNOME Shell panel, not replacing its bus name or changing the engine. Guest was originally configured with xkb/us and no ibus daemon; installed ibus, ibus-gtk3 and ibus-libpinyin in guest, selected libpinyin there. No host desktop or host IBus connection was made.

Initial run failed before sending: Python GI `Gio.DBus.session` raised `AttributeError: 'gi.repository.Gio' object has no attribute 'DBus'`; result contained no commits and both owned entries were empty. The probe was corrected to `Gio.bus_get_sync(Gio.BusType.SESSION, None)`.

Corrected run and cancellation-timer repeat both produced:

```json
{"before_engine":"libpinyin","commits":[["甲",true],["乙",true]],"initial_focus":"a","a_after_first":"甲","second_focus":"b","cancelled_before_third":true,"a":"甲","b":"乙","after_engine":"libpinyin"}
```

The last result removed a locally scheduled third synthetic send before dispatch. It does not test cancellation of a D-Bus request already in flight. Focus switch is between two GTK Entry widgets in the same application window, not across windows; it does not verify browser, CLI, Xorg, Ubuntu 24.04, real engine composition preservation or actual product packaging. PanelService and GNOME Shell `_panelService` are not a stable public GNOME extension API. This was a disposable virtual desktop and does not establish release support.

## Independent delivery-policy prototype

The historical standalone predecessor test printed `delivery gate checks passed`; that predecessor is not shipped. The current candidate has its own reproducible gate tests. This is a standalone, non-exported prototype: an externally authenticated caller and capability begin one exclusive task; commits accept one Unicode scalar with strictly increasing sequence, reject controls, prevent replay, discard on cancellation/owner loss, and stop after an unknown delivery result. `attempted` means only that the panel call returned; it does not claim target receipt. No transcript is logged. Cancel cannot retract a D-Bus message that has already entered the Shell.

This test injects a fake synchronous callback, not GNOME/IBus or InkEcho; it cannot establish delivery or soundness of a real authentication implementation. The callback after Begin must resolve `getIBusManager()._panelService` anew for every send, verify that the panel is live, and never capture a target; its absence must be detected before any send, while an error after an attempt is ambiguous and may not cause fallback. A real extension must verify D-Bus unique sender and carefully provision/revoke a capability over an authenticated channel; same-UID processes are not strongly isolated by 0600 files. There is currently no implemented capability channel or D-Bus production server in this prototype, so it must not be packaged or exposed.

GNOME 46.0 source and current upstream both include the manager and `_panelService` object; 46 was source-inspected only, not tested, and 50.1 was actually tested as above. `_panelService` is private/unstable; GNOME Shell extensions execute inside Shell, so bugs can crash the desktop and version-by-version packaging, install/upgrade/removal, session lock and focus, DBus caller verification and same-UID security must be reviewed. The test code was independently authored under MIT; upstream IBus and GNOME licenses must be reviewed if code is copied rather than using APIs. Preserve the original IM engine and composition, avoid querying surrounding text, and separately test normal text, unicode, control/newline semantics, cross-window focus, target receive/drop, app cancellation during output, Shell/IBus restart and the exact Ubuntu 24.04 and 26.04 packages before support claims.

Guest cleanup: restored `enabled-extensions` to `@as []`, `sources` to `[('xkb','us')]`, selected `xkb:us::eng`, disabled/uninstalled the temporary extension and confirmed its bus name had no owner, deleted temporary files, removed the ten newly installed IBus/pinyin packages, and QMP normal powerdown returned exit status 0. Downloaded apt archive cache and package manager history remain in the disposable guest. The original source list and engine were restored; no claim is made about pre-edit state during the probe.
