# Same-artifact acceptance gap audit and bounded desktop checks

2026-10-29, AppImage0.10.2 SHA-256 `222c017a4f9e10bf4d6422cf402a2b7ea57245adb267a4409cce87ca74551694`,104393208 bytes. This is the existing frozen candidate; no rebuild, publication or stable-entry change occurred. [Original required package subset](unconfirmed-current-candidate-validation.md) and [real-system Fcitx gate](unconfirmed-fcitx-auto-validation.md) remain valid for this exact artifact. Historical different-SHA claims are not inherited.

## Audit against project specification18/24

| Scope | Prior222c evidence | New bounded evidence | Remaining gap |
|---|---|---|---|
| Ubuntu24 GNOME46 X11 |Actual GUI, HTTP/realtime local protocol, GTK keyboard/Fcitx Unicode/current cursor/cancel/cleanup |No repeated successful samples |Physical microphone/hotkeys, real cloud, arbitrary apps and full integration |
| Ubuntu24 GNOME46 nativeWayland |Unverified for222c |Actual nativeWayland GUI and real-system Fcitx GTK continuous switch/cancel |Native keyboard API/unavailable fallback, HTTP/realtime chain in this session, browser/terminal and broad native target coverage |
| Ubuntu26 GNOME50.1 nativeWayland |Actual GUI, HTTP/realtime local protocol, GTK keyboard/Fcitx, cancel/cleanup |Actual Chrome154 local contenteditable full/cancel/continuous switch using verified zero-send native-keyboard fallback |Actual DeepSeek page, user's browser version/profile/IME, physical microphone and cloud |
| Ubuntu26 trueXorg |Unverified |Read actual installed XFCE Xorg entry and attempted selection; no actual Xorg/XFCE process appeared |Still unverified; existing XWayland evidence must not be relabelled Xorg; no GNOME Xorg entry present |

The specification's required same-artifact dual-OS subset was already recorded in the earlier report. These new measurements narrow specific compatibility gaps but do not turn the four-session table into a blanket support promise. Physical Ctrl+F4/F13/F14/Escape portal, nonfocus overlay, desktop install/path repair/autostart, provider UI and authenticated real cloud, non-XKB/preedit and hostile-service cases remain unverified for this SHA.

## Ubuntu24 actual nativeWayland

A fresh independent overlay over stopped Ubuntu24 parent/base/seed, all parents read-only, started with the same KVM/no-new-privileges/isolated-container setup. Initial GDM explicitly had WaylandEnable=false while actual installed entries included ubuntu-wayland.desktop. Only in the disposable overlay, that setting was removed and AccountsService Session selected ubuntu-wayland; guest gdm3 restarted. System user-manager environment reported XDG_SESSION_TYPE=wayland and WAYLAND_DISPLAY=wayland-0. This was a real desktop switch, not an environment-only override.

The exact candidate was SHA checked and launched by FUSE. Five app screenshots, nativewayland, visibletrue, exit0; help screenshot visually inspected and showed Ubuntu24.04.5/GNOME/Wayland. Actual log is `ggap-ui24-wayland.log` (the harmless doubled g is from fixture filename substitution). Raw screenshots remain local `/tmp/inkecho-unconfirmed-candidate-20261029/vm24/output/gap-ui24-wayland/`.

System Fcitx5.1.7 on the real desktop session bus, packaged addon/Session/auto router, owned GTK targets all GdkWaylandDisplay:

- Unpaused continuous200 CJK switch: A60/B140, exact concatenation, B focus confirmed, succeeded, no keyboard fallback.
- Cancellation on first observed receiver input: only1 character, cancelled, no late tail after completion observation.

No native keyboard Unicode success or fallback is claimed for GNOME46. No protocol/microphone test was rerun for this new session; the new Fcitx sender used fixed synthetic provider and recorder responses. Environment and input-source comparisons returned0, daemonwait0, service ownerfalse, no capability,0600 lock proved released by nonblocking flock and removed. Original source stayed xkb/us. Guest exited0/noOOM, then its own overlay was removed, releasing524357632 bytes.

## Actual Chrome on Ubuntu26 nativeWayland

A new sequential overlay used the same artifact and real systemFcitx5.1.19 plus packaged auto router. Existing local browser archive was read-only linked into the fixture input, avoiding another host copy; it was extracted only inside the disposable guest. Browser version was Google Chrome154.0.8037.97. No user browser profile or external site/account was opened. Chrome ran visibly with explicit ozone-platform=wayland and enable-wayland-ime using a fresh temporary profile, localhost HTTP contenteditable controls, and no headless flag. The old fixture no-sandbox flag was retained only inside this disposable guest; it is not an application recommendation or a supported browser configuration claim.

