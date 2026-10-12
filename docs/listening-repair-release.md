# Recording cancellation repair release validation

Date: 2026-10-13, Asia/Shanghai. Release candidate: `0.1.0a5`.
The reported failure is premature cancellation during recording or immediately
after transcription begins. The root reviewer observed two transitions from
transcribing to cancelled within 7–11 milliseconds and a separate cancellation
after about four seconds of recording. Those old logs lacked a cancellation
reason; timing alone does not establish the cause.

## Version and preservation

Project metadata, application version and dependency lock use `0.1.0a5`.
The offline lock check passed. The existing alpha4 versioned image remains at
`dist/InkEcho-0.1.0a4-x86_64.AppImage`, SHA-256
`6d8816f87089caf3b317b605baa37f2a2811da43afbc719af26e7cb9bcb40acb`.
The stable deployed path remains unchanged pending source freeze and acceptance.

## Acceptance boundaries

Unit tests, package startup and provider capability checks cannot substitute for
actual target-focus workflow evidence. Any successful native GTK check must
identify the session, target, audio source, service type and cancellation
conditions. User Ctrl+F4, provider model, credentials and appearance are preserved
unless an explicit deployment record below states otherwise.

## Source changes

The accessibility backend now scopes invalidating events to the captured target
instead of cancelling for unrelated application lifecycle traffic. The feedback
path emits a fixed `target_changed` diagnostic and a visible explanation when
focus or the caret changes, while retaining explicit cancellation as a separate
case. Target text, application titles, credentials and audio are not logged.

The backend/application focused run passed 48 checks with one opt-in native
check skipped. The feedback module passed 42 orchestration/UI/logging checks.
See [event-scope repair validation](listening-repair-validation.md) and
[cancellation feedback validation](listening-feedback-validation.md) for precise
coverage and limitations.

## Actual packaged microphone-to-input workflow

The candidate source was subsequently confirmed frozen. Its AppImage is
`dist/InkEcho-0.1.0a5-x86_64.AppImage`, 108694008 bytes, SHA-256
`8a7ea103e6c299323038cb8c16e649e6608ed0dd892031c8e1755684d4f2dadb`.
The adjacent checksum verified successfully. The root reviewer independently
matched all 33 source/asset files to the frozen source and verified that all
symbolic links remained inside the extracted image.

The exact image was extracted to `build/listening-alpha5-extracted/squashfs-root`.
The existing `scripts/validation/voice_workflow_probe.py` ran with that image's
Python, modules, Qt plugins and runtime libraries on an owned Xvfb `:96` and a
private D-Bus session. The only additional library path supplied the test helper
`libxdo.so.3`. Xvfb, xdotool and libxdo were downloaded from the configured Ubuntu
APT repository and extracted under `build/listening-test-tools`; no system package
was installed. The owned Xvfb process was terminated after the test.

For reproduction, first start an owned Xvfb on a free private display such as
`:96` with `-screen 0 1280x900x24 -nolisten tcp`, and terminate it after the check.
Then run:

```sh
task_appdir="$PWD/build/listening-alpha5-extracted/squashfs-root"
task_tools="$PWD/build/listening-test-tools/root"
env DISPLAY=:96 XDG_SESSION_TYPE=x11 QT_QPA_PLATFORM=xcb \
  PYTHONHOME="$task_appdir/usr" PYTHONPATH="$task_appdir/packages" \
  PYTHONNOUSERSITE=1 QT_PLUGIN_PATH="$task_appdir/packages/PySide6/Qt/plugins" \
  LD_LIBRARY_PATH="$task_appdir/usr/lib/inkecho:$task_tools/usr/lib/x86_64-linux-gnu" \
  dbus-run-session -- "$task_appdir/usr/bin/python3" \
  scripts/validation/voice_workflow_probe.py \
  --xdotool "$task_tools/usr/bin/xdotool" \
  --output build/listening-alpha5-voice-workflow.json
```

