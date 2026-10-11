# Acceptance checklist

Reviewed against all sections of [PROJECT_SPEC](PROJECT_SPEC.md), 2026-10-12.
This is a development preview, not a claim that the complete desktop compatibility
matrix or the universal voice-input product has passed acceptance.

## Implemented and locally tested

| Requirement | Evidence and scope |
|---|---|
| Single active task, unique IDs, cancellation and stale reply rejection (§21) | `test_core.py`, `test_application.py`, `test_desktop_acceptance.py`; real local-service voice probe below |
| Capture target before slow credential lookup (§12,21) | Focus change during pending key lookup cannot retarget; qasync + real credential worker dispatch tested with disposable injected backend |
| No clipboard and Unicode input (§12) | Actual focused GTK AT-SPI insertion, mixed Chinese/Latin/Greek/emoji/newline, cancellation and away-back focus test; X11 restricted controls only |
| Microphone selection, RAM audio, limits and cleanup (§5) | Actual host microphone repeated capture, cancellation/restart/timeout; real workflow sends valid mono 16 kHz WAV to localhost only |
| Qwen transcription and separate polishing adapter (§6–8) | Actual TLS-verified localhost HTTP protocol tests, response/error/timeout/empty/cancel cases; real vendor recognition remains pending |
| Optional polishing and fallback (§7) | Successful pipeline plus enabled/disabled failure fallback regressions; usage fields preserved or marked unknown |
| Independent providers, models and capability tests (§8) | Separate records and role-specific UI; model discovery distinct from test request; manual model IDs accepted |
| Versioned atomic configuration and migration (§9,20) | Defaults, separate JSON, v0 backups, corrupted/future files preserved, path validation, owner-only permissions tested |
| Credentials (§10) | Explicit Secret Service backend, no plaintext fallback; actual disposable item create/read/update/delete tested; no user secrets accessed |
| Prompt CRUD and built-in protection (§11) | Selection, create/copy/edit/delete and built-in copy behavior; UI preview/test request controls |
| Main window and settings (§14) | Nine real pages rendered in isolated X11 at 1120×850; Chinese text visually reviewed; UI interaction regressions recorded separately |
| Status overlay (§13) | Production overlay keeps GTK target focused during actual recording/ASR/polishing/injection flow; waveform/pulse, position, opacity and duration configuration |
| Statistics and diagnostics (§15,17) | Numeric daily aggregates, Unicode codepoint count, explicit unknown tokens, corrupted data preservation, explicit clear and bounded diagnostic logs |
| Lifecycle and IPC (§16) | Separate processes route show/toggle/cancel/quit to one instance; primary exits 0; no-tray settings and stop/cancel alternative implemented |
| Shortcut settings (§4) | GNOME GSettings temporary F13/F14/ordinary-combo registration/readback/restore; conflict and quoting tests; activation caveat below |
| Desktop integration (§19) | Explicit install/repair/remove, path-change detection, icons and opt-in autostart; ownership checks preserve unrelated files/config/credentials |
| Cross-platform boundaries (§3,23) | Pure task controller/config/provider logic separated from Linux accessibility/hotkey/integration adapters; no Windows/macOS support claim |

## Actual integrated voice workflow

`scripts/validation/voice_workflow_probe.py` runs the production `Session`, real Qt
`Recorder`, real `ProviderClient`, real `AccessibilityInput` and production `Overlay`
on a private Xvfb display. A separate GTK process is the target; a temporary trusted
HTTPS server returns a fixed Unicode phrase. Credentials are a disposable injected
fixture, not a real provider account. TLS verification is enabled.

Source run on Ubuntu 26.04.1, Xvfb `:91`, Qt 6.12.0 passed:

- Exact `你好 InkEcho，世界！ café Ω 😀\n第二行。` delivered to the target.
- Three real microphone payloads: 19786, 19786 and 19104 WAV bytes; no audio files.
- One successful transcription-plus-polishing task; two cancelled tasks.
- A delayed reply after cancellation and a delayed reply after focus-away-and-back
  both left the target unchanged. The overlay preserved target focus.
- Statistics: 3 recordings, 1 success, 2 cancellations, 28 delivered codepoints,
  3 transcription calls, 1 polishing call, reported tokens 5/7/12.
- Recorder resources and PCM buffers released after each operation.

Evidence: `build/voice-source-acceptance.json` (generated locally, not a release
artifact). This proves an integrated microphone/network/desktop path with a fixed
local reply; it does **not** measure real cloud recognition or polishing quality.

```sh
dbus-run-session -- env DISPLAY=:91 QT_QPA_PLATFORM=xcb \
  XDG_SESSION_TYPE=x11 PYTHONPATH=src \
  .venv/bin/python scripts/validation/voice_workflow_probe.py \
  --output build/voice-source-acceptance.json
```

