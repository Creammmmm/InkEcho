# Memory-only target comparison preparation — 2026-10-16

This phase adds the parent side of a controlled GTK memory target to the
[phase-one comparison](performance-cloud-comparison-validation.md). The first
actual GTK run failed; revised R2 normal A/B execution **passed the limited
local-TLS/owned-GTK acceptance**, independently reviewed by the root agent.
No cloud/keyring/microphone path is enabled. The first desktop scope is only
configuration A then B with fixed generated audio and fixed local TLS results;
other `--owned-gtk` scenarios are rejected before opening anything.

## Source and process controls

Execution uses the original worktree's absolute entry path, not copied scripts.
The reviewed plan fingerprints the entry, local TLS fixture, new parent module,
owned GTK child and existing `performance_host_a13.py` preflight implementation.
The worker repeats that fingerprint check and full a13 artifact/inventory audit.
All five files remained frozen throughout each actual run. Separately verified
R1 and R2 audit copies are not execution inputs.

The native controller is the existing reviewed
`build/a13-host-r3/native/xdotool`, not an assumed system installation. The plan
pins its wrapper, `bin/xdotool` and `lib/libxdo.so.3` hashes and checks their
actual original locations; the wrapper embeds those original locations.
The child is `scripts/feasibility/owned_memory_text_fixture.py`, pinned at
`ce73be70846dfa3725156c7e7710ec21b500fce492f7ada8765ce77c5abf8849`.
This phase does not modify that independently reviewed GTK implementation.

The R2 actual worker used a13's shipped Python, AppRun Python/library/Qt paths,
production ManagedQtEventLoop and X11 Qt (`xcb`). HOME, XDG directories and TMP
are isolated. Only explicit desktop connection/session variables are preserved.
Existing read-only GNOME screen-lock and logind checks run before QApplication;
unknown, locked or unverified sessions fail without changing system settings.
The system-Python GTK child gets `GDK_BACKEND=x11` and the simple GTK text
context; package Python, Qt and library variables are removed to protect GI.

Worker and GTK child start new signal sessions. Each Popen owner immediately
records PID, process start ticks and exact credential-free argv. The bounded
anonymous socket protocol returns text to RAM only; no text file, stdout body
or requested-text accumulator is used. Disk records contain process metadata,
counts, equality flags and production TaskTiming only.

A fixture-only guard checks the active window, PID and start ticks against the
owned target set immediately before every press. Releases remain allowed after
focus changes. Production KeyboardInput still selects the current cursor and
keeps its R8 output-session mapping lifecycle. Recording/feed performs no focus
reads. Only after that synthetic recording does the fixture activate its own
target, outside the stop-to-first timing interval. This controlled placement is
not a product rule binding future output to a captured target.

The readback is compared in memory after the real Session producer reaches its
terminal state. Session.close and all pending producers must complete before
the target receives normal protocol close. Only the original Popen owner may
record a process exit code; a missing PID never implies exit zero. Unexpected
readiness retains the already recorded identity and fails. A read, readiness,
activation, close or exit observation timeout shields the same operation,
preserves the handle and waits without killing or restarting it. After any
timeout or failed acceptance, the second arm is not started.

## Completed local checks

Ruff lint and formatting checks passed on the five Python implementation/test
files changed or reused here. The two focused test files passed **45 tests in
9.86 seconds**, using only pure process/socket controls, a simulated display and
loopback TLS. Tests cover malformed/oversized/duplicate/invalid-UTF8 frames,
readiness rejection with retained identity, read/close observation timeout,
no restart/kill, missing-PID ambiguity, signal-session creation, delivery outside
owned windows, PID/start mismatches, releases after focus changes, isolated
environments, immediate per-arm acceptance and Session-before-target cleanup.
The cleanup integration uses a simulated target and is not GTK evidence.

The updated entry also ran the actual a13 shipped Python in **offscreen mode
with asyncio.run**, naturally exiting zero for all ten original synthetic
arm/scenario combinations. Eight actual package module origins were verified,
now including `inkecho.runtime`; the runtime module's provenance alone is not
an actual ManagedQt desktop run. Results report
`package_protocol_synthetic_display`, not desktop/cloud acceptance.

Phase-one `build/performance-cloud-comparison-{plan,offline}.json` is unchanged.
New evidence is separate:

- `build/performance-memory-comparison-tests.log`
- `build/performance-memory-comparison-phase2/headless-plan.json`
- `build/performance-memory-comparison-phase2/headless-offline.json`
- `build/performance-memory-comparison-phase2/owned-plan.json`
- `build/performance-memory-comparison-phase2/owned-preview.json`

