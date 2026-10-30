# 0.15.0: same-artifact actual package acceptance

Source `76aeb33dc69365570023c30d3dcf88bdbe9d60af`; version **0.15.0**, x86_64 Linux.
Artifact `source/dist/InkEcho-0.15.0-x86_64.AppImage`, **104425976 bytes**,
SHA256 **94a73232871abaca8c91fb5f58e52059be404f10605955562d39bf31ec64354a**.
The following bounded actual-package cases completed on both Ubuntu systems.
This remains a candidate pending independent review; no tag, publication,
host installation, autostart or stable-entry update was performed.

## Identity and method

The normal-hook version-only source commit changed only three version metadata
files. Exact clean-source workflow passed: **2685 passed, 2 skipped, 99.32s**;
Ruff lint and 424-file formatting checks passed. Receipt is local Git validation
metadata; it proves source checks, not the truth of desktop acceptance.
`frozen-source-identity.json` binds the Git archive. No later working source is
imported. Build ran in its separate frozen source directory using pinned cached
assets. Every actual guest independently verified the identical SHA, version,
**3707 inventory files, 1048 symlinks and 94 application source/assets**.
Modules used the actual FUSE APPDIR/packages, never the earlier R5 source overlay.

Guests ran sequentially under unique Docker names, no external network,
read-only parent mounts, independent RAM write layers and own input/output
shares. The first Ubuntu24 Wayland guest was fully stopped/archived before an
independent previously qualified Ubuntu24 Xorg snapshot; that guest fully stopped
before Ubuntu26. No host seat, user browser, real key or transcript was passed.
Browser fixtures used fresh private profiles, fixed public text, ordinary Chrome154
sandbox and actual Wayland surface/keyboard-enter plus DOM focus evidence.
Renderer seccomp2/no_new_privs1/nested PID metadata was sampled in native cases.
Native Chrome explicitly uses GTK3/IBus, --enable-wayland-ime and text-input-v3;
this is not an unchanged arbitrary user browser configuration.

Browser Session probes persist output_method=ibus-owned with actual ConfigStore,
actual app.Session and a supplied production DefaultAutoOutputRouter. Only the
recorder/provider are synthetic. This does not separately establish constructor-
default router creation during a real output task. Standalone native UI tests
use actual packaged Session/CompatibilityPage/ConfigStore with QtGui synthetic
key events; no physical global hotkey or microphone is claimed.

## Actual session/backend matrix

| Environment | Actual cases and results |
| --- | --- |
| Ubuntu24.04.5/GNOME46 Wayland | AppImage five pages/show-quit IPC/cold controls/damaged-config preservation; HTTP ASR, Qwen realtime/VAD, provider UI and 226 packaged-interpreter provider regressions passed. Explicit-owned native UI, native Chrome textarea/contenteditable, cancellation/current-caret, real GTK libpinyin protection passed. XWayland GTK keyboard pipeline normal22/cancel1 passed. |
| Ubuntu24.04.5/GNOME46 real Xorg, independent snapshot | Actual x11 seat, manager environment and Xorg process confirmed. Same-SHA audit; AppImage GUI/lifecycle; keyboard normal22/cancel1; actual Fcitx auto routing/official Pinyin/preedit guards/normal/partial-cancel/current-caret pipeline and resource cleanup passed. Not an XWayland claim. |
| Ubuntu26.04.1/GNOME50.1 Wayland | Same inventory/UI/local protocol and 226 provider regressions passed. Explicit-owned native UI/Chrome/GTK libpinyin protection passed. Native GTK keyboard and XWayland GTK keyboard each normal22/cancel1/current-caret/no-late/map restoration passed. |
| Ubuntu26.04.1/XFCE4.20 real Xorg | Actual x11 seat/manager environment/Xorg process confirmed. Same-SHA GUI/lifecycle, keyboard normal22/cancel1, actual Fcitx auto/Pinyin/preedit/normal/cancel/current-caret pipeline passed. Actual no-target Fcitx zero-send fallback to keyboard and cancellation passed. This is not GNOME50 Xorg. |

The independent 24 Xorg snapshot is the previously qualified pinyin24 stopped
snapshot, raw SHA af64ba75b695edb5f72b2ffaa42466b5b65eb3dc250b024340d96d6501d89717,
read-only archive pin in `xorg24-followup/parent-snapshot-identity.json`. First
snapshot Xorg focus failure remains separately recorded, not promoted to PASS.

## Explicit-owned observations and boundaries

On **both systems**, native Chrome textarea: normal fixed Chinese/Unicode/LF
22 code points complete; partial cancellation1; pending cancellation0; prepare-
time caret move sends all22 to second field. Contenteditable corresponding
normal22/cancel1/prepare-switch22 passed. Snapshot stability was observed for at
least1.3s. Native UI saved ibus-owned, saved separate old ibus/V2, then saved
ibus-owned again; the regular1000ms refresh showed native-only/no-fallback/
unconfirmed constraints. Source module paths are recorded in results.

Normal Session outcomes remain **unconfirmed**. Exact DOM is independent fixture
observation, never production target acknowledgement. Both systems' direct-router
one-scope native-to-XWayland case received exactly two prefix characters in the
native window, then **ibus_delivery_unknown / attempts2**, zero in XWayland,
zero keyboard presses/releases, no replay/no late input, maps/resources restored.
This proves safe stop of explicit native-only delivery, **not continuous cross-
backend support** or a repair to the older auto owned-route boundary.

