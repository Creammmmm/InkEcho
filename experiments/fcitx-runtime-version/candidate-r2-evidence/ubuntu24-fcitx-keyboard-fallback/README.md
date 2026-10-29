# Real Fcitx no-target to X11 keyboard, Ubuntu 24

The isolated Ubuntu 24.04 Xorg guest used candidate AppImage SHA-256
`f6378650f230215a0ff0a7196a80ddc48e9429e2546b55afe40105d8a5889d05`.
Its installer started the actual Fcitx bridge in private data directories. The
package Session ran automatic routing against owned GTK3 simple text views,
with synthetic audio/transcription and no clipboard or real credentials.
Instrumentation wrapped the real bridge and keyboard calls solely to record
selection, Commit replies, errors and ordering; it did not change their results.
Each probe run uses a new task; r8, r9, r11 and r10 use different fixed synthetic
texts, and no uncertain task was replayed.

In r7, the full 200-character Chinese sample, one A/B 1/199 natural switch,
and one cancellation after A's first character passed. Each recorded Fcitx
selection, real Commit result 3, `no_target` with accepted=0, offset=0 and
uncertain=false, followed by real keyboard insertion. Cancellation retained one
already-sent character. The other switch failed safely with `delivery_unknown`,
accepted=0 and uncertain=true, no output and no keyboard fallback. The runner
exited 0 but the failed fixture is explicitly not a pass.

r8 repeated independently: full and one switch failed with a Commit coroutine
`CancelledError`, converted to `delivery_unknown`; the other switch and cancel
passed the same real no-target-to-keyboard branch. r9 again had one failed switch,
its Commit coroutine cancelled after 0.3ms; full, other switch and cancel passed.
In r11, tracing the real `asyncio.wait_for` budget showed one failed switch's
last three budgets were 23.394ms, 11.848ms, 0.593ms; the last call was cancelled
after 1.1ms and became `delivery_unknown`. The other three r11 cases passed.
The source limits each retry by the remaining 0.5s focus grace, accounting for
this dangerously short final budget. This identifies the deadline truncation;
it does not prove all possible unknown deliveries have the same cause.

The proposed source fix treats focus grace as the deadline to start a new Commit,
not the confirmation budget of one already started. It retains the normal
per-request timeout, task deadline and cancellation checks; ambiguous replies
still fail closed without retry or fallback. In r10 the same extracted candidate
was overlaid only with the fixed `fcitx5.py`, SHA-256
`bf07c2476489590ba56f6ea20d5c65dea15b7f410394bf0efc443806856cfee1`.
All four fresh tests passed: full 200 characters, two natural A/B 1/199 switches,
and cancellation with one already-sent prefix character. Each explicitly
recorded the real no-target/zero-accepted result before keyboard use. Traced
Commit budgets were 3.0 seconds (the normal bridge timeout, also bounded by the
task deadline), not a shrinking grace remainder. A genuinely nonresponsive
Commit can now wait longer before reporting uncertainty. r10 is a source overlay,
not a newly built or accepted AppImage. Fcitx unit tests passed 38/38 and full
Ruff passed at the time of this experiment.

All raw scripts, service and test logs are retained under r7–r11, `.txt` added
to code file extensions. To reproduce, copy a version's scripts to `probes/`
under its `root` path, remove `.txt`, copy the same AppImage beside `probes/`,
then run its `run.sh` in an isolated Xorg guest. Each runner uses and verifies
the guest's existing Xauthority, starts a private Fcitx instance and restores
session variables. r10 additionally overlays the recorded source copy. Keep
failed logs: shell exit 0 does not mean every fixture passed. End-of-run checks
found no Fcitx process or owner, restored IBus environment, and removed private
test files; the guest then shut down normally and container exit was 0. This is
not dual-system package acceptance, nor does it establish arbitrary cross-app
or post-prefix fallback behavior.