Use an already-running private Xvfb display, never a user desktop. The machine run
used extracted xdotool via `--xdotool /tmp/inkecho-x11/usr/bin/xdotool` and its library
directory in `LD_LIBRARY_PATH`. System Python needs GTK 3 introspection; openssl is
used only to generate the disposable local TLS certificate. The test reads the
actual default microphone for three short recordings; audio stays in RAM and is
sent only to the temporary localhost server.

## Desktop launch and process acceptance

`scripts/validation/desktop_app_probe.py --output NEW_DIRECTORY` starts the app with
private temporary config/data/cache/runtime directories, renders all nine pages,
uses secondary processes for `--show`, `--toggle`, `--cancel`, `--quit`, and confirms
clean primary shutdown. It then deliberately damages its own disposable config and
checks exit 1 with the exact bytes preserved. It never edits user configuration.
Source run passed; evidence is `build/ui-acceptance-source-final/result.json`.
The final AppImage also passed the same complete driver on Xvfb `:91`: all nine
pages rendered at 1120×850, secondary commands succeeded, primary exit was 0,
and damaged configuration was preserved with exit 1. All nine screenshots were
visually inspected for legible Chinese, navigation and form layout; long pages
have scrollbars. Evidence: `build/ui-acceptance-appimage-final/result.json`.

Tested artifact: `dist/InkEcho-0.1.0-alpha-x86_64.AppImage`, 107547128 bytes, SHA-256
`cb35d203024538a4ee3d55c6ccb8619059ce9f4bfda387fd1b92e2291eec11a4`.
The README screenshot is an unmodified copy of its actual home page.

The independent root review repeated final AppImage lifecycle checks with
`PYTHONPATH`, `PYTHONHOME` and `LD_LIBRARY_PATH` cleared; all passed
(`build/ui-root-final-appimage/result.json`). It then extracted that exact image,
verified all 31 application source files byte-for-byte against the checkout and
all 3883 inventory regular-file hashes, and ran the voice workflow using the
**bundled Python and packages** on private Xvfb `:92`. Only xdotool's own helper
library was supplied externally; application libraries came from the bundle.

Final bundled-runtime voice result (`build/voice-root-final-appimage.json`): exact
28-codepoint Unicode delivery, overlay focus preserved, cancelled and focus-away-
and-back late replies unchanged, 3 tasks / 1 success / 2 cancellations, reported
tokens 5/7/12, real microphone WAV payloads 17738 / 18422 / 18422 bytes, no audio
files or clipboard access. This closes packaged pipeline acceptance for the tested
fixture scope. Ubuntu 24.04 nonroot/read-only/network-disabled userspace startup
also passed with all nine pages; real desktop compatibility remains pending.

Add `--appimage /absolute/path/to/InkEcho.AppImage` to validate the packaged entry
point and capture its SHA-256. The report must refer to that tested artifact, not
an earlier build. Generated screenshots need human visual review; PNG dimensions
alone do not establish correct rendering.

```sh
.venv/bin/pytest -q tests/test_desktop_acceptance.py
```

Five regression cases pass, including the actual qasync event loop and threaded
credential lookup with a disposable backend. Run thread/socket integration tests
in a normal authorized local environment: the development sandbox rejects asyncio
self-pipe sends with `EPERM`, which can prevent worker completion wakeups. No
application workaround disables security controls for this test restriction.

## Pending or deliberately unavailable

| Requirement | Remaining acceptance work |
|---|---|
| Native Wayland input (§12,24) | Disabled in the application; safe focused browser/terminal delivery not demonstrated. Native editor transport alone is insufficient |
| Arbitrary X11 targets (§12) | Only compatible editable AT-SPI controls; Chrome/VTE tested versions lack the required interface. Diagnostic XTest success is not a safe application backend |
| Real Ubuntu 24.04 and 26.04 desktop matrix (§24) | Xvfb is not a full X11 desktop. Ubuntu 24.04 container loading is not a Wayland/X11 desktop test |
| Native global key activation and physical F13/F14 (§4) | Portal binding timed out; GSettings readback succeeded but the native session later locked. No unlock or consent bypass; physical activation remains unverified |
| Native overlay stacking/transparency/click-through (§13) | Xvfb focus checks pass; compositor behavior and full native Wayland behavior remain unverified |
| Real vendor account requests (§6–8,28) | No user API credentials used; actual Qwen/DeepSeek authentication, model availability, recognition accuracy and account quotas not accepted by local fixtures |
| Clean desktop deployment (§18,27) | Final packaged UI/IPC, bundled-runtime voice and Ubuntu 24.04 userspace startup passed. Additional clean real desktops must still verify host audio, accessibility and desktop services |
| Cross-platform support (§2,23) | Windows/macOS adapters are future work |

The native desktop was locked during later tests. Tests did not unlock it, alter
permission stores, inject into user documents, read the clipboard, or treat a
missing native test as a pass. See [feasibility](feasibility-report.md),
[compatibility matrix](compatibility-matrix.md), [packaging](packaging.md), and
[application validation](application-validation.md) for detailed evidence.
