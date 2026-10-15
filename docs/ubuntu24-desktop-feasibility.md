# Ubuntu 24.04 desktop feasibility: survey and actual KVM progress

Updated: 2026-10-16. This report supersedes the initial survey's current-state
conclusion while retaining its historical limits. A disposable Ubuntu 24.04
system has now actually booted its own kernel, systemd and GNOME desktop under
KVM. The Docker container hosts QEMU; the tested desktop is a full guest VM,
not a container desktop sharing the Ubuntu 26.04 host kernel.

The original a10 extracted runtime passed native Wayland UI startup, but its
native keyboard worker did not authorize on this guest's GNOME 46 interface.
Its initial Xorg checks and failed combined-target 20 ms runs remain historical
evidence below and in [the a10 VM report](ubuntu24-vm-performance-validation.md).
The reviewed R6 production-source repair has since passed the complete Xorg
four-target 40/20 ms sequence and cancellation. A separately built a11 artifact
has also passed its first eight desktop modes, including output-time focus
switching and fixed local TLS pipeline checks. See [R6 source evidence](ubuntu24-source-r6-validation.md)
and [a11 artifact evidence](performance-a11-package-validation.md).

The preserved a11 R2 long-stream test confirmed exact text and cancellation but
found material GTK readiness latency after cleanup. The later queued-fragment
aggregation change has since passed separate R7 source checks and the actual
a12 artifact's eight Noble R1 modes. The a12 fast-arrival 150-codepoint check
had GTK/VTE readiness of 0.1747/0.3388 seconds after both tasks and cleanup;
this single case is not arbitrary-paced or immediate-after-output evidence.
The actual a12 R2 stream, with fixture-configured 70 ms sleep per fragment,
was exact and canceled safely but still
needed 5.8435 seconds for a new GTK window after cleanup: latency acceptance
failed. R8 task-scoped mapping lifecycle source checks have since passed
separately. The new a13 actual artifact has now passed seven independently
reviewed Noble modes; separate
[Ubuntu 26.04 host limited checks](performance-a13-host-validation.md) have also
passed. No complete Ubuntu 24.04, physical hardware or cloud speech-accuracy support is
claimed. Historical a10/a11 artifacts, experimental R5, source R6/R7 and current
a12/a13 artifact evidence are separate; later success does not rewrite old failures.

## Historical survey boundary

The initial 2026-10-16 survey found no ready Ubuntu 24.04 desktop or VM in the
locations checked. It used package metadata from temporary read-only,
network-disabled containers, device existence/access checks and scoped media
searches. It did not start a desktop, open KVM, install host packages, change
user settings, read API credentials or make cloud requests.

That survey observed Ubuntu 26.04.1 on the host, approximately 32 GB RAM and
1.4 TB workspace space free; local Noble images contained minimal runtime
libraries without a GNOME/Xorg desktop. `/dev/kvm` was accessible through the
approved host execution path but had not been exercised; the normal tool
sandbox hid that device. No QEMU executable or guest image was initially ready.
The previous Ubuntu 24.04 offscreen userspace smoke therefore proved neither
an actual Noble kernel boot nor a desktop input path. Those historical results
remain valid within their original scope; the later VM work below changes the
current environment inventory.

## Actual isolated VM

The controller is [ubuntu24_vm.py](../scripts/validation/ubuntu24_vm.py), with
[guest checks](../scripts/validation/ubuntu24_vm_guest.py) and the isolated
[tool-image recipe](../scripts/validation/ubuntu24-vm/Dockerfile). All lab files
are under `build/ubuntu24-perf-vm`; the container is
`inkecho-ubuntu24-perf-vm`.

