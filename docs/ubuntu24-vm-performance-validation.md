# Ubuntu 24.04 KVM desktop validation

Date: 2026-10-16. Status: **incomplete**. The a10 package has run in an actual
Ubuntu 24.04 guest kernel and GNOME desktop. Some individual 20 ms targets pass,
but the combined 20 ms target sequence has failed to map its next window.
Those combined failures remain failures; this report does not establish full
Ubuntu 24.04 support or a reliable cross-application speed improvement.

The environment, image download verification, guest network recovery and
native Wayland preflight are recorded in
[the VM feasibility report](ubuntu24-desktop-feasibility.md). Local receipts
below are under `build/ubuntu24-perf-vm/output/`; failed logs and older probe
versions are retained beside their replacements.

## Actual environment and artifact

The same disposable KVM guest runs Ubuntu 24.04.5, kernel
`6.8.0-142-generic`, systemd, GNOME Shell 46.0 and a real GDM Xorg login session
20. This is not Xvfb, a container desktop or an XWayland session. QEMU uses
four vCPUs and 4096 MiB RAM. Timings are virtual-machine observations, not
bare-metal measurements.

The artifact is `InkEcho-0.1.0a10-x86_64.AppImage`, SHA256
`5c515dd0e3ceb8eb910baa45f392d8be28bfda109c5e1d59865e5a0733b7d55a`.
Checks use its extracted runtime, packaged Python 3.13.15 and Qt 6.12 with the
production managed Qt event loop. They do not validate FUSE startup. The 43
packaged source files correspond to product snapshot `b963879`.

Provisioning network access was disconnected before these tests. SSH and
local fixtures remain inside the container/guest. The guest receives no host
audio, desktop bus, user profile or credential store. Target applications use
`GTK_IM_MODULE=gtk-im-context-simple`, `QT_IM_MODULE=compose` and
`XMODIFIERS=@im=none`; input uses the production keyboard backend.

For unattended testing only, the guest's idle locking was disabled and the
same existing session unlocked after direct lock-state diagnosis. Historical
locked-session failures are retained in the feasibility report. No host idle
policy changed, and the product does not bypass a locked desktop.

## Keyboard results in the unlocked session

The fixed mixed Unicode sample has 28 codepoints; repeated measurements use
five copies, 140 codepoints. The control explicitly sets all three keyboard
settle intervals to 40 ms; the candidate uses the unchanged product default
of 20 ms. Each command starts a new packaged Python process. The probe checks
owned PID, process start time and current window before every press.

| Receipt | Result | Elapsed input time | Boundary |
| --- | --- | --- | --- |
| `keyboard40-unlocked-r3.json`, GTK | 140 exact; balanced; map restored | 18.0362 s | Combined control |
| Same, VTE | 140 exact; raw bytes exact; balanced; map restored | 17.9910 s | Combined control |
| `keyboard20-unlocked-r3.json`, GTK | 140 exact; balanced; map restored | 9.5094 s | First target only; combined run failed |
| Same, next VTE | Ready file, live process, zero visible windows; zero presses | No input | Combined failure |
| `keyboard20-vte-unlocked-r3.json` | 140 exact; raw bytes exact; balanced; map restored | 9.5493 s | Separate VTE process, not a replacement for combined acceptance |
| `keyboard-cancel-unlocked-r3.json` | Exactly 12 presses and releases; exact prefix; no tail after 0.5 s; map restored | 0.8211 s | Actual partial cancellation |
| `keyboard20-unlocked-r4.json`, GTK | 140 exact; balanced; map restored | 9.4745 s | Diagnostic adapter, same acceptance |
| Same, next VTE | Live/ready; two owned windows unmapped on desktop 0; zero presses | No input | Combined failure; cleanup retained |

The reviewed r3 probe SHA256 is
`1bb4ffd8b5781056eff6c4b3259e27866bf4c0b9e02611784107e9fad55b121b`;
r4 is `09163aec2b2e4a5b625b18f6064b9f67cd311e8cf8d79b0bed73ac2f566910b7`.
The added diagnostics do not change guard conditions, pacing or the 120
readiness attempts. Individual faster results cannot establish that the whole
20 ms sequence is reliable.

Chrome 154.0.8037.97 was copied from the host's public software installation
only, without a browser profile. Its installed main binary SHA256 matches the
software manifest:
`6c792041b07547a662e1b17974d1dc34a3db630379b45d9d89ddd7e3e68cc587`.
The disposable guest uses its normal root-owned setuid sandbox; no
`--no-sandbox`, sysctl change or external page was used.

