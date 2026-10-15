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

The a11 R2 long-stream extension now confirms exact text and cancellation but
reveals material subsequent GTK readiness latency after cleanup. R1 improvement
in the fixed whole-insertion scenarios is not an overall repair. The newer
queued-fragment aggregation change still awaits actual R7 source and later a12
artifact validation; a11 Ubuntu 26 host rechecks are deferred. No complete
Ubuntu 24.04 desktop, physical hardware or cloud speech-accuracy support is
claimed. Source, old a10 package, R5 experiment, a11 and the unvalidated next
revision remain separate evidence categories.

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

The next change aggregates only already-queued fragments up to 128 codepoints;
it does not wait for future provider deltas or deliberately delay the first
character. Focused local tests pass, but the actual R7 source check and planned
independent a12 artifact acceptance are still pending. a11 is preserved as its
measured historical artifact; its Ubuntu 26 host pipeline/UI rechecks are
paused rather than repeating a version scheduled for replacement. Neither a
unit-test pass nor the new worktree code retroactively repairs a11.


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

Remaining acceptance includes resolving and retesting the observed long-stream
desktop latency in actual R7 source and a new a12 artifact, followed by the
relevant host checks; actual VM microphone/voice capture, physical shortcut/F13/F14 behavior,
focus changes during recording/recognition, overlay focus, credentials,
FUSE-mounted launch, desktop integration/autostart and unavailable-native-path
cleanup/recovery. Output-time two-window focus switching has the separate a11
result above; it is not a test of every workflow phase. No cloud ASR request
was part of these desktop checks. KVM with software-rendered virtual graphics
is real guest desktop evidence, but physical GPU/seat/microphone behavior and
a clean installed physical Ubuntu 24.04 machine remain untested. The separate
userspace container and earlier Ubuntu 26.04 host reports retain their original
scope. The a9/stable installation and user configuration remain preserved; no
push, release or deployment is part of these checks.