| Item | Actual evidence |
| --- | --- |
| Guest image | Official dated Noble server cloud image, `https://cloud-images.ubuntu.com/noble/20260926/noble-server-cloudimg-amd64.img`; pinned SHA256 `6a81c37564db9b1ee84e141922625e1d7c5b389b99bb3c572e0243607d5bb4d2`, 625612288 bytes |
| Image verification | `image-manifest.json` records the official HTTPS manifest URL, manifest hash and matching image hash; this is the recorded HTTPS/pinned-hash check, not a claim of separate signature verification |
| Tool image | `inkecho-ubuntu24-perf-vm-tools:20261016`, recorded image ID `sha256:849c832dda5155906c580d2a5c3147e2a9094350d626088faf2a456d345809b9` |
| VM resources | QEMU KVM accelerator, q35, 4 vCPUs, 4096 MiB RAM, separate 32 GiB qcow2 overlay and virtio VGA; surrounding container capped at 5 GiB and 4 CPUs |
| Actual boot | `output/guest-boot.json`: Ubuntu 24.04.5 LTS, kernel `6.8.0-142-generic`, PID 1 `systemd`, virtualization `kvm`; QMP reports KVM present and enabled |
| Provisioning | Initial boot receipt still has cloud-init running; subsequent `output/guest-provisioned.json` records `done`, exit 0 and boot finished |
| Installed desktop | GNOME Shell `46.0-0ubuntu6~24.04.16`, GDM `46.2-1ubuntu1~24.04.9`, Xorg core `2:21.1.12-1ubuntu1.8`, XWayland `2:23.2.6-1ubuntu0.8`, VTE `0.76.0-1ubuntu0.1`, Python GI `3.48.2-1` |
| Actual graphical identity | `output/identity-wayland.json` and `output/identity-isolated-wayland.json`: active owned logind Wayland session 7, UID 1000, GNOME Shell 46.0; `output/identity-x11.json`: actual X11 session 20, same guest OS/kernel |
| Historical AppImage | Local a10 preview SHA256 `5c515dd0e3ceb8eb910baa45f392d8be28bfda109c5e1d59865e5a0733b7d55a`; guest checks verify the artifact before using its extracted runtime |

The `mutter` command-package entry in the provisioning receipt is
`not-installed`; this must not be interpreted as no running compositor. The
actual GNOME Shell process, active graphical session and RemoteDesktop
introspection provide the runtime evidence. The identity receipts have
`desktop: null`; GNOME identity comes from the owned running process and its
version, not an invented logind Desktop field.

QEMU runs as UID 1000 with a read-only container root, dropped capabilities and
`no-new-privileges`; `/dev/kvm` is its only passed host device. No host home,
desktop socket, host audio, host session bus, API key store or GPU render device
is mounted. The dedicated input share is read-only and the output share writable.
An ephemeral lab SSH key is distinct from user credentials. QMP, VNC and SSH
forwarding bind container loopback; no host port is published. Input probes use
owned guest targets, literal keyboard delivery and no clipboard, input-method
or text-input submission API.

Provisioning initially used a Docker bridge for official image/package setup.
After provisioning, `isolate` disconnected that bridge; controller-to-guest SSH
through the container's own `127.0.0.1:2222` still worked, including the isolated
Wayland identity check. External network disconnection must not be confused
with unplugging the guest NIC or disabling the guest's IPv4 configuration.

## Network failure and recovery retained

SSH became unreachable during setup. The saved guest diagnostics show the SSH
socket and service were still active and listening on port 22, while the guest
`enp0s4` had lost IPv4 and the route list was empty. This was not evidence that
SSH had stopped, KVM had failed, or external bridge isolation necessarily
prevented loopback forwarding.

The recovery applied netplan only inside the disposable guest. It restored
loopback SSH reachability; later successful graphical identity and Xorg checks
are post-recovery observations. No host network configuration was changed. Do
not treat `guest-ip-after.json` as a successful recovery receipt: that
intermediate snapshot still has no guest address or route. The saved
`identity-after-netplan.log` also contains an earlier
`graphical_wayland_environment_mismatch`; keep it as a failed attempt rather
than converting it to a passing identity result.

Evidence is retained under `output/`: `guest-ip.json`, `guest-route.json`,
`guest-ip-after.json`, `guest-route-after.json`, `guest-ssh-status.txt`,
`guest-listeners.txt`, `guest-networkctl.txt`, `guest-nm-devices.txt`,
`guest-netplan-before.txt`, `guest-netplan-repair.txt`,
`qmp-network-info.json`, `qmp-network-diagnosis*.log`,
`qmp-netplan-repair.log` and the repair completion marker. The QMP repair log
only confirms that the fixed provisioning command was sent; subsequent SSH
checks provide the reachability evidence. A failed connection, command-sent
marker and actual successful check are separate observations.

## Native Wayland: UI passes, current keyboard path unavailable

