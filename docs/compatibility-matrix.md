# Compatibility matrix

Updated: 2026-10-16. **Pending is not supported.** Evidence is specific to
version, host/guest session, target and workflow. A passed keyboard fixture
is not full voice-input or desktop support. No current path uses clipboard
or system input-method submission, including as a fallback.

## Current a13 Noble actual-package and R8 source scope

The latest built artifact is a13, fixed to product source `eeb2d0c`. Its exact
clean workflow passed Ruff/format for 233 files and 1078 tests/three skips in
20.01 seconds. Seven Noble actual-package modes now naturally exited 0 and
passed independent acceptance; **host checks remain pending**. R8 source checks
using old a12 dependencies passed separately; those source checks cannot
substitute for a13 artifact validation. The independent a13 checks establish
the limited package execution described above. Neither changes the preserved
a12 artifact. R7/a12 fast-stream positives and
a12 paced-stream latency failure remain separate historical results.
See [a13 actual-package evidence](performance-a13-package-validation.md),
[R8 source evidence](ubuntu24-source-r8-validation.md),
[a12 artifact evidence](performance-a12-package-validation.md) and
[a12 paced counterexample](performance-a12-paced-validation.md).

| System/session and version | Actual measured result | Still outside that result |
| --- | --- | --- |
| Ubuntu 24.04.5 KVM / GNOME 46 actual Xorg / R8 new source, old a12 dependencies | Paced/fast150 exact and cancel-safe; writes/restores/insertions 145/1/150 and 145/1/6; post-cleanup GTK/VTE 0.1734/0.3882 and 0.1706/0.2901 s; first press before future text, exact [12,44] routing | Verified source Session/task scope only; observer and two-task cleanup remain, not immediate response or broad reliability; a12 unchanged |
| Same actual Noble guest Xorg / a13 artifact, product eeb2d0c | Seven modes passed with strict actual package origins: default four targets140exact, cancel12, normal/long-paced/long-fast local TLS, lone first press plus exact [12,44] focus, extracted AppRun nine pages; paced GTK/VTE 0.1753/0.2983 s after both tasks/cleanup | No new a13 40 ms control; host pending, no real VM mic/cloud/physical shortcut/overlay-focus/FUSE/installation claim; no distribution or immediate response guarantee |
| Historical Ubuntu 24.04.5 KVM / GNOME 46 actual Xorg / R7 new source, old a11 dependencies | 150 exact fast-stream codepoints, 150 writes/six restores, cancellation/cleanup, isolated first character and [12,44] focus route; post-cleanup GTK/VTE 0.1639/0.2216 s | Source-only with verified new origins; not a repaired a11 package or general responsiveness guarantee |
| Historical same guest Xorg / a12 artifact R1 | Eight modes: four-target matched 40/20 checks, cancel12, normal local TLS 40/20, fastlong150, streamed first/focus and extracted AppRun nine pages; fastlong GTK/VTE 0.1747/0.3388 s after both tasks/cleanup | R2 paced-stream latency failed despite R1 success; no VM microphone/cloud, physical shortcut/F13/F14, overlay focus, FUSE, installation/autostart or arbitrary-paced/immediate-response claim |
| Historical same guest Xorg / unchanged a12 artifact R2 | Fixture-configured 70 ms sleep per fragment; 150 exact and cancel-safe, but 288 writes/150 restores; after both tasks/cleanup new GTK needed 5.8435 s, sequential VTE 0.3393 s | Mechanical gates passed; latency acceptance failed. R8 source passed separately, a13 Noble actual artifact passed separately; host pending; not an overall fix |
| Historical Ubuntu 24.04.5 KVM / GNOME 46 actual Xorg / R6 source | New production source imported explicitly; complete Chrome textarea/contenteditable, GTK, VTE 40/20 ms groups each 140 exact; cancel after 12 and no tail over 0.5 s | Not a package test; old a10 interpreter/dependencies do not mean a10 contains the repair |
| Historical same guest Xorg / a11 artifact R1 | Artifact's own modules: same four-target matched checks, cancellation, 56-codepoint two-window switch with exact 12/44 split, fixed local TLS WSS/SSE pipeline including fast25, extracted AppRun nine pages | No VM microphone/cloud speech, physical global shortcut/F13/F14, overlay-focus acceptance, FUSE mount, menu installation or autostart; R2 below shows that long-stream desktop latency remains |
| Historical same guest Xorg / unchanged a11 artifact R2 | 150 streamed codepoints and cancellation exact; 288 mapping writes, 150 restores; fresh GTK readiness 6.0944 s after both tasks/cleanup, sequential VTE 0.285 s | Mechanical readiness gate passed but material desktop delay remains; not an overall fix; later R7/a12 results do not change this artifact |
| Ubuntu 24.04.5 KVM / GNOME 46 native Wayland / historical a10 artifact | Extracted AppRun nine pages, normal exit; actual keyboard-worker authorization failed, missing SetKeymap/KeymapCapabilities | Current native input path unavailable in this measured installation; not proof that every alternative is impossible; no a13 native guest input success |
| Ubuntu 26.04.1 / GNOME 50.1 / earlier a9 and a10 | Owned native/XWayland target and package results retained in [a9 acceptance](native-wayland-parent-validation.md) and [a10 package report](performance-package-validation.md) | Historical versions, not a13 host revalidation; native BMP restriction remains, arbitrary apps and complete desktop matrix unproven |
| Ubuntu 24.04 / minimal offscreen container / earlier packages | Userspace startup and nine-page screenshots in the recorded container checks | No actual guest desktop/kernel, microphone or keyboard acceptance follows from the container |
| Windows/macOS | Not implemented or tested | No compatibility claim |

