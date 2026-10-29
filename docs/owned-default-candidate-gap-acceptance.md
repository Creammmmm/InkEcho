# Same-SHA owned-default candidate: focused acceptance gap closure

2026-10-29. This supplements [the initial actual-package acceptance](owned-default-candidate-package-acceptance.md); it closes only the specifically listed gaps and does not rewrite the initial quota fault, fixture failures or unrelated unverified application matrix.

Artifact remains version 0.10.2, 104401400 bytes, SHA-256 `77f252509097fe550188122acbe912783e9ad4b4ea33296fe23a2d64da3729ef`, preserved at `/tmp/inkecho-owned-default-candidate-20261029/source/dist/InkEcho-0.10.2-x86_64.AppImage`. Neither source, shared working tree, stable entry nor publication was changed. The candidate's own packaged Python/modules are used, without source-module overlays. Packaged app hash remains `98c26bd0a172acd9957f3e5ce4aa8cb54cd923066baaafcae1af03836bca8ca2`; additional production module hashes are recorded in `packaged-module-sha256.json`.

Fresh sequential Ubuntu24 and Ubuntu26 KVM child disks use stopped existing parents/base/seed mounted read-only. No two VMs run concurrently. Each guest checks the same SHA before first extraction. Subsequent scripts reuse that extraction. All tests are own synthetic input in disposable desktops, with actual graphical sessions/system services. No physical microphone, real cloud credentials or user configuration is opened.

## Ubuntu24: enabled V5 with actual system Fcitx

Actual X11 was initially used for the independent keyboard checks below. Then the actual packaged OwnedExtensionManager explicitly installed V5 with strict file verification and unchanged enabled-extension settings. Only the disposable guest was switched through GDM to real GNOME Wayland; the packaged manager explicitly enabled V5 after relogin. Actual installation_state returned enabled.

With that V5 still enabled and real distro Fcitx/native addon installed in the same actual guest user data directory seen by the default Session:

- Continuous automatic Fcitx input follows current focus from target A to B, 56+144=200 exact codepoints. No keyboard insertion occurs.
- Receiver-first-character cancellation keeps exactly one codepoint and no later characters. No keyboard insertion occurs.
- A GTK simple-context receiver provides no Fcitx target. Actual Commit replies report status3; final no_target has accepted=0, offset=0, uncertain=false. The default router fails safely, receiver remains empty and no keyboard fallback is invoked while V5 is enabled.
- Cancellation after the first actual status3 reply uses real Session.cancel, returns cancelled, accepted=0, receiver remains empty, and no keyboard insertion or late text occurs. A pure forwarding D-Bus observer triggers this test action; it does not change replies, router/factories or continuation guards.

These routing cases construct actual Session with synthetic recorder/transcriber and no injected inputs. They are actual package/system-route tests, not real audio/cloud accuracy tests. Input environment/source restoration comparisons are0; Fcitx exits0 and its service owner is false.

The first no-target-cancel attempt used a two-second timer. The actual 0.5-second no-target protection had already completed with failed outcome when that late cancel arrived. Its fixture verdict is FAIL and is preserved under `fcitx-owned-enabled24-gap/guard-cancel.jsonl`; it is not claimed as a successful cancellation. Only that case was rerun with the first-real-zero-reply trigger, under `fcitx-zero-cancel24-r2`, and passed. Other cases were not weakened or replayed.

## Independent actual keyboard monitoring

This replaces the earlier empty-event boolean with nonempty independent receiver observations. The actual default Session constructor selects the production desktop keyboard implementation, with output method explicitly keyboard; synthetic recorder/transcriber keep the sample bounded. A separate distro GTK3 target records each actual key-press/key-release hardware code and keyval without changing delivery. The mixed Unicode sample is nine codepoints: `甲Ωcafé\n乙。`. Its first actual receipt triggers cancellation in the partial case. The sender then remains alive for cleanup; the target waits a further1.3 seconds before its verdict.

| Actual guest/session | Complete sample | First-receipt cancel | Independent state after cleanup |
|---|---|---|---|
| Ubuntu24.04.5 GNOME X11 | exact9 codepoints; press9/release9 | one codepoint; press1/release1 | actual XQueryKeymap before/after has no down keys; receiver still_pressed=[] |
| Ubuntu26.04.1 GNOME native Wayland | exact9 codepoints; press9/release9 | one codepoint; press1/release1 | receiver still_pressed=[]; actual Mutter keymap hash and group/depressed/latched/locked identical before/after, all modifier values0 |

All four samples have no release-without-press and no late text. Mutter snapshot keymap SHA is `e9e6b45d29d38fa1d6a42847b1666d9b94c45160e61516632a326a4f10673ded`. These are independent received-event and actual server/compositor-state checks, not a count of attempted worker calls. Native Wayland exposes modifier state here, not a universal query of every nonmodifier key held anywhere; nonmodifier release proof is scoped to every event observed by the owned receiver. Pre-held user modifiers, Caps/latched transitions, concurrent user typing and arbitrary race schedules were not exercised in these samples.

## Reproduction and cleanup

Preserved base `/tmp/inkecho-owned-default-gap-20261029` contains original input fixtures, full outputs, serial logs, SHA records and summary. Confirm parents and existing own child are stopped before replay. Use `python3 launch-vm.py 24`, `ssh24.sh 'bash -s' < vm24/input/prepare.sh`, then `key-monitor.sh`, `install-owned.sh`, `select-wayland.sh`, `enable-owned.sh`, `fcitx-auto/run-priority-guard.sh`, and `fcitx-auto/run-zero-cancel.sh`. For26, launch only after24 stops, prepare once, then `key-monitor.sh`. The known24 boot SSH timeout is retained; keep the same process rather than relaunching. Input files are mounted read-only; output is a task-owned evidence directory.

Both guests shut down normally; final container states show exited0, PID0, noOOM. Only their stopped unreferenced own child overlays were removed:24 released480382976 bytes;26 released52563968 bytes. No quota fault occurred in this supplemental run. Quota afterward had1395402752 bytes remaining before the small report copy. The AppImage, frozen source and all original records remain.

All other initial limitations remain: no actual Chrome/DeepSeek, Codex/Electron, GTK4/Qt input application matrix, Ubuntu26 Xorg, password field, preedit-block, malformed-installation actual package test, physical microphone, real provider authentication or shortcut/Portal authorization is added by this run. IBus delivery remains unconfirmed; these keyboard/Fcitx samples do not upgrade its acknowledgement contract. No release readiness beyond the measured scope is asserted.