`output/ui-wayland.json` records nine screenshots and normal exit for the
actual a10 AppImage runtime in the guest's GNOME 46 Wayland session. The guest
helper ran `--appimage-extract` and then the extracted `AppRun`; keyboard checks
use that same artifact's packaged Python. This does not validate FUSE-mounted
AppImage startup, application-menu installation or login autostart in the guest.
The images are `output/ui-wayland/page-01.png` through `page-09.png`; launch/extraction logs
and `guest-desktop-initial.png` are retained. This proves native UI startup in
this VM, not microphone, global shortcut or Unicode input support.

The runtime introspection and packaged production-worker test are recorded in
`output/native-preflight-wayland.json`:

| Observation | Result |
| --- | --- |
| `SetKeymap` method | Absent |
| `KeymapCapabilities` property | Absent |
| `ConnectToEIS` method | Present |
| Keyboard keycode/keysym notification methods | Present |
| Production worker connection | `worker_connected: true` |
| Production worker authorization | `worker_authorized: false`, code `cleanup_pending` |
| Cleanup confirmation | `worker_cleanup_completed: false`, code `session_closed` |
| Clipboard / input-method / text-input request | All false |

The worker's required keymap capability is absent in this exact installed
interface, and its actual authorization attempt failed. Cleanup was attempted
but not confirmed successful by the worker; `session_closed` is a recorded
failure code, not a successful cleanup result. An earlier subprocess failure
is separately retained in `native-preflight-failed.json` and its logs.

The original survey's upstream Mutter 46 interface concern is now backed by
actual guest introspection for these two capabilities. The conclusion applies
to the current production native worker on this GNOME 46 installation. It does
not prove that all future Noble updates or every alternative keyboard protocol
are impossible. No alternative native delivery path has been implemented or
accepted in this VM, and no clipboard or system input-method fallback was used.

## Historical a10 Xorg: initial phase 0 check

The guest has switched to an actual GNOME Xorg login session; this is distinct
from an XWayland client under Wayland or a nested Xvfb display. The guest helper
requires an active owned logind `x11` session, an X display and no inherited
Wayland display before running the probe. It sources the owned graphical
session environment rather than treating the SSH session as the desktop.

At this checkpoint, `output/keyboard-phase0.json` records the packaged keyboard
implementation under the managed Qt event loop with a **40/40/40 ms control**
pacing override and one 28-codepoint sample per target:

| Owned target | Actual receipt | Elapsed | First sent | Cleanup checks |
| --- | --- | --- | --- | --- |
| GTK | 28/28 exact, no mismatch | 3.6258 s | 57.47 ms | Balanced events; keymap restored |
| VTE | 28/28 exact; raw bytes exact | 3.5926 s | 50.99 ms | Balanced events; keymap restored |

`output/keyboard-phase0-x11.json` records completed execution, guest identity
and matching AppImage hash. The adapted probe hash is
`e63918790bbacd964e8d0190f6fd7e1613b838f573173eb9e4d83dbe98bbbafd`, recorded in
`output/keyboard-probe-manifest.json`. Probe logs are retained alongside the
receipts. Targets explicitly use `GTK_IM_MODULE=gtk-im-context-simple`,
`QT_IM_MODULE=compose` and `XMODIFIERS=@im=none`; the producer uses the keyboard
backend, not input-method submission.

This was an initial feasibility checkpoint. At that time the requested repeated GTK/VTE
**40 ms versus production 20 ms** comparison and partial-output cancellation
have not yet been reviewed at this checkpoint. No speed improvement,
no-late-tail cancellation result, browser support or full Ubuntu 24.04 Xorg
compatibility is claimed from this single control run. Later receipts must be
reviewed separately before extending the conclusion.

## Locked Xorg session: failed attempts and same-session recovery

The unattended guest subsequently locked itself. The original
`output/wm-diagnose-run.log` and its preserved structured snapshot
`output/wm-locked-x11.json` directly show logind session 20 with
`LockedHint=yes`, `IdleHint=yes`, ScreenSaver `GetActive=true`, idle time
613653 ms and `_NET_ACTIVE_WINDOW=0`. GNOME Shell PID 26971 and Xorg PID 26789
were still running. This is direct evidence of the locked desktop state rather
than a guess based on keyboard timing.

