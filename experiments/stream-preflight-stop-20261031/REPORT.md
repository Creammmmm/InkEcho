# Streaming preflight stop validation

The output router is exercised locally using fake input backends. If an automatic
stream preflight fails after consuming its pending selection, a caller that catches
the error must not send further fragments in that scope. Before this fix, the new
restricted Fcitx regression failed because a subsequent insert reached the keyboard
substitute. The fix marks the output scope failed on preflight errors and stops.
It does not change the choice of output backend or authorize an additional route.

Reproduce in the project development environment:

```sh
python -m pytest -q tests/test_fcitx_preflight_restricted.py tests/test_output_router.py tests/test_fcitx_owned_handoff.py tests/test_owned_upgrade_diagnostic.py
python -m ruff check src/inkecho/platform/output_router.py tests/test_fcitx_preflight_restricted.py
```

The four files passed 149 tests and lint passed. New cases cover restricted
preflight failure, a stopped predicate, actual task cancellation while detection
is pending, deadline expiration, and cancellation during bridge cleanup. They
assert that no text is sent in the same scope after catching the stop and that a
separate next task can still output. The bridge and keyboard are substitutes;
this is not a real desktop, Portal, input-method or package acceptance test. The
regression demonstrates a caller-recovery path and does not establish that the
ordinary application UI catches and retries this error.