The actual package app.py origin/hash matched SHA `a9f9484618d487cfd0b7b39836ae8bcfe576ee2cfb0fa50bfc6f6481fb988989`. In all3 samples, auto selected realFcitx first; it reported no_target, accepted0, unsent_offset0, uncertainfalse. Only then did the real Hybrid keyboard path emit through nativeWayland `_insert_prefix`. These are successful keyboard fallback cases, not claims that native Chrome accepts direct Fcitx commits.

| Chrome local contenteditable case | Independent DOM result | Actual Session |
|---|---|---|
| Full200-character output |A200/B0, exact |succeeded |
| Cancel on first received character |A1/B0, exact prefix and no tail after final observation |cancelled |
| Continuous current-focus switch |A4/B196, concatenation exact, B focused; sender never stopped/resumed |succeeded |

The local page focuses only its own newly created editable field on its own window-focus event. After first input it opens the second owned page; later characters naturally go there. The previous stopped-sender variant was removed for this run. Content/focus observations come from this owned page's HTTP events, not arbitrary surrounding text or a clipboard. The sender waits through completion and the browser fixture observes another1second before the final result. This exercises real Chrome contenteditable behavior, not actual DeepSeek DOM/network integration or the user's installed version/configuration.

## Resource failure retained and cleanup recovered

All3 browser input samples independently returned passedtrue. The aggregate runner then failed while writing passed-checks/cleanup via9p, with OSError24/Too many open files; its overall exit1 remains a failure, not silently relabelled a clean whole-run pass. SSH also timed out. Read-only inspection of the dedicated QEMU found softnofile1024, hard524288 and exactly1024 fds. Only this test process's softlimit was raised to8192 using prlimit; SSH/9p recovered immediately. No successful input sample was rerun.

A separate cleanup command restored the saved user-manager environment, verified environment/source byte comparisons0, confirmed noFcitx process and NameHasOwnerfalse, and checked no capability plus released0600 lock. The original daemon-wait exit was not recorded because that write failed, so no exit0 is asserted for the Chrome fixture daemon. The package input cancellation outcomes and exact receiver observations remain distinct from this infrastructure failure. No product code was modified to raise resource limits. This is a test VM/QEMU9p descriptor limit diagnosis, not a product descriptor-leak exclusion.

## Ubuntu26 Xorg availability check and stop boundary

The guest had `/usr/share/xsessions/xfce.desktop` with Exec=startxfce4 and existing startxfce4/Xorg executables; GNOME had only Wayland entries. Selecting Session=xfce in the disposable AccountsService file and restarting gdm3 did not establish Xorg: the user environment still showed GNOME/Wayland and actual logind listed only a Wayland desktop; noXorg/xfce4-session process was observed. A second actual-session check prevented stale user-manager metadata from being counted as X11. No extra desktop installation, repeated configuration research or forcedXvfb substitution followed. This session remains unverified.

Final service ownerfalse, noFcitx or Chrome process/capability was listed. Guest shut down normally exited0/noOOM; its own overlay was removed, releasing58986496 bytes. The previous separate engine-identity CLI failures remain in the earlier report; no new engine-identity restoration claim follows. Original parent disks and user config were never written.

## Evidence and reproduction

[Summary](../experiments/unconfirmed-gap-20261029/gap-summary.json) retains route/outcome events and independent counts. Exact new fixture scripts are archived with `.txt` suffix under vm24/input and vm26/input. Raw result/cleanup/session logs are under the matching output directories. Existing package/Fcitx fixture source is bound by the preceding report; this increment includes only new scripts and results. `gap-browser.py.txt` shows local DOM contenteditable, current-focus handling, no paused sender and exact assertions.

Use the preceding independent-VM recipe with stopped parents and a fresh overlay.24 selects the already installed Wayland entry only in that overlay, then runs gap-gui.sh and gap-fcitx-run.sh.26 runs gap-browser-run.sh in its actualWayland desktop; after the retained9p failure, gap-recover-cleanup.sh independently captures restoration. The26 Xorg attempted selection and actual-session observations are retained in gap-xfce-* logs. Both actual AppImages check the exact SHA before use. No cloud keys, clipboard, user documents or real browser account were accessed.

No source-tree files were edited by this task. New candidate support claims require root review and remain bounded as above; no release, stable alias, commit or push was performed.
