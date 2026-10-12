# Native Wayland voice workflow validation

## Scope and artifact

On 2026-10-13, the alpha6 package was exercised on Ubuntu 26.04.1 / GNOME
Wayland. The complete native voice workflow **has not passed**. The bounded runs
stopped before recording because the backend could not capture an active, focused
editable target. This is separate from the earlier successful native input-only
probe recorded in [listening repair validation](listening-repair-validation.md).
Neither result establishes support for every Wayland application.

Artifact: `dist/InkEcho-0.1.0a6-x86_64.AppImage`, 108,694,008 bytes, SHA-256
`827573c8b4d25d22ce5342e2f2fe2882357dfcc21b0dca180abfb9965aabbc52`.
No application source, package, installed process or user configuration changed.

## Reproduction

The tracked helper requires the artifact to be extracted into the path below. It
imports application modules from that extraction and rejects another import root.
It creates temporary configuration, statistics, logs and desktop integration paths;
uses a disposable injected credential and a certificate-verified HTTPS server bound
to `127.0.0.1`; and launches only owned GTK fixtures. The system GTK child clears
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
and rechecks fresh focus; it never bypasses production focus checks. The intended
assertions cover exact mixed Unicode insertion after real microphone capture and
local ASR/polishing fixtures, cancellation before a delayed response, and native
focus loss to a second owned GTK editor before a delayed response. All owned
children, notifications, temporary data and recorder resources are cleaned up.
These intended assertions remain unpassed in this session.

## Observations

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
  additions passed Ruff lint/format checks; they were not used to claim another
  native acceptance run.

The earlier native input-only pass remains valid for that observed run. The
complete microphone → local HTTPS → production notifications → native safe input
path remains pending stable target capture. Physical Ctrl+F4, physical notification
buttons, real cloud recognition quality and arbitrary user applications are not
validated by this helper. No clipboard, simulated global key events or `xdotool`
are used. The running user's alpha6 instance and settings were left intact.