The actual Noble VM runs its own kernel, systemd and graphical login, distinct
from the container smoke and from host XWayland. Its lock/network recovery,
UI extraction method and initial a10 failures are retained in
[VM feasibility](ubuntu24-desktop-feasibility.md) and
[historical VM results](ubuntu24-vm-performance-validation.md). Do not backfill
the later source/a11/a12 results into the unchanged a10 artifact. Global shortcuts,
F13/F14, actual microphone and overlay-focus cells remain unaccepted for this
VM even when its keyboard, synthetic local pipeline and UI checks pass.

## Historical stage 0 matrix — 2026-10-12

The following table preserves the observations from its date; it does not
override the version-specific current table above. Host GNOME Wayland,
XWayland, Xvfb and offscreen userspace evidence are separate. Read
[the feasibility report](feasibility-report.md) before interpreting a passed
item as a complete application workflow.

| System/session | Global shortcut | F13/F14 | Microphone | Chinese/Unicode without clipboard | Overlay focus | AppImage |
|---|---|---|---|---|---|---|
| Ubuntu 24.04 / X11 desktop | Pending | Pending | Pending | Pending | Pending | Desktop pending; separate headless userspace smoke passed |
| Ubuntu 24.04 / Wayland desktop | Pending | Pending | Pending | Pending | Pending | Desktop pending; separate headless userspace smoke passed |
| Ubuntu 26.04 / X11 desktop | Pending | Pending | Pending | Full desktop pending | Pending | Full desktop pending |
| Ubuntu 26.04.1 / GNOME Wayland host | Portal session created; binding timed out | No confirmed activation | Real default mic capture passed repeatedly | GNOME editor AT-SPI transport passed only; Chrome/VTE AT-SPI unsupported; portal input unproven | Pending | Stage 0 packaged visible launch passed; final alpha native desktop test pending (locked session) |
| Ubuntu 26.04.1 / isolated Xvfb lab (not full desktop) | Ctrl+Alt+K synthetic activation and conflict rejection passed | Synthetic activation with temporary/restored map passed; physical keys pending | Actual host microphone used in source and final bundled-runtime workflow | Real Chrome, GNOME editor and VTE received Unicode via diagnostic XTest; targeted GTK AT-SPI final packaged workflow passed Unicode/cancel/focus-away-back | Production overlay retained focus during real workflow; no compositor | Final alpha nine-page/IPC/config checks and bundled-runtime microphone-to-input workflow passed |
| Ubuntu 24.04 / minimal offscreen container | Not applicable | Not applicable | Not tested | Not tested | Not tested | Final alpha full application: nine pages, bundled Chinese font, clean exit; nonroot/network-disabled/read-only |

