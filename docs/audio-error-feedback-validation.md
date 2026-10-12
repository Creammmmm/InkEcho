# Audio failure feedback and read-only diagnosis

Date: 2026-10-13. This investigation did not record microphone audio, upload
audio, access API keys, or change the user's recording preferences.

## Observed audio configuration

Read-only Qt device enumeration and saved recording preferences reported:

- Three input devices; the application uses the system default input.
- The selected device exists and accepts mono signed 16-bit audio at 16 kHz.
- The configured recording limit is 120 seconds.
- `wpctl get-volume @DEFAULT_AUDIO_SOURCE@` returned `Volume: 0.70` without a
  muted flag.

These metadata checks do not establish that useful sound reaches the microphone.
The desktop was locked during this investigation, so native editor interaction
was not tested. The recorder has no voice-activity or silence-based automatic stop.
Its existing end conditions are explicit stop/cancel, the duration or byte limit,
and an audio-source error or stopped state. No new silence threshold, all-zero
audio rejection, or change to those end conditions was introduced.

## Confirmed feedback defects

The recorder already emitted specific fixed errors for missing devices,
unsupported formats, startup failures, interruptions, empty input and the maximum
duration. `Session._audio_failed` discarded that reason and reported only a generic
audio failure. `Session.sample_audio` also discarded it; its synchronous failure
path could leave the future's exception unconsumed. Finally, the settings-page
exception handler replaced microphone-test errors with a generic message.

The repair preserves known codes and their fixed Chinese explanations. Unknown
reasons map to `audio_failed` without exposing their contents. A failed task emits
one specific notification and diagnostic, clears the stored reason on termination,
and cannot reuse it in a later task. Microphone tests preserve the same safe
reason and consume their result future, including synchronous failures. The test
page displays the specific explanation. No audio data or arbitrary exception
contents are added to logs.

## Local validation

```sh
.venv/bin/python -m pytest -q \
  tests/test_application.py tests/test_ui.py tests/test_audio.py tests/test_logging.py
```

Result: **65 passed, 1 skipped**. The skipped test is the explicitly opt-in live
microphone test and was not enabled. The new regressions cover specific failure
codes, safe treatment of unknown reasons, a single task notification, synchronous
and later microphone-test failures, no unhandled-future exception, cleanup between
tasks, and the actual settings-page error handler. They use fake recorder events,
isolated configurations and the offscreen Qt backend. Ruff lint and formatting
passed for the four changed code and test files.

This fixes a demonstrated loss of diagnostic detail; it does not establish that
the user's current failure originated in the microphone. Packaged acceptance is
recorded separately in the release validation report.
