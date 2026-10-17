# Noble live A/B controller: implementation preparation

This report preserves the preparation checkpoint. On 2026-10-17, subsequent
explicit contextual human authorization and one actual Noble cloud A/B run were
accepted separately; see [the bounded cloud validation](performance-noble-cloud-validation.md).
The preparation-only boundaries below describe their original checkpoint, not
the later live result.

This stage prepared [a new controller/node tool](../scripts/validation/performance_noble_live.py)
and its [local tests](../tests/test_performance_noble_live.py). At this checkpoint root had accepted
the actual Noble read-only plan and one actual SSH/launcher/a13-worker offline
handoff, recorded below. No guest GUI, real SecretStore access, public-WAV
handoff/upload, external connection or network mutation had occurred at that point. Existing
[Noble local TLS acceptance](performance-noble-comparison-validation.md) remains
separate evidence. A valid plan hash or `--live` flag is not human authorization.
The earlier automatic refusal of the public-WAV / official destination / stored
key combination remained binding throughout preparation. On 2026-10-17, the
human's explicit permission to use keys, in context of the preceding fixed
sample/destinations/four-request/temporary-network request, was reviewed by root
before the single later run. Preparation, a plan hash or `--live` never supplied
that authorization themselves.

## Fixed experiment and staging

The experiment compares two configurations of the same shipped a13 package,
not a13 against an earlier version. A uses Qwen HTTP `qwen3-asr-flash` and
synchronous DeepSeek polish; B uses `qwen3-asr-flash-realtime` WSS and streamed
polish. Both use the existing exact workspace Qwen endpoints and
`https://api.deepseek.com/chat/completions`, `deepseek-flash`, the same fixed
public prompt, disabled thinking and 128 maximum output tokens. The original
public WAV is pinned by SHA
`0d650ab4f08bd3a5d3d59fd67d085fd0765ddabe4729294f4106fceece321fdf`,
571456 original bytes, 282322 mono PCM16 frames at 16000 Hz / 17.645125 seconds.
It is never re-encoded. Each arm gets one ASR and one polish attempt, total four,
with no discovery, warmup, request retry or replay and a new cold HTTP client.

New exclusive host staging uses
`build/ubuntu24-perf-vm/input/live-comparison-noble-cloud-r1` and
`build/ubuntu24-perf-vm/output/live-comparison-noble-cloud-r1`. The guest sees
`/mnt/input/live-comparison-noble-cloud-r1` and the corresponding `/mnt/output`
directory. The original a13 AppDir remains
`/home/inkecho/inkecho-a13-runtime-r1/squashfs-root`, with the original artifact
under `/mnt/input/a13-r1`. No old snapshot, raw evidence, product, existing seven
Noble tool sources or handoff source is changed.

Default `--role host --plan` is stdlib and read-only: it verifies full a13
inventory and links, nine tool source hashes, safe metadata/hashes of the three
host configuration JSON files, canonical credential refs, and the actual public
WAV hash/size/header. Reading that local WAV is not an upload. No credential
backend, subprocess, Qt or provider SDK is initialized. `--mode offline-handoff`
instead pins 0.2 seconds of generated silence and fixed fake keys; its plan SHA
is distinct and it never reads the public WAV. There is no arbitrary audio,
credential reference, endpoint or audio-constraints CLI override.

`--prepare` alone creates exclusive staging, copies only the nine reviewed tools
and writes two safe plans plus exact argv previews. It does not contact Docker
or SSH. Both local plan variants must pass before staging, so a missing/changed
public fixture is discovered before a future credential read. Guest `--role node
--plan` rechecks snapshot paths and sources, the entire package inventory,
existing native hashes, and the pinned Noble kernel/GNOME/session/lock state.
It refuses other known validation producers and does not start a GUI or read
audio/keys. Actual nine imported production module origins are audited later by
the actual shipped worker, before READY.

## READY, memory transfer and owners

The future host starts exactly `docker exec --interactive … ssh -T …`, with
strict existing known-host verification, a fixed remote launcher and no PTY.
Both SSH/controller and the actual shipped-Python worker use independent process
sessions. Logs are exclusive 0600 files in private directories; executing
controller/launcher/worker processes disable only their own core dumps.