## Historical a8 input boundary (keyboard behavior introduced in a7)

The a7 keyboard route follows the output-time cursor and does not require an
editable target before recording. Focus changes do not cancel; explicit
cancellation and expired task IDs still stop later output. Host desktop protocol
and target application protocol are distinct.

| Backend/target | Measured status at a8 | Limit |
| --- | --- | --- |
| XSendEvent / owned GTK XWayland on GNOME Wayland | Production keyboard and source/full-package microphone + local HTTPS workflow passed Unicode and cancellation | No arbitrary application or physical-shortcut claim |
| XSendEvent / owned Chrome 154 XWayland | Diagnostic delivered exact 28-code-point Unicode sample, including newline | Actual user Codex editor not tested; per-application handling can differ |
| Production KeyboardInput / owned VTE 0.84 XWayland | 28 code points, exact 53 raw PTY bytes and restored map; no shell started | Return is one CR byte in this raw PTY test, not an LF; user terminal applications not tested |
| Keyboard route / native Wayland GTK, including native GNOME Text Editor | Unsupported by the a7 X11 transport | Native portal keysym route dropped characters; old AT-SPI tests used a different policy |
| Current Codex XWayland window | Transport identity verified read-only; text delivery pending | Missing AT-SPI EditableText does not by itself determine new keyboard compatibility |
| Other X11/XWayland targets and full X11 desktop | Backend intended for X11/XWayland; unmeasured target/desktop behavior pending | X server accepting an event does not acknowledge application editing |
| Windows/macOS | Not implemented or tested | No compatibility claim |

See [current-cursor acceptance](current-cursor-input-validation.md) and
[keyboard transport evidence](keyboard-transport-validation.md). The following
AT-SPI table and dated supplements preserve alpha6-and-earlier measurements and
do not describe the current input policy.

## Historical targeted AT-SPI boundary through alpha6

| Backend/target | Status | Why |
|---|---|---|
| Targeted AT-SPI / focused editable GTK fixture | Final bundled-runtime microphone + local HTTPS + safe delivery tested | Sends to a captured object rather than current global focus |
| Targeted AT-SPI / native GNOME Text Editor 50.1 (GTK 4) | Alpha6 actual microphone + local HTTPS + production notifications + exact Unicode input and explicit cancellation passed | Isolated owned standalone document; native focus-loss case, physical shortcuts and real cloud quality not tested for this target |
| Targeted AT-SPI / Chrome 154 native Wayland textarea | Unsupported for tested version | Does not expose `EditableText` |
| Targeted AT-SPI / VTE native terminal | Unsupported | Does not expose `EditableText` |
| XTest / Xvfb browser, terminal, editor | Diagnostic only | Focus check and global delivery are not atomic |
| RemoteDesktop keyboard portal / native Wayland | Session/consent handshake passed, input not proven | Own fixture never passed fresh active-window checks; no sample sent |
| Windows/macOS | Not implemented or tested | Interfaces remain isolated for future adapters |

The GNOME GSettings shortcut adapter subsequently passed temporary registration,
readback, quoted marker-command launches and exact settings restoration. The native
session had locked before activation could be tested, so the Wayland shortcut/F13/F14
cells remain pending. See [global shortcuts](hotkeys.md).

An installed portal, visible application window, passing unit test, or isolated
toolkit fixture does not establish support for all applications in a desktop row.
No backend falls back to a clipboard. Unsupported input must remain a visible
recoverable application error rather than being reported as successful dictation.


