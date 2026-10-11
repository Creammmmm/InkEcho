# Compatibility matrix

Measured 2026-10-12. **Pending is not supported.** Host GNOME Wayland and isolated
Xvfb evidence are separate. Read [the feasibility report](feasibility-report.md)
before interpreting a passed item as a complete application workflow.

| System/session | Global shortcut | F13/F14 | Microphone | Chinese/Unicode without clipboard | Overlay focus | AppImage |
|---|---|---|---|---|---|---|
| Ubuntu 24.04 / X11 desktop | Pending | Pending | Pending | Pending | Pending | Desktop pending; separate headless userspace smoke passed |
| Ubuntu 24.04 / Wayland desktop | Pending | Pending | Pending | Pending | Pending | Desktop pending; separate headless userspace smoke passed |
| Ubuntu 26.04 / X11 desktop | Pending | Pending | Pending | Full desktop pending | Pending | Full desktop pending |
| Ubuntu 26.04.1 / GNOME Wayland host | Portal session created; binding timed out | No confirmed activation | Real default mic capture passed repeatedly | GNOME editor AT-SPI transport passed only; Chrome/VTE AT-SPI unsupported; portal input unproven | Pending | Actual packaged visible launch passed on development host |
| Ubuntu 26.04.1 / isolated Xvfb lab (not full desktop) | Ctrl+Alt+K synthetic activation and conflict rejection passed | Synthetic activation with temporary/restored map passed; physical keys pending | Not tested in this isolated display | Real Chrome, GNOME editor and VTE received Unicode via diagnostic XTest; targeted GTK AT-SPI adapter passed Unicode/cancel/focus-away-back | Focus remained on fixture; no compositor | xcb runtime dependencies investigated; see packaging report |
| Ubuntu 24.04 / minimal offscreen container | Not applicable | Not applicable | Not tested | Not tested | Not tested | Nonroot, network-disabled, read-only container runtime smoke passed |

## Current input support boundary

| Backend/target | Status | Why |
|---|---|---|
| Targeted AT-SPI / focused editable GTK fixture | Real transport and cancellation/focus invalidation tested | Sends to a captured object rather than current global focus |
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
