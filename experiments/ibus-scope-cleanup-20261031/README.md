# IBus scope cleanup failure validation

This is a synthetic local regression against source commit `6cadd2d`, not a
desktop or AppImage acceptance. It uses real `IBusBridge` implementations and
real temporary `Capability` files with a synthetic client/D-Bus boundary.
File deletion is fault-injected; no actual user input or credentials are used.

Before the change, eight legacy/owned scope cases (cleanup after provider
failure, attempted output, cancellation, or expiry) failed because the cleanup
exception replaced the original result. A real Session with legacy IBus also
sent the original text after a provider failure cancelled the consumer and its
capability cleanup failed. A separate explicit owned-route Session similarly
reprepared the route after this fault. These are controlled reproductions, not
proof of an actual user's delivery history.

The fix classifies uncertain IBus scope cleanup as an input failure and records
the affected consumer task in a weak set. Session checks its own consumer after
stopping it: a cleanup fault suppresses original-text fallback even when
cancellation was preserved. Overlapping cleanup of an earlier task does not
suppress a later independent task's fallback. This marker is not evidence that
a target received text. Attempted counts and uncertain dispatch remain intact.

On 2026-10-31, the following was run from an isolated `/tmp` source copy with
`QT_QPA_PLATFORM=offscreen`, Python 3.13.15 and `TMPDIR` under `/tmp`:

```
python -m pytest -q tests/test_explicit_owned_scope_cleanup.py \
  tests/test_ibus_scope_cleanup_regression.py tests/test_application_streaming.py \
  tests/test_fcitx5_install.py tests/test_fcitx5_staging.py --tb=short
```

Result: **128 passed**. The added tests include both IBus bridge variants,
actual capability file fault injection, overlapping tasks, partial dispatch,
expiry, cancellation, owned preflight and no replay. Ruff lint and formatting
checks passed for the changed source and test files.
The isolated tests use synthetic clients and a synthetic provider; they do not
verify an actual GNOME shell, remote service, microphone or target application.
Temporary capability files can remain if unlink really fails. Cleanup fault
marking does not remove or resolve that filesystem fault.