## Final alpha packaged workflow supplement

The final `InkEcho-0.1.0-alpha-x86_64.AppImage` (107547128 bytes, SHA-256
`cb35d203024538a4ee3d55c6ccb8619059ce9f4bfda387fd1b92e2291eec11a4`)
passed independent clean-development-environment GUI launch, all nine pages,
single-instance show/toggle/cancel/quit and damaged-config preservation on private
Xvfb. This is the full application, distinct from the stage 0 probe artifact.

The exact extracted artifact's own Python/packages also passed actual default
microphone → TLS-verified localhost test provider → production Session/Overlay →
AT-SPI GTK editor on private `:92`. Exact 28-codepoint mixed Unicode was delivered;
late replies after cancellation and focus-away/back left the target unchanged.
Statistics recorded 3 tasks, 1 success and 2 cancellations; WAV payloads were
17738 / 18422 / 18422 bytes. No audio files, clipboard access or real cloud account
calls were involved. This is safe input evidence for that specific editable GTK
fixture, not browser/terminal or native Wayland production support.

Independent Ubuntu 24.04 userspace recheck rendered nine pages and exited 0 with
no host home, audio or credential mounts (`build/ubuntu24-qa.ugphfK`). Inventory
review matched 31 application source files, 3883 regular-file hashes and 1048
symlinks, with no symlink escaping the AppDir. Full reproduction and final evidence
are in [local validation](local-validation.md) and [packaging](packaging.md).

## 0.1.0a2 input attempt policy

Wayland is no longer rejected solely by session name. The application attempts the
same strict targeted AT-SPI capture as X11, and starts only after an active window,
focused editable control and stable caret are verified. All existing cancellation,
epoch and final focus checks remain in force. This is **experimental per-target
availability**, not a newly verified Wayland desktop support row.

A 2026-10-12 follow-up on the unlocked native host and in a private headless GNOME
50.1 Wayland compositor both refused inactive/unfocused GTK fixtures safely. No
sample was injected. The complete focused Wayland workflow remains pending; see
[input repair evidence](input-repair-validation.md). Controls without EditableText,
including the previously tested Chrome and VTE controls, remain unsupported.

## 0.1.0a5 recording cancellation repair supplement — 2026-10-13

The actual alpha5 AppImage (SHA-256
`8a7ea103e6c299323038cb8c16e649e6608ed0dd892031c8e1755684d4f2dadb`)
passed native GNOME Wayland startup and nine-page rendering. This supersedes the
historical table's pending final-alpha startup entry, but not its pending native
input/overlay workflow. A bounded owned native GTK probe obtained a safe target
once; a repeat could not establish ACTIVE focus, so no native Unicode workflow
success is claimed from that attempt.

The exact extracted alpha5 Python/modules passed real host microphone → locally
verified HTTPS fixture → production Session/Overlay → GTK AT-SPI delivery on a
private Xvfb `:96`: 28 Unicode code points delivered; explicit cancellation and
focus-away/back late replies left the target unchanged; 3 recordings, 1 success,
2 cancellations. No clipboard, saved audio or real cloud account was used. This
is isolated X11 fixture evidence, not full X11 desktop or Wayland support.

The same artifact passed private offscreen nine-page/IPC/config-preservation
checks and a nonroot, network-disabled, read-only Ubuntu 24.04 container startup.
See [alpha5 release validation](listening-repair-release.md) for the exact artifact,
reproduction and current limitations. The original historical rows remain intact.

## Native Wayland follow-up — 2026-10-13

