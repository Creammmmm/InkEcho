# a13 actual-package validation

Status: the independent a13 artifact was built, extracted and statically audited.
All seven Noble actual-package modes completed naturally and root independently
accepted their limited results. No desktop result is inferred from source R8 or
an earlier AppImage. Host acceptance remains separate; a13 is not deployed.

## Artifact and source

- Fixed product commit: `eeb2d0ce8f8c5a6690b0ab54e0196da4254eb767`.
- Artifact: `dist/InkEcho-0.1.0a13-x86_64.AppImage`, 108,907,000 bytes, SHA256
  `8dce4eedee71373a27e0e6507592b1240617412a8a6f114230b9a53f4d286a89`.
- The clean-commit workflow passed: 1,078 tests passed, three skipped in 20.01 s;
  Ruff/format covered 233 files. Root independently checked its receipt at
  `.git/validation/eeb2d0ce8f8c5a6690b0ab54e0196da4254eb767.json`, bound to
  source-R8 report SHA256
  `8a7fa8282fcb373769f71bd5fa94102869b81ac292e0f17c0fceb7eb44cbfe41`.
- Before build, all 13 cached system-asset archives and the pinned AppImage
  runtime checksum passed. There were no missing cached assets or downloads.
  The normal builder and independent extraction both exited naturally with 0.
- Complete extracted inventory: 3,958 files, 1,048 symlinks; all hashes/link
  targets passed. All 43 packaged source files matched the frozen before-build
  source and unchanged after-build source. Both websockets 15.0.1 license copies
  matched the repository license.
- The non-GUI actual-package entry audit used the shipped Python, imported ten
  application modules plus websockets, checked all origins and full inventory,
  then dispatched only CLI help without creating QApplication or a window.
  App hash `d4e58b4cb6de9ceed5d471574bc32e6a1cf255b125e93eb49838ed41146482bd`,
  keyboard `03e67f372bc669f279b135f3f4a73db6bafb4b30c2a862a83292e72ce11f968a`
  and streaming `c46eb6e13627067d9c918415defe57eb93898f30e3e57795ed9c828edab89ce1`
  match the actual package. Root independently verified the artifact and static
  inventory/source/license evidence.
- Records: `build/performance-a13-source-before-build.json`,
  `build/performance-a13-artifact.json`, `build/performance-a13-entry-audit.json`,
  separate build/extract/entry logs and `build/performance-a13-extract.json`.
  Three user JSON files and a9/a10/a11/a12/stable artifact hashes were unchanged.

## Actual-package procedure

New independent tools are `scripts/validation/ubuntu24_vm_a13.py`,
`artifact_output_session_runtime_probe.py` and
`artifact_output_session_cursor_probe.py`. They do not change a12/R8 historical
helpers, inputs, payloads or labels. The new `a13-r1` RO input snapshot contains
all 43 source audit references, seven tool/license files and this actual artifact.
Its manifest SHA256 is
`a62e0bc34f9fc738d5b8375e4981fbf2baabbf51eecda6238241b5110b8dd131`.
Production imports use **only** extracted `AppDir/packages` and shipped Python/Qt;
there is no source-root override or candidate restoration patch. The entry
verifies ten application origins, including the repaired Session and keyboard,
plus the separately checked websockets origin against inventory and source hashes.

Run reviewed complete payloads serially, with a genuine terminal state before
starting the next mode:

1. `default20`: four owned targets (Chrome textarea, Chrome contenteditable, GTK,
   VTE raw terminal), five repetitions/140 codepoints each, actual Qt loop and
   unmodified production pacing. Existing a12 40 ms controls are historical
   context only; they are not a new a13 control measurement.
2. `cancel12`: owned GTK; exactly 12 successful presses, exact prefix, 0.5 s
   no-tail observation, event balance and restored mapping.
3. `pipeline20`: fixed synthetic PCM through local TLS WebSocket ASR/HTTPS SSE,
   normal 25-codepoint/24-printable fixture with configured 0.35 s fragment delay,
   actual Session output, final-only ASR, overlap, cancellation and cleanup.
4. `pipeline-paced`: the original 150-codepoint/144-printable counterexample
   using configured 0.07 s server sleeps. Record actual mapping/restoration and
   insertion counts, exact readback, cancellation and task timings.
5. `pipeline-fast`: the same 150-codepoint sample with configured 0.001 s delay.
6. `focus-stream`: actual StreamingOutput consumer enters the formal packaged
   `KeyboardInput.output_session()` API. One character must be successfully
   pressed before the producer supplies the remaining 55; after 12 presses,
   focus changes between two owned GTK targets. Require exact `[12, 44]` routing,
   balanced events, restored mapping and completed scope exit.
7. `ui`: actual AppRun, a fresh disposable profile, nine settings-page PNGs and
   normal quit. This mode alone does not validate native Wayland input, IPC,
   damaged-profile recovery or FUSE mounting.

Both long pipelines retain the original 12-second probe wait for
`session.pending`, unchanged production deadlines and a 50 ms count-only observer
of the verified direct-child fixture's owned temporary readback. After the normal
task, second cancellation task, 1.2 s no-tail observation and full cleanup, new
owned GTK/VTE windows are created without an intervening GetActive query.
Report the observed full-readback-to-exit gap and subsequent spawn/readiness
intervals; this is not immediate-last-character response or a latency distribution.
First-character timing means successful simulated press, not rendered text.
Configured fixture sleeps are not measured client arrival intervals.

