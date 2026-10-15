# Ubuntu 24.04 production-source R6 validation

Date: 2026-10-16. Status: **all three source checks passed**. This is a
**source-runtime** check, not acceptance of a newly built AppImage. It follows
the explicit R5 restoration experiment recorded in
[the VM report](ubuntu24-vm-performance-validation.md). The old a10 artifact
and R5 receipts remain unchanged.

The reviewed production change removes the per-character `restore()` call
while preserving the outer synchronous cleanup, current-focus and cancellation
checks, key release and all three 20 ms settle intervals. The R6 probe counts
successful production mapping/restore calls transparently; it has no
experimental restoration-policy option.

## Frozen source and actual runtime

The separate [source runner](../scripts/validation/ubuntu24_vm_source.py)
prepares a new read-only guest input tree, `source-r6`, with all 43 application
files, the reviewed R6 keyboard probe and the WebSocket license. Its complete
manifest SHA256 is
`03c77fc27b8555248e59887870bf69ce788405d3fd1b9b78d5b680411638075e`.
The keyboard backend SHA256 is
`1aff28ceab124e9745f2afda5ac8fec084d71be3185719a73556ad0b755f60f3`;
the probe SHA256 is
`f0cb80b62727f9c03c26af8c929255bf99c41c349c8afe3769dc38b49d897344`.

The guest verifies the pinned manifest and every copied file before input.
The interpreter and dependencies come from the existing a10 artifact, SHA256
`5c515dd0e3ceb8eb910baa45f392d8be28bfda109c5e1d59865e5a0733b7d55a`.
New source is explicitly selected through `--source-root`, ahead of the old
package on `PYTHONPATH`. Each receipt must identify `inkecho`, its keyboard
module and its runtime module inside that new tree with hashes matching the
manifest. Reusing dependency binaries does not mean the old artifact contains
the source fix.

The existing offline Ubuntu 24.04.5 KVM guest and actual GDM Xorg session 20
are retained. It has its own kernel `6.8.0-142-generic`, GNOME Shell 46.0 and
four vCPUs/4096 MiB RAM. Tests use packaged Python 3.13.15, Qt 6.12 and the
managed Qt event loop. The guest's test-only idle policy remains disabled as
documented in the historical VM report. The host policy is unchanged.

All targets are newly created owned fixtures, including Chrome's fresh profile
and standard sandbox. Every press retains the frozen PID/start-time/current
window guard. No clipboard, system input-method submission, microphone,
credential store or cloud service is used. Before/after ScreenSaver queries
use the real guest session bus with packaged runtime library variables removed.
There is no high-frequency observer during these performance runs.

## Reproducible check and acceptance

The runner saves its full guest payload and SHA256 before every run. Logs are
exclusive and the snapshot cannot replace an existing source-r6 directory.
The control and default runs each start a fresh process and visit Chrome
textarea → Chrome contenteditable → GTK → VTE, five fixed mixed-Unicode
samples per target (140 codepoints). The cancellation run uses only GTK and
cancels after 12 successful presses.

```sh
.venv/bin/python scripts/validation/ubuntu24_vm_source.py prepare
.venv/bin/python scripts/validation/ubuntu24_vm_source.py run \
  --mode control40 --label control40
.venv/bin/python scripts/validation/ubuntu24_vm_source.py run \
  --mode default20 --label default20
.venv/bin/python scripts/validation/ubuntu24_vm_source.py run \
  --mode cancel12 --label cancel12
```

Do not repeat those labels against an existing lab. If a probe exceeds the
120-second observation budget, the runner records its PID/start time and
running state rather than killing it during cleanup. Any such task requires
continued observation before another desktop input run.

Acceptance requires exact text, balanced press/release events, restored maps,
VTE raw-byte equality, all three expected source origins, `runtime_kind=source`,
`restore_policy=production` and `production_behavior_modified=false` with no
candidate field. A complete 140-codepoint target has 135 mapped printable
characters and five Return events: 136 mapping writes and one successful
restore call are expected. Partial cancellation expects 13 writes and one
restore, the exact 12-character prefix and no tail during 0.5 seconds.

Actual result receipts are stored in `build/ubuntu24-perf-vm/output/` under
`source-r6-{control40,default20,cancel12}.json`, with separate
`-acceptance.json`, payload manifests and fixture logs. All three probes
naturally exited 0; no observation timeout, forced termination or remaining
probe occurred. Each wrapper acceptance passed all 43 file hashes, all three
runtime origins/hashes, the required production flags and measured counts.

## Actual results

All eight full-target observations received exactly 140 codepoints, with
balanced events, restored maps, 136 mapping writes and one successful restore
call. VTE raw bytes matched in both groups. The same source and actual Qt
event loop were used; only the three settle intervals differ.

| Target | 40 ms input time | Default 20 ms input time | Reduction | First press, 40 → 20 ms |
| --- | --- | --- | --- | --- |
| Chrome textarea | 18.2250 s | 9.5153 s | 47.79% | 62.06 → 32.28 ms |
| Chrome contenteditable | 18.1495 s | 9.4931 s | 47.69% | 51.15 → 30.43 ms |
| GTK | 18.2024 s | 9.4729 s | 47.96% | 49.24 → 31.86 ms |
| VTE | 18.2590 s | 9.4879 s | 48.04% | 51.52 → 30.86 ms |

These reductions describe this one matched VM run with five fixed samples
per target. They are not a distribution of fresh-window trials, bare-metal
performance or a cloud speech-latency result. All four targets ran consecutively
inside each process; no failed combined sequence was replaced with isolated
single-target measurements.

The production cancellation check received exactly the 12-character prefix,
balanced its 12 presses with releases, restored the map and observed no tail
for 0.5 seconds. Counts were 13 mapping writes and one successful restore.
Input took 0.8471 s; first press occurred at 52.98 ms. Its receipt has
`cancelled`, `expected_prefix`, `no_late_tail` and `map_restored` all true.

| Clean native ScreenSaver query | Before | After | Result |
| --- | --- | --- | --- |
| 40 ms control | 3.5 ms | 7.3 ms | Both false |
| Default 20 ms | 3.8 ms | 14.6 ms | Both false |
| Cancel 12 | 3.7 ms | 2.7 ms | Both false |

These boundary queries establish the observed state before and after each
run. They do not establish desktop responsiveness throughout input; the R5
sidecar's measured in-flight query delays remain historical evidence.

This confirms the reviewed production-source path in this actual VM without
the experimental policy wrapper. A separately built a11 artifact still needs
its own source inventory, module-origin and desktop acceptance. The existing
a10 artifact has not changed. Microphone, cloud ASR, global shortcuts, native
GNOME 46 keyboard support and full Ubuntu compatibility are outside these
source keyboard checks.