The guest launcher creates private anonymous credential and READY pipes, starts
the actual a13 worker, and immediately records the actual Popen PID/start/argv
in the shared handle. It checks the worker READY against that independent record
and inventory-derived module hashes before forwarding it to host stdout. The
host independently reads the parent-owned handle and checks its command, PID and
start, plus all nine expected module hashes and zero budgets. READY never
self-authenticates its PID. The SSH stdio and child FDs must meet the strict
[anonymous-pipe handoff contract](performance-live-handoff-validation.md).

Only after READY and complete-plan revalidation can the host lazily initialize
the production SecretStore and read `provider/qwen` and `provider/deepseek`.
Each individual lookup revalidates the full plan again; audio reading also does.
The host checks the actual security module origin/hash before backend creation.
Keys and unchanged original WAV bytes pass through SSH stdin into the child's
anonymous FD. All write ends close to establish EOF before the receiver returns
RAM credentials/audio. Payloads never enter argv, environment, ordinary files,
handles or logs. Parser and backend failures use fixed codes without free-form
exception or argument echoes. Python strings are not cryptographically erased;
the tool does not claim protection against OS swap or privileged inspection.

For live mode, only after this handoff does the worker create ManagedQtEventLoop
and owned GTK, then reuse `core.run_arm`, `Budget`, `safe_result` and `accept`.
No host API substitution, custom network backend, environment proxy, URL rewrite
or TLS bypass exists. Production HTTP/WSS retains certificate/hostname/SNI
verification, no environment proxy and no redirects. The real Session retains
recording/current-cursor/expiry/cancel semantics and serial keyboard output;
late replies cannot trigger a repeated arm or text replay.

The launcher reloads the worker's latest handle before marking natural terminal,
preserving results, budget counters, imported origins and GTK identities. An
arm's cleanup witness is reset before that arm; only its returned safe row's
`mapping_restored_and_driver_closed`, `matched_releases` and `target_exit_zero`
flags prove cleanup after the HTTP context. Session.close returning alone is
insufficient. Witnesses are persisted before acceptance, so an authentication
failure can fail the experiment while still proving resource cleanup. An
exception without a returned row is conservative unknown, not evidence from A
reused for B. Owned targets must also have actual recorded terminal status.

`experiment_passed` is separate from overall `passed`: the latter remains false
until producer/resource checks and network restoration have all succeeded.
Unknown cleanup or a restoration error cannot leave a success receipt. The first
host `failure_code` and `host_failed_phase` are preserved; any later cleanup
failure has separate fixed `cleanup_failure_code` / `cleanup_failed_phase`
fields. Worker wrappers preserve the core's earlier `live_failure_code` and
`failed_phase`, or record their own first safe reason before changing phase.

Observer interruption is not a request to kill a producer. There is no timeout
termination, automatic restart, budget reset or compensating B. Existing worker
Session signal handlers remain the explicit cancellation path while an arm is
active; any future signal action must use the same verified worker identity.
SSH loss or unproven terminal/cleanup preserves identities, profiles and pending
state; it does not authorize starting another mode. The controller may wait for
natural completion instead of imposing a new deadline.

## Scoped network operation, unexecuted at preparation checkpoint

Only the existing container ID
`0582fbea0288c17e40759c823892d60c750f51b43d1de17722cabf33bd136a2f`,
original start timestamp, host PID 517799 and QEMU PID 1/start 26717597 are
accepted. Original NetworkSettings must be empty. The existing bridge is pinned
to ID `946c8b2d57de6eb9a62c60c209e9415f63881999afc389655be6cabe5b603a9f`,
driver bridge/internal false. Mutations address the container ID, not an arbitrary
name. No network is created and no global network/lock/idle setting is changed.

The live branch alone can connect that existing bridge after verified READY.
This allows normal guest TCP/TLS and may also allow guest background services to
communicate: the four-call budget applies only to this tool's API requests, not
all VM traffic. Connect intent is recorded before mutation; ambiguous failures
are not retried. After the actual worker and targets are terminal and cleanup is
verified, the owner disconnects its bridge and verifies empty NetworkSettings.
A failed experiment can still restore the network; unknown producer/cleanup
state cannot. Offline handoff never connects or disconnects any network.

