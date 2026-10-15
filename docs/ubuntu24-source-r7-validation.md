# Ubuntu 24.04 R7 source streaming validation

Date: 2026-10-16. Status: both reviewed source modes passed in the actual VM.
This is **new source using old a11 runtime
dependencies**, not a newly built package. The preserved a11 artifact still
has its original source and its recorded R2 window-readiness delay.

## Frozen source and provenance

The new `source-r7-streaming` read-only snapshot has 43 application files.
Its manifest SHA256 is
`7e5d2dcca6c0d89d877ad9b8d728b8cfb3a4d3f53ec969fe12022179912b7498`.
The changed StreamingOutput source SHA256 is
`c46eb6e13627067d9c918415defe57eb93898f30e3e57795ed9c828edab89ce1`;
keyboard remains
`1aff28ceab124e9745f2afda5ac8fec084d71be3185719a73556ad0b755f60f3`.
The project version is still a11, but that label does not identify this
unpackaged revision; the manifest and changed source hash do.

The production change combines only already queued contiguous fragments,
up to 128 codepoints per send. It does not wait for future fragments before
starting a send. Queue capacity and active-item bounds remain 4096 + 128
codepoints, with explicit cancellation checks. The source validation does
not replace the production keyboard, provider client, or StreamingOutput.

The [R7 runner](../scripts/validation/ubuntu24_vm_source_streaming.py) reuses
the existing offline KVM guest, Ubuntu 24.04.5/kernel 6.8.0-142-generic/GNOME
46 actual Xorg session 20. Python/Qt and dependencies come from the unchanged
a11 artifact SHA256
`a61b2a036863d9c2ea1515055c7fadb7c9905e9a0139aa05e94936b32a67cb97`.
The runner verifies that artifact and the new source/tool files. It explicitly
puts the selected new source first on the pipeline import path.

The [source entry](../scripts/validation/source_pipeline_probe.py) verifies
ten application modules against the new source paths and manifest hashes,
including StreamingOutput and KeyboardInput. WebSockets is the separately
recorded dependency exception: its actual path must be inside the selected
old a11 dependency directory, and its file hash must match that package's
inventory. The pipeline itself must report `runtime_kind=source`. There is
no assertion that a new package or full new-package inventory was tested.

## Long local pipeline and readiness scope

The exact pipeline fixture tool remains
`2122ea8dfb59808c23a72b07caab0f059550140b4fc199e37fe4612f42a17a12`,
profile `one-character-fast-long`: 150 codepoints, 144 printable, one delta
per codepoint at a nominal 1 ms server interval. The 12-second bound remains
the tool's wait for `session.pending`, not a production task deadline.
Application deadlines and timeouts are unmodified.

The same nominal 50 ms observer reads only the verified direct-child GTK
fixture's temporary readback file and retains length/timestamps, never body
text. This diagnostic is not an observer-free performance baseline. It
records first observed 150-codepoint readback → complete pipeline exit →
new readiness process/fixture startup, with polling and scheduling uncertainty.
The complete pipeline includes its second cancellation task, a 1.2-second
tail observation and session/TLS cleanup. Subsequent readiness is explicitly
**after both tasks and cleanup**, not immediately when normal output ends.

If the new source pipeline passes, the no-input GTK/VTE readiness helper is
the unchanged R2 tool, SHA256
`8ab688389f19aa9f7550b70d2163a81c55f40d773bd8d338c9e10ac574608434`.
It runs with old a11 package imports solely as a fixture/Qt harness: it does
not execute StreamingOutput or send text. This reuse does not classify the
new source pipeline as an a11 package. The 120 readiness attempts, target
ownership checks and failure-scene capture remain unchanged. No extra
ScreenSaver query or wait is added before readiness.

## Lone first character and focus semantics

The separate [source cursor probe](../scripts/validation/source_streaming_cursor_probe.py)
uses the real new StreamingOutput → real KeyboardInput path and the reviewed
two-owned-window press guard. It first appends one character and must observe
its first successful keyboard press before supplying the remaining 55
codepoints. This checks that batching does not require later deltas to send
the first character. After the twelfth press it switches to the second owned
GTK window. Acceptance requires exact [12, 44] prefix/suffix routing, no
focus-change cancellation, balanced events and restored mapping. Counts are
recorded rather than forcing the old single-insertion restore count onto
the new streamed sequence.

The long pipeline also checks cancellation during partial real input, exact
final text, ignored ASR previews, no late canceled tail, held-key/map cleanup,
server errors and fixture-thread termination. All audio is fixed synthetic
PCM sent only to loopback TLS fixtures; there is no user credential read,
cloud request or real microphone input.

