# a13 host validation

Status: root accepted the limited host checks: r2 standalone input/cancellation
and r3 microphone-to-local-TLS/native UI. The r2 microphone failure remains
preserved below. Its follow-up changed only the validation harness audio-runtime
environment; the a13 artifact and product source stayed unchanged. No host lock
policy or user configuration was changed. This does not establish cloud speech
accuracy or native Wayland keyboard delivery.

## Frozen package, tools and actual host

- Actual a13 artifact SHA256:
  `8dce4eedee71373a27e0e6507592b1240617412a8a6f114230b9a53f4d286a89`,
  product commit `eeb2d0ce8f8c5a6690b0ab54e0196da4254eb767`.
- Actual package runtime:
  `build/performance-a13-extracted-iwmzy2mn/squashfs-root`. Production code uses
  only its packages, shipped Python and Qt. The frozen entry audits ten
  application modules plus websockets, full inventory (3,958 files/1,048 links),
  43 source files and two WebSocket licenses.
- r1 was an unexecuted preparation draft; r2 and r3 have separate actual runs below.
- Reviewed r2 snapshot manifest:
  `build/a13-host-r2/manifest.json`, SHA256
  `06f158ada6b047f14493748cee6f0798531748575d9c37a65c2516623d7da4d6`.
- Complete frozen command previews: `build/a13-host-r2/previews.json`, SHA256
  `257db431d4ee36cd04f52c27353ec9756d46fc90de81d0e3185bbf132d488402`.
  Root independently reviewed all commands, tools, guards, snapshot hashes and
  static package evidence; its related regression passed 43 tests in 0.44 s.
- Root authorized the exact structured `observer_argv` arrays, serially:
  `default20`, `cancel12`, `pipeline-microphone`, `ui-native`. Each actual run
  checks the manifest, native fixture-tool hashes and fresh lock/session state.
  No shell reconstruction of the argument arrays was used.

Read-only metadata in `build/a13-host-r2/host-metadata.json` records Ubuntu
26.04.1 LTS, kernel 7.0.0-38-generic, GNOME Shell binary 50.1 and installed
XWayland package `2:24.1.10-1`. The actual session is `wayland`, desktop
`ubuntu:GNOME`, display `:0`. Shipped QtCore reports Qt/PySide6 6.12.0 without
creating QApplication. The input scenarios use X11/XWayland transport in this
Wayland host session; they do not validate native Wayland keyboard delivery.

## r2 actual results

The host was unlocked before each of the three actual modes:
`ScreenSaver.GetActive=false`; same-user Wayland graphical logind session was
verified, using the approved lookup when XDG_SESSION_ID was absent. No idle,
locking or unlock settings were changed. Every actual process reached a natural
terminal state; no producer was forcibly killed or restarted.

| Default pacing, actual ManagedQtEventLoop | Exact codepoints | Elapsed (s) |
| --- | ---: | ---: |
| Chrome textarea, fresh local fixture | 140 | 9.3364 |
| Chrome contenteditable, fresh local fixture | 140 | 9.3352 |
| Owned GTK | 140 | 9.5043 |
| Owned VTE raw terminal | 140 | 9.3893 |

All four targets had exact readback, balanced events, restored mapping and
136 writes/one restore. No pacing override, source-root override or candidate
restoration patch was used. PID 568075/start ticks 27795882 exited 0.

Standalone GTK cancellation, PID 570090/start ticks 27801627, exited 0. It
received exactly the first 12 codepoints, had no late tail during the unchanged
0.5-second observation, and restored mapping (13 writes/one restore), with
balanced events. Elapsed time was 0.8121 s. Ownership guards protect only these
fresh test targets; product current-cursor semantics are unchanged.

The actual microphone scenario, PID 570185/start ticks 27807136, exited 1.
`pipeline-microphone/acceptance.json` records `passed=false`, `running=false`;
there is no completed `result.json`. Its original observer log records:

- Qt PipeWire connection failure, reporting the host instance was down.
- PulseAudio context connection failure.
- Timeout while the frozen pipeline waited at line 591 for audio bytes to reach
  the loopback WebSocket before recording stop.

The full traceback and untouched identity/argv/profile/log are preserved under
`build/a13-host-r2/pipeline-microphone`. At the initial failure, the isolated runtime-directory environment
was a diagnosis candidate; no product fault or causal fix was claimed. The r3
controlled follow-up below supports that diagnosis for this test attempt.
No claim of successful microphone capture, transcription or full output is made.
The test used local TLS fixture endpoints and memory-only fixture credentials;
there were no cloud requests, user-keyring reads or stored microphone audio.

Serial execution stopped after this failure. `ui-native` was not started; there
are no native UI screenshots, IPC results or damaged-profile results from r2.
The approved tool requires a fresh disposable profile and verifies an empty
transcription model before any UI toggle, but this source-reviewed guard has not
yet been exercised by this r2 run. It must not be presented as passed acceptance.

## r3 controlled follow-up and provenance

Root reviewed the complete r2-to-r3 code diff and new guards; 57 related tests
passed in 0.44 s with Ruff/format. Only the microphone mode retains the original
host audio runtime, after validating its absolute directory, same UID, mode 0700
and owned local PipeWire/Pulse sockets. Remote audio-endpoint overrides are
rejected. Its configuration/data/state/cache remain private. Native UI keeps a
separate private runtime and a fresh profile, using the actual Wayland socket.
This is a per-process harness change, without host service or policy changes.

The independent `build/a13-host-r3` snapshot has 48 files and these frozen inputs:

