# In-memory recorder validation

`inkecho.audio.Recorder` records mono signed 16-bit PCM and emits a WAV payload
entirely in memory. It supports explicit device IDs, 16/24/48 kHz requested
rates, RMS levels, empty-recording errors, bounded duration and byte count,
cancellation, device errors, and cleanup. Unsupported device formats fail
explicitly; no implicit format conversion is claimed. Default format is 16 kHz
mono Int16. Default maximum duration is 120 seconds; accepted bounds are
0.1–300 seconds. There is no audio file output.

`start` refuses a second recording. `stop` drains remaining input, releases the
source and returns/emits WAV bytes plus measured sample duration. `cancel`
discards samples without emitting a successful result. Timeout and interruption
stop recording, discard memory and emit one fixed error code. The caller owns
any returned WAV bytes and must release them after its bounded network task.

Qt 6.12's deprecated `QAudio.Error` compares unequal to the actual returned
`QtAudio.Error` despite identical numeric values. Live testing exposed this;
the implementation uses `QtAudio`. Qt's legacy `QAudio::State` signal also
failed Python argument conversion in this environment, so a 50 ms event-loop
timer checks source error/state instead. The recording-duration timer and byte
limit bound capture independently. No blocking wait occurs in the recorder.

## Reproduce

Unit tests (mock devices, real WAV parser):

```sh
uv run pytest -q tests/test_audio.py
```

Opt-in real device test in an authorized desktop session:

```sh
INKECHO_TEST_MICROPHONE=1 timeout 20 uv run pytest -q -s \
  tests/test_audio.py::test_live_repeated_same_process_capture
```

The live test records three short snippets in the **same process**, validates
WAV headers and nonempty frames, and discards each payload. It then verifies
cancel/restart and maximum-duration failure/restart. It reports only numeric
metadata. Restricted agent sandbox audio sockets are inaccessible; the measured
live run used desktop audio access outside that sandbox.

Measured 2026-10-12 on Ubuntu 26.04.1 / GNOME Wayland / Logitech G PRO X Gaming
Headset: three 16000 Hz mono Int16 captures, durations 0.7023125, 0.7023125 and
0.659625 seconds; cancel/restart and timeout/restart passed. No audio was saved.
The final run passed in 2.65 seconds with no Qt signal conversion errors.

Unit checks cover correct WAV sample preservation, incomplete/empty frames,
source release, empty recording, device errors, duplicate start, missing device,
unsupported format, synchronous start failure, bounded capture memory,
idempotent late timeout handling, and cancellation without a result. Together
with the core suite: 37 passed, one opt-in live test skipped; the separate real
test passed. This does not validate cloud recognition quality, every microphone,
device unplug/replug, or long-duration stability.
