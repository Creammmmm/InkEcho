# a12 actual-package validation

Status: static build audit and the eight Noble R1 modes completed successfully.
The separate paced-arrival test reproduced a remaining window delay; host
desktop checks are deferred. This
is an actual-package checkpoint, not acceptance inferred from source-only R7
evidence or earlier AppImages. a12 is not deployed.

## Artifact and immutable product source

- Product commit: `06f5600a57402335e97b3975afc38009d6233e58`.
- Artifact: `dist/InkEcho-0.1.0a12-x86_64.AppImage`, 108,907,000 bytes.
- SHA256: `e31dbc6301318ab10632c12a7437ae7cd01482f2b1ee39655a82e43b6900eae9`.
- The complete workflow passed on the clean product commit: Ruff/format (225
  files), 1,051 tests passed and three skipped in 19.90 seconds. Its receipt is
  `.git/validation/06f5600a57402335e97b3975afc38009d6233e58.json`.
- Build and extraction both exited normally. All 43 application source hashes
  matched before and after the build and in the extracted artifact. The inventory
  contains 3,958 files and 1,048 symbolic links. Both copies of the websockets
  15.0.1 BSD license match the repository license.
- Root independently verified the artifact digest, inventory and product source.
  Build records: `build/performance-a12-artifact.json`,
  `build/performance-a12-source-before-build.json`,
  `build/performance-a12-build.log` and `build/performance-a12-extract.log`.

## Actual-package method and R1 execution

`scripts/validation/ubuntu24_vm_a12.py prepare` creates a new `a12-r1` snapshot
under `build/ubuntu24-perf-vm/input`. Its source copies are audit references only.
The guest loads production code exclusively from the extracted a12
`AppDir/packages`, using its own Python and Qt; there is no source-root override
or candidate restore policy. The entry tool verifies ten application module
origins, including `streaming_output` and `platform.keyboard`, and the websockets
origin against the artifact inventory. Application module hashes also match the
43-file product manifest. All three new helpers and the frozen fixture tools are
included in the snapshot manifest. Separate preview and executed payloads are
archived with hashes; all eight preview/run pairs matched exactly. The snapshot
manifest SHA256 is
`e156849dbdeddec90cef2633e51c88dc1aec63fe9a086413a722d5934732349a`.
Existing a11, R6 and R7 records remain unchanged. A format-only preparation draft
was archived as `a12-r1-unexecuted-format-draft`; it was never executed and is
neither a desktop failure nor a passing run.

In the existing offline Ubuntu 24.04 KVM guest, serial modes are:

1. `control40`, then `default20`: five repetitions of the fixed Unicode sample in
   each of Chrome textarea, Chrome contenteditable, GTK and VTE; same production
   mapping and actual Qt event loop, with only the control pacing overridden.
2. `cancel12`: owned GTK cancellation after 12 successful presses, with prefix,
   no-tail, event balance and mapping restoration checks.
3. `pipeline40`, then `pipeline20`: synthetic PCM through local TLS WebSocket
   ASR and HTTPS SSE fixtures to the production output path and owned GTK.
4. `pipeline-long`: the unchanged 150-codepoint/144-printable, one-character-fast
   SSE profile. A 50 ms read-only observer records only counts and timestamps from
   the verified direct-child fixture and its owned temporary readback file.
   After both tasks, the cancellation observation and full pipeline cleanup, a
   separate no-input probe creates fresh owned GTK and VTE windows. The report
   records the observed full-readback-to-exit interval and spawn/readiness times.
   This is a matched diagnostic with observer and scheduling uncertainty, not a
   latency distribution or an immediate-after-normal-output measurement. The
   unchanged 12-second probe wait for `session.pending` is a validation bound;
   application deadlines and timeouts are unmodified.
5. `focus-stream`: actual `StreamingOutput` receives one character, waits for its
   successful first press before the producer supplies the remaining 55, and
   changes focus between two owned windows after 12 presses. It requires exact
   `[12, 44]` routing, balanced events and restored mapping.
6. `ui`: the actual AppRun opens nine pages with a fresh disposable profile and
   exits normally. This mode alone does not establish native Wayland behavior,
   IPC, corrupt-config handling or FUSE mounting.

Owned-target PID, process-start and active-window guards only protect the test;
production retains current-cursor semantics. Counter and send wrappers do not
replace production algorithms or add/defer restoration. A live observation
budget never kills a pending producer or its cleanup; its PID/start identity is
retained and no next mode begins until a genuine terminal state is confirmed.