| Input | SHA256 |
| --- | --- |
| r3 manifest | `d58343494b6cb1c5477db931c79cc3f5b204089f7af612d9248c5285d6cbf7bf` |
| r3 complete previews | `300f01ede73837c398a79991afa7a757db4aecf6af3568765ee286218c26ac27` |
| Original r2 host tool | `02beb1bb0cf92395a001d87664bf04ef7c4fa5f52d4bb765a88f5be88e2f73b0` |
| Frozen r3 host tool | `2ad7cb09d94a0d5360d773c5de778fab65d381f2e2ddc4d62a6019feca570d1f` |
| Associated r3 guard tests | `2762a7fea8992bcf1896d099eb73f4d155106648cea25027993bd16903ec563a` |
| Keyboard fixture | `f0cb80b62727f9c03c26af8c929255bf99c41c349c8afe3769dc38b49d897344` |
| Local TLS pipeline fixture | `26ba7b1198846f9f1585d473aeee7c5767aebf20634c0d17627a105e4ae2bb0d` |
| Actual-package entry | `4d4ccd9bdd6a886eb02e1a5647923c66155d9481e11fa7a52fc626fa92cc3441` |

The new manifest explicitly references eight frozen r2 control/failure files and
checks their hashes. Thus r3 uses the previously passed input/cancellation
controls and preserves the failed microphone observation; no result was copied
into a new passing run or overwritten. Root independently verified all snapshot,
native-tool and prior-reference hashes and the complete child/observer argument
arrays before approving only `pipeline-microphone` then `ui-native`. Execution
used those exact structured arrays serially, with no other producer or GUI mode.
The host stayed unlocked with same-user Wayland logind verification before both.

### Actual microphone through local TLS

Producer PID 572824/start ticks 27901402 exited naturally with 0; strict
acceptance passed. Runtime scope was the validated `/run/user/1000` audio runtime.
The actual packaged Recorder sent 3,200 PCM bytes to the local WebSocket before
stop in each of two tasks. ASR previews were ignored; only the fixture final ASR
reached polishing. The normal task delivered exactly 25 codepoints, beginning
output before polishing completed; the cancellation task added one character
and no later tail. Server errors were empty and fixture threads closed.

- Successful task: 25 mapping writes/one restore/three completed insertions.
- Cancelled task: two writes/two restore calls/zero completed insertions. Cleanup
  calls may restore an already empty row without another mapping write.
- Stop to first successful X11 key-press dispatch: 36.749 ms.
- Stop to output completed: 1,862.684 ms.
- Stop to task finished: 1,862.798 ms.

This validates real microphone capture, pre-stop streaming, protocol handling
and actual XWayland keyboard output to the owned GTK field through local TLS
fixtures. The ASR response is fixed fixture text, so this is no speech-recognition
accuracy or cloud-latency claim. Microphone PCM stayed in memory/local services;
no audio file, cloud request, user API credential or user-keyring read was used.
Root independently read all raw/timing/cleanup results, the observer log and eleven
actual-package origin hashes, accepting this limited chain.

The artifact/code and fixture remained unchanged between r2 and r3. Restoring
access to the owned local audio runtime while retaining private configuration
made this test pass. Together with r2 audio-connection errors, this supports the
specific harness isolation as the failure source for that attempt. It does not
explain every microphone failure a user may encounter.

### Native Wayland UI, IPC and damaged disposable profile

The native UI observer PID 572963/start ticks 27904059 exited 0. The primary AppRun
PID 572966/start ticks 27904120 rendered nine visible Wayland pages and exited 0.
All four secondary `show`, `toggle`, `cancel`, `quit` processes exited 0 without
premature primary shutdown. The damaged disposable-profile process exited 1 as
expected and left the deliberately invalid configuration bytes unchanged. All
seven process records are terminal: `[0, 0, 0, 0, 0, 0, 1]`. No timeout,
termination, kill or producer restart was used.

The empty transcription model in this new profile was explicitly checked before
UI toggle. That actual default rejects before input authorization or API-key
lookup, so no UI recording or credential access occurred. The result confirms
`ui_toggle_records_audio=false`, `empty_model_verified_before_toggle=true`,
`native_wayland_ui=true`, successful IPC and preserved damaged configuration.
This is UI/lifecycle evidence; native Wayland keyboard delivery was not tested.

The nine original PNGs are 2,240 by 1,700 pixels. They and `contact.png` are at
`build/a13-host-r3/ui-native/pages`. Root independently viewed the contact and
provider-page originals 03/04, accepting Chinese text/layout/controls for the
visible viewport; long provider pages are scrollable and not every control was
exercised. Root also checked the full primary log, actual eleven module origins,
child argv, seven process outcomes and damaged bytes.

The original UI primary log retains PipeWire/Pulse disconnection warnings under
its intentionally private runtime and Qt Wayland text-input surface-focus
warnings. No UI audio task was requested. These did not prevent the verified
pages, IPC or clean exit; the UI run is not microphone evidence and is not
claimed warning-free. Audio evidence comes only from the separately successful
microphone run with validated host-audio runtime.

## Preservation and boundaries

`build/a13-host-r3/preservation.json` confirms that all three existing user JSON
files and a9/a10/a11/a12/stable artifact hashes remain unchanged; a13 still has
SHA256 `8dce4eedee71373a27e0e6507592b1240617412a8a6f114230b9a53f4d286a89`.
All original r1 preparation, r2 negative evidence, r3 snapshots, profiles, logs and
process identities remain available. No existing installation or stable alias
was replaced.

The evidence is limited to the named owned XWayland targets, real microphone to
local fixtures, and native Wayland UI/IPC/lifecycle on this actual host. It does
not establish native keyboard input, arbitrary applications, physical global
shortcut behavior, cloud speech accuracy, installation/FUSE behavior or a latency
distribution. No clipboard or system-input-method submission was used for output.
No extra mode, build, deployment, push or release was performed in this host task.
