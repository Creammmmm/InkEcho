# InkEcho v0.2.0 — current-cursor Linux voice input

This formal release contains the verified four-slot native Wayland keyboard
output, a 10 ms per-character release wait, and whole-utterance final-ASR /
protocol-closure overlap with the existing streaming polishing/output pipeline.
Each key still has its own acknowledgement; prepared hints never emit text.
Explicit cancellation, expiry and replacement stop unsent output without replay.
Recording does not capture a target; output follows the current cursor.
No clipboard or system input method is used.

The preceding a18 package measured one native 100-character sample at about
3.31 seconds; its source 30/20/10 ms comparison and local TLS pipeline proof are
recorded in [a18 acceptance](a18-dual-ubuntu-validation.md). Those are historical
a18 measurements, not a substitute for the new 0.2.0 artifact's same-SHA dual-OS
acceptance. The 0.2.0 package report must record its own version, SHA and results
before publication.

Release scope is Linux x86_64: Ubuntu 24.04 Xorg and Ubuntu 26.04 GNOME native
Wayland/XWayland as actually validated. GNOME 46 native Wayland remains
unsupported. No Windows/macOS, arbitrary application, physical shortcut,
real microphone or authenticated cloud-recognition claim is added by local
synthetic-audio/TLS tests. Credentials remain in Secret Service; audio and
transcript history are not retained by default.

The release-source version is 0.2.0. Later report/development commits use
0.2.1 and subsequent patch versions under the per-commit version policy; they
are not additional release assets unless independently built and published.

## Historical 0.1.0a8 — remove the retired focus-tracking adapter


This cleanup removes the unused captured-target AT-SPI adapter from production
source and packaging. Historical probes/tests keep that algorithm under test-only
support; no production module imports it. Current-cursor keyboard behavior,
explicit cancellation and stale-task protection remain unchanged. Recording does
not bind a target, and moving focus does not cancel a task.

See [source removal audit](focus-tracking-removal-audit.md) and
[alpha8 package validation](focus-tracking-removal-release.md) for the actual
artifact checks and deployment status. The supported transport remains X11 /
XWayland; this cleanup does not add native Wayland target or arbitrary application
support. Earlier acceptance results retain their measured versions below.

## Historical 0.1.0a7 — input at the current cursor

Recording no longer captures or requires an editable target. Windows and caret
may change during recording, transcription and polishing without cancelling the
task. The production keyboard backend resolves the X11/XWayland focus during
output, so later characters may follow a window switch. Explicit cancellation
and expired tasks still stop unsent text; already sent keys cannot be retracted.
No clipboard or system input method is used.

The final AppImage passed real microphone → verified local HTTPS → production
notification → owned GTK XWayland output and late-reply cancellation on a GNOME
Wayland host. Separate production checks covered switching windows mid-output,
partial cancellation, destroyed-window errors and an owned raw VTE terminal
without a shell. An owned Chrome XWayland diagnostic passed Unicode delivery.
These results do not establish arbitrary application support: native Wayland
GTK is unsupported by this backend, and the user's XWayland Codex input has not
been exercised. “Keys sent” reports dispatch, not acknowledgement by every app.

See [current-cursor acceptance](current-cursor-input-validation.md) for the final
artifact hash, exact commands, results, deployment status and limitations;
[keyboard transport evidence](keyboard-transport-validation.md) separates each
native target measurement. Build instructions are in [packaging](packaging.md).
Provider configuration, credentials and appearance are unchanged by this input
revision. Earlier release sections below retain their original input policy and
measurements; they do not describe alpha7's current behavior.

## Historical 0.1.0a6 — specific audio error feedback

This focused release preserves the recorder's specific, sanitized failure reason
through normal recording and microphone-test feedback. Missing devices,
unsupported formats, start failures, interruptions, empty input and recording
timeouts receive distinct explanations. Input routing, cancellation policy,
providers, dependencies and appearance are unchanged. Current package evidence
and the locked-native-session limitation are recorded in
[audio feedback validation](audio-feedback-validation.md).

## Earlier recording cancellation repair

This preview narrows accessibility-event handling to the captured target and
reports why a recording or pending result was cancelled. Unrelated application
lifecycle events must not cancel dictation, while real target focus changes,
caret changes and explicit cancellation continue to stop delivery. The exact
tested scope is recorded in [recording cancellation repair validation](listening-repair-release.md).

## Retained provider and appearance improvements

This preview aligns transcription requests with the configured model's supported
protocol and reports actionable Chinese configuration/service errors. Unsupported
realtime selections are rejected before recording or a capability request, rather
than sent through an incompatible ordinary HTTP chat endpoint. Dynamic discovery
still does not by itself establish a model's transcription capability.

The application uses the user's supplied logo artwork and a coordinated navy/white
palette for settings, tray and desktop integration. AppImage names now include the
exact package version: `InkEcho-0.1.0a6-x86_64.AppImage`. The stable legacy filename
is updated only after local acceptance; earlier versioned images are preserved.

The guarded AT-SPI input restrictions remain: target identity, editability, active
focus, cancellation and stale-result checks must all pass. Experimental Wayland
target checks do not imply universal browser/terminal compatibility. No clipboard
fallback is introduced. Keys remain in Secret Service; recordings and transcripts
are not retained by default.