An unlocked native GNOME Wayland run passed owned GTK 3 target capture, exact
Chinese/Latin/emoji insertion, explicit cancellation rejection and stale-target
rejection after a second owned window took focus. This is a direct-input result
for that fixture; see [native input evidence](listening-repair-validation.md#unlocked-native-wayland-follow-up-direct-input-passed).

Initial complete packaged microphone/local-HTTPS/notification and separate
public-sample/cloud/Session attempts stopped before recording or requests when no
active target could be captured. Read-only checks found zero Mutter
physical/logical monitors, zero GTK outputs and only a zero-size Qt placeholder
despite an unlocked session. This historical obstacle is documented in
[native cloud/display validation](native-cloud-workflow-validation.md).

After the user restored display outputs, root confirmed one physical and one
logical monitor and an unlocked session. The exact alpha6 runtime then **passed**
actual microphone → certificate-verified local HTTPS → production MainWindow
notifications → native owned GTK input: 28 Unicode code points, three recordings,
one success and two safe cancellations (explicit cancel and native focus loss),
11 accepted notifications and no visible Qt window. No clipboard, saved audio,
user credentials or cloud requests were involved. See
[native voice validation](native-voice-workflow-validation.md). This validates the
owned GTK fixture with fixed local replies; physical shortcuts, real speech
recognition quality and arbitrary application targets remain outside that result.
The actual GNOME Text Editor 50.1 (GTK 4) then independently **passed** the same
alpha6 microphone/local-HTTPS/production-notification path in an isolated owned
standalone document: two recordings totaling 1.25525 seconds, 28 exact Unicode
code points, one success, one explicit cancellation with unchanged text after a
late reply, eight accepted notifications and no visible Qt window. Its focus-loss
case was not exercised; do not transfer the GTK 3 focus-loss result to this target.
See [GNOME Text Editor validation](native-voice-workflow-validation.md#gnome-text-editor-501-native-workflow).

A separate guarded run of the same alpha6 runtime also **passed** public audio
sample → production Session → real ASR and polishing → native owned GTK input:
one ASR call, one polishing call, 194 returned characters exactly matched the
editor, and 20.095 seconds elapsed. This run substituted a public sample for the
microphone, did not exercise MainWindow notifications, and kept returned text in
memory. See [native cloud validation](native-cloud-workflow-validation.md).
These are separate successful workflows, not one test of live user speech
through cloud recognition and production notifications.

The running Codex instance exposed frames and null child references, with no
capturable editable input control; it is currently unavailable to the strict
AT-SPI input backend. This does not establish the behavior of other Codex versions
or configurations. See [Codex target evidence](codex-input-validation.md).
Historical measurements above remain unchanged; these checks do not establish
universal Wayland support.

## 0.1.0a7 current-cursor supplement — 2026-10-14

Source and versioned AppImage workflow checks passed on the real GNOME Wayland
host with owned GTK XWayland targets: recording began on a noneditable button;
a local HTTPS reply was delayed while focus moved to a second window; all 28
Unicode code points arrived there; a second task was cancelled without late
output. Production notifications stayed windowless and normalized keymaps were
restored. No cloud call, user key, clipboard or system input method was used.

Separate production backend checks passed switching between two owned windows
mid-output, partial cancellation with a matching key release, and a destroyed
owned-window error without process termination. Owned Chrome and VTE results
above are separate transport checks, not additional full speech workflows.
The a7 package also produced nine actual native Wayland settings screenshots
using disposable defaults. Deployment confirmation is recorded separately in
[current-cursor acceptance](current-cursor-input-validation.md).


## 0.1.0a8 retired-adapter cleanup — 2026-10-14

The final alpha8 AppImage contains no retired AT-SPI adapter or historical test
support, and all current application files match the cleaned source. Its exact
packaged runtime passed the same native-host/owned-XWayland current-cursor
microphone/local-HTTPS workflow: one success, one explicit late-reply cancellation,
28 exact Unicode code points, seven accepted notifications and restored keymap.
The actual AppImage also passed isolated native Qt Wayland startup. This confirms
the cleanup preserves that measured workflow; it adds no new target or desktop
matrix coverage. See [alpha8 release validation](focus-tracking-removal-release.md).