Root's separate read-only network preflight is preserved at
`build/performance-noble-live-network-prep`: it observed the pinned container with
NetworkSettings empty, the existing bridge identity, and the same QEMU identity.
Those inspect/proc commands exited naturally without stderr. This is identity
evidence, not an approved or attempted network connection.

## Host staging and reviewed command templates

Root must review source, staged hashes, plan fingerprints and exact argv before
the sole executor uses any real guest path. Root performed one provisional
read-only host plan during review: 3958 files / 1048 links and the three config
hashes / fixed public WAV were verified. Source was still changing, so that
preliminary fingerprint is not a final snapshot plan and no staging occurred.
Root subsequently executed final `--prepare`, which exited 0. Independent
recalculation confirmed both plan hashes and all nine source hashes. The new
snapshot contains exactly 12 files (nine sources, two plans and preview), with
no symlinks, pyc or extra files; its output directory was empty. The full a13
3958-file / 1048-link inventory, three user configuration hashes and original
public WAV still match the fixed values. Frozen staging fingerprints are:

- Offline plan: `2c98576fa3d9913ff7f303df0bedd31c17e0a5cf0667cc3c4cdb5a0facf2e2af`.
- Live plan: `afc62ab0f059419f189c54ac3a921357b5fa5f047ec7039a3c14d3cb4aa0f5f8`.
- Preview SHA256: `554a6995dffdf19f1d0eb92d040ce55dfe8109ca94198a707480775190c2b305`.

These staging results are separate from the subsequent guest/offline acceptance
below. Cloud execution has not occurred. The reviewed host commands were:

```sh
.venv/bin/python scripts/validation/performance_noble_live.py --plan
.venv/bin/python scripts/validation/performance_noble_live.py --mode offline-handoff --plan
.venv/bin/python scripts/validation/performance_noble_live.py --prepare
```

The prepared `preview.json` contains separate precise execution argv for the two
mode fingerprints. The reviewed read-only guest plan entrypoint was:

```sh
/usr/bin/python3 -B /mnt/input/live-comparison-noble-cloud-r1/scripts/validation/performance_noble_live.py --role node --mode offline-handoff --plan
```

After its review, the host-owned local handoff used this command template:

```sh
.venv/bin/python scripts/validation/performance_noble_live.py --mode offline-handoff --offline-handoff --accept-plan-sha EXACT_OFFLINE_PLAN_SHA
```

This used actual SSH/launcher/shipped worker but only fixed generated PCM
and fake keys; it did not construct a provider SDK client, QApplication, owned
window or microphone. That actual guest step subsequently passed as recorded
below. At that preparation checkpoint, a future
`--mode live --live --accept-plan-sha EXACT_LIVE_PLAN_SHA` still required
explicit human authorization covering the WAV, both official
destinations, stored keys and necessary temporary network operation. Prepared
argv, code review and offline success cannot provide that consent.

## Actual Noble plan and offline handoff acceptance

Root independently reviewed and accepted the actual read-only node plan under
`build/performance-noble-live-plan-r1/plan.json`. Its raw JSON SHA256 is
`ca44328291543e559e9dd08e72246a14de65463a2b28ea66ddd5cd55891dd7da`;
its logical fingerprint matches the offline plan
`2c98576fa3d9913ff7f303df0bedd31c17e0a5cf0667cc3c4cdb5a0facf2e2af`
and all nine staged source hashes. SSH owner PID 599683/start 28604595 exited
naturally with code 0 and empty stderr. This command did not run a worker or
perform a handoff.

The separately reviewed single offline handoff then exited naturally with code
0 (host execution receipt 95191). Formal records are under
`build/ubuntu24-perf-vm/output/live-comparison-noble-cloud-r1/offline-handoff`:

- `controller.json` SHA256
  `22c3d438f625ce4102f469633178c04b6a982076958adb1d5dbbf1be7c55639f`.
