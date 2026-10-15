# a12 paced-arrival counterexample

The actual a12 package accurately delivered the paced 150-codepoint stream and
completed its functional checks, but a new GTK window took **5.8435 seconds** to
become ready. The mechanical `passed` field does not establish that the desktop
latency problem is solved. Host testing is deferred; no product change, release,
deployment or repeated attempt is included in this diagnostic.

## Frozen inputs and reproducibility

- Product: `06f5600a57402335e97b3975afc38009d6233e58`, actual
  `dist/InkEcho-0.1.0a12-x86_64.AppImage` (108,907,000 bytes), SHA256
  `e31dbc6301318ab10632c12a7437ae7cd01482f2b1ee39655a82e43b6900eae9`.
- New controller: `scripts/validation/ubuntu24_vm_a12_paced.py`, SHA256
  `d421e8582197651f519bf301221b463648070ac2f09dc0c75b464c7feb3cc24f`.
- Separate snapshot `build/ubuntu24-perf-vm/input/a12-r2-paced/manifest.json`,
  SHA256 `c88deb05096c4a1681eb38eaafcfd8271d8251b1b511200995ee1652db5dc507`:
  all 43 product source audit references and eight tool/license files.
- Fixed fixture: `performance_package_probe.py`, SHA256
  `26ba7b1198846f9f1585d473aeee7c5767aebf20634c0d17627a105e4ae2bb0d`.
  Profile `one-character-paced-long` retains the same 150 codepoints/144 printable
  characters; the configured server sleep between fragments is 0.07 seconds.
  This parameter is not a measurement of client arrival intervals.
- Complete preview and executed payloads are byte-identical, SHA256
  `cd711f7e0329c3324858e1a9a04d000c52b11b4e8ec33fca13a984131837c699`,
  archived as `build/ubuntu24-perf-vm/output/a12-r2-paced-{preview,payload}.py`
  with adjacent hash manifests. Root reviewed the complete derivation, snapshot,
  payload and Ruff/format/compile checks before execution; its independent
  fixture regression passed 115 focused tests.

Reproduce only in the dedicated existing offline VM after reviewing the full
payload: prepare and preview the new controller, then run its single `run`
action. Evidence paths are exclusive; do not overwrite an existing snapshot or
rerun into an existing output label. Historical a11/R1/R7 inputs and reports
remain unchanged.

The new controller derives the reviewed R1 guest procedure by explicit evidence
name/profile replacements and adds a gate for the configured 0.07-second delay.
The actual runtime directory remains
`/home/inkecho/inkecho-a12-runtime-r1/squashfs-root`; this was a reuse, not a new
extraction. Full inventory, license and 43 source hashes were rechecked before
execution. Production imports use only that AppDir's packages and its shipped
Python/Qt: ten application module origins, including streaming and keyboard,
plus websockets are hash-checked. There is no source-root override, candidate
patch or production algorithm replacement.

## Actual run

The same real Ubuntu 24.04.5/KVM guest, kernel 6.8.0-142-generic, GNOME Shell 46.0
and unlocked actual Xorg logind session 20 were retained. Producer PID 50515,
start ticks 827699, and subsequent readiness PID 50542, start ticks 829259, both
reached natural exit 0. No observation timeout or forced cleanup occurred.

The pipeline delivered exactly 150 codepoints; ASR previews were excluded,
first output occurred before polishing completed, cancellation had no late tail,
server errors were empty and fixture threads closed. Successful output recorded
**288 mapping writes / 150 successful restorations / 150 completed insertions**.
The cancellation task recorded 2/1/0. Thus merging already queued fragments did
not reduce restoration frequency for this particular paced workload. The server
reported 152 successful delta flushes across the complete and cancelled tasks;
that is not a count of received client fragments.

| Measurement | Observed value |
| --- | ---: |
| Stop to first successful press | 42.489 ms |
| Stop to output completed | 10,537.782 ms |
| Polishing duration | 10,533.351 ms |
| Observed full readback to complete pipeline exit | 2,767.659 ms |
| Readiness subprocess spawn after observed exit | 4.857 ms |
| GTK fixture spawn after observed exit | 443.529 ms |
| GTK fixture readiness from its spawn | **5.8435 s** |
| VTE fixture spawn after observed exit | 6,305.979 ms |
| VTE fixture readiness from its spawn | 0.3393 s |

The 50 ms observer reads only a verified direct-child fixture's owned temporary
readback file and records counts/timestamps. Sampling and scheduling uncertainty
apply. Readiness starts after the complete normal task, second cancellation
task, 1.2-second cancellation observation and full cleanup. It is not a test of
windows created immediately after the normal task's last character. The original
12-second probe wait for `session.pending`, application deadlines, window-ready
attempt count, production settling times and ownership guards were unchanged.
No extra GetActive query was inserted before readiness.

The existing functional readiness gate passed, but this result is a direct
counterexample to extending R1 fast-arrival responsiveness to paced arrivals.
It does not by itself prove the internal Mutter mechanism or a latency
distribution. A production repair needs separate source and actual-package
validation, including cancellation, first-character timing and current-cursor
focus switching; no experimental restoration wrapper was used here.

## Evidence and boundaries

Raw pipeline, origins, acceptance, next-window JSON and logs are under
`build/ubuntu24-perf-vm/output/a12-r2-paced-pipeline-long*`.
`a12-r2-paced-audit.json` confirms preview/run identity and no traceback,
unawaited-coroutine or asynchronous-generator warnings in both primary logs.
All targets were newly created, owned fixtures; no clipboard, input-method
submission, real microphone, user credentials, user documents or cloud ASR was
used. The real KVM desktop is not bare-metal timing. This evidence does not
claim GNOME 46 native Wayland input support or cloud speech accuracy.
