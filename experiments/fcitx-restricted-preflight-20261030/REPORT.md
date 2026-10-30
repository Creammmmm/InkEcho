# Restricted Fcitx preflight fallback validation

On 2026-10-30, the actual Python router was exercised locally using fake Fcitx
and keyboard backends. This is an offline policy test, not an Ubuntu desktop,
real input method, permission portal, or packaged application acceptance test.

Before the change, the new restricted-state cases failed: after a Fcitx connect
failure the router connected and authorized the keyboard before rejecting the
fallback. The change rejects the fallback immediately after bridge cleanup when
keyboard fallback is forbidden. It does not enable an additional output path.

Reproduce with the project development environment:

```sh
python -m pytest -q tests/test_fcitx_preflight_restricted.py tests/test_output_router.py tests/test_fcitx_owned_handoff.py tests/test_owned_upgrade_diagnostic.py
python -m ruff check src/inkecho/platform/output_router.py tests/test_fcitx_preflight_restricted.py
python -m ruff format --check src/inkecho/platform/output_router.py tests/test_fcitx_preflight_restricted.py
```

The four test files passed 143 tests; lint and formatting checks passed. The
new tests cover enabled/unknown restricted states, absent/disabled permitted
fallback, changed owner, cleanup exception and failure flag, cancellation while
cleanup is suspended, and successful Fcitx selection. They assert no bridge
commit, keyboard connection or authorization on restricted failures. Earlier
composition guards, cleanup diagnostics, and task cancellation remain in force.

These mocks cannot establish desktop capability or prove Ubuntu 24.04/26.04
compatibility, GNOME Xorg behavior, real preedit protection, or input delivery.