Test PID/start/active-window guards protect only owned targets; product input
retains current-cursor semantics. Send and mapping counters do not replace
production restoration algorithms. Observation budgets never kill a producer or
pending cleanup; preserve its PID/start identity and wait for its true terminal
state. All output labels and complete preview/run payload files are exclusive.

## Noble results and independent acceptance

All seven modes reached natural exit 0; both extra long-stream readiness
processes did too. Their functional and strict actual-package gates passed.
The same real Ubuntu 24.04.5/KVM instance, kernel 6.8.0-142-generic, GNOME Shell
46.0 and unlocked Xorg logind session 20 were retained. There were no observation
timeouts, forced producer termination or concurrent desktop tests.

| Default production pacing, 140 codepoints | Exact readback | Elapsed (s) |
| --- | --- | ---: |
| Chrome textarea | Yes | 9.5201 |
| Chrome contenteditable | Yes | 9.4629 |
| GTK | Yes | 9.4908 |
| VTE raw terminal | Yes | 9.4663 |

Each target recorded 136 mapping writes/one restore, balanced events and a
restored map. These are new a13 results at default 20 ms parameters; the 40 ms
a12 measurements remain historical, not newly run a13 controls. Standalone GTK
cancellation delivered exactly 12 codepoints, had no late tail during 0.5 s and
restored mapping with 13 writes/one restore.

All three actual-package Session pipelines received exact final text, excluded
ASR previews, allowed only final ASR into polishing, began output before polishing
finished, suppressed cancellation tails and closed fixture threads with no server
errors. Their configured profiles/delays and sample lengths matched the reviewed
gates. The cancellation task in each recorded two writes/two successful restore
calls/zero completed insertions; restore-call counts may include a cleanup call
that performs no mapping write.

| Session pipeline | Normal 25 | Paced 150 | Fast 150 |
| --- | ---: | ---: | ---: |
| Mapping writes | 25 | 145 | 145 |
| Successful restore calls | 1 | 1 | 1 |
| Completed insertions | 3 | 150 | 6 |
| Stop to first successful press (ms) | 47.844 | 46.804 | 49.946 |
| Stop to output completed (ms) | 1,865.296 | 10,545.329 | 10,181.160 |

The paced case therefore exercises the formerly failing restoration frequency
with the actual new package, rather than extrapolating from a queued fast stream.
The old a12 paced case remains preserved as a counterexample with 288 writes,
150 restore calls and 5.8435 s GTK readiness. The following table retains the
natural two-task/cleanup gap; it does not measure immediate-last-character
responsiveness or a distribution.

| Long-stream observation | Paced 150 | Fast 150 |
| --- | ---: | ---: |
| Observed full readback to pipeline exit (ms) | 2,798.888 | 2,797.023 |
| Readiness subprocess spawn after exit (ms) | 11.552 | 10.048 |
| GTK fixture spawn after exit (ms) | 433.289 | 419.036 |
| GTK readiness from fixture spawn (s) | **0.1753** | **0.1602** |
| VTE fixture spawn after exit (ms) | 626.624 | 596.739 |
| VTE readiness from fixture spawn (s) | 0.2983 | 0.2701 |

The formal-scope focus test delivered 56 codepoints exactly as `[12, 44]`.
Context entry and completed exit were confirmed. A successful first press preceded
queuing the remaining 55 characters; it took 34.384 ms. Output took 3.9288 s,
with 55 writes/one restore, balanced events and a restored mapping. Focus switched
after 12 presses, and later characters entered the new owned window.

Actual AppRun rendered nine pages and exited 0 with a disposable profile. Original
PNGs and `contact.png` are in
`build/ubuntu24-perf-vm/output/a13-r1-ui-pages`; provider pages 03/04 are scrollable
long pages. Root independently viewed the contact and both originals, accepting
Chinese text/layout/controls within this screenshot scope. This does not prove
untested controls or native keyboard delivery.

Root independently read all raw results and seven acceptance records, checked
each of the six mode audits' eleven module origins against the locally extracted
a13 artifact, verified every complete preview/run pair byte for byte, and accepted
these seven limited results. Evidence files are exclusively named
`build/ubuntu24-perf-vm/output/a13-r1-*`, including raw/acceptance/origin JSON,
full payloads and adjacent SHA manifests. `a13-r1-suite-audit.json` records the
same payload identity/origin checks and no traceback, unawaited-coroutine or
asynchronous-generator warning in nine primary/readiness logs. Chrome fixture
subprocess logs are separately retained; no universally warning-free desktop is
claimed. The preservation record confirms unchanged user JSONs, old five
artifacts, current 43 product sources and new a13 artifact SHA.

The three new tools remain frozen at their snapshot hashes: runtime entry
`4d4ccd9bdd6a886eb02e1a5647923c66155d9481e11fa7a52fc626fa92cc3441`,
formal focus `f71e7e58256ba7488b5f926b2b07bc6aefd9f024e2e3b6f9b2f2632118008980`,
controller `57a0351b63433628b7f06508ce87db26ed94a2a1258cffc48d3d76b6dde7a463`.
No production algorithm or validation gate changed during execution.

## Remaining acceptance and boundaries

This is a real Ubuntu 24 GNOME/Xorg KVM desktop scope, not bare-metal timing,
GNOME 46 native Wayland support or universal application compatibility. There
were no cloud ASR requests, credentials, real microphone, user documents,
clipboard or input-method submission in these modes. Local fixture timing is not
cloud speech accuracy or network performance. Host microphone/input/UI/IPC and
corrupt-profile checks require separate reviewed a13 tools and evidence. No
host checks, deployment, push or release are included in this VM report. Old
artifacts, a13 and user JSONs remain unchanged.
