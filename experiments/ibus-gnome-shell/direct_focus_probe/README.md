# Direct Clutter focus experiment (isolated VM only)

This prototype deliberately removes an event from GNOME Shell's shared Clutter
event queue and examines its text. It is **only** safe to run in a disposable
desktop containing synthetic test input. It can reorder an unrelated event and
must not be installed on a real user desktop or shipped as a product feature.

In an isolated Ubuntu 26.04 GNOME 50 Wayland VM, this test created its own GTK
entry and button. The temporary extension called `Main.inputMethod.commit('甲')`,
retrieved the queued event, checked it was the expected synthetic IM commit,
then called the current `Clutter.InputFocus.process_event()` synchronously.
The extension could then activate the owned button within the same callback.
The local `probe.py` and `preedit.py` are guest-side test scripts, which expect
the extension to be installed and the files copied to `/tmp/inkecho-wayland-focus`.

Without a focus switch, the entry received the synthetic character twice in a
trial. The button had no active input focus and the probe reported no attempt.
An unrelated XWayland comparison window failed to initialize due to Xauthority;
that run does not validate XWayland. In a later native-only trial with a switch
to the button in the same callback, both attempts returned `handled=true` and
activated the button, but the entry was empty after the first and contained only
one character after the second. The tests used two evolving versions of the
probe and extension; exact earlier hashes were not retained, so these results
are exploratory, not package acceptance or a measured failure rate.

For a separate synthetic preedit trial the extension requested preedit `测试`
while the owned entry was active. Before direct commit, the entry's Pango layout
contained the synthetic preedit and its preedit-change signal reported length 2.
After the direct synthetic `甲`, entry text was `甲`, but its layout was
`甲测试` and the last preedit-change length remained 2. This observes synthetic
preedit on an xkb engine, not a real Chinese input engine or its subsequent
composition behavior. The exact files for the final preedit trial had SHA-256:
extension `c40be15b4af5b72eb3077c6fc97c2e2a67f8669c8db2d5c9089078f02d136623`,
actor `04804c54cde7cb1664372b194d96ee587e3f38545acd9fcda8108f1095784bf2`,
preedit script `7b4d1838f1bac1a4ec180384d664c21f3c0d1e299a31e972da1b89463cbb364e`.

This is a counterexample to treating `process_event()`'s true result as target
receipt or assuming synchronous processing prevents loss when focus changes.
It does not test Ubuntu 24.04, the product, actual speech, browsers, terminals,
or non-XKB preedit. Afterward the local extension was disabled and removed,
enabled extensions restored to empty, temporary files removed, and the three
packages installed for the trial were removed. The VM was shut down normally,
with container exit 0. Package-manager history and cache remain in the disposable
guest. No host desktop or user text was accessed.