The original R1 headless plan fingerprint is
`e43cf18e9b59433acc6434dfba7f63464bd2cbe4bb691353b08c23499d4ca8dc`.
The original R1 owned plan fingerprint is
`6db39b98f297002e5bfb679ab747efffc919b4013efaaaa4b5a59bef5fbe1384`.
Both bind the same historical R1 source and differ in explicitly selected display
mode/native controls. Changing any bound file requires a newly reviewed plan.

## First actual desktop run — retained failure

The designated agent executed the reviewed R1 normal command once. Launcher
PID 579710/start 28054350 naturally exited 1; shipped-Python worker PID
579711/start 28054386 naturally exited 1. Its sole GTK target PID
579727/start 28054443 verified readiness with XID 37748739, acknowledged normal
protocol close and naturally exited 0. Popen owners confirmed both terminal
states; no observation timeout occurred. B was not started. Stdout contained
only the fixed generic failure, stderr was empty, and no arm timing/readback
metadata was retained. This proves readiness/cleanup, **not successful input or
the reason for rejection**.

Original `owned-normal.json`, `normal-handle.json`, preview and observation
records remain unchanged under `build/performance-memory-comparison-phase2`.
Before any R2 change, all five R1 bound scripts were copied to its `audit-source`
tree and checked against the original plan hashes. `audit-source-record.json`
records those checks; these copies are audit material, never execution inputs.

Static review found a separate, definite fixture guard contract error:
production `_XDriver.focus()` validates ancestry under the active top-level
window and then returns the actual focused child XID. R1 incorrectly required
the dispatch child to equal the owned top-level and read the child's PID.
R2 instead matches the active top-level against the owned set, checks its
PID/start identity and requires production focus to equal the dispatch XID.
Releases remain unrestricted for cleanup. Pure tests cover top 21 with child
211/PID only on top, plus outside-active and wrong-dispatch rejection. The
missing R1 arm metadata prevents claiming this was its proven failure cause.

R2 records fixed-schema arm flags, counts, TaskTiming and allowlisted Session
diagnostic codes **before acceptance**, retaining failed arm metadata when it
stops B. Unknown exception text is never formatted or persisted. First fixed
`failure_code`/`failed_phase` survive later cleanup and owner exit observation.
Guard check booleans distinguish owned top-level from dispatched child;
mapping-before/after-GTK and before-close booleans diagnose baseline drift
without weakening the original mapping gate. The actual keyboard closed state
is also recorded. No guard or mapping condition is bypassed to obtain a pass.

R2 focused checks passed **49 tests in 9.88 seconds** with pure controls,
simulated display and local TLS; Ruff checks passed. New records are
`build/performance-memory-comparison-r2-tests.log` and the independent
`build/performance-memory-comparison-phase2-r2/{owned-plan,owned-preview}.json`.
The R2 plan fingerprint is
`1447bcf9704c59cc05f6fa9d2aed1767c41d40db85aa457073acad6aafed6742`.

## R2 actual desktop run — limited acceptance passed

After root review of the complete launcher/worker argv, five source hashes,
native controls and environment policy, the designated agent executed normal
A then B once. This used the actual a13 Session, TaskTiming, HTTP/WSS/SSE
parsers, KeyboardInput and ManagedQtEventLoop under the host GNOME Wayland
session's XWayland path, with new owned system-Python GTK windows. The read-only
host preflight verified an unlocked graphical session. No cloud, credentials,
microphone, clipboard or input method was used.

| Role | PID | Start ticks | Owner-observed natural exit |
| --- | --- | --- | --- |
| Launcher | 581213 | 28107250 | 0 |
| Shipped-Python worker | 581214 | 28107287 | 0 |
| A system-Python GTK target | 581229 | 28107343 | 0, ready and close ACK |
| B system-Python GTK target | 581255 | 28107492 | 0, ready and close ACK |

The two targets reused top-level XID `37748739`, but their PIDs and start ticks
were different and checked by the guard. Both reported all five ownership/focus
checks true and `dispatch_equals_owned_top=false`: the actual dispatch went to
the current GTK child window. This confirms that distinguishing focused child
from owned top-level is required by this real target; the missing R1 arm data
still prevents retroactively assigning its sole failure cause.

| Normal local configuration | A | B |
| --- | --- | --- |
| Actual ASR fixture calls (HTTP/WSS) | 1 / 0 | 0 / 1 |
| Actual polishing fixture calls | 1 buffered | 1 SSE |
| Exact in-memory readback | 6 characters | 6 characters |
| Successful presses / releases | 6 / 6 | 6 / 6 |
| Stop request to first dispatched character | 298.232 ms | 42.158 ms |
| Stop request to output completed | 666.895 ms | 437.867 ms |
| Recording-stop-request milestone from task start | 230.027 ms | 229.325 ms |

