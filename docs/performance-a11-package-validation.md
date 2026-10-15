# a11 artifact validation

Date: 2026-10-16. Status: static checks and all eight R1 actual-artifact VM
checks passed. R2 long streaming completed accurately but exposed slow
subsequent GTK window readiness; that latency remains unresolved. Host
acceptance is pending.
This new artifact is separate from
the preserved a10 preview and installed a9/stable aliases. Nothing is deployed
or released by these checks.

## Frozen build

| Item | Evidence |
| --- | --- |
| Product commit | `004b054eb324d6c54b622db6df4d0e2ede106b57` |
| Artifact | `dist/InkEcho-0.1.0a11-x86_64.AppImage` |
| SHA256 | `a61b2a036863d9c2ea1515055c7fadb7c9905e9a0139aa05e94936b32a67cb97` |
| Size | 108907000 bytes |
| Build | Natural exit 0; `build/performance-a11-build.log` |
| Static actual-artifact audit | 3958 file checksums, 1048 contained symlinks, 43 source files matched to pre-build manifest |
| WebSocket dependency | 15.0.1, both packaged license copies matched |
| Local records | `build/performance-a11-source-before-build.json`, `build/performance-a11-artifact.json` |

The production change retains the mapping during each insertion and restores
it in the existing synchronous final cleanup. It preserves current-cursor
delivery, cancellation checks, key release and the three default 20 ms settle
intervals. Its prior source-only validation is documented in
[the R6 source report](ubuntu24-source-r6-validation.md); that report does not
prove that a newly built artifact executes the same code.

The version change is limited to the project version in `pyproject.toml`,
`src/inkecho/__init__.py` and the project's `uv.lock` entry. The lock passed an
offline check without dependency changes. Main's clean product-commit workflow
passed 1026 tests with three skipped, plus lint and formatting checks, on the
clean product commit. Validation-tool-only changes following that snapshot are
separately hashed and are not injected into packaged application modules.

## Actual guest and provenance gates

The existing isolated Ubuntu 24.04.5 KVM guest runs its own kernel
`6.8.0-142-generic`, GNOME Shell 46.0 and real GDM Xorg session 20. It retains
four vCPUs and 4096 MiB RAM. This is VM evidence, not bare-metal timing, a
container desktop, Xvfb or XWayland. The guest remains disconnected from
external networking. There is no host desktop, microphone or credential-store
mount.

The new [a11 runner](../scripts/validation/ubuntu24_vm_package.py) uses a fresh
read-only `a11-r1` input tree and a separate guest a11 extraction directory.
Its manifest SHA256 is
`4f316a7813ae0769adab57983870921c4bbdf04dea00322d6835f7a645f137f9`.
It copies the 43 source files only for hash comparison and never places them
on the application's import path. Application execution uses only the selected
artifact's interpreter and `AppDir/packages`, with no `--source-root`, candidate
restoration policy or replacement production keyboard algorithm. Test guards
and counters wrap the real send/map/restore calls; they neither add nor defer
restoration.

Each mode verifies the pinned artifact, all inventory files and symlinks, the
43 packaged source files and both WebSocket licenses inside the guest. Keyboard
and focus checks additionally match the `inkecho`, keyboard and runtime module
paths/hashes to the actual AppDir and source manifest. The generic R6 probe
labels its raw runtime as `unclassified` when no source root was supplied;
the runner's separate package classification is based on those strict
interpreter, artifact, inventory and actual-origin checks. TLS pipeline checks
independently audit the actual package and verify ten packaged module origins.

The read-only tool manifest records these validation-only files:

- Keyboard probe: `f0cb80b62727f9c03c26af8c929255bf99c41c349c8afe3769dc38b49d897344`.
- Local TLS pipeline probe: `9a2136308fc49319e27e97622f982f9b5d593a72e629f38e4c7e396cd07ac170`.
- Owned focus-switch probe: `7957a24d2d6b35f48d57a22478ffd8a96b3e22086786bee623f827f3b24e025f`.
- WebSocket license: `3d6a0c050d8bec52fabad502e45fb25bd02bcadbd70dea34d447b6a0ff4e6da8`.

All eight complete proposed guest payloads and SHA256 manifests were saved
before any a11 guest input. Every actual run also archives its payload before
SSH execution. Output logs are exclusive. A 120-second observation timeout
preserves the live producer and records its PID/start time, rather than killing
pending key/map cleanup or starting another concurrent input mode.

## Serial acceptance scope

The four-target control/default checks use separate new packaged Python
processes and fresh owned Chrome textarea, Chrome contenteditable, GTK and
VTE fixtures, five mixed Unicode samples (140 codepoints) each. Only pacing
differs between 40 ms control and default 20 ms. Expected production counts
are 136 successful mapping writes and one successful restore per full target.
The cancellation check sends exactly 12 codepoints, then checks a 0.5-second
tail-free interval, balanced events and restored mapping.

