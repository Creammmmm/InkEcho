# Core task safety validation

The first core module implements a single active task with an opaque captured
target, unique task ID, bounded lifetime, and explicit asynchronous completion.
It is independent of Qt and supplier HTTP details. No desktop backend is wired
to this module yet; the tests use deterministic mock adapters and **do not
establish real desktop injection safety**.

## Adapter contract

The orchestrator asynchronously captures a target, then calls `begin(target)`.
Target identity includes a focus generation that becomes invalid on every
focus transition, including switching away and back to the same window.
`target_is_current` checks cached invalidation without blocking the event loop;
the backend must refresh actual focus immediately before delivery as well.

`InputPort.inject(task_id, target, text, can_continue)` dispatches asynchronous
work and returns immediately. The bridge awaits the backend operation and calls
`injection_finished(task_id)` or `injection_failed(task_id)`. Until then, the task
remains `INJECTING`. The backend must call `can_continue` before every delivery
chunk and revalidate its target; this does not make global simulated keystrokes
safe or authorize an unverified fallback. Clipboard operations are prohibited.

Every provider reply carries the original task ID. Cancel invalidates that ID
immediately, drops the retained original text and target, reports `CANCELLED`,
then returns to `IDLE`. Late callbacks cannot affect a newer task. Terminal
notification callbacks cannot restart a task until the previous transition
finishes. Focus changes permanently cancel the task. An event-loop timer must
call `tick()` while waiting to enforce deadline/focus invalidation. Default
whole-task lifetime is 180 seconds, configurable within 1–600 seconds.

`recording_stopped`, `transcribed` and `polished` only accept results in their
matching states. Blank transcription fails. Polishing failure or blank output
uses original transcription by default; disabling fallback fails instead.
Failures retain only fixed categories, not exception messages, transcripts or
credentials. A successful task is reported only after matching injection
completion.

## Reproduce

```sh
uv run pytest -q tests/test_core.py
```

Measured 2026-10-12: core and recorder unit suites together passed 37 tests,
with one opt-in real microphone test skipped in the ordinary run. Coverage
includes unique IDs, concurrent start rejection, the success sequence,
cancelled/stale/out-of-order callbacks, focus changes at recording/transcribing/
polishing boundaries, last-moment focus loss, cancellation during chunked
delivery, delayed injection completion, late completion after a newer task,
whole-task timeout, blank results, polishing fallback enabled/disabled,
sanitized adapter failures and terminal-state callback reentrancy, and observer exceptions during terminal/idle
notifications. Observer exceptions propagate while the task is released and the
controller returns to IDLE, so subsequent work remains possible.

This module does not call cloud APIs or manipulate a real target. Provider
workers, qasync orchestration, focus event subscriptions and actual targeted
injection require their own integration acceptance before application use.
