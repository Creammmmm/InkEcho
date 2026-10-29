# Actual system Fcitx automatic route — candidate421180, Ubuntu24

2026-10-29. This uses the existing `InkEcho-0.10.2-x86_64.AppImage`, SHA-256
`42118031876729529974e6c20d746638d5d09611f4bb34b4ae189fb4717ada7b`,
without rebuild or source replacement. Candidate location:
`/tmp/inkecho-v2-appimage-candidate-20261029/source/dist/InkEcho-0.10.2-x86_64.AppImage`.
The same candidate's GUI and HTTP/WebSocket/generated-audio keyboard checks are
recorded in [the main candidate report](current-v2-appimage-candidate-validation.md).

## Actual environment and route

Ubuntu24.04.5, GNOME46, X11 in a new independent child qcow2 of a confirmed
stopped parent. Original parent/base mounted readonly; writable data only in
/tmp. Actual desktop session bus `unix:path=/run/user/1000/bus` and system
`/usr/bin/fcitx5` **5.1.7**, not dbus-run-session, a service mock or keyboard stub.
The packaged FcitxInstaller installed and verified the bundled native candidate
in a private user data directory. Only the test daemon used private config/cache;
the actual graphical session's source settings were read unchanged. The three
systemd user-manager framework hints were temporarily set to fcitx, then restored.
Fcitx clipboard and IBus-service-emulation frontends were disabled, so this test
did not read the clipboard or take the preexisting IBus service identity.

Package `collect_system_framework` and `detect_system_framework` both reported
Fcitx with the same verified live unique owner; service executable/UID and live
runtime version checks were performed by the unmodified package collector.
`system-detection.json` records desktop-bus owner evidence; r2 has a new owner
because its separately started actual daemon was new. App source loaded from the
extracted candidate has SHA-256
`8af5a728a16894e7f011388cea5e9607ae4228db0c9d421104acf94d6f3ffc8a`.
The sender used real packaged Session/OutputRouter/Fcitx5Bridge/KeyboardInput;
Recorder and transcription client were synthetic fixtures returning fixed public
text, not microphone/cloud evidence. Observer wrappers recorded original
calls/results; they did not replace sends or detector decisions.

## Results

| Case | Actual result |
|---|---|
| Automatic Fcitx switch, r2 | 200 Chinese characters; owned A25/B175; exact concatenation, both nonempty, B actual focus confirmed, Session succeeded. Sending was **not suspended**: no SIGSTOP/resume. The target's first received character opened/focused its own B window through GTK and xdotool; this is programmatic focus, not a physical user action. Backend fcitx, no keyboard invocation, no bridge error. |
| Automatic Fcitx cancel, r2 | Receiver A exactly one character/B empty; Session cancelled, no tail after delayed observation. Backend fcitx and no keyboard invocation. |
| Simple target/no compatible Fcitx context, r1 corrected helper | Auto first selected real Fcitx; trusted `no_target`, accepted0, unsent_offset0, uncertainfalse arrived before actual KeyboardInput.insert. Only then real keyboard delivered exact15-character `无目标 fallback Ω。`; Session succeeded. The simple text widget was focused: “no target” here means no Fcitx input context, not absence of an editable keyboard destination. |
| Cancel after keyboard fallback, r1 corrected helper | Same zero-accepted/known-unsent handoff, then receiver exactly one character, Session cancelled and no tail. |

The results are in
`experiments/ibus-v2-package-20261029/fcitx-auto-ubuntu24/`.
`fcitx-auto-summary24.json` points to r2 Fcitx and r1 fallback results. The first
Fcitx switch/cancel helper failed in its reporting callback because the added
maps check forgot to import Path, then its timer reported timeout. Original
helper bytes and failure logs are retained. Only that helper import was fixed;
no product was changed. Only the two affected cases were rerun; already passing
fallback cases were not repeated. R2's parser explicitly required both passed.

## Cleanup and limits

Daemon exited0, owner false, system environment and input-source before/after
comparisons both0. Original IBus engine xkb/us was still available. No .cap
remained; the expected0600 persistent lock file was verified unlocked and then
removed by the fixture. Private addon/config/cache and candidate guest directory
were removed. Child VM normal shutdown exited0/noOOM; original backing remained
readonly. Candidate artifact and evidence are retained. No stable entry, shared
worktree, commit, push or release was changed.

This measures this candidate's real system Fcitx automatic route and real keyboard
fallback in these owned GTK X11 controls. It does not establish browser/terminal,
Ubuntu24 nativeWayland, Ubuntu26 Fcitx, non-XKB composition/preedit, concurrent
users/services, malicious same-UID races, unknown/partially accepted fallback,
physical shortcuts/microphone or real cloud. It does not override the separate
IBus `ibus_delivery_unknown` limitation or make an unconfirmed send replayable.
The system hints were temporarily configured for an actual test Fcitx daemon;
this is not a claim about arbitrary preexisting user Fcitx configurations.

## Reproduction

Raw measured Python files are archived as .py.txt; copy back to .py only in a
disposable logged-in Ubuntu24 GNOME X11 guest. Keep the same AppImage SHA and use
`run.sh`/`system-evidence.py.txt`/`sender.py.txt`/`target-focus.py.txt`. `run.sh`
is the final r2 invocation (switch/cancel only), with package extraction, private
addon staging, real desktop collector, actual service and restoration trap.
The already-passing fallback invocation used the same corrected target helper:
set `GTK_IM_MODULE=gtk-im-context-simple`, `INK_TARGET_KIND=fallback`,
`INK_TEST_TEXT='无目标 fallback Ω。'` and `INK_PROBE_MODE=auto`, then run
`target-focus.py full` and `target-focus.py cancel` before daemon cleanup. No
source or binary of the candidate is edited for either route. Do not run these
session-environment changes in a real user desktop.