The generated PCM contains 200 ms of audio per arm. Two paced feed waits and
target activation occur before the stop request, so this is **not exactly equal
200 ms wall-clock recording**: the actual milestones above are approximately
230 ms. It is also not public-WAV playback. Stop-to-first uses production
TaskTiming and actual successful keyboard dispatch, not glyph rendering time.
These single local observations demonstrate orchestration under fixed fixture
delays; they do not establish a cloud speed-up or a latency distribution.

Both rows passed the CLI acceptance, with exact audio/forwarded ASR input,
no focus reads during recording/feed, no tail/replay, matched releases,
unchanged keyboard mapping during target startup, restored mapping before
Session.close and a closed keyboard driver afterward. Session diagnostics were
empty. Each completed Session and all producers were closed before its target
received normal close. No timeout or failure was recorded; stdout and handle
contained only approved metadata and stderr was empty. Root independently
checked both rows, their safe-schema handle copies, all process terminal
receipts and absence of text markers in records.

All eight package origins matched the pinned a13 inventory:

| Module | SHA-256 |
| --- | --- |
| `inkecho.app` | `d4e58b4cb6de9ceed5d471574bc32e6a1cf255b125e93eb49838ed41146482bd` |
| `inkecho.performance` | `4957fe5e2ed956be3b238387f0b31eaac34fcfb772b524dde244bf38db7167cb` |
| `inkecho.providers` | `52bbe926fe55a0ddace510f6d78b7e88fcb71c1ffb2aee4bd4253939d1af72f6` |
| `inkecho.realtime` | `b6e8a37b1b2f1a0cb2c202284815bb1c214eb98ceca3f8dd7856c7a488efc573` |
| `inkecho.polish_stream` | `47588cd3b4e546e6a8f6eef1057208d32c49ce6cee564919e1f42660b10582dd` |
| `inkecho.streaming_output` | `c46eb6e13627067d9c918415defe57eb93898f30e3e57795ed9c828edab89ce1` |
| `inkecho.platform.keyboard` | `03e67f372bc669f279b135f3f4a73db6bafb4b30c2a862a83292e72ce11f968a` |
| `inkecho.runtime` | `28508099d1811f27562b548c71403c85601bab2e961a68db77ca72692ea798bf` |

Raw R2 evidence stays under
`build/performance-memory-comparison-phase2-r2/`: `owned-normal.json`,
`normal-handle.json`, `owned-launcher.json`, `owned-launcher-terminal.json`,
`owned-observer.log`, the plan and preview. The launcher record preserves its
complete argv; the handle preserves the exact shipped-worker argv and both
system-Python child argv (`--fd 22` and `--fd 32`). `audit-source-record.json`
verifies R2 copies of the five bound scripts against the actual plan. They are
not executed or substituted for R1 evidence.

Read-only preservation checks after R2 match the pre-a13 baseline for all three
existing user JSON files and a9/a10/a11/a12/stable artifacts. Including the
unchanged a13 artifact gives six preserved artifacts; a13 remains SHA-256
`8dce4eedee71373a27e0e6507592b1240617412a8a6f114230b9a53f4d286a89`.
The booleans are recorded in R2 `preservation.json`; no config or artifact was
rewritten, deployed, pushed or released.

## Exact R2 command retained for review

The following command was executed once. Its original handle/output must not be
overwritten; any future run requires a new reviewed plan/path and designated
desktop execution. The machine-readable preview preserves its environment
policy and complete argv.

```sh
/home/lth/github/InkEcho/.venv/bin/python \
  /home/lth/github/InkEcho/scripts/validation/performance_cloud_comparison.py \
  --package-root /home/lth/github/InkEcho/build/performance-a13-extracted-iwmzy2mn/squashfs-root/packages \
  --owned-gtk \
  --xdotool /home/lth/github/InkEcho/build/a13-host-r3/native/xdotool \
  --offline --scenario normal \
  --handle /home/lth/github/InkEcho/build/performance-memory-comparison-phase2-r2/normal-handle.json \
  --accept-plan-sha 1447bcf9704c59cc05f6fa9d2aed1767c41d40db85aa457073acad6aafed6742 \
  > /home/lth/github/InkEcho/build/performance-memory-comparison-phase2-r2/owned-normal.json
```

Observe the same run, without restarting it or reading target text:

```sh
/home/lth/github/InkEcho/.venv/bin/python \
  /home/lth/github/InkEcho/scripts/validation/performance_cloud_comparison.py \
  --observe-handle /home/lth/github/InkEcho/build/performance-memory-comparison-phase2-r2/normal-handle.json
```

Real desktop focus/cancel/expiry scenarios are not enabled in this first slice.
Stage three and the live four-call real-speech comparison still require code
preparation, review and separate execution authorization. Those steps include
the full public-WAV timeline, credential-boundary validation and outgoing call
budget enforcement; this is not merely waiting for permission. The local R2
result does not complete that original goal or prove cloud latency reduction.