Keep the earlier failures distinct. The combined initial probe stopped with
`Owned target not ready` in
`keyboard20-initial-target-not-ready.log` and its outer run log. The separate
GTK-only and VTE-only attempts in `keyboard20-gtk.log` and
`keyboard20-vte.log` reached `KeyboardError: unsupported_target`, with an
active-window query failure before sending. The locked snapshot establishes
an actual environmental interference and can explain an unavailable target at
that point; the earlier combined failures did not sample LockedHint at each
failure instant, so their individual causes remain unconfirmed. These logs are
not a measured 20 ms sample with missing characters and must not be counted as
one. The fixture-only diagnosis (`fixture-diagnose-x11.json`) separately found a ready
file and visible owned window for each process; fixture launch readiness alone
does not establish a usable unlocked keyboard target.

The lab recovery changed settings only for the disposable guest:
`guest-idle-policy-change.json` records `idle-delay` from 300 to 0 and
`lock-enabled` from true to false, specifically for unattended benchmarking.
The original idle-delay was **five minutes**; 613653 ms is the idle duration at
the diagnostic observation, not a ten-minute configured lock threshold.
`sudo loginctl unlock-session 20` then succeeded. The post-recovery
`wm-unlocked-x11.json` records the **same** session 20, GNOME PID 26971 and Xorg
PID 26789, with `LockedHint=no`, `IdleHint=no` and ScreenSaver `GetActive=false`.
GDM was not restarted and no host lock, desktop or network setting was changed.
The unlocked snapshot still has `_NET_ACTIVE_WINDOW=0`; it proves that the lock
cleared, not that a future fixture automatically owns focus. Every later probe
must still verify its own target.

The lab probe was subsequently extended to retain fixed failure-phase/error
codes and already-sent counts in a failure JSON, with separate fixture stderr.
The revised adapter is recorded in `keyboard-probe-r3-manifest.json`, SHA256
`1bb4ffd8b5781056eff6c4b3259e27866bf4c0b9e02611784107e9fad55b121b`.
The original phase 0 adapter/hash and all failed attempt logs remain historical
evidence; the diagnostic change is not a production keyboard pacing change.
The repeated comparisons were subsequently rerun in this unlocked session.
The a10 failures and explicit R5 experiment are retained in the historical VM
report; the R6 source and a11 artifact results below are later, separate checks.

## Later production repair and actual a11 first-round results

The preserved a10 compound 20 ms failure was not fixed by unlocking alone:
later diagnostics found the next target unmapped even in an unlocked session.
The controlled R5 test-only restoration policy reduced map writes enough for
the complete sequence to pass. This experiment did not modify the a10 artifact
and did not prove every detail of the compositor mechanism or eliminate all
observed desktop-query latency. Its experimental flags and failed production
control are retained in [the historical VM report](ubuntu24-vm-performance-validation.md).

The production change committed in `a7db97f` removes restoration from the
per-character loop and retains the existing synchronous final cleanup per
insertion. It preserves key release, current-focus and task/cancel checks and
all three 20 ms settle waits. The R6 source runner explicitly imports the new
read-only source tree while reusing the old package's interpreter/dependencies;
it verifies all source hashes and runtime origins. Four consecutive owned
targets at each of 40 and 20 ms received 140 exact codepoints; VTE bytes were
exact. The partial-cancel check received exactly 12 codepoints, released keys,
restored the map and observed no tail for 0.5 seconds. See [the R6 report](ubuntu24-source-r6-validation.md).
This source result is not a retroactive acceptance of a10.

The new a11 product snapshot is `004b054eb324d6c54b622db6df4d0e2ede106b57`.
Its independent artifact is `dist/InkEcho-0.1.0a11-x86_64.AppImage`,
108907000 bytes, SHA256
`a61b2a036863d9c2ea1515055c7fadb7c9905e9a0139aa05e94936b32a67cb97`.
The first actual-artifact round has eight naturally exited, passing modes:

- Complete Chrome textarea → contenteditable → GTK → VTE, five 28-codepoint
  samples per target, at 40 ms control and production 20 ms. All eight target
  observations were 140 exact, with balanced events, final map restoration,
  136 mapping writes and one successful restore. VTE raw bytes matched.
- Partial cancellation after 12 successful presses, exact prefix and 0.5-second
  tail-free observation, with balanced releases and restored map.
- Local TLS normal 40/20 ms and `one-character-fast` 25-codepoint pipelines:
  synthetic PCM, fixed WSS final/preview events, fixed HTTPS SSE and actual
  production keyboard into owned GTK; exact output, ignored previews and
  cancellation without a late tail. No real microphone or cloud is involved.
