# Local delivery validation

Date: 2026-10-12. This record supports the repository's exact-commit pre-push
receipt; generating a receipt reruns the automated checks on committed clean HEAD.
It does not convert fixture results into untested desktop compatibility claims.

## Automated checks

```sh
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m pytest -q
```

Independent root review: Ruff and formatting checks passed, **211 tests passed,
1 opt-in microphone test skipped**. Real microphone use was additionally exercised
in the integrated pipeline below. Tests requiring local sockets/thread wakeups ran
in an authorized local environment; restricted-sandbox `EPERM` wakeup failures were
not hidden by application changes.

## Actual final artifact

- File: `dist/InkEcho-0.1.0-alpha-x86_64.AppImage`, 107547128 bytes.
- SHA-256: `cb35d203024538a4ee3d55c6ccb8619059ce9f4bfda387fd1b92e2291eec11a4`.
- Two complete unchanged-input builds matched byte-for-byte on this host.
- Independent extraction matched 31 application source files and all 3883
  inventory regular-file hashes. Packaging review also verified 1048 symlinks,
  25 runtime distributions and 59 retained Qt attribution pages; no symlink escaped
  the AppDir.
- Full application started in Ubuntu 24.04 userspace, nonroot/read-only/network
  disabled, rendering nine pages with bundled Chinese fonts. This is not a desktop
  input/audio/shortcut test. Independent final recheck exited 0 with nine pages
  in `build/ubuntu24-qa.ugphfK`, without host home, audio or credential mounts.

## Actual GUI and process checks

The final artifact was launched with development Python/library environment cleared
on private Xvfb `:92`. Nine pages rendered, secondary processes delivered show,
toggle, cancel and quit, primary exit was 0, and damaged disposable configuration
returned exit 1 with original bytes intact. Independently repeated on `:91`, with
all nine 1120×850 screenshots visually inspected. The README screenshot comes
from that exact artifact, not a mockup.

Reproduce with `scripts/validation/desktop_app_probe.py --appimage ARTIFACT
--output NEW_DIRECTORY` on a private test display. Evidence:
`build/ui-root-final-appimage/result.json` and
`build/ui-acceptance-appimage-final/result.json`.

## Actual packaged voice pipeline

The exact extracted artifact's Python and packages ran
`scripts/validation/voice_workflow_probe.py` on private Xvfb `:92`. It used the real
microphone/Recorder, production Session, TLS-verifying ProviderClient, real AT-SPI
GTK target and production Overlay. A temporary localhost provider returned fixed
text; credentials were disposable injected test values.

- WAV payloads: 17738 / 18422 / 18422 bytes, valid 16 kHz mono PCM.
- Exact 28-codepoint Chinese/mixed Unicode sample delivered after ASR and polishing.
- Cancellation and focus-away-back during delayed replies left the target unchanged.
- Overlay retained target focus; buffers/resources released; no audio files.
- Statistics: 3 recordings, 1 success, 2 cancellations; reported tokens 5/7/12.
- No clipboard access; no user application/document modified.

Evidence: `build/voice-root-final-appimage.json`. A separate source run and
pre-freeze packaged AppDir run also passed. Only xdotool's helper library came
from outside the final bundle; application libraries came from the image. The
clean-environment GUI launch separately verifies bundle startup dependencies.

## Remaining acceptance boundaries

Native Wayland input remains disabled, physical/native shortcut activation is
unverified, Chromium/VTE targets lacking EditableText remain unsupported, and the
full Ubuntu 24.04/26.04 desktop matrix remains incomplete. No real cloud account
recognition-quality test was performed. The locked native session was not unlocked
or bypassed. This deliverable is an explicitly limited Linux development preview.

Detailed scope: [acceptance checklist](acceptance-checklist.md),
[application validation](application-validation.md),
[release notes](release-notes.md), [packaging](packaging.md).
