# InkEcho 0.1.0-alpha — Linux preview

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
