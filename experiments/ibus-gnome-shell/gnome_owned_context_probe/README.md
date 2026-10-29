# GNOME-owned IBus context identity: bounded research

2026-10-29, Ubuntu 26 isolated virtual seat, GNOME Shell 50.1. No text dispatch, keyboard events, clipboard, surrounding-text reads, engine changes, host GUI or host IBus connections. Docker network none, QEMU restrict=on; original stopped backing readonly. Shared project worktree unchanged.

`actual.log` preserves the first fixture failure: extension bus name had not yet been acquired; no receiver created. `run_wait.py` adds bounded name acquisition wait. `actual-r2.log` and `raw26.tar` retain the successful second run. Standard session D-Bus owner PID 1404 resolved to root-owned /usr/bin/gnome-shell. Own actor 2393 exited normally 0.

## Observations

- Native GTK entry using Shell input method: authenticated Shell-created context `_2` matched actual current IBus context `_2`; candidate twice, including restored state.
- Genuine GTK IBus entry, simple entry and button: currentFocus false; not_applicable. This gate does not identify GTK-owned IBus contexts and does not mean those controls lack IBus support.
- A separately created synthetic client named `gnome-shell`: Shell path remained `_2`, current context became `_4`; rejected context_mismatch. Client-name spoofing alone cannot pass this own-path comparison.
- After destroying own synthetic context and moving button→native, current `_2` matched again.
- Ten offline tests exercise the exact gate.js, including mismatch, native/focus/ShellUI and preedit true/unknown rejection.

## Limits

This is a read-only identity-scope prototype, not a product route or universal capability detector. No text was submitted; it proves neither delivery nor target receipt, lossless pending-focus behavior, live preedit protection, cancellation while dispatching, GTK-owned context identity, Ubuntu24/Shell46 support, packaged integration, or arbitrary applications. currentFocus and own context are GNOME private implementation details. Same-window widget changes need not advance focus-window epoch; asynchronous sampling cannot become a target receipt. Do not enable automatic selection from this evidence. ReadAsync prototype also lacks handling of a synchronous throw when starting current_input_context_async; this must be hardened separately before integration, not silently folded into the tested source pin.

## Cleanup

`cleanup.log` preserves a cleanup inspection error: ibus CLI had insufficient desktop environment and returned no bus; settings themselves had restored. `cleanup-r2.log` uses actual guest user-manager environment, confirms extensions empty, idle-delay300, lock-enabled true, engine xkb:us::eng, actor absent, temporary extension removed. `restored.json` is in raw26.tar. `poweroff.log`: normal poweroff and original docker wait0. `final-container.json`: exited0, Running false, OOMKilled false. No further samples run.

## Review use

`experiment.patch` only adds a unique research directory and is checked with git apply --check; it is not applied. Runner has exact disposable lab machine-id guard. Never run it against a user's desktop. vm_lab.py is retained as raw reproducibility context, not general deployment tooling.
