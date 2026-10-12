# Native Wayland voice workflow validation

## Scope and artifact

On 2026-10-13, the alpha6 package was exercised on Ubuntu 26.04.1 / GNOME
Wayland. After display outputs were restored, the packaged runtime's complete
**microphone → local HTTPS → production notifications → safe native GTK input
workflow passed** for an owned GTK 3 fixture, including cancellation and
focus-loss protection. A separate GNOME Text Editor 50.1 (GTK 4) run also passed
recording, notifications, exact input and cancellation; focus loss was not tested
in that variant. Earlier attempts blocked before recording while the compositor
exposed no display outputs;
they are retained below. This result is separate from the earlier native
input-only probe in [listening repair validation](listening-repair-validation.md).
It does not establish support for every Wayland application or cloud ASR quality.

Artifact: `dist/InkEcho-0.1.0a6-x86_64.AppImage`, 108,694,008 bytes, SHA-256
`827573c8b4d25d22ce5342e2f2fe2882357dfcc21b0dca180abfb9965aabbc52`.
No application source, package, installed process or user configuration changed.

## Reproduction

The tracked helper requires the artifact to be extracted into the path below. It
imports application modules from that extraction and rejects another import root.
It creates temporary configuration, statistics, logs and desktop integration paths;
uses a disposable injected credential and a certificate-verified HTTPS server bound
to `127.0.0.1`; and launches only owned editor processes. The system GTK child clears
packaged Python/library environment variables. The microphone, if target capture
succeeds, records briefly to RAM and sends only to this localhost fixture. No
recording file is written and no user credential or cloud provider is accessed.

```sh
env QT_QPA_PLATFORM=wayland \
  PYTHONHOME="$PWD/build/audio-alpha6-extracted/squashfs-root/usr" \
  PYTHONPATH="$PWD/build/audio-alpha6-extracted/squashfs-root/packages" \
  LD_LIBRARY_PATH="$PWD/build/audio-alpha6-extracted/squashfs-root/usr/lib/inkecho" \
  PYTHONNOUSERSITE=1 \
  build/audio-alpha6-extracted/squashfs-root/usr/bin/python3 \
  scripts/validation/native_voice_workflow_probe.py \
  --package-root build/audio-alpha6-extracted/squashfs-root/packages \
  --output build/native-alpha6-voice-workflow.json
```

The helper constructs the production `MainWindow` without showing it and uses its
actual `handle_command`, `update_state` and `DesktopNotifications` paths. Its only
input adapter addition restricts production target capture to the owned GTK PID
and rechecks fresh focus; it never bypasses production focus checks. The
assertions cover exact mixed Unicode insertion after real microphone capture and
local ASR/polishing fixtures, cancellation before a delayed response, and native
focus loss to a second owned GTK editor before a delayed response. All owned
children, notifications, temporary data and recorder resources are cleaned up.
The restored-display run passed these assertions.

## Successful restored-display GTK 3 run

After the user reported the display restored, the root agent independently read
one physical and one logical Mutter monitor and an unlocked GNOME session. It
ran the final tracked helper with the exact alpha6 extracted runtime. The result
in `build/native-alpha6-voice-workflow.json` reports `passed=true`, version
`0.1.0a6`, native `wayland` for both the desktop session and Qt, and the expected
module path inside the extracted artifact.

- Three owned-PID captures succeeded with no capture error. Three actual
  microphone recordings totaled 1.9575625 seconds; the local HTTPS server
  received WAV payloads of 20,470 / 21,152 / 21,152 bytes.
- The first task completed recording → transcription → polishing → injection →
  success and delivered all 28 mixed Unicode code points exactly to the owned
  GTK editor. Statistics recorded one success, two cancellations, zero failures,
  28 characters and 12 fixture tokens.
- Eleven actual desktop notification requests were accepted through the
  production MainWindow policy. No Qt top-level window became visible, and the
  recording target retained fresh focus while notifications were emitted.
- Explicit cancellation of the second task and native focus loss to a second
  owned editor during the third task both prevented delayed replies from
  changing either editor. The `target_changed` diagnostic belongs to this
  intentional focus-loss case.
- Recorder resources were cleared. No audio file, clipboard operation, user
  credential access or cloud request was involved; only the localhost fixture
  received RAM audio and returned fixed test text. The user's running alpha6
  instance and settings were left intact.

This validates that specific native GTK workflow and notification policy. The
fixed server response does not assess recognition quality. Physical Ctrl+F4,
physical notification buttons and arbitrary user applications remain outside this
helper's acceptance scope. The separately authorized public-sample cloud workflow
is reported in [cloud validation](native-cloud-workflow-validation.md).

