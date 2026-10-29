# Fcitx capability ownership cleanup validation

This records source-level validation on 2026-10-30. It is not a new AppImage,
standalone addon qualification or arbitrary desktop support claim. The native
Begin4 protocol and ELF are unchanged by this Python resource-lifetime fix.

## Fault and fix

The capability client previously closed its token inode descriptor immediately
after publication and retained only `(st_dev, st_ino)`. On the project's ext4
filesystem, unlinking that file and creating a foreign regular file or symlink
could reuse the same identity. Cleanup then wrongly removed the replacement.
The original tmpfs experiments did not demonstrate that reuse and are preserved
unchanged under `experiments/fcitx-auth`.

The production client now retains the descriptor until cleanup, preventing inode
reuse while the task owns it. Cleanup additionally requires a regular file,
checks identity without following symlinks, closes capability/lock/directory
descriptors through nested `finally` blocks, and clears identity and token even
when cleanup raises. This does not claim an atomic compare-and-unlink guarantee
against malicious same-UID path replacement after the identity check.

## Actual observations

Independent checks on the unpatched production client reproduced incorrect
removal for three symlink and three regular-file replacements on ext4. Six
controls holding the original descriptor preserved replacements. The fixed
client's maintained tests then passed on both tmpfs and the same ext4 filesystem:
normal/exclusive ownership, crash recovery, foreign stale files, unsafe runtime,
failed publication, stat/unlink cleanup failure, live unlinked inode retention,
regular/symlink replacement and deliberately matching symlink identity.

An independent synthetic fault check closed each of the three descriptors and
then raised an error. All three variants still closed the other descriptors,
cleared fields/token and allowed harmless repeated cleanup. Combined capability
and fault checks: **14 passed in 0.24 seconds on ext4**. The larger related
capability/protocol/cancellation/IBus source regression selection passed **89
checks in 2.68 seconds** using a private short tmpfs directory. These are offline
checks; no host input service, user configuration or real provider was changed.

Original observations are retained locally in
`/tmp/inkecho-product-r2-review/production-inode-reuse.json` and
`/tmp/inkecho-product-r2-review/PRODUCTION-CAPABILITY-REVIEW.md`. These local paths
are supporting review records, not required inputs to the maintained tests.

## Reproduction

Use the development interpreter and an unused private directory for each run:

```sh
.venv/bin/python -m pytest -q tests/test_fcitx5_capability.py \
  --basetemp /run/user/1000/inkecho-capability-test-UNIQUE
```

Replace `1000` with the actual user ID and `UNIQUE` with a fresh name. For the
filesystem comparison, rerun only this capability suite with a new private
`--basetemp` under the project's ignored `dist` directory on ext4. Do not reuse a
directory containing evidence or user data: pytest owns its base temporary tree.
No mocked test should replace the real descriptor/regular-file assertions.

The earlier full workflow failure at `dec26e2` remains in ignored
`dist/validation-0.11.2-dec26e2/workflow.log`. Its deep ext4 temporary root also
exceeded the UNIX socket pathname limit for unrelated IBus tests. Final complete
workflow checks must use a short private runtime temporary root, retain that
failed log, and generate a receipt for the exact final clean commit. Switching
temporary filesystems alone does not fix the production inode-ownership defect.