No cloud endpoints, user credentials, real microphone, user documents, clipboard
or system input-method delivery are involved in the VM checks. This is a real
Ubuntu 24.04 GNOME/Xorg desktop in KVM, not bare-metal timing. GNOME 46 native
Wayland keyboard support remains subject to the previously recorded API limit.

## Noble R1 results

All eight modes reached a genuine terminal exit 0 and their strict acceptance
records passed. All used the same offline KVM instance and actual unlocked GNOME
46/Xorg logind session 20. Evidence is under
`build/ubuntu24-perf-vm/output/a12-r1-*`: separate raw JSON, acceptance JSON, full
payloads and hashes, logs, origin audits and original UI PNGs.
`a12-r1-suite-audit.json` confirms matching preview/run payloads and no traceback,
unawaited-coroutine or asynchronous-generator cleanup warnings in the eight
primary logs. Chrome fixture subprocess warnings are retained in their own logs;
this does not claim a universally warning-free desktop.

| Owned target, 140 codepoints | 40 ms control (s) | Default 20 ms (s) |
| --- | ---: | ---: |
| Chrome textarea | 18.1806 | 9.4846 |
| Chrome contenteditable | 18.1833 | 9.5076 |
| GTK | 18.1937 | 9.5221 |
| VTE raw terminal | 18.1804 | 9.4959 |

Every target received the exact fixed sample, with balanced presses/releases,
136 mapping writes and one successful restoration. GTK cancellation delivered
exactly the first 12 codepoints, had no tail during the 0.5-second observation,
and restored mapping (13 writes/one restore).

Both normal local TLS pipelines delivered all 25 codepoints exactly, ignored
ASR previews, allowed only final ASR into polishing and sent the first character
before polishing completed. Cancelled tasks produced no late tail; server errors
were empty and fixture threads closed. Stop-to-first-character was
58.544/55.776 ms for control/default; stop-to-output-completed was
3,305.197/1,876.008 ms. Each successful stream had 27 mapping writes, three
restorations and three completed insertions; the cancelled stream had 2/1/0.
These are local fixture results, not cloud response times or speech accuracy.

The fast-long stream delivered all 150 codepoints exactly. It recorded 150
mapping writes, six restorations and six completed insertions; cancellation
recorded 2/1/0. Stop-to-first-character was 48.700 ms and
stop-to-output-completed was 10,164.228 ms. The count observer saw full readback
2,797.501 ms before complete process exit. After both tasks and cleanup, the
readiness subprocess was created 21.288 ms after observed exit; its GTK fixture
started at exit +435.917 ms and became ready in 0.1747 s. VTE started at
+628.615 ms and became ready in 0.3388 s. This single observed fast-arrival case
corroborates the earlier source diagnostic within its stated scope. It does not
establish recovery when fragments arrive slowly enough for the output queue to
empty between insertions.

The real StreamingOutput focus test received exactly `[12, 44]` in two owned
windows. Its lone first character was successfully pressed before the remaining
55 were queued. First press took 38.954 ms; output took 3.9613 s, with 57 mapping
writes/three restorations and exact routing, balanced events and clean mapping.
The AppRun UI produced nine pages and exited 0. Original PNGs and `contact.png`
are in `a12-r1-ui-pages`; long provider pages have scrollbars. This UI mode does
not include IPC, corrupt-profile or native Wayland acceptance.

The separately recorded `a12-r1-preservation.json` confirms unchanged hashes for
three existing user JSON files, a11/a10/a9/stable artifacts, and the new a12
artifact. The non-GUI entry smoke audit is
`build/performance-a12-entry-audit.json` with its separate log.

## Remaining acceptance

The separate [paced-arrival counterexample](performance-a12-paced-validation.md)
used the same actual package and sample, with a configured 70 ms server interval.
It delivered all 150 codepoints but made 288 mapping writes/150 restorations and
a new GTK fixture took 5.8435 s to become ready after both tasks and cleanup.
Its mechanical acceptance passed; the latency issue remains unresolved. R1
fast-arrival results must not be extrapolated to this workload. Root independently
reviewed the R1 raw results, all 11 module origins, preview/run pairs, nine-page
contact and provider-page originals. A future production fix requires separate
source and actual-package validation; none is inferred from these fixtures.

Host Ubuntu 26.04 XWayland four-target/cancellation checks, actual-microphone to
local-TLS pipeline, and native Wayland UI/IPC/corrupt-profile/normal-exit checks
remain pending with separate a12 paths and disposable profiles. No validation
here establishes cloud speech accuracy or unrestricted application compatibility.
Existing artifacts, stable alias and user JSON files must remain unchanged.
