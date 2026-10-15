# Noble memory comparison adapter — 2026-10-16

`scripts/validation/performance_noble_comparison.py` prepares the existing
Ubuntu 24.04 GNOME46/Xorg guest for the [comparison core](performance-live-comparison-validation.md).
The adapter's actual normal A/B execution **passed root-reviewed acceptance on
the specified Noble guest**. Its only execution mode is
generated PCM → owned loopback TLS → actual a13 Session → owned GTK memory
readback. It has no cloud, microphone, public-WAV, user-configuration or keyring
branch. The real-cloud route on Ubuntu 24.04 remains unprepared.

## Historical source boundaries

The earlier [owned GTK comparison](performance-memory-comparison-validation.md)
is bound to commit `9e0aeee109c348386bf315053edc8759c5102eba` and its retained
phase-two R1/R2 raw results and audit-source copies. The comparison core is bound
to `1647df4a0d058b6336fc4d5198e17349557dfe37`; its final six-script audit copies
remain under `build/performance-live-comparison-core-r3/audit-source`.
The root agent validated that clean core commit with 1245 passed / 3 skipped
and Ruff/format checks on 253 files.

This adapter adds only two necessary seams to existing helpers:
MemoryTarget accepts an optional native verifier and child path, with the
previous host behavior as its default; the core forwards optional target
arguments. Product sources and the a13 artifact are unchanged. These changes
legitimately invalidate the earlier worktree fingerprints. Use the historical
commits/audit copies for old evidence, not an old fingerprint with current files.
No earlier raw results or source copies were overwritten or reinterpreted.

## Node, plan and safety controls

The root independently reviewed fresh read-only metadata in
`build/performance-live-comparison-noble-prep-r2/` (`container.json`,
`qemu-qmp.json`, `guest.json`, `ssh-terminal.json`). It describes the existing
running KVM guest, Ubuntu 24.04.5 / kernel 6.8.0-142-generic, GNOME46.0,
actual Xorg logind session20, uid1000, GNOME PID26971/start95097, unlocked
with ScreenSaver inactive. No validation producer was present. The container's
external networks remained disconnected. Those observations are historical;
the adapter must repeat its own checks before launch and before each arm.
The guest's recorded systemd degraded state is not treated as a dead VM.

The exact system native controls are pinned:

| Guest file | SHA-256 |
| --- | --- |
| `/usr/bin/xdotool` | `a21dba4297e197ef27035071f6a36061cc8604ac360df19792db99ad3fd9a5f5` |
| `/usr/lib/x86_64-linux-gnu/libxdo.so.3` | `13b91b899cbbae9030a00405a50c203f66d9adc13796bc22508d3cfbf731a231` |

The existing memory GTK child remains pinned at
`ce73be70846dfa3725156c7e7710ec21b500fce492f7ada8765ce77c5abf8849`.
Injected native verification runs before child startup and activation.
The read-only preflight verifies Ubuntu24.04, kernel, uid, the same GNOME
PID/start/comm/version, session20 User/Type/LockedHint and ScreenSaver false.
Unknown state fails closed. It neither unlocks nor changes desktop settings.
Native queries receive only a fixed desktop/PATH environment, stripping package
library variables and arbitrary inherited secrets; command output is never
copied into diagnostic records.

The default guest `--plan` audits all 3958 package files / 1048 links and seven
staged script hashes, actual native hashes, exact execution paths and node
preflight. It imports no Qt or keyring and reads no user JSON or public audio.
The separate host `--preview` verifies staged sources and the local package but
only declares guest pins. It explicitly says guest preflight was not run.
**Its fingerprint cannot authorize guest execution.** Actual `--offline-owned`
requires the independently reviewed actual guest plan fingerprint and repeats
the checks in the shipped-Python worker and before each arm.

Only the explicit graphical connection whitelist is preserved: DISPLAY `:0`,
the guest's `/run/user/1000/gdm/Xauthority`, fixed session bus, session type
`x11`, session ID20 and desktop `ubuntu:GNOME`. All writable HOME/XDG/TMP
locations, including runtime, stay private beside the exclusive handle. Qt uses
`xcb`; the child uses system Python with simple GTK context and without package
Python/library variables. No user config is copied into this profile.

Each arm uses the existing core's actual a13 Session, cold ProviderClient,
HTTP/WSS parsers, polishing/SSE and KeyboardInput. Credentials are fixed fake
values; the network transport can only target its owned loopback TLS fixtures.
The fixture verifies original generated audio and ASR-to-polishing text in RAM;
each arm must have exactly its expected ASR transport and one polishing call.
The shared budget records reservations before sends. Safe result metadata is
written before CLI acceptance; failure or observation timeout prevents arm B.
The existing current-focus child/toplevel/PID/start delivery guard, TaskTiming,
20ms buffer-read polling, partial-output isolation and Session-before-target
cleanup remain in use. This adapter does not claim new focus-switch/cancellation
desktop scenarios; those have separate historical evidence.

