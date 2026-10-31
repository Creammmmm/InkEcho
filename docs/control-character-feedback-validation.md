# Streaming control-character feedback validation

On 2026-10-31, a synthetic provider was used with the real `Session` and an
isolated Qt offscreen window. No microphone, cloud request, system notification,
or actual input target was used. The output transport was a test double.

Run from a development environment:

```sh
QT_QPA_PLATFORM=offscreen TMPDIR=/var/tmp python -m pytest -q \
  tests/test_application_streaming.py tests/test_streaming_output.py
```

The test checks that a tab at the beginning yields no text and a specific error
in the real Qt status bar and visible in-app error notice. For a tab after a
confirmed prefix, the prefix is not replayed, including when original-text
fallback is enabled. Before any attempted output, the configured original-text
fallback is still used. CR and LF normalization and rejection of unsupported
control characters remain covered by the streaming tests. Actual cloud provider
responses and Wayland desktop notifications were not tested here.

Result on the isolated checkout before the commit: 69 tests passed; Ruff lint
and formatting checks passed. Full exact-commit checks are recorded separately
by the local validation workflow before push.