- One 56-codepoint production insertion switching between owned GTK windows
  after 12 presses: exact 12/44 split, balanced events and final restoration.
- Nine Xorg UI pages and normal exit through this artifact's extracted AppRun;
  main reviewed the screenshots. This is not FUSE mounting or installation.

Receipts are `output/a11-r1-*.json` and separate `*-acceptance.json`, with
payload manifests and fixture logs. The artifact's own interpreter and modules
were used without a source-root override or candidate restoration wrapper.
Every mode verifies 3958 inventory files, 1048 symlinks, 43 source hashes and
two WebSocket licenses; actual production module origins are checked. The
source/module identity gates prevent a working source tree from masquerading
as the built artifact. No user credentials or cloud requests were used.

These are R1 fixed-scenario results, not an overall repair. Boundary ScreenSaver
false replies do not prove continuous responsiveness throughout input. Fixed
five-copy samples are not a reliability distribution across many independent
new windows. The following R2 result limits the earlier conclusions; all raw
receipts remain in [the a11 package report](performance-a11-package-validation.md).
Old a10, R5 experiment, source R6 and a11 must remain separately labelled.

## R2 counterexample: accurate long output, residual desktop latency

The actual unchanged a11 artifact's R2 stream delivered 150 codepoints exactly,
with correct partial cancellation, balanced events and restored mapping. The
normal task nevertheless made 288 mapping writes, 150 successful restores and
150 completed insertions: a source fix within each insertion did not combine
one-character streamed insertions. The pipeline naturally exited 0, without
cloud, credentials or microphone use.

The 50 ms parent observer first saw the full 150-character readback 2766.534 ms
before the entire pipeline process's observed exit. That interval includes
the second cancellation task, its 1.2-second tail observation and session/TLS
cleanup; it is not an exact production last-key timestamp or a deliberate
additional idle wait. The next-window probe launched 2.783 ms after the
observed exit, with the actual GTK fixture spawning after interpreter startup
at exit +414.118 ms. That fresh GTK fixture still took **6.0944 seconds** to
become ready. The next VTE, started only after that sequential GTK check,
became ready in 0.285 seconds. Its later success cannot prove immediate VTE
responsiveness when long output ended.

The unchanged 120-attempt readiness loop and pipeline checks mechanically
passed, but the near-six-second GTK delay is a material unresolved result.
The probe's 12-second wait for session.pending is an observation bound, not
the production task deadline. No production deadline was extended or sample
reduced to obtain a pass. This diagnostic observer differs from the unobserved
R1 timing runs. Receipts are
`output/a11-r2-long-{pipeline,next-window,acceptance}.json`; their passed flags
must not be summarized as the absence of desktop latency.

The subsequent change aggregates only already-queued fragments up to 128
codepoints, without waiting for future deltas. Its R7 source and separate a12
artifact results below do not retroactively repair a11. a11's Ubuntu 26 host
checks were deferred in favor of the new artifact. The observed R2 limitation
and its original artifact remain historical evidence.


## Historical R7 source and a12 actual-artifact checkpoint

[The R7 source report](ubuntu24-source-r7-validation.md) records new read-only
source origins using old a11 interpreter/dependencies. Its 150-codepoint long
local pipeline was exact, with 150 writes, six restores and six insertions,
correct cancellation and cleanup. Post-cleanup GTK/VTE readiness was
0.1639/0.2216 seconds. A separate streamed cursor run successfully pressed
one character before the rest were queued, then routed all 56 codepoints
exactly [12,44] after a window switch. This is scoped source evidence, not a
new package or proof of changed a11 contents.

The separately built a12 is product
`06f5600a57402335e97b3975afc38009d6233e58`, artifact
`dist/InkEcho-0.1.0a12-x86_64.AppImage`, 108907000 bytes, SHA256
`e31dbc6301318ab10632c12a7437ae7cd01482f2b1ee39655a82e43b6900eae9`.
The exact clean artifact-source commit workflow passed Ruff/format for 225 Python files and
1051 tests with three skipped in 19.90 seconds. Actual package checks use only
its extracted AppDir modules and interpreter, with ten application module
origins and WebSockets dependency origin/hash verified; no source-tree import
override or candidate restoration wrapper is used. Its inventory validates
3958 files, 1048 symlinks, 43 product source hashes and both license copies.

