# Same-artifact session matrix: actual Xorg and Wayland fallback boundaries

2026-10-29. Candidate AppImage0.10.2 SHA-256 `222c017a4f9e10bf4d6422cf402a2b7ea57245adb267a4409cce87ca74551694` remained unchanged. This extends [the earlier gap audit](unconfirmed-candidate-gap-audit.md). That audit's Ubuntu26 Xorg-unverified statement was true at its checkpoint; the new current-API session selection below established actual XFCE Xorg. Earlier failed attempts are preserved. No product edits, rebuild, publication or stable-entry update were performed.

[Machine summary](../experiments/unconfirmed-matrix-20261029/matrix-summary.json) separates successful input from negative safety checks and failed input/cancellation samples. Same candidate source hash `a9f9484618d487cfd0b7b39836ae8bcfe576ee2cfb0fa50bfc6f6481fb988989` was observed from actual packaged app.py in all new sender cases. Frozen source/runtime provenance and required dual-OS local-protocol acceptance remain in the preceding reports, not inferred from this narrower increment.

## Current measured session matrix for this exact SHA

| Actual desktop/session | GUI | Observed successful output | Boundaries |
|---|---|---|---|
| Ubuntu24.04.5/GNOME46/Xorg |Previously passed |Actual keyboard and real-system Fcitx GTK, normal/cancel/switch and zero-send fallback |Original same-SHA report; not rerun here |
| Ubuntu24.04.5/GNOME46/nativeWayland |Previously passed native GUI |Real-system Fcitx GTK200-character continuous switch/cancel in prior same-SHA increment |This new increment proves zero-send fallback cannot output to either native or XWayland simple target: unsupported_compositor,0 characters |
| Ubuntu26.04.1/GNOME50.1/nativeWayland |Previously passed |Actual keyboard/Fcitx GTK and actual nativeChrome local contenteditable via zero-send keyboard fallback |Earlier same-SHA reports; Chrome fixture resource failure retained separately |
| Ubuntu26.04.1/XFCE/Xorg |New actual FUSE GUI pass |New real-system Fcitx GTK200-character switch/cancel and zero-send realX11 keyboard15-character fallback/cancel |This is XFCE Xorg, not GNOME Xorg; GNOME Xorg entry is absent |

This is a scoped matrix of measured paths, not a claim that every input backend, application or specification item works in all four sessions. Physical microphone/cloud, physical hotkeys/F13/F14/Escape portal, overlay nonfocus, installation/path repair/autostart and arbitrary applications remain outside this increment. The complete HTTP/realtime local protocol chain was not rerun in XFCE or Ubuntu24 Wayland; its same-SHA evidence is on Ubuntu24 Xorg and Ubuntu26 GNOME Wayland.

## Ubuntu26 actual XFCE Xorg

A new independent writable overlay over stopped read-only original parent/base/seed was started with KVM/no-new-privileges and no external container network. No original disks or user data were modified. The guest already had xfce.desktop, startxfce4 and Xorg; no desktop installation was needed.

The previous on-disk Session edit and an initial live SetXSession(xfce) did not select XFCE: current AccountsService exposed Session=ubuntu, XSession=xfce and SessionType empty. Actual user-manager/logind/process checks still showed Wayland. Introspection then verified the available SetSession and SetSessionType APIs. Only inside the disposable guest, the following current APIs were called and gdm.service restarted:

```sh
sudo gdbus call --system --dest org.freedesktop.Accounts \
  --object-path /org/freedesktop/Accounts/User1000 \
  --method org.freedesktop.Accounts.User.SetSession xfce
sudo gdbus call --system --dest org.freedesktop.Accounts \
  --object-path /org/freedesktop/Accounts/User1000 \
  --method org.freedesktop.Accounts.User.SetSessionType x11
sudo systemctl restart gdm.service
```

The disposable gdm config had WaylandEnable=false. Actual verification then showed XDG_CURRENT_DESKTOP=XFCE, XDG_SESSION_TYPE=x11, real `/usr/lib/xorg/Xorg` and xfce4-session processes, and logind Type=x11. This closes the earlier launch uncertainty without substituting XWayland or Xvfb.

The actual candidate SHA was checked inside the guest. FUSE app GUI produced5 visiblexcb screenshots and exit0; the help screenshot was visually reviewed and correctly showed Ubuntu26.04.1/XFCE/X11. Raw log `gmatrix-xorg-ui26.log` contains optional Qt host-portal-registration warnings; this GUI check is not a physical shortcut/portal acceptance claim. An immediately subsequent redundant artifact copy hit transient Text file busy while the FUSE helper finished exiting. No input had started. The fixture was changed to reuse the existing artifact and verify its SHA rather than overwrite its inode; the original exit1 was retained, and only the previously unrun input cases were executed.

Real systemFcitx5.1.19 on the actual desktop bus, actual packaged Session/OutputRouter, ownedGTK X11Display targets:

| Case | Receiver | Actual result |
|---|---|---|
| AutoFcitx200 CJK continuous current-focus switch |A33/B167, exact concatenation, B focus confirmed, sender not paused |succeeded; no keyboard fallback |
| Fcitx active cancellation |Only1 character, no late tail |cancelled |
| No compatibleFcitx target |Explicit no_target, accepted0, offset0, uncertainfalse; only then actualX11 keyboard emitted15 exact characters |succeeded |
| Cancellation during keyboard fallback |Only1 character, no late tail |cancelled |

All4 receiver assertions passed. The sender's recorder/transcription fixtures are synthetic and have no real microphone/cloud input. Fcitx clipboard and IBus-emulation frontends were disabled. Before/after user-manager environment and GNOME source settings compared byte-identically, daemonwait0, ownerfalse, no capability,0600 lock proved released and removed. No extra mapping-restoration claim is made from these observers; preceding exact-session keyboard-table evidence is not silently transferred to this XFCE run. Guest shutdown exited0/noOOM/PID0; own overlay was removed only afterward, releasing62722048 bytes.

## Ubuntu24 nativeWayland: zero-send fallback actual behavior

Another fresh sequential24 overlay completed the known120-second network-online wait on the same process; an early SSH banner timeout was retained without restarting. Only this overlay's gdm setting/session was changed to the already verified realWayland setup. System user-manager reported WAYLAND_DISPLAY=wayland-0 and XDG_SESSION_TYPE=wayland. Real systemFcitx5.1.7 ran on its desktop bus. The exact package SHA was checked.

Three owned simple-input GTK targets deliberately did not supply a compatibleFcitx context. The native target used GDK_BACKEND=wayland and was measured GdkWaylandDisplay; the other two used GDK_BACKEND=x11 inside the actualWayland session and were measured X11Display, so these are XWayland targets, not an Xorg session.

| Attempt | Actual product behavior | Test disposition |
|---|---|---|
| Native simple target, full output |Fcitx no_target(accepted0/offset0/uncertainfalse)→Hybridconnect/authorize→unsupported_compositor; Sessionfailed; both targets empty |Negative zero-send safety check passed; input is unsupported |
| XWayland simple target, expected full output |Same unsupported_compositor before keyboard insertion,0 characters |Input sample failed; do not call XWayland fallback supported on this SHA/session |
| XWayland simple target, planned partial cancellation |Same failure before first character,0 characters, cancellation trigger never fired |Input/cancellation sample failed; does not establish partial cancellation here |

The overall runner exited1 because the latter2 expectations failed. These failures are preserved as actual package behavior. The native negative check's passedtrue only means it proved a zero-send failure after a verified emptyFcitx attempt; it is not an output-success assertion. All3 report the same production diagnostic: `unsupported_compositor`, with text explaining GNOME46 lacks the required Unicode keyboard-mapping interface and recommending a separately chosen Xorg session. No keyboard_insert_started event occurred, no text was replayed and no forced compatibility override was used. The optional `input_failure_code` observer was null after task cleanup, so the retained diagnostic event is the authoritative code observation.

This result narrows current behavior: working realFcitx GTK output on Ubuntu24 nativeWayland does not imply the automatic keyboard fallback can succeed there. In this artifact even an active XWayland target did not bypass the native authorization boundary. The observation is not a proof that every possible XWayland implementation is impossible and is not silently fixed by changing desktop variables.

Before/after environment/source comparisons0, daemonwait0, service ownerfalse, no capability,0600 lock released and removed. Source setting remained xkb/us. Guest shutdown exited0/noOOM; only then own overlay was discarded, releasing476385280 bytes. This also removes all disposable session/addon configuration; parent disks remain read-only.

## Reproduction and remaining limits

Exact new fixture source is archived with `.txt` suffix under vm24/input and vm26/input. `matrix-target-focus.py.txt` adds only the explicit native zero-send negative expectation; `matrix-sender.py.txt` adds an error-metadata observer and forwards the existing real transport calls. No product module was overlaid. Each case independently records target text, selectedbackend, no_target status, actual Session outcome and packaged source hash. New raw logs include both failed session selections, current API introspection and corrected actualXorg verification, GUI/copy-race failure, runner outputs and resource cleanup.

Use the existing stopped-parent/read-only/KVM/9p/private-Unix-SSH recipe.26 runs matrix-xorg-gui.sh and matrix-xorg-run.sh after actualXorg verification.24 runs matrix-fallback-run.sh only after actualWayland verification. Avoid overwriting mounted artifacts; reuse only after checking the exact SHA. No cloud credentials, clipboard or user documents are used. Raw GUI PNGs remain local in `/tmp/inkecho-unconfirmed-candidate-20261029/vm26/output/matrix-xorg-ui26`.

No additional samples were run after the platform behavior was established. Both VMs are stopped, own overlays gone, candidate/earlier evidence preserved. These results do not authorize publication, stable-entry replacement or claims about untested user browser versions, DeepSeek actual DOM/network, Qt/terminal/preedit cases, GNOME26 Xorg, physical hardware or all resource-race conditions. Root review and any clean-HEAD verification remain separate.