- `handle.json` SHA256
  `7a63abd8b8ac5d5a895a1f7df6b29b1a819499418166c227db8e328bed4b3681`.
- SSH PID 599873/start 28610578 and actual a13 worker PID 54447/start 1892339
  both have original-parent observed natural exit 0.
- The worker argv matches shipped a13 Python, `-B`, role worker, offline mode,
  accepted offline fingerprint, credential FD 3 and READY FD 6. All nine actual
  module origins match the complete original a13 inventory.
- Worker `offline_handoff_verified` / `cleanup_complete` and controller `passed`
  / `experiment_passed` / `producer_terminal_and_clean` are true. Targets and
  results are empty; no API reservations or calls occurred. Both logs are zero
  bytes; records/logs have mode 0600.

Success passed the actual strict code checks for READY identity/origins, zero
initial budgets, anonymous-pipe type/direction and complete EOF. Raw READY,
credentials and audio were not recorded. The only payload was 6444 bytes of
generated 0.2-second silence and fixed fake keys; this was not real SecretStore
or public-WAV handoff validation. No SDK request, GUI or microphone was used.
The host controller's own PID/start was not persisted by this tool; receipt
95191 and exit 0 are its available execution evidence. No identity is invented
to fill that gap.

Root also read the post-run audit
`build/performance-noble-live-plan-r1/offline-handoff-audit.json`: the original
container remains running with empty NetworkSettings. The host plan, staged
sources, original a13 and three user configuration hashes were rechecked and
unchanged. This proves the specified keyless Noble handoff path while leaving
normal external TLS, real credentials, public speech recognition and cloud A/B
performance unvalidated.

## Local verification and remaining gates

```sh
.venv/bin/pytest -q tests/test_performance_noble_live.py tests/test_performance_live_handoff.py
.venv/bin/ruff check scripts/validation/performance_noble_live.py tests/test_performance_noble_live.py
.venv/bin/ruff format --check scripts/validation/performance_noble_live.py tests/test_performance_noble_live.py
```

On 2026-10-16, the initial 100-test set passed in 0.26 seconds. After review added
failure-accounting regressions, 52 controller tests plus 52 existing handoff tests
passed: 104 total in 0.29 seconds; Ruff lint/format passed. Local tests use synthetic
metadata/audio, fake credential callbacks, real anonymous pipes and one real
local Python child with stubbed node/package audits. They exercise the actual
worker handoff and launcher relay/EOF/natural-exit handling, preserved worker
results, host identity checks, bad READY and changed-plan rejection before keys
or networking, distinct offline audio, lazy per-key validation, bridge control
doubles, failure-with-cleanup, unknown cleanup/terminal, A/B shared budget/order,
and prevention of stale cleanup evidence after B raises. Added cases verify
experiment success plus restoration failure remains overall failed, experiment
failure plus cleanup failure preserves the original reason/phase, and worker
failure preserves an existing core reason. A fresh local Python
process also checks imports/default stubbed planning remain stdlib-only. The
tests do not call Docker/SSH, real keyring, public audio, SDK requests or GUI.
These results establish local control behavior, not Noble live acceptance.

Root independently repeated the final 104-test set in 0.24 seconds, with Ruff
lint and format checks passing. A separate read-only review of the final failure
accounting changes also passed. These checks did not execute a guest command or
access real credentials/cloud services.

Host source/test/plan review, staging, actual keyless guest plan and actual
offline handoff are complete. Exact clean-HEAD verification is recorded
separately by `.git/validation/<HEAD>.json` and
`build/performance-noble-live-clean-workflow.log`; this report does not presume
that future command succeeds. The intended command is:

```sh
.venv/bin/python scripts/validation/workflow.py run --module performance-noble-live --evidence docs/performance-noble-live-preparation.md
```

At this preparation checkpoint, human live authorization and sole-executor cloud
A/B observation plus cleanup/network receipts were still pending. They were
subsequently accepted for one bounded run, documented in
[Noble cloud validation](performance-noble-cloud-validation.md); the earlier
preparation evidence is retained unchanged in scope. Neither preparation nor
that single sample establishes cloud accuracy or general Ubuntu24 performance.