All eight Noble R1 artifact modes naturally exited 0 and passed strict
acceptance: four consecutive owned targets at each of 40 and 20 ms, cancel12,
normal local TLS pipeline40/pipeline20, fastlong150, streamed cursor/focus and
nine-page extracted AppRun UI. The four targets each received 140 exact
codepoints per group; VTE bytes, events and final maps matched. Cancellation
received the exact prefix and no tail during the observation. The cursor test
pressed its lone first character before future content was queued and routed
exactly [12,44]. Root independently reviewed raw/acceptance evidence and the
nine-page contact sheet. UI is still extraction-based, not guest FUSE mounting,
IPC, corrupt-config or installation acceptance.

The actual a12 fastlong150 matched the R7 source counts: 150 writes/six
restores/six insertions, exact text, proper cancellation, balanced events and
map restoration. First press was at 48.700 ms, completion at 10164.228 ms from
stop, using synthetic PCM and fixed loopback WSS/SSE. The 50 ms observer saw
full readback 2797.501 ms before complete process exit, including the second
cancel task, tail observation and TLS/session cleanup. The readiness process
then spawned at observed exit +21.288 ms, its GTK fixture at +435.917 ms;
GTK readiness took 0.1747 s and sequential VTE 0.3388 s. This is one observed
post-cleanup fast-arrival case, not a distribution or an immediate response
measurement at the last normal character. No microphone, cloud or credential
store was used.

Records are `output/a12-r1-*`, including distinct raw and acceptance JSON,
source-origin audits, snapshots, exact preview/run payload hashes and original
UI PNGs. [The a12 package report](performance-a12-package-validation.md)
maintains the full reproduction and results. Preservation checks retain the
old a11/a10/a9/stable artifacts and existing user JSON hashes.

## a12 R2 paced counterexample: latency acceptance failed

The same actual a12 artifact subsequently ran the 150-codepoint workload with
a fixture-configured 70 ms server sleep between one-character fragments.
This is not a measured client arrival interval. Text was exact, cancellation had no tail,
events balanced and mapping cleaned up. The normal task nevertheless recorded
288 mapping writes, 150 successful restores and 150 insertions. Stop to first
press was 42.489 ms and stop to completion 10537.782 ms. These are fixed local
TLS/synthetic-PCM results, not cloud speech or microphone measurements.

The observer's full readback preceded complete process exit by 2767.659 ms,
including the second cancel task and cleanup. After that exit and interpreter
startup, a fresh GTK took **5.8435 seconds** to become ready. The following VTE
then took 0.3393 seconds; that later sequential success cannot prove earlier
immediate VTE responsiveness. The mechanical text/cleanup/readiness checks
passed, but material desktop delay remains and **latency acceptance failed**.
No sample, readiness gate, production deadline or 12-second probe observation
bound was relaxed.

The read-only R2 snapshot manifest is
`c88deb05096c4a1681eb38eaafcfd8271d8251b1b511200995ee1652db5dc507`;
the reviewed payload hash is
`cd711f7e0329c3324858e1a9a04d000c52b11b4e8ec33fca13a984131837c699`.
Actual raw, origin and acceptance evidence is under
`output/a12-r2-paced-pipeline-long*.json`; reproduction and scope are in
[the paced counterexample report](performance-a12-paced-validation.md).
R1 fast-arrival positive evidence
and R2 paced negative evidence must remain separate; neither the raw passed
boolean nor a short first-press time establishes an overall fix. The 50 ms
observer and two-task/cleanup scope still preclude a last-character immediate
responsiveness claim.

The subsequent R8 source and separate a13 Noble actual-package checks below
have now passed; separate limited a13 host checks have also passed. Neither
those source results nor later worktree changes retroactively repair this immutable a12 artifact.
a12 host checks were deferred in favor of the replacement artifact.

## R8 source and separate a13 Noble actual-package checks passed

[The R8 source report](ubuntu24-source-r8-validation.md) separately validates
the production Session's task-scoped X11 mapping lifetime. The source snapshot
uses old a12 interpreter/Qt/dependencies, while ten application origins and
hashes match the new source tree. There is no candidate restoration wrapper.
Paced and fast use the same 150-codepoint sample with fixture-configured server
sleep of 70 ms and 1 ms respectively, not measured client arrival intervals.