| Chrome receipt | Textarea | Contenteditable |
| --- | --- | --- |
| `keyboard-browser-phase0-unlocked-r3.json` | 28 exact | 28 exact |
| `keyboard-browser40-unlocked-r3.json` | 140 exact, 17.9205 s | 140 exact, 17.8468 s |
| `keyboard-browser20-unlocked-r3.json` | 140 exact, 9.5912 s | Next fixture unmapped, zero presses; combined failure |

Chrome GPU transient warnings occur in the passing control and phase 0 logs
as well as the failed candidate log. Their presence does not establish the
cause of the mapping failure.

## Local full-pipeline package checks

`pipeline40-unlocked-r3.json` and `pipeline20-unlocked-r3.json` both pass:
synthetic PCM enters the actual Session, local TLS WebSocket ASR returns a
fixed final result, local HTTPS SSE supplies fixed polish chunks, and the
production X11 keyboard sends them to a newly created owned GTK field.
Both check final text exactly, first press before SSE completion, ignored ASR
previews, partial cancellation without a late tail, balanced key events and
restored mapping. Both have no fixture server error and joined server threads.

| Measurement | 40 ms control | Default 20 ms |
| --- | --- | --- |
| Stop to first sent key | 66.675 ms | 51.744 ms |
| Output duration | 3158.543 ms | 1812.506 ms |
| Stop to completion | 3225.217 ms | 1864.250 ms |

These are fixed local-fixture results in the VM, with **zero cloud requests,
zero credential-store reads and no microphone input**. They do not measure
cloud ASR speech accuracy or provider latency. Both audits found 3958 runtime
files, 1048 symlinks, the 43 expected product-source hashes, two WebSocket
license copies and ten expected production-module origins.

## UI and unresolved mapping diagnosis

`ui-wayland.json` and `ui-x11.json` each record normal exit and nine screenshots
from the actual extracted artifact. Both sets were visually inspected; the
pages render without blank content or obvious layout corruption. These are
disposable empty-key profiles. UI startup is separate from native keyboard
support: the current native worker still fails authorization on this guest's
GNOME 46 interface, which lacks `SetKeymap`.

The r4 failure snapshot confirms an unlocked session, desktop 0 and unmapped
owned next-target windows. It does not support a different-workspace or
missing-character explanation. The fixed diagnostic
`wm-backlog-vte-observation.json` subsequently sampled GNOME at 0/2/5 seconds:
all 20 threads sleeping, only one additional user CPU tick across five seconds,
no system tick increase, and three immediate ScreenSaver false replies.
A new **no-input** owned VTE mapped within 0.214 seconds and remained viewable
at 2/5/15 seconds. This proves later recovery, not responsiveness during the
earlier failure. Guest GNOME key-binding warnings are retained as observations;
no causal conclusion is drawn from them.

A separate, read-only sidecar ran the unchanged, SHA-checked r4 combined probe.
`mapping-watch-r4.json` records 40 samples; the underlying probe exited
normally with failure status 1, not a monitoring timeout or forced termination.
`keyboard20-monitored-r4.json` again has 140 exact GTK characters followed by
an unmapped VTE and zero VTE presses. This is a diagnostic run, not a
replacement performance score.

The associated ScreenSaver calls began near 2/6/10/14 seconds and all hit
their separate two-second budget. A call completed false at 18.656 seconds
after 640.7 ms, and the next completed false in 10.6 ms. During that interval,
X server root-property queries still completed in approximately 1–4 ms.
GNOME CPU counters increased by 86 user ticks and 77 system ticks over about
20.6 seconds at 100 ticks per second; it was not continuously CPU-saturated.
The actual frame client was `/usr/libexec/mutter-x11-frames`, PID 26991,
process name `mutter-x11-fram`. Its 15 threads sampled sleeping and CPU
increased by only two user ticks. The GTK top-level had
`_MUTTER_NEEDS_FRAME=1` and a parent owned by that frame client. The next VTE
windows remained unmapped, parented directly to the root, with no
`_MUTTER_NEEDS_FRAME` property, until probe cleanup.

These observations correlate delayed desktop D-Bus and window management
with the failure; they do not establish its cause. The original wait-channel
filter rejected compiler suffix dots, so null values in that run are missing
diagnostic data, not evidence of a particular kernel wait. A later idle-only
snapshot (`mapping-watch-r4-idle-wchan.json`) records both processes in
`do_poll.constprop.0`. The filter was corrected for future observations.
`mapping-watch-r4-source-manifest.json` retains the exact first-run helper
snapshot and hash; that correction did not trigger another keyboard run.
Product source, readiness timeout and default pacing remain unchanged while
the cause is investigated.