The local TLS pipeline uses fixed synthetic PCM, fixed ASR final/preview
events, local HTTPS SSE and the actual production keyboard in an owned GTK
field. Normal 40/20 ms runs retain the three-chunk SSE fixture. An additional
`one-character-fast` profile sends one codepoint per delta at 1 ms intervals.
It preserves the actual first-send/stream-completion ordering: the complete
fast response may arrive before the first simulated key. That is not falsely
reported as streaming overlap. Accuracy, cancellation, map/held-key cleanup,
profile identity, actual desktop input and module provenance remain required.
Successful server flush counts are separate from client reception evidence.

The [focus-switch probe](../scripts/validation/package_cursor_switch_probe.py)
inserts 56 mixed codepoints through one production insertion. After 12 presses,
it switches between two newly owned GTK windows. Each subsequent press checks
its actual current target against either owned PID/start time/window. Acceptance
requires the first field's exact 12-codepoint prefix, the second field's exact
remaining suffix, no focus-change cancellation, balanced events and one final
restoration. No user window or clipboard/input-method delivery is involved.

The final UI mode captures nine pages from the extracted a11 `AppRun` in this
Xorg session, with a separate empty-key profile. It does not establish native
Wayland input, IPC, damaged-config recovery, FUSE launch, desktop installation
or login autostart.

After the prepared payloads have been reviewed, the explicit modes are run
serially:

```sh
.venv/bin/python scripts/validation/ubuntu24_vm_package.py run --mode control40
.venv/bin/python scripts/validation/ubuntu24_vm_package.py run --mode default20
.venv/bin/python scripts/validation/ubuntu24_vm_package.py run --mode cancel12
.venv/bin/python scripts/validation/ubuntu24_vm_package.py run --mode pipeline40
.venv/bin/python scripts/validation/ubuntu24_vm_package.py run --mode pipeline20
.venv/bin/python scripts/validation/ubuntu24_vm_package.py run --mode pipeline-character-fast
.venv/bin/python scripts/validation/ubuntu24_vm_package.py run --mode focus-switch
.venv/bin/python scripts/validation/ubuntu24_vm_package.py run --mode ui
```

All eight R1 modes now naturally exited 0, with their separate
`a11-r1-*-acceptance.json` receipts passed. No observation timeout or forced
producer termination occurred. Raw reports, actual payloads, manifests and
fixture logs remain alongside the previews. Each actual payload matches its
reviewed preview. The main reviewer independently accepted the receipts,
including the focus split and nine UI pages; that review does not turn this
limited suite into complete platform support.

## Actual R1 results

Both four-target sequences completed consecutively in their own processes.
Every target received exactly 140 codepoints, balanced its events and restored
the map, with 136 writes and one successful restore. VTE bytes matched in both
groups. The package's three measured module origins matched the a11 AppDir and
source hashes. Only settle intervals differ between the groups.

| Target | 40 ms input | Default 20 ms input | Reduction |
| --- | --- | --- | --- |
| Chrome textarea | 18.1217 s | 9.4921 s | 47.62% |
| Chrome contenteditable | 18.1981 s | 9.5629 s | 47.45% |
| GTK | 18.1746 s | 9.5144 s | 47.65% |
| VTE | 18.2284 s | 9.4727 s | 48.03% |

These are this VM's fixed-sample timings, not bare-metal or provider latency
claims. The cancellation mode received exactly 12 codepoints, then no tail
over 0.5 seconds; events balanced and mapping restored with 13 writes and one
successful restore. It took 0.8181 s, with first press at 30.25 ms.

All three local TLS pipeline modes verified ten actual package module origins,
the full inventory, fixed final text exactly, ignored previews, final-only ASR
handoff, cancellation without a tail and balanced/restored desktop input.
All have `server_errors=[]` and joined fixture threads. The fast profile's
scope is only 25 codepoints, not arbitrary long one-character streams.

| Local SSE profile / pacing | Stop to first press | Output duration | Stop to output complete | Normal-task writes / restores / completed insert calls |
| --- | --- | --- | --- | --- |
| Normal / 40 ms | 52.452 ms | 3208.971 ms | 3261.422 ms | 27 / 3 / 3 |
| Normal / 20 ms | 54.087 ms | 1806.043 ms | 1860.129 ms | 27 / 3 / 3 |
| One-character-fast, 25 / 20 ms | 49.051 ms | 1676.455 ms | 1725.506 ms | 48 / 25 / 25 |