The probe used a real host microphone, a locally trusted HTTPS service returning
fixed test text, a disposable injected credential and an owned GTK editable
fixture. Actual result: **passed**. It delivered exactly 28 mixed-Unicode code
points, preserved target focus while showing the X11 overlay, and left the target
unchanged after explicit cancellation and focus-away/back with late replies.
Statistics recorded three recordings, one success and two cancellations. RAM WAV
payloads were 17738, 19786 and 17738 bytes. No audio files or clipboard access were
performed. No user credential or real cloud service was used.

Evidence: `build/listening-alpha5-voice-workflow.json`. This proves the packaged
workflow for this isolated X11 GTK fixture. It is not native GNOME Wayland proof
and does not measure real ASR quality.

## Package startup

The actual alpha5 image also passed:

- Private D-Bus/offscreen nine-page rendering, single-instance
  show/toggle/cancel/quit, clean primary exit 0 and malformed disposable config
  exit 1 with original bytes preserved. Evidence: `build/listening-alpha5-offscreen`.
- Ubuntu 24.04 cached, nonroot, network-disabled, read-only container: nine pages
  and exit 0. Evidence: `build/ubuntu24-qa.NbOYTr`. Expected missing-audio-server
  warnings remain; no host user home, audio or display socket was mounted.
- Native GNOME Wayland with a disposable application profile: nine pages,
  visible window and exit 0. Home, compatibility and About were visually
  inspected; the navy/white appearance remains intact and About reports alpha5.
  Evidence: `build/listening-alpha5-native`. The Home capture replaces the README
  image. This test did not record or invoke a provider.

Reproduce those package checks after building from the locked dependencies:

```sh
env -u PYTHONPATH -u PYTHONHOME -u LD_LIBRARY_PATH QT_QPA_PLATFORM=offscreen \
  dbus-run-session -- .venv/bin/python scripts/validation/desktop_app_probe.py \
  --output build/listening-alpha5-offscreen \
  --appimage dist/InkEcho-0.1.0a5-x86_64.AppImage
scripts/packaging/check_ubuntu24.sh
```

Choose a new output directory for repeated runs.

## Native target boundary and complete source checks

A bounded probe on the current native GNOME Wayland desktop obtained an active,
focused owned GTK application target once. A follow-up attempt could not obtain
ACTIVE focus. No successful native Unicode workflow is claimed from these
attempts; native input acceptance remains pending. See the event-scope report for
the exact fixture and observed events. These native checks are separate from the
passing private Xvfb packaged workflow above.

The root reviewer ran the complete source suite: **299 passed, 2 skipped in
5.33 seconds**. The opt-in microphone/PID skips do not count as native workflow
acceptance. Actual microphone capture is independently covered by the packaged
workflow above. The dedicated event-lifecycle probe is separate: a passing
unrelated-window lifetime check without observed foreign state events is not
proof that such an event caused the user's cancellation. Synthetic bus replay
must be labelled synthetic wherever its result is reported.

## Local deployment and push gate

The root reviewer sent `--quit` to the old instance, then atomically replaced the
stable `dist/InkEcho-0.1.0-alpha-x86_64.AppImage` and checksum sidecar with the
accepted alpha5 image. The replacement background process remained alive after
three seconds. The versioned alpha4 image remains preserved.

A before/after byte comparison covered every JSON file under the user's InkEcho
configuration, including providers, prompts and application settings: all were
unchanged. Ctrl+F4 remained registered. Desktop integration status, icons and
appearance remained unchanged; no GNOME settings were written and no key or API
was accessed during deployment.

After committing this report, the exact clean HEAD must pass the normal hook
receipt command before push:

```sh
.venv/bin/python scripts/validation/workflow.py run \
  --module injection --evidence docs/listening-repair-release.md
```

The exact-HEAD receipt is generated after this report is frozen and is retained
locally under `.git/validation/`; the source-suite result above does not bypass it.
