# Per-task performance timing — 2026-10-15

This module establishes observations, not a measured speed improvement. The base
commit is `96b3b5d424b60b98070ef6c311e830ecdc9cd4a6`. The existing phase 0
Unicode and current-cursor evidence is in [feasibility-report.md](feasibility-report.md),
[current-cursor-input-validation.md](current-cursor-input-validation.md), and
[native-wayland-parent-validation.md](native-wayland-parent-validation.md). Those
reports retain their measured environments and limits. The current machine is
Ubuntu 26.04.1, GNOME/Mutter 50.1; no Ubuntu 24.04 desktop latency result is claimed.

## Observations and integration contract

`Session.performance` emits one metadata dictionary at success, failure or explicit
cancellation. `Session.last_performance` retains the latest terminal dictionary in
memory. The existing `finished` signal and `Statistics.record` arguments are
unchanged. `MainWindow` writes the dictionary through
`DiagnosticLog.record_performance`; it appears in the existing statistics/log page
and the private rotating `$XDG_STATE_HOME/inkecho/logs/inkecho.log` (default
`~/.local/state/inkecho/logs/inkecho.log`). Log files have mode 0600 and existing
128 KB / two-backup rotation. No persistent task history or new configuration is
created.

The schema accepts only a fixed version, fixed terminal outcome, fixed event names
and finite nonnegative numeric milliseconds (bounded to one day), or null for a
missing observation. It accepts neither task UUIDs nor provider/model identifiers,
audio, text, prompts, keys or free-form failure messages. Invalid metadata is
rejected before logging. Existing ordinary log timestamps remain unchanged.

Events are offsets from a per-task monotonic origin:

- Recording started, stop requested, and audio ready (`recording_stopped`). The
  shortcut and all production stop buttons use `Session.stop_recording`, observing
  the stop request before the recorder can synchronously emit its finished signal.
  A test or external caller that directly invokes `recorder.stop` has no observed
  request timestamp: request-based durations remain null, not estimated.
- ASR adapter call started and successful result completed. This boundary includes
  adapter preparation, encoding and network work; it does not claim that bytes
  have already reached the socket. Realtime ASR may mark its start while recording
  is still active. Failed or cancelled requests retain a start and no successful
  completion; the terminal outcome and task-finished timestamp remain available.
- Polishing adapter call started, first nonempty text segment observed, successful
  result completed. The existing nonstreaming adapter has no early segment, so
  the first segment is observed only when its complete text returns. A subsequent
  streaming adapter must mark the first actual nonempty text delta, excluding
  reasoning or usage-only events, and completion after its final event.
- First character dispatched and output completed, followed by task finished.
  Starting `insert()` is explicitly not a first-character observation. Missing
  transport support yields null. A send observation proves dispatch to desktop
  transport, not that a receiving application rendered or accepted the character.

A backend opts in using `supports_first_sent_callback = True` and supports
`insert(..., on_first_sent=callback)`. It calls `callback(sent_at)` after its first
successful character press, where `sent_at` is `time.monotonic()` at the send.
Omitting the optional timestamp uses callback time. For an asynchronous worker,
the worker must return its actual press timestamp; reporting a later ACK as the
press time would include its post-release waits. The parent must validate that
timestamp before forwarding it. Session also rejects non-finite, future or
pre-task values without changing delivery. Duplicate observations keep the first;
late callbacks after cancellation or from replaced tasks are ignored. Cleanup and
key-release events are not text-dispatch observations.

Derived durations include stop-to-first-dispatch, stop-to-output-complete, output
duration from first dispatch through the adapter's cleanup, ASR, polishing, and
stop-to-audio-ready. Null always means unobserved or inapplicable. No zero-filled
guesses or automatically replayed text are introduced.

## Reproducible checks and actual results

Before implementation, the complete original suite passed **509 tests, 2 skipped
in 8.05 seconds**, recorded by the primary agent in
`build/performance-original-suite.log`. An independent rerun passed **509 tests,
2 skipped in 8.01 seconds** (`/tmp/inkecho-timing-prechange-suite.log`). In the
restricted sandbox, localhost socket fixtures are denied: that invocation had
57 setup errors and one socket-related failure. Repeating with permission for
local loopback fixtures passed; this was an environment restriction, not a code
regression.

Run the focused metadata, orchestration, logging and offscreen UI checks:

```sh
.venv/bin/python -m pytest -q tests/test_performance.py \
  tests/test_application.py tests/test_logging.py tests/test_ui.py
```

Actual result: **98 passed in 2.39 seconds**,
`build/performance-timing-tests.log`. These are synthetic/headless tests: controlled
clocks, fake providers, fake recorders and simulated keyboard dispatch. Coverage
includes partial failure/cancellation, duplicate and stale callbacks, preserving
ordinary statistics, exact stop-request ordering, absent send observation, actual
worker-style timestamps excluding ACK delay, no sensitive schema fields, strict
numeric validation, and cancelling network tasks before closing the shared owner.
Changed Python files passed Ruff lint and formatting. Subsequent integrated suite
results belong in the primary integration report, not retroactively in this count.

Run the reproducible orchestration baseline (no microphone, credentials, external
requests or real keyboard events):

```sh
PYTHONPATH=src .venv/bin/python scripts/validation/performance_baseline.py \
  > build/performance-synthetic-baseline.json
```

The script uses a private temporary configuration; 3 samples, 10 fixed synthetic
Unicode characters, an artificial 150 ms ASR wait, 100 ms polishing wait and
120 ms per character. The fake keyboard observes a synthetic press after its first
40 ms wait. Actual medians on this machine were **291.323 ms stop-to-first,
1164.244 ms output duration, 1455.822 ms stop-to-output-complete**. These numbers
verify boundary accounting against explicit delays; they are **not** real cloud,
microphone, desktop, Ubuntu 24.04 performance or evidence of an improvement.
The JSON labels itself `synthetic_headless`, `desktop_validated: false`,
`cloud_validated: false`. `--no-polishing`, `--asr-ms`, `--polish-ms`,
`--char-ms`, `--characters`, and `--samples` allow repeatable comparison. Scheduler
overhead means observations are not expected to equal the artificial sleeps.

For a real desktop/cloud baseline, run the changed application with its normal
private credentials, use an owned empty test field, speak the same fixed sample,
and stop with Ctrl+F4 or the stop button. Read the fixed-schema `performance` log
entry. Record OS/session, backend, provider protocol, sample count, output codepoint
count, exact-text comparison and cancellation/map-restoration checks separately;
do not include credentials, audio or recognized text in timing logs. A null
first-dispatch field is not a zero-latency measurement. Measure native Wayland
and X11 separately, and only report Ubuntu 24.04 after actually testing it there.

## Remaining work and boundaries

This module changes no keyboard pacing and implements no realtime/cloud stream.
Actual first-press callbacks must be supplied and verified by each keyboard
adapter. It also does not establish authenticated cloud latency or microphone
quality. Future realtime and streaming modules reuse the fixed observations and
must preserve task-ID, deadline and cancellation guards. Existing phase 0 scope
limits still apply. No push, tag, release or deployment was performed for this
module.