The actual first press preceded polish completion in all three R1 runs. This
is an observed boolean, not an assumption imposed on future fast-profile
results. Fast25 recorded 50 successful server delta flushes across its two
completed streams; those flush counts are not client-reception counts.
Each pipeline's canceled task recorded two writes, one successful restore and
zero completed insert calls. The 48-write/25-restore fast25 observation confirms
that one-character provider deltas still cause per-insertion restoration;
the source fix does not automatically combine queued streaming fragments.

The actual focus-switch run sent all 56 codepoints through one insertion.
The first owned field contained the exact 12-codepoint prefix; the second
contained the exact 44-codepoint suffix. The route sequence matched the
switch, no focus-change cancellation occurred, events balanced, and the map
restored with 55 writes and one successful restore. Input took 3.9055 s.

The Xorg UI mode exited normally and produced nine original PNGs in
`output/a11-r1-ui-pages/`; a contact sheet is
`output/a11-r1-ui-contact.png`. Both implementing and main reviewers inspected
the sheet; main also inspected the longer provider pages 03 and 04. Chinese
text, controls and layouts appeared normal; scrolling on long pages was
acceptable. No R1 main log contains a traceback, runtime warning, ignored
exception or destroyed-task warning. Known Chrome GPU transient warnings in
fixture logs are retained rather than treated as an input failure.

An independent R2 snapshot uses the newer long profile with 150 codepoints,
then tests new owned window readiness, as recorded below. R1 is neither
overwritten nor upgraded to a claim about that larger load. Host Ubuntu 26 XWayland input, actual
microphone-to-loopback pipeline and native Wayland UI/IPC/config-recovery checks
for this specific a11 artifact are also outstanding. No cloud speech accuracy,
cloud latency, installation or autostart result is claimed here.

## R2 long one-character stream and subsequent window readiness

R2 preserves R1 and uses a new read-only snapshot, manifest SHA256
`787573bdae28af525ebfed8bf09b82ae3d0bf4db2ad3bcf47d7a03fb70e0651f`.
Its long-profile pipeline tool is
`2122ea8dfb59808c23a72b07caab0f059550140b4fc199e37fe4612f42a17a12`.
The approved and actual full payloads have matching SHA256
`50ac985def1edd92cd905d8d5dd921b183c609eb4b60dcc8c45b85c62d42b5d8`.
The [stress runner](../scripts/validation/ubuntu24_vm_streaming_stress.py)
executes the same a11 artifact with the unchanged 12-second probe wait for
`session.pending`; application deadlines and timeouts are unmodified. That
wait is the validation tool's limit, not the production task deadline. It then
runs the separate
[no-input next-window probe](../scripts/validation/package_next_window_probe.py).

The pipeline naturally exited 0 and its full-text/cancellation/cleanup checks
passed: 150 codepoints, 144 printable codepoints, exact readback, balanced
events, restored mapping, no late canceled tail, no server errors and joined
fixture threads. Package inventory and ten actual module origins passed.
The normal task recorded **288 mapping writes, 150 successful restore calls
and 150 completed insertions**; cancellation recorded 2/1/0. Thus the large
number of tiny streamed insertions still generates repeated mapping updates.
Stop to first press was 58.503 ms, output duration 10260.251 ms and stop to
output completion 10318.755 ms, within the unchanged probe wait.

This diagnostic has a nominal 50 ms parent observer, so its timings are not
the unobserved R1 performance baseline. The observer reads only the new
pipeline's verified direct-child GTK fixture state, checking its PID/start
time, exact frozen fixture script and dedicated temporary pathname. It retains
only length/timestamps, not body text. Its first observed 150-character
readback preceded the complete pipeline process's observed exit by
**2766.534 ms**. That interval includes the second cancellation task, its
1.2-second tail observation and session/TLS cleanup. Polling and scheduling
introduce uncertainty; it is not an exact timestamp of the production last key.

No extra desktop query or deliberate wait preceded the next-window process:
it spawned 2.783 ms after the observed pipeline exit. Python/Qt startup then
placed the first actual GTK fixture spawn at exit +414.118 ms. Its readiness
took **6.0944 seconds**, near the end of the unchanged 120-attempt readiness
loop. The following VTE fixture, started sequentially at exit +6526.067 ms,
became ready in 0.285 seconds. Both had live owned processes, ready files and
visible windows; no text was sent to these readiness fixtures. Their package
origins matched the selected artifact.

The mechanical pipeline/readiness gates passed and no producer remained
running, but the GTK delay is a material unresolved finding. This is
**readiness after both tasks and cleanup**, not immediate responsiveness when
the normal long output ends. Sequential VTE success after waiting for GTK
also cannot establish that VTE would have been immediately responsive earlier.
No sample was reduced, probe wait extended or failed sequence replaced. The two
R2 logs contain no traceback, runtime warning, ignored exception or destroyed
task warning. Receipts are `output/a11-r2-long-{pipeline,next-window,acceptance}.json`.