| R8 actual source mode | Writes / normal restore calls / insertions | Post-cleanup GTK/VTE readiness |
| --- | --- | --- |
| Paced150 | 145 / 1 / 150 | 0.1734 / 0.3882 s |
| Fast150 | 145 / 1 / 6 | 0.1706 / 0.2901 s |

Both received exact text, rejected canceled tails, balanced events, cleaned up
maps, had no server errors and closed fixture threads. The standalone source
focus case confirmed a successful first press before queuing the next 55
codepoints and exact [12,44] routing after changing windows, with 55 writes,
one restore and completed output-session context exit. All source producers
and readiness processes naturally exited 0; root reviewed raw results,
origins and payload identity. Evidence has prefix `source-r8-output-session-`
under the existing output directory. The source commit is `d13ebcd`.

These are single matched source diagnostics. Full readback to complete process
exit still included the second cancellation task, its tail observation and
TLS/session cleanup: paced 2848.225 ms and fast 2795.182 ms. Readiness occurs
after that cleanup, not immediately at the last normal character. Neither
R8 source results nor boundary ScreenSaver queries prove arbitrary-paced/load
reliability, an internal Mutter cause, glyph rendering or cloud speech latency.

The versioned product is now a13, frozen source commit
`eeb2d0ce8f8c5a6690b0ab54e0196da4254eb767`. Its exact clean workflow passed
Ruff/format for 233 Python files and 1078 tests/three skips in 20.01 seconds;
the receipt binds the R8 evidence report. The separately built artifact is
`dist/InkEcho-0.1.0a13-x86_64.AppImage`, 108907000 bytes, SHA256
`8dce4eedee71373a27e0e6507592b1240617412a8a6f114230b9a53f4d286a89`.
Static audit matches all 43 source files, 3958 inventory files, 1048 symlinks,
two license copies and ten application origins plus websockets. Source/build
identity and preserved older artifacts/user JSON hashes are recorded in
`build/performance-a13-artifact.json`; the non-GUI entry audit is
`build/performance-a13-entry-audit.json`.

[The independent a13 package report](performance-a13-package-validation.md)
now records seven Noble modes, each naturally exited 0 and accepted by root:
default20 four targets, cancel12, normal local TLS pipeline, paced/fast long
pipelines, streamed first-character/focus and extracted AppRun UI. Its new
snapshot manifest is
`a62e0bc34f9fc738d5b8375e4981fbf2baabbf51eecda6238241b5110b8dd131`.
All seven preview/run payloads match, and the six non-UI modes independently
match ten package application origins plus websockets, including repaired
Session and keyboard. No source-root override or restoration candidate is used.
Records are `output/a13-r1-*`, separate from source R8 and old package evidence.

Default20 delivered 140 exact codepoints in each of Chrome textarea,
contenteditable, GTK and VTE, balanced events and restored maps with 136 writes
and one restore; VTE bytes matched. No a13 40 ms control was run: a12 controls
remain historical only. cancel12 delivered the exact prefix and had no tail
over 0.5 seconds. Normal local TLS25 was exact with 25 writes/one restore/three
insertions, stop to first press 47.844 ms and completion 1865.296 ms.

| a13 actual-artifact long mode | Fixture sleep | Writes / normal restores / insertions | Post-cleanup GTK/VTE |
| --- | --- | --- | --- |
| Paced150 | 70 ms | 145 / 1 / 150 | 0.1753 / 0.2983 s |
| Fast150 | 1 ms | 145 / 1 / 6 | 0.1602 / 0.2701 s |

Both were exact and cancel-safe, with balanced events, restored mapping, no
server errors and joined threads. Cancellation counters include a second
successful cleanup call with no mapping write; two calls do not imply two
actual map restorations. Full readback still precedes complete process exit by
2798.888/2797.023 ms, including the second task and cleanup. Actual GTK fixtures
spawn at exit +433.289/+419.036 ms. These are observed post-cleanup measurements,
not immediate-last-character response, distributions or cloud latency evidence.