Real GTK Wayland libpinyin: guest hardware n/i established preedit “你” before
output; actual owned probe succeeded. Public candidate output was refused with
ibus_delivery_unknown; committed text stayed empty and composition unchanged.
Original input sources and xkb:us::eng were restored. Fixture actor termination
was intentional after the observation, not a spontaneous product crash.

The old ibus enum/legacy factory were retained by an actual empty-input Session
on both systems, with zero dispatch/cancelled outcome. This is configuration
compatibility only: **no successful V2 protocol connection/input was proved**.
Old V5 install/enable were refused with precise upgrade diagnostics while all
seven old files stayed unchanged; new package assets were installed explicitly
only inside guests, after saving old state and normally reloading GNOME.

Ubuntu26 Xorg additional fallback: actual Fcitx no_target/accepted0/uncertainfalse/
unsent_offset0, frontend absent, then keyboard sent the exact15-code-point public
sample. A second actual zero-Fcitx attempt followed by keyboard was cancelled
at one prefix character; no remaining text appeared. Its error attempts field0
is not evidence of zero keyboard delivery: owned DOM/key events show that one
keyboard character. The zero here refers to Fcitx before handoff. This new-SHA
fallback sample was not repeated on24 and is not generalized to24 or other
sessions. Explicit ibus-owned itself never authorizes this fallback.

## Retained failures and fixture qualifications

1. Ubuntu24 ordinary120s network-online boot wait caused two SSH timeouts;
   the same guest was retained, not repeatedly started.
2. Two original24 GUI probes observed page05 existence before its bytes completed
   and reported invalid PNG. Product exited0/rendered5/visibleWayland. All five
   completed PNG streams subsequently passed full CRC/IEND/IDAT validation. A
   private fixture copy waits for five complete CRC/IEND streams within the
   original15s, retaining all original size/show-quit/lifecycle assertions.
   Independent GUI runs then passed. Frozen source and artifact were unchanged.
   See private-gui-readiness-adaptation.json and screenshot-readiness-race-r1.json.
3. Native UI fixture initially imported deliberately trimmed development-only
   QtTest: import failed before any UI/input. Final fixture uses shipped QtGui
   synthetic key events. Initial sub-second status sample preceded the existing
   one-second timer; separate post1.2s sample showed correct explicit constraints.
4. First24 Xorg context command lacked its output directory; retained and fixed
   before package output. Actual Xorg session then lacked usable NET_ACTIVE_WINDOW/
   owned focus; failed before dispatch, no guard relaxation. That snapshot was
   restored/archived and an independent historically qualified Xorg snapshot
   passed every described gate. No product or transport was swapped.
5. First26 Xorg command lacked the common session proof helper, before input.
   The unchanged24 helper was copied; actual XFCE/Xorg proof and gates passed.
6. Both native Chrome pending-cancel runs retained an existing dbus-next
   unhandled-Future BrokenPipe warning. Zero DOM input and cleanup were observed;
   warnings are not hidden or recast as input success.
7. First26 final IBus engine readback failed. Exact old assets/settings had already
   been restored; a subsequent readback with actual manager graphical environment
   succeeded with xkb:us::eng and original xkb source, then normal poweroff. No
   definitive root cause is inferred from these two diagnostic calls.

## Cleanup, reproduction and untested scope

All three QEMU guests normally exited0; exact old extension files/settings,
original input source/engine and original login session were restored where
changed. Package FUSE mounts disappeared; no owned candidate process, capability,
held generated key/modifier, virtual audio module or Fcitx service owner remained;
lock checks were free. Own RAM write layers were losslessly compressed, streamed
back in full and hashed before container exit; raw receipts/final states retained.
No parent disk was modified or removed. No shared source changes after source
freeze and no stable entry change occurred.

Reproduction: decode raw-byte-archive.json entries with gzip/base64 and verify
SHA256/size before use; original-byte whitespace is preserved. Execute recorded
host command JSON and included controllers/launchers in fresh independent guest
directories, sequentially; verify the exact source archive/candidate SHA and
parent chains. Only cases named by actual command/result records were executed;
some inherited helper files are retained for context and are not extra PASS
claims. Frozen source is reproducible from the named commit, not future HEAD.
Framework/test manifests identify the external package-probe dependencies.
external-retained-pins.json names large retained screenshots, disks/source archive
and AppImage; it does not falsely materialize them in this evidence patch.
The patch alone is not a complete operating-system/browser distribution.

Synthetic recording/provider fixtures and public owned controls only. No real
microphone, physical global shortcut/Escape portal, full overlay matrix, host
installation/autostart, live vendor/cloud credentials, DeepSeek website, Codex,
real user browser/profile or arbitrary application matrix was tested. No clipboard.
GNOME46 native keyboard remains unqualified/unsupported; owned native success is
not keyboard success. No GNOME50 Xorg entry was exercised;26 X11 is XFCE. This
round does not remeasure20/40/80ms timing and never treats40ms/draw signals or
producer barriers as receiver acknowledgement. Large texts, load/focus races,
all engines, all cancellation boundaries and every automatic fallback pair were
not exhaustively validated. In-flight delivery cannot be retroactively withdrawn;
uncertain text is never automatically replayed.
