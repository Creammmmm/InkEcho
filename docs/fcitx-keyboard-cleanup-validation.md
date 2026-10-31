# Fcitx to keyboard handoff cleanup validation

The automatic route may fall back to simulated keyboard input only after a
Fcitx task reports a verified zero-attempt, no-target result. If closing that
bridge fails, the handoff stops, reports cleanup failure, and does not connect
or send through the keyboard. Cancellation and deadline expiry take precedence.
The bridge is detached before its one close so scope teardown does not close it
again and mask the original failure.

Local automated validation, 2026-10-31:

```sh
TMPDIR=/var/tmp .venv/bin/python -m pytest -q \
  tests/test_output_router.py tests/test_fcitx_owned_handoff.py \
  tests/test_streaming_output.py
```

Result: 175 passed. The fault-injection cases cover cleanup failure, stop,
deadline expiry and asynchronous cancellation. An integration test uses the real
Fcitx Python bridge and capability file with a simulated D-Bus service: it
returns no target, leaves remote Cancel unanswered until the bridge timeout,
and injects unlink failure. The test observes timeout cancellation, one cleanup
diagnostic, bus disconnection, released capability lock and no keyboard output.

This is not a real desktop or remote-service test: a timeout cannot establish
that a real service processed Cancel. The production bridge's default remote
Cancel timeout is three seconds, and an unlink failure may leave the capability
file behind; the local descriptors and lock are released even on that failure.
