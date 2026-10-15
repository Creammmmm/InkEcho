# Ubuntu 24 source R8 output-session validation

Status: the three source checks completed naturally and root independently
accepted their raw results, origins and payload identity. The paced case
restored mapping once and a fresh GTK window became ready in 0.1734 s. This is
source evidence; the unchanged existing a12 AppImage is not repaired by it.

## Why this check exists

The actual a12 paced-arrival diagnostic delivered all 150 codepoints accurately
but retained 288 mapping writes/150 restorations and delayed a fresh GTK window
by 5.8435 seconds. Its functional gate passed; its responsiveness problem did
not. See [the original counterexample](performance-a12-paced-validation.md).
R8 changes the production X11 mapping lifetime for one streaming consumer task;
validation must exercise that actual Session path without a candidate wrapper.

## Frozen source and dependencies

- Source version remains `0.1.0a12`, but source hashes differ from that artifact.
- Root-reviewed `src/inkecho/app.py` SHA256:
  `d4e58b4cb6de9ceed5d471574bc32e6a1cf255b125e93eb49838ed41146482bd`.
- Root-reviewed `src/inkecho/platform/keyboard.py` SHA256:
  `03e67f372bc669f279b135f3f4a73db6bafb4b30c2a862a83292e72ce11f968a`.
- All other 41 source files match fixed product commit
  `06f5600a57402335e97b3975afc38009d6233e58`; queued coalescing remains
  `c46eb6e13627067d9c918415defe57eb93898f30e3e57795ed9c828edab89ce1`.
- Independent root-focused regression: 228 tests passed in 0.81 s; six related
  files (two production, two tests, two new tools) passed Ruff/format. This is
  not a full workflow receipt for a committed new release.
- Separate source snapshot:
  `build/ubuntu24-perf-vm/input/source-r8-output-session/manifest.json`, SHA256
  `68a9823eec29c38b0f7cfae572eb3ba19689e5c23b883e85f3b1f3976e22eb93`.
  It contains all 43 source audit hashes and seven tool/license hashes.
- Dependencies are the actual unchanged a12 package, SHA256
  `e31dbc6301318ab10632c12a7437ae7cd01482f2b1ee39655a82e43b6900eae9`,
  using `/home/inkecho/inkecho-a12-runtime-r1/squashfs-root` in the guest.
  Its full inventory and both WebSocket licenses are checked before execution.
  Production application modules must load from the new source snapshot;
  websockets and Python/Qt load from this separately audited dependency package.

Preparing inputs requires the two root-approved source hashes. Missing hashes
were verified to reject before creating a snapshot. The source entry checks ten
application origins, including Session, streaming output and keyboard, against
the new manifest and checks websockets against the old package inventory.
The runtime is explicitly `source`.

## Regression environment

Root's first full-suite attempt in the ordinary sandbox encountered 26 local-TLS
fixture setup errors: `AF_INET PermissionError`, errno 1. After 529 passes and
three skips, root interrupted that specific pytest PID 560888 with SIGINT to
collect diagnostics; it exited 2 after 105.90 s. This attempt did not pass. No VM
or GUI producer was killed and neither tests nor production code were changed
for the environment issue. In the approved local-socket environment the same
full suite subsequently exited 0: **1,078 passed, three skipped in 19.77 s**,
with Ruff/format on 233 files. Root read `build/performance-r8-integrated.log`.
These are integrated checks of the frozen source, not a clean-commit workflow
receipt for a newly built package. GUI runs waited for the test process to end.

## Reproducible procedure

New tools are `scripts/validation/ubuntu24_vm_source_output_session.py` (controller,
SHA256 `3a11d7bb8b13196a585cb8b52ce0d2b4ae6d057d08760705ddb782dba6766fbc`)
and `scripts/validation/source_output_session_cursor_probe.py` (focus,
SHA256 `d3d4eefa07a2f5ae0d90282f42ed94dd0f848c29736a528cb6e8e24381c3c4d4`).
The fixed SSE fixture is revision
`26ba7b1198846f9f1585d473aeee7c5767aebf20634c0d17627a105e4ae2bb0d`.
Historical R7 and a12 R1/R2 tools, snapshots and evidence are unchanged.

After approved preparation, generate and review complete `preview --mode` payloads,
then execute `run --mode` serially in this order, only proceeding after a genuine
terminal state:

1. `paced`: the original 150-codepoint/144-printable sample, configured server
   fragment sleep 0.07 s, through actual Session and its public output-session
   lifecycle. Capture restoration/insertion counts, exact readback, cancellation,
   first-character timing, server errors and closed fixture threads.
2. `fast`: the same sample with configured 0.001 s sleep, to check the previously
   improved fast-arrival workload with the new lifetime.
3. `focus`: actual StreamingOutput in a separate consumer task enters the formal
   `KeyboardInput.output_session()` context. The producer supplies one character,
   waits for its successful press, then supplies the remaining 55. After 12
   presses, the test changes focus between two owned GTK windows and requires
   exact `[12, 44]` routing, balanced events, restored mapping and completed
   context exit. Counter/send guards do not replace restoration behavior.

