# Compatibility matrix

Measured 2026-10-12. **Pending is not supported.** Host GNOME Wayland and isolated
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