The launcher, shipped-Python worker and GTK children retain immediate PID/start
and credential-free argv records. The original Popen owner must observe natural
terminal exit; a missing PID is not success. Signal sessions are separate.
Observation timeout retains the same handle and operation, without kill/restart.
An interrupted observer must leave the worker's persistent profile intact.
All actual-run producers reached owner-observed natural terminal states.

## Completed local checks

The focused suite passed **97 tests in 6.95 seconds**, including the new adapter
tests plus the parent memory controls and core tests. Ruff lint/format passed on
the adapter, its tests and both modified helpers. The new tests use only command
and process stubs, an anonymous socketpair and the existing synthetic-display
local TLS tests. They do not start GTK or run guest commands. They cover strict
node/native checks, rejected unknown lock state, stripped native environment,
host-preview versus actual-plan separation, default/injected parent controls,
private worker paths, exact argv, redacted failure and no next arm after failure.

Evidence:

- `build/performance-noble-comparison-r1/tests.log`: approved local socket/TLS run,
  unified-exec session91848 naturally exited0.
- `build/performance-noble-comparison-tests.log`: earlier approved run before
  removing one source-string assertion, 98 passed / 6.80s; session87783 exited0.
- `build/performance-noble-comparison-r1/sandbox-attempt.json`: the first attempt
  used the restricted socket sandbox and had EPERM failures. The original command
  was `.venv/bin/python -m pytest -q tests/test_performance_noble_comparison.py
  tests/test_performance_memory_target.py --tb=short`. Its original captured
  output is the session15301 tool transcript, not a redirected stdout file.
  It reported 8 failed / 22 passed / 41.44s after SIGINT to identified pytest
  PID588792; the same owner tool subsequently reported exit2. This retained
  metadata is explicitly not raw stdout. No GUI/product producer was involved,
  and this sandbox failure is not a product or desktop acceptance result.

## Staged preview and exact proposed commands

Seven hash-exact script copies plus `manifest.json` are staged at
`build/ubuntu24-perf-vm/input/live-comparison-noble-r1`; the existing read-only
9p mount exposes them as `/mnt/input/live-comparison-noble-r1`.
No artifact copy, user JSON, public WAV or credential was added to that payload.
The guest uses its previously audited a13 AppDir and original mounted artifact:

- AppDir: `/home/inkecho/inkecho-a13-runtime-r1/squashfs-root`.
- Artifact: `/mnt/input/a13-r1/InkEcho-0.1.0a13-x86_64.AppImage`.
- Artifact SHA-256: `8dce4eedee71373a27e0e6507592b1240617412a8a6f114230b9a53f4d286a89`.
- Exclusive handle: `/mnt/output/live-comparison-noble-r1/handle.json`.
- Persistent private profile: `/mnt/output/live-comparison-noble-r1/worker-profile`.

The host-only staged-source preview was generated with:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B build/ubuntu24-perf-vm/input/live-comparison-noble-r1/scripts/validation/performance_noble_comparison.py \
  --preview \
  --package-root /home/lth/github/InkEcho/build/performance-a13-extracted-iwmzy2mn/squashfs-root/packages \
  --appimage /home/lth/github/InkEcho/dist/InkEcho-0.1.0a13-x86_64.AppImage
```

Its clean record is `build/performance-noble-comparison-r1/host-preview-clean.json`,
fingerprint `192c6e8e9e4d2f30b92de725beb6e312d5a19d044aeed807d9ead776f423e541`.
The original `host-preview.json` is retained unchanged. That first preview had
generated three unmanifested Python3.13 `.pyc` caches. Before any guest use,
exactly those three files and their empty cache directory were removed. The
clean preview disables bytecode writes and equals the original preview exactly;
the directory now contains only seven hash-verified sources and `manifest.json`,
with no `.pyc` or extra files. This is recorded in `staging-clean.json` alongside
the previews. Disabling writes alone would not prevent reading an existing cache.
After root review, the sole desktop agent ran this read-only guest plan (with
`PYTHONDONTWRITEBYTECODE=1` and Python's `-B` cache-write protection):

```sh
/usr/bin/python3 /mnt/input/live-comparison-noble-r1/scripts/validation/performance_noble_comparison.py \
  --package-root /home/inkecho/inkecho-a13-runtime-r1/squashfs-root/packages \
  --appimage /mnt/input/a13-r1/InkEcho-0.1.0a13-x86_64.AppImage --plan
```

The guest plan naturally exited0 with empty stderr and is retained at
`build/performance-noble-comparison-r1/plan.json`. Its actual fingerprint is
`1c285f6c458434180ffb7975a915ea083713e97c7fb4f5528766255c7685d621`.
The root independently matched the seven script hashes, actual native pins,
full package inventory and unlocked node preflight. The host preview's different
fingerprint was never used for execution. Plan SSH process identities and
terminal status are retained in `plan-ssh-{owner,terminal}.json` beside that plan.

Only after review of this actual plan, the root approved the sole desktop agent's
one normal A→B execution. The actual guest launcher argv was:

```sh
/usr/bin/python3 -B /mnt/input/live-comparison-noble-r1/scripts/validation/performance_noble_comparison.py \
  --package-root /home/inkecho/inkecho-a13-runtime-r1/squashfs-root/packages \
  --appimage /mnt/input/a13-r1/InkEcho-0.1.0a13-x86_64.AppImage \
  --offline-owned \
  --accept-plan-sha 1c285f6c458434180ffb7975a915ea083713e97c7fb4f5528766255c7685d621