Both pipeline modes retain the same 50 ms count-only observer, direct-child
PID/start identity checks and owned temporary readback. They retain the unchanged
12-second probe wait for `session.pending`; production deadlines/timeouts are not
extended. After both normal and cancellation tasks, the 1.2-second no-tail
observation and full cleanup, new owned GTK/VTE windows are created. No GetActive
query delays that startup. Their tool runs using old a12 package dependencies
with **no text input requested**; its old module origins are compared to the
dependency inventory, not incorrectly to the repaired source hashes. This
readiness check is not itself execution of the source keyboard repair.

Sampling/scheduling uncertainty and the natural full-readback-to-process-exit
gap must be reported. This is not an immediate-after-last-character latency
measurement or a distribution. Observation budgets retain live PID/start identity
without terminating pending key cleanup or starting another GUI probe. All test
windows are owned; the product's current-cursor behavior is not replaced by the
test ownership guard. The existing offline Ubuntu 24 KVM instance and real
GNOME/Xorg session are reused, with no cloud, credentials, real microphone,
clipboard or input-method submission.

Preview hashes under `build/ubuntu24-perf-vm/output/`:

| Mode | Complete preview SHA256 |
| --- | --- |
| paced | `b73ff41a966631d7a48d503582978438d3ccc8a316efe6dfd0f9b820151ef207` |
| fast | `44697ab5719d7d2050534d17ec43e2aa057d335ac194d14292b595ce642c12e6` |
| focus | `594fac97e21696af0b225727cdacbd417fb7e7846a7237730fad26f71b9f285f` |

## Actual results and acceptance

All three complete executed payloads matched their reviewed previews byte for
byte, and every producer/readiness process exited naturally with code 0. The
same offline Ubuntu 24.04.5 KVM instance, kernel 6.8.0-142-generic, GNOME Shell
46.0 and actual unlocked Xorg logind session 20 were retained. Root independently
read all raw results, acceptance/readiness records and all eleven runtime origins
per mode, comparing each to frozen source or the separately audited dependency
package. Both pipelines reached the actual source Session output scope.

| Pipeline measurement | Paced, configured 0.07 s | Fast, configured 0.001 s |
| --- | ---: | ---: |
| Exact final codepoints | 150 | 150 |
| Mapping writes | 145 | 145 |
| Successful restore calls | 1 | 1 |
| Completed insertion calls | 150 | 6 |
| Stop to first successful press | 54.537 ms | 57.054 ms |
| Stop to output completed | 10,555.780 ms | 10,239.081 ms |
| Observed full readback to pipeline exit | 2,848.225 ms | 2,795.182 ms |
| Readiness subprocess spawn after exit | 18.516 ms | 5.979 ms |
| GTK fixture spawn after exit | 459.478 ms | 419.380 ms |
| GTK readiness from fixture spawn | **0.1734 s** | **0.1706 s** |
| VTE fixture spawn after exit | 652.190 ms | 607.652 ms |
| VTE readiness from fixture spawn | 0.3882 s | 0.2901 s |

Both delivered the exact fixed final text, ignored ASR previews, sent first
output before polishing finished, suppressed cancelled tails, reported no server
errors and closed fixture threads. Each cancellation task recorded two mapping
writes, two successful restore calls and zero completed insertions. Restore-call
counters include cleanup calls that may have no mapping write; these are not
counts of additional characters or two separate mapping restorations.

For the same paced sample, the historical actual a12 counterexample had
288 writes/150 restore calls/150 insertions and GTK readiness of 5.8435 s. The
source case therefore improved the measured post-cleanup window readiness and
restoration frequency for this controlled workload. This is a single matched
source diagnostic with the stated observer and cleanup gap, not a distribution,
proof of an internal Mutter cause, cloud latency improvement or immediate
last-character-to-window-response guarantee. First-character timing measures a
successful simulated press; it does not measure glyph rendering.

The focus mode exercised the formal context in the actual consumer task:
`output_session_entered` and `output_session_exit_completed` were true. Its lone
first character was successfully pressed before the remaining 55 were queued;
56 codepoints arrived exactly as `[12, 44]` in the two owned windows. First press
took 24.235 ms and output took 3.9337 s, with 55 mapping writes/one restore,
correct routing, balanced events and restored mapping. No target was pinned by
the product; switching focus caused the remaining characters to enter the new
owned window.

The three primary modes and two readiness logs have no traceback, unawaited
coroutine or asynchronous-generator cleanup warnings. The count-only origin and
payload cross-check is `source-r8-output-session-suite-audit.json`; raw mode,
acceptance, origin and readiness records share the `source-r8-output-session-`
prefix in `build/ubuntu24-perf-vm/output`. Preservation hashes in
`source-r8-output-session-preservation.json` confirm that all three user JSON
files, a9/a10/a11/a12/stable artifacts are unchanged and current source still
matches the frozen R8 manifest. Root separately rehashed user/artifact state.

The source repair and these specific results are ready for a local commit. A
new version and actual-package validation remain required. No host tests, build,
deployment, push or release are part of this source validation.