The current checksum and package evidence are in the audio feedback report.
The earlier authenticated provider diagnostic is retained in
[provider repair release validation](provider-repair-release.md). Reproducible
build instructions are in [packaging](packaging.md).

## Historical alpha1 evidence

The following section records the original `0.1.0a1` release and its environment
on 2026-10-12. Its hashes, test counts and desktop state are historical and must
not be treated as acceptance of later releases.

This preview provides a complete settings application and the voice-input
pipeline: RAM-only microphone capture, configurable Qwen transcription,
optional DeepSeek/OpenAI-compatible polishing, cancellation, and guarded
AT-SPI delivery to supported editable targets. Cloud credentials are stored
in Secret Service; no transcript/audio history is saved. Desktop launcher
installation, path repair and explicitly enabled autostart are available.

The Python package version is `0.1.0a1`; the artifact filename uses
`InkEcho-0.1.0-alpha-x86_64.AppImage`. Source is MIT; bundled dependencies retain
their own licenses. Build/verification instructions are in [packaging](packaging.md).

## Scope and known limits

- Linux x86_64 preview. No Windows/macOS compatibility claim.
- Production injection is targeted AT-SPI EditableText delivery, with focus
  generation and task cancellation checks. Chromium and VTE targets that do
  not expose this interface are rejected. The earlier XTest feasibility probe
  is not a production global-key fallback. No clipboard fallback exists.
- Native Wayland unrestricted input is not enabled. The current native desktop
  is locked; no attempt was made to unlock it for final acceptance. Isolated
  Xvfb tests must not be reported as GNOME Wayland acceptance.
- Model IDs must be selected/configured and a real key provided. Local HTTPS
  simulated-service tests verify the documented request/response pipeline;
  authenticated Qwen/DeepSeek transcription quality has not been measured.
- Cloud transcription sends the recording to the configured service; optional
  polishing sends its transcript. Local metadata-only statistics/logs do not
  turn this into offline speech recognition.
- Ubuntu24 offscreen container startup proves userspace startup only. A real
  desktop must provide display/graphics, audio, D-Bus, accessibility and a
  usable Secret Service. Container audio-service warnings are expected because
  no audio device or desktop bus is mounted.

## Package evidence

Initial full-app package testing on 2026-10-12 passed all nine Chinese settings
pages under isolated Xvfb, with development Python/library environment removed.
Bundled imports passed for Qt Core/GUI/Widgets/Network/Multimedia/Svg, qasync,
D-Bus, Secret Service, httpx, certifi, cryptography native bindings and Python SSL.
The package is approximately 102.6 MiB after removing unused Qt modules and adding
Noto Sans CJK, utility libraries and license notices. The earlier stage-zero
artifact remains separately preserved at approximately 242 MiB.

Ubuntu24 offline/non-root/read-only full application startup also passed after
the clean-image check identified missing Kerberos libraries (now bundled) and
PulseAudio client libraries (declared desktop baseline). The final frozen artifact was built twice byte-identically (same host,
`mksquashfs 4.7.5`, unchanged inputs), with 107,547,128 bytes and SHA-256:

```text
cb35d203024538a4ee3d55c6ccb8619059ce9f4bfda387fd1b92e2291eec11a4
```

The final artifact passed Ubuntu24 again: `screenshots: 9`, `platform: offscreen`,
`visible: true`, clean exit. Captures are in `build/ubuntu24-qa.c4zzrz` on the
validation host. The bundled font renders Chinese on that image, which does
not install Noto. Inventory verification matched 3,883 regular files, 1,048
symbolic links, 25 runtime distributions and 59 retained Qt attribution pages.

A packaged AppDir pipeline check before the final freeze also passed actual
microphone → locally verified HTTPS ASR/polish → AT-SPI GTK target: exact 28
Unicode code points, overlay focus preserved, cancel and away/back late replies
unchanged. Three RAM WAV captures measured 18,422 / 19,786 / 17,738 bytes; no audio
files or clipboard access. The local service returns fixed text, so this is
pipeline and safety evidence, not live-cloud recognition-quality evidence.
The final AppImage also passed the independent desktop lifecycle driver:
nine 1120×850 pages visually inspected, actual single-instance show/toggle/cancel/
quit commands, clean primary exit, and damaged-config exit with original bytes
preserved. Evidence: `build/ui-acceptance-appimage-final/result.json`.
Independent final-artifact review repeated lifecycle checks with development
`PYTHONPATH`, `PYTHONHOME` and `LD_LIBRARY_PATH` removed, then extracted the exact
image and matched 31 application source files plus all 3,883 inventory hashes.
The extracted image's own Python and packages passed the full microphone → verified
local HTTPS → production Session → AT-SPI GTK workflow on private Xvfb `:92`:
28 Unicode codepoints delivered, overlay focus preserved, cancelled and away/back
late replies unchanged, 3 tasks / 1 success / 2 cancellations, 5/7/12 reported
tokens and real WAV payloads 17,738 / 18,422 / 18,422 bytes. No audio files or
clipboard access. The only external library was xdotool's test-helper library;
application dependencies came from the image.

Final evidence: `build/ui-root-final-appimage/result.json` and
`build/voice-root-final-appimage.json`. All 211 automated tests passed, with one
explicit opt-in microphone test skipped by default; actual microphone capture was
covered separately by the full pipeline. Ruff and formatting checks passed.
See [local validation](local-validation.md) and the
[acceptance checklist](acceptance-checklist.md) for scope and reproduction.