```

The launcher started the exact same absolute script with a13's
`/home/inkecho/inkecho-a13-runtime-r1/squashfs-root/usr/bin/python3`, the same
package/artifact arguments and accepted fingerprint, plus `--worker`, without
the launcher's `-B` argument; its environment already set
`PYTHONDONTWRITEBYTECODE=1`. The worker ran production ManagedQtEventLoop with
actual Xorg Qt, not asyncio.run/offscreen. Each GTK child argv was
`/usr/bin/python3 /mnt/input/live-comparison-noble-r1/scripts/feasibility/owned_memory_text_fixture.py --fd N`,
with actual inherited anonymous FDs22 for A and32 for B. These were independently
matched to the reviewed paths, rather than inferred from process names.

## Actual Noble normal A/B acceptance

The root independently read the complete stdout, handle, launcher owner/terminal,
SSH terminal and preservation records. Both rows passed the core's actual
`safe_result` and `accept` functions and exactly matched the handle's metadata
mirror. All nine actual package-module hashes matched the audited a13 package,
including Session, HTTP/WSS/SSE, KeyboardInput, runtime and security. Both stderr
files were empty. There was no timeout or failed producer.

| Process | PID | Start ticks | Natural owner-observed exit |
| --- | --- | --- | --- |
| Host SSH operator | 590721 | 28394959 | 0 |
| Guest launcher | 53838 | 1676719 | 0 |
| a13 shipped-Python worker | 53849 | 1676806 | 0 |
| Owned GTK A | 53873 | 1677031 | 0, ready verified and close ACK |
| Owned GTK B | 53898 | 1677268 | 0, ready verified and close ACK |

The GTK server reused toplevel XID44040195 between arms. Their distinct PID/start
identities, actual readiness and Popen-owner exits were checked separately; XID
reuse was not treated as identity. The SSH exit alone was not used as evidence
that the worker or targets had exited. The SSH argv and wrapper input fingerprint
are retained in `execution-ssh-owner.json`; wrapper SHA-256 is
`0588a7647dfad56f627ee371ffdbc28e46e0dc8b79d6ee0576e15610af2fa2d6`.

| Single local-fixture observation | A: HTTP + buffered polish | B: WSS + SSE polish |
| --- | --- | --- |
| Stop request → first keyboard dispatch | 373.151 ms | 47.352 ms |
| Stop → first nonempty buffer observation | 407.545 ms | 85.658 ms |
| Stop request → output completed | 767.131 ms | 447.821 ms |
| Exact readback / confirmed / dispatched | 6 / 6 / 6 | 6 / 6 / 6 |
| Reserved fixture calls | ASR1 + polishing1 | ASR1 + polishing1 |

Both arms had matched releases, no tail/replay, no recording-time focus reads,
restored mappings and closed keyboard drivers, clean target exit and no Session
diagnostics. The production stop-request events occurred at 204.416ms for A and
205.071ms for B on their own task timelines. The audio payload was exactly
200ms of generated PCM; it was not a claim of exactly200ms wall-clock recording.
The first-buffer value is the existing 20ms polling/roundtrip observation, not
glyph presentation. A's first dispatch followed polish completion; B's preceded
completion, demonstrating the two intended local parser/output paths.

Raw evidence under
`build/ubuntu24-perf-vm/output/live-comparison-noble-r1/`:

- `launcher-stdout.json`: complete metadata result and nine actual origins.
- `handle.json`: exact worker/GTK argv, identities, actual exits, reservations and
  per-arm metadata persisted by the owning producers.
- `launcher-owner.json`, `launcher-terminal.json`, `launcher-stderr.log`.

Host operator evidence under `build/performance-noble-comparison-r1/`:

- `execution-ssh-{stdout.jsonl,stderr.log,owner.json,terminal.json}`.
- `guest-execution-wrapper.py`: reviewed bounded guest owner, not a product patch.
- `post-preservation.json`: all three user JSON hashes and six AppImage artifacts
  unchanged; all seven staged source hashes still match, no missing/extra files
  or `.pyc`; the running container still has `Networks=[]`.

## Remaining scope

This acceptance covers two normal arms with generated audio, owned loopback TLS,
actual a13/ManagedQt and one owned GTK field per arm on this Noble Xorg session.
The fixed service response, audio duration, output length, cold-client conditions
and polling overhead constrain these single observations. They do not establish
real-speech accuracy, cloud latency improvement, long-stream latency, a performance
distribution, new Noble cancellation/focus-switch results or broader Ubuntu24
desktop support. No public WAV, real microphone or stored credential was used.
The actual public-WAV cloud comparison still needs a separately reviewed Noble
network/credential-memory route and explicit human authorization for audio,
destinations and stored keys. This phase implements or attempts none of those.