## Reproduction and evidence

Preparation and reviewed previews were followed by serial actual execution:

```sh
.venv/bin/python scripts/validation/ubuntu24_vm_source_streaming.py prepare
.venv/bin/python scripts/validation/ubuntu24_vm_source_streaming.py preview --mode long
.venv/bin/python scripts/validation/ubuntu24_vm_source_streaming.py preview --mode focus
.venv/bin/python scripts/validation/ubuntu24_vm_source_streaming.py run --mode long
.venv/bin/python scripts/validation/ubuntu24_vm_source_streaming.py run --mode focus
```

The complete long preview SHA256 is
`711a82fcaba4601fa68985043198fe10b733c0136de17cec072516536aed659e`;
the focus preview SHA256 is
`24ff2fdbe62a0b5eb0ec1804b010b2de85fa302bef5bd8566b56bd243bb7f203`.
They are stored under `build/ubuntu24-perf-vm/output/source-r7-streaming-*-preview.py`
with manifests. Actual payload hashes exactly match both reviewed previews.
Execution ran one mode at a time and archived the exact payload before SSH.
Observation
timeouts retain PID/start time instead of killing pending keyboard cleanup.
Original R1/R2 scripts, snapshots, payloads, artifacts and reports are unchanged.

## Actual long-stream result

The source pipeline naturally exited 0. Its raw report and wrapper acceptance
passed, with `runtime_kind=source`. Ten application origins and hashes matched
the new snapshot, explicitly including the `c46eb6...` StreamingOutput and
unchanged `1aff28...` keyboard. WebSockets came from the selected old a11
dependency directory and its file checksum matched that package's inventory.

All 150 codepoints were received exactly. Cancellation sent no late tail;
desktop press/release balance and mapping restoration passed. The fixture had
no server errors and all fixture threads closed. The normal task recorded
**150 mapping writes, six successful restore calls and six completed
insertions**, compared with the retained a11 R2 result of 288/150/150 on the
same 150-codepoint profile. The canceled task still recorded 2/1/0.

| Source diagnostic timing | Observed value |
| --- | --- |
| Stop to first press | 52.383 ms |
| Output duration | 10149.912 ms |
| Stop to output completion | 10202.295 ms |
| First observed 150-character readback → complete process exit | 2850.808 ms |
| Observed process exit → readiness process spawn | 9.542 ms |
| Observed process exit → first actual GTK fixture spawn | 379.096 ms |
| New GTK readiness | 0.1639 s |
| Following VTE readiness | 0.2216 s |

Both new owned fixtures were alive, had ready files and visible windows.
Their unchanged old-a11 package origins were verified only for fixture
execution. No text was sent to them. The older matched a11 R2 GTK readiness
was 6.0944 s; this source run did not show that long delay. This is one matched
diagnostic observation, not a latency distribution or a universal guarantee.
The 2.850-second natural cancellation/cleanup interval and nominal 50 ms
observer remain part of its scope; it does not demonstrate responsiveness
immediately when normal output ends.

## Actual first-character and focus result

The source focus mode also naturally exited 0, and its raw and wrapper reports
passed the same ten-application-origin checks. The lone first character's
successful keyboard press occurred before the other 55 codepoints were queued.
First press was observed at 35.467 ms. After press 12, the fresh second window
received the rest: exact counts [12, 44], exact prefix/suffix and exact routing.
Focus movement did not cancel the source stream. All 56 codepoints completed,
events balanced and mapping restored, with 57 writes and three successful
restores across three completed streamed insertions. Total input was 4.0008 s.

The main reviewer independently inspected long raw/origins/acceptance,
next-window metadata and focus raw/acceptance and accepted these findings.
Pipeline, readiness and focus logs contain no traceback, runtime warning,
ignored exception or destroyed-task warning. Both modes have real terminal
states and no retained producer. No sample or readiness gate was relaxed.

Receipts are under `build/ubuntu24-perf-vm/output/`:

- `source-r7-streaming-{pipeline,origins,next-window,acceptance}.json`.
- `source-r7-streaming-focus.json` and `source-r7-streaming-focus-acceptance.json`.
- Reviewed/actual payloads, SHA256 manifests and separate process/fixture logs.

No cloud request, user credential read, real microphone, deployment or release
occurred. This passes the scoped new-source checks; a separately built a12
artifact still needs its own strict package and desktop acceptance. The a11
artifact remains unchanged with its original recorded limitation.
