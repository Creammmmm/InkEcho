# Fcitx cleanup stop status validation

The output scope previously reported `input_cleanup_failed` if the Fcitx
capability cleanup failed after cancellation or expiry happened while awaiting
the bridge's Cancel reply. This focused change observes the last output task's
status after that wait if the output body had no existing exception. A stop
result retains the number of acknowledged dispatch attempts, and cleanup
failure is separately reported. Broken status callbacks do not invent a stop;
existing output errors retain priority. No text is replayed.

## Reproduction and result

From the project checkout with development dependencies installed:

```sh
TMPDIR=/var/tmp .venv/bin/pytest -q tests/test_fcitx5.py tests/test_fcitx_owned_handoff.py tests/test_fcitx_preflight_restricted.py
```

150 passed. The added parameterized test uses the production `Fcitx5Bridge`,
a controlled fake D-Bus peer, one already dispatched character, a delayed
Cancel response, and injected capability cleanup failure. It checks cancellation,
expiry, a still-active task, and two callback exception types; the original
character is committed exactly once and the connection is closed. This is a
synthetic protocol test, not a desktop or actual package acceptance. A request
already in flight cannot be withdrawn and dispatch acknowledgment is not proof
of target delivery. This change does not solve IBus Xorg compatibility.