## GNOME Text Editor 50.1 native workflow

A subsequent bounded run used the actual GNOME Text Editor 50.1 (installed package
`50.1-0ubuntu0.1`, GTK 4) on the same native GNOME Wayland desktop. The root agent
independently read `build/native-alpha6-gnome-editor-workflow.json`: `passed=true`,
version `0.1.0a6`, expected extracted-package import path, and native Wayland Qt.
The probe exited successfully in approximately 4.88 seconds.

Use the same runtime environment as the GTK 3 command, selecting this target:

```sh
env QT_QPA_PLATFORM=wayland \
  PYTHONHOME="$PWD/build/audio-alpha6-extracted/squashfs-root/usr" \
  PYTHONPATH="$PWD/build/audio-alpha6-extracted/squashfs-root/packages" \
  LD_LIBRARY_PATH="$PWD/build/audio-alpha6-extracted/squashfs-root/usr/lib/inkecho" \
  PYTHONNOUSERSITE=1 \
  build/audio-alpha6-extracted/squashfs-root/usr/bin/python3 \
  scripts/validation/native_voice_workflow_probe.py \
  --package-root build/audio-alpha6-extracted/squashfs-root/packages \
  --target gnome-text-editor \
  --output build/native-alpha6-gnome-editor-workflow.json
```

The editor ran as a separate owned process with `--standalone --ignore-session`,
its own temporary empty document, isolated XDG config/data/cache/state directories,
and `GSETTINGS_BACKEND=memory`. Target capture checked the actual owned PID and
fresh focus; text readback checked ownership again before `GetText` and compared
only this owned document in memory. No existing user document or editor session
was used. The owned process and temporary directories were cleaned up afterward.

- Two actual microphone recordings totaled 1.25525 seconds; local HTTPS received
  WAV payloads of 19,786 and 20,470 bytes, with two ASR fixture requests and one
  polishing fixture request.
- The first task completed successfully and all 28 mixed Unicode code points
  exactly matched the owned editor buffer. The second task was explicitly
  cancelled after its request began; the delayed response left that buffer
  unchanged. Statistics recorded one success, one cancellation and zero failures.
- Eight production desktop notification requests were accepted, with zero
  visible Qt windows. Three owned-PID captures include the initial empty-document
  preflight and the two recording starts. No diagnostic error was emitted.
- No clipboard, saved audio, user credential or cloud request was involved.
  Fixed localhost replies validate delivery, not real ASR quality. This variant
  did **not** test focus loss to a second editor: the corresponding result fields
  are `null`. Physical shortcuts and notification-button actions were not tested.

The separate real-cloud/public-sample pass used the GTK 3 fixture; it must not be
presented as a real-cloud GNOME Text Editor or live-user-speech result. These
observations establish the measured GNOME Text Editor workflow, not universal
GTK 4 or Wayland application compatibility.

## Earlier attempts before display restoration

- Two complete-helper attempts stopped waiting for the first recording state.
  The diagnostic-enabled attempt returned `states=[]`,
  `diagnostics=["desktop_unavailable"]`, zero owned captures and zero HTTP requests.
  There was no microphone recording or text insertion.
- `org.gnome.ScreenSaver.GetActive` returned `false` during this investigation.
  Qt printed `There are no outputs - creating placeholder screen`; this is an
  observation, not proof that screen power state caused the capture failure.
  A later coordinated read-only diagnosis confirmed that the actual GNOME
  compositor advertised zero physical/logical monitors, system GTK saw zero
  outputs, and packaged Qt had only a zero-size placeholder; see
  [display diagnosis](native-cloud-workflow-validation.md#read-only-display-diagnosis).
  The reason outputs disappeared and the user's earlier failure remain unknown.
- The existing input-only helper was then run with the packaged runtime (clearing
  packaged Python/library variables only for its system GTK child). It also
  returned `No active, focused editable target is available` before insertion.
- The source command that had passed earlier was repeated unchanged:
  `PYTHONPATH=src .venv/bin/python scripts/feasibility/listening_event_probe.py`.
  It now returned the same capture failure. Thus this evidence does not isolate a
  package-only or notification-only defect.
- The final helper adds immediate diagnostic failure detection and writes a
  structured failure result as well as a success result. These reporting-only
  additions passed Ruff lint/format checks. The final helper subsequently passed
  after display restoration, as recorded above.

These earlier failures do not invalidate the separately observed native input-only
pass or the later complete local-provider workflow pass. No clipboard, simulated
global key events or `xdotool` were used during either attempt.
