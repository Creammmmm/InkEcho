# Compatibility matrix

Initial measurements below are from 2026-10-12; dated release supplements follow.
**Pending is not supported.** Host GNOME Wayland and isolated
Xvfb evidence are separate. Read [the feasibility report](feasibility-report.md)
before interpreting a passed item as a complete application workflow.

| System/session | Global shortcut | F13/F14 | Microphone | Chinese/Unicode without clipboard | Overlay focus | AppImage |
|---|---|---|---|---|---|---|
| Ubuntu 24.04 / X11 desktop | Pending | Pending | Pending | Pending | Pending | Desktop pending; separate headless userspace smoke passed |
| Ubuntu 24.04 / Wayland desktop | Pending | Pending | Pending | Pending | Pending | Desktop pending; separate headless userspace smoke passed |
| Ubuntu 26.04 / X11 desktop | Pending | Pending | Pending | Full desktop pending | Pending | Full desktop pending |
| Ubuntu 26.04.1 / GNOME Wayland host | Portal session created; binding timed out | No confirmed activation | Real default mic capture passed repeatedly | GNOME editor AT-SPI transport passed only; Chrome/VTE AT-SPI unsupported; portal input unproven | Pending | Stage 0 packaged visible launch passed; final alpha native desktop test pending (locked session) |
| Ubuntu 26.04.1 / isolated Xvfb lab (not full desktop) | Ctrl+Alt+K synthetic activation and conflict rejection passed | Synthetic activation with temporary/restored map passed; physical keys pending | Actual host microphone used in source and final bundled-runtime workflow | Real Chrome, GNOME editor and VTE received Unicode via diagnostic XTest; targeted GTK AT-SPI final packaged workflow passed Unicode/cancel/focus-away-back | Production overlay retained focus during real workflow; no compositor | Final alpha nine-page/IPC/config checks and bundled-runtime microphone-to-input workflow passed |
| Ubuntu 24.04 / minimal offscreen container | Not applicable | Not applicable | Not tested | Not tested | Not tested | Final alpha full application: nine pages, bundled Chinese font, clean exit; nonroot/network-disabled/read-only |

## Current input support boundary

| Backend/target | Status | Why |
|---|---|---|
| Targeted AT-SPI / focused editable GTK fixture | Final bundled-runtime microphone + local HTTPS + safe delivery tested | Sends to a captured object rather than current global focus |
| Targeted AT-SPI / native GNOME Text Editor 50.1 | Unicode transport demonstrated; focused production workflow pending | Test document was not active during transport probe |
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

The subsequent complete packaged microphone/local-HTTPS/notification workflow
and separate public-sample/cloud/Session workflow remain **unvalidated**: both
stopped before recording or requests when no active target could be captured.
Later read-only checks found zero Mutter physical/logical monitors, zero GTK
outputs and only a zero-size Qt placeholder despite an unlocked session. See
[native voice validation](native-voice-workflow-validation.md) and
[native cloud/display validation](native-cloud-workflow-validation.md).

The running Codex instance exposed frames and null child references, with no
capturable editable input control; it is currently unavailable to the strict
AT-SPI input backend. This does not establish the behavior of other Codex versions
or configurations. See [Codex target evidence](codex-input-validation.md).
Historical measurements above remain unchanged; these checks do not establish
universal Wayland support.
