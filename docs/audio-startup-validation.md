# Audio startup and input consent validation

2026-10-20, source changes for 0.5.3. This is source-level validation, not
AppImage acceptance or a claim about cloud recognition accuracy.

## Findings and change

The old toggle awaited desktop keyboard connection and consent before opening
QAudioSource. Speech spoken during that permission wait could never enter the
recording. Recording now starts after configuration and credential validation,
while the same task's input consent proceeds concurrently. Denied or cancelled
consent stops recording and discards the task. Text cannot be dispatched before
that task's consent succeeds; ASR final completion and cancellation gates remain.
The first recording can consequently be capturing while the desktop consent
prompt is displayed. Configuration and credential loading still precede capture.

QAudioSource can buffer data before readyRead is connected. The recorder now
drains that first available buffer immediately. It requests a 20 ms buffer;
backends may select another size, so this is not a startup latency guarantee.
The recording readiness signal means a complete PCM sample has been received,
not that speech is audible or the cloud has recognized it. Preparation and first
sample readiness have distinct UI signals. Synchronous cancellation or source
replacement from capturing/level callbacks cannot forward old PCM to a new task.

## Reproduce and actual results

Run from the project environment:

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q tests/test_audio.py tests/test_application.py tests/test_application_realtime.py tests/test_application_early_realtime.py tests/test_realtime_preview.py tests/test_application_streaming.py
.venv/bin/ruff check src/inkecho/audio.py src/inkecho/app.py tests/test_audio.py tests/test_application.py tests/test_application_realtime.py scripts/validation/audio_onset_probe.py
```

The implementer observed 126 passing tests and two opt-in microphone tests
skipped, including actual loopback TLS WebSocket/HTTPS/SSE checks. A subsequent
level-callback replacement regression adds one passing case. The root reviewer
independently observed 287 passing related tests and two skips. Tests require
local socket and worker-thread permissions; the restricted sandbox's bind failure
and stalled credential-thread run were not interpreted as product failures.

Synthetic tests preserve startup PCM without a later readyRead notification,
cover split 16-bit samples, ensure readiness occurs once per capture, stop timers
on reentrant cancellation, and reject old data after source replacement. A delayed
consent test captures the beginning, stops, and completes ASR while still emitting
zero characters; authorizing then permits output. Denied and cancelled consent
produce zero output and close their streaming resources.

`scripts/validation/audio_onset_probe.py` is an optional metadata-only desktop
probe. It creates uniquely named virtual PulseAudio-compatible nodes, selects
only its explicitly named synthetic source, plays generated PCM into its own
sink, records first-frame/marker times for three runs, removes only module IDs it
created, and checks that system default devices remain unchanged. It writes no
audio or transcript. It was not run on this host because pactl/paplay are absent;
no dependencies were installed. This tool has not established physical-device
onset timing on either Ubuntu version.

## Limits and separate protocol finding

No real microphone, user speech, live cloud request, or recognition-accuracy
benchmark was used. Ubuntu 24.04 on another machine can have different device,
network and model settings; no exact latency or accuracy improvement is claimed.

The selected local configuration was checked through a strict metadata allowlist:
Qwen realtime at 16 kHz, cloud polishing disabled. Credentials were not read for
this investigation. Existing Qwen manual mode commits only on stop, and therefore
does not guarantee recognition drafts during recording. That protocol issue needs
a separate bounded multi-utterance server-VAD implementation and validation; this
audio fix does not claim to solve it or remove the final output barrier.