The matching r4 **40 ms** sidecar control, in
`mapping-watch-monitored40-r4.json`, naturally exited 0: both targets received
140 exact codepoints, balanced events and restored mappings; VTE raw bytes
also matched. GTK input took 17.9272 s and VTE 17.9207 s. Its 76 observations
span 0–40.161 seconds. ScreenSaver queries also repeatedly hit their two-second
budget during this slower control, then returned false near the ends of each
target. The phenomenon is therefore not exclusive to the 20 ms candidate.
The same frame-client process stayed alive and used only five additional CPU
ticks. The full control payload was saved retrospectively from the known,
unchanged executed helper and settings, and its manifest explicitly states
that provenance; later runs save their payload before execution.

## Explicit restoration-policy experiment

The reviewed r5 adapter has SHA256
`e3f4e17e8ce3fd4fd70199d7359c0199a5b65d198fb093a35eddc5ceec1341c6`.
Its default policy transparently counts calls around the actual package's
existing keyboard implementation. Its explicitly selected
`end-of-insertion-candidate` policy defers per-character restoration only in
the test scope; the scope's synchronous `finally` invokes the real restore
once before returning. It does not replace insertion or weaken target guards.
The product source and AppImage are unchanged. Candidate receipts explicitly
have `production_behavior_modified: true` and must not be reported as normal
package behavior.

The same sidecar, actual Qt loop, mixed sample and owned GTK→VTE sequence
produced:

| Receipt | GTK writes / restore calls | VTE | Desktop query observation |
| --- | --- | --- | --- |
| `keyboard20-default-monitored-r5.json` | 270 / 141 restore calls, 140 exact | Unmapped, zero presses; run failed | Four two-second ScreenSaver timeouts |
| `keyboard20-candidate-monitored-r5.json` | 136 / 1 actual restore, 140 exact | 140 exact including raw bytes; 136 writes / 1 actual restore | All eight queries completed false within two seconds; some took 1.77–1.80 s |

There are 135 printable characters and five actual Return events in this
140-codepoint sample. A restoration call after Return need not perform a
mapping write, hence the measured production total is 270 rather than 280.
The candidate reports 141 deferred restore calls per insertion and one
successful real restore; both target maps and press/release balance passed.
Its underlying probe naturally exited 0. Exact full guest payloads and SHA256
manifests were saved **before** both r5 runs.

The subsequent `keyboard20-candidate-browser-monitored-r5.json` also naturally
exited 0. Its fresh Chrome textarea and contenteditable each received 140 exact
codepoints, with balanced events, restored maps, 136 mapping writes and one
successful real restore. Input took 9.5142 s and 9.5039 s. All eight observed
ScreenSaver calls completed false, but the maximum was still 1.7994 s; zero
timeouts does not mean zero desktop-query latency.

`keyboard20-candidate-cancel-monitored-r5.json` sent exactly 12 codepoints to a
fresh owned GTK field, then canceled. The prefix was exact, all 12 presses had
releases, no later tail appeared over 0.5 seconds, and the map was restored.
It recorded 13 mapping writes, one successful real restore and 12 deferred
restore calls. Input took 0.8153 s. Its three ScreenSaver calls returned false
in 4.5/12.8/20 ms. Both runs retain the explicit experimental-policy flags and
pre-run full payload manifests. No probe remained running after these checks.

Reducing map writes was sufficient for these controlled combined-target runs
to complete; this does not prove the entire desktop mechanism or eliminate
the remaining measured desktop-query latency. Neither these successes nor
the in-memory experiment fixes the existing a10 artifact. A reviewed source
change and new actual-artifact acceptance would be separate work.

`host-preservation-after-vm.json` confirms that the three user JSON file hashes,
the installed a9 artifact and the stable alias match the pre-test baseline.
No installation, deployment or release occurred.

## Reproduction and remaining gates

For this existing isolated VM, reviewed helpers can be sent through its
container-loopback SSH connection. Do not rerun `prepare` on a running VM.
For example, the unlocked control was:

```sh
.venv/bin/python scripts/validation/ubuntu24_vm.py ssh -- python3 - \
  keyboard40 --label unlocked-r3 --probe-generation r3 \
  < scripts/validation/ubuntu24_vm_guest.py
```

Use distinct labels for new receipts; evidence logs are opened exclusively.
An old receipt is not replaced when a new condition is tested. The diagnostic
helper is `scripts/validation/ubuntu24_vm_mapping_watch.py`; it launches the
frozen r4 probe with independent observation and preserves its nonzero exit.

Remaining gates include resolving or explicitly bounding the combined-target
mapping failure, a usable native GNOME 46 keyboard path, actual microphone
and global shortcut acceptance in this VM, and packaging installation/autostart
checks. None is established by the synthetic pipeline or successful UI pages.