The formal packaged output-session focus mode sent its first character before
the remaining 55 were queued and routed all 56 exactly [12,44], with 55 writes,
one restore and balanced events. AppRun/Xorg nine pages and normal exit were
reviewed by root, including the contact sheet and long provider pages. This
UI mode does not include IPC, damaged-profile, native Wayland or FUSE checks.
Separate Ubuntu 26 host results are linked below. These Noble modes used only
synthetic PCM and loopback fixtures, without cloud requests, credentials or a
real microphone. No deployment, push or release occurred; a12's immutable
negative history remains unchanged.

## Separate a13 Ubuntu 26.04 host checks

The unchanged a13 artifact also passed limited checks on the Ubuntu 26.04.1,
GNOME 50.1 actual Wayland host; see [the host report](performance-a13-host-validation.md).
Four owned XWayland targets each received 140 exact codepoints at default20,
and cancel12 had the exact prefix and no tail. Actual Recorder capture through
fixed local TLS ASR/polish services to owned GTK delivered 25 exact codepoints,
with cancellation adding only one character. Stop to first press/completion was
36.749/1862.684 ms for this local fixture, not cloud speech or accuracy evidence.
Native Wayland AppRun nine pages, IPC and preserved damaged configuration also
passed; the empty-model UI toggle did not record or read keys, and native input
was not tested. These are host results, not guest microphone acceptance.

The original r2 host microphone failure remains preserved. Its private runtime
hid the host audio sockets; r3 changed only the tool's microphone environment to
retain the validated host audio runtime and passed, without changing product
source, artifact or user settings. It does not explain all user audio failures.
The a9 stable entry and public v0.1 a8 artifact remain unchanged.

## Reproduction and outstanding acceptance

Review the controller and dedicated directory before starting a new lab. The
initial setup sequence is shown below for a fresh, separately provisioned lab;
it downloads software and starts an isolated VM, so it is not a read-only
survey. Do not rerun `prepare` against the running VM; the controller guards
against changing a running/paused/restarting guest's disk or inputs.

```sh
.venv/bin/python scripts/validation/ubuntu24_vm.py download
.venv/bin/python scripts/validation/ubuntu24_vm.py build
.venv/bin/python scripts/validation/ubuntu24_vm.py prepare
.venv/bin/python scripts/validation/ubuntu24_vm.py show-start
.venv/bin/python scripts/validation/ubuntu24_vm.py start
```

Wait for cloud-init to finish and verify the actual graphical login. After
package setup, disconnect external network access and check the owned desktop
through the remaining loopback SSH path:

```sh
.venv/bin/python scripts/validation/ubuntu24_vm.py isolate
.venv/bin/python scripts/validation/ubuntu24_vm.py ssh -- python3 - identity \
  < scripts/validation/ubuntu24_vm_guest.py
.venv/bin/python scripts/validation/ubuntu24_vm.py ssh -- python3 - ui \
  < scripts/validation/ubuntu24_vm_guest.py
.venv/bin/python scripts/validation/ubuntu24_vm.py ssh -- python3 - native-preflight \
  < scripts/validation/ubuntu24_vm_guest.py
```

The last two commands require the actual Wayland login for the native results
above. For Xorg keyboard probes, switch the disposable guest to its own Xorg
login and verify `identity` again; setting an environment variable does not
perform that switch. The guest helper exposes `keyboard-phase0`, `keyboard40`,
`keyboard20` and `keyboard-cancel`, and writes distinct JSON/log receipts. The
adapted VM probe must be present under the input path with its recorded manifest;
it is a lab fixture, not an unrecorded modification to production input code.
This report does not claim that unreviewed future runs have passed.

Remaining acceptance includes the full platform matrix; arbitrary timing/load
and immediate desktop response remain unproven. The seven Noble modes and
separately scoped Ubuntu 26 host checks do not fill those gaps.
Actual VM microphone/voice capture, physical shortcut/F13/F14 behavior,
focus changes during recording/recognition, overlay focus, credentials,
FUSE-mounted launch, desktop integration/autostart and unavailable-native-path
cleanup/recovery. Output-time two-window focus switching has separate historical package and
R7/R8 source and a13 actual-package results above; it is not a test of every workflow phase. No cloud ASR request
was part of these desktop checks. KVM with software-rendered virtual graphics
is real guest desktop evidence, but physical GPU/seat/microphone behavior and
a clean installed physical Ubuntu 24.04 machine remain untested. The separate
userspace container and earlier Ubuntu 26.04 host reports retain their original
scope. The a9/stable installation and user configuration remain preserved; no
push, release or deployment is part of these checks.
