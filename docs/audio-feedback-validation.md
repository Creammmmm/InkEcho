# Audio error feedback validation

Release candidate: `0.1.0a6`. This focused change retains a recorder's specific
failure reason in normal recording and microphone-test feedback.

## Scope and preserved baseline

The alpha5 package remains preserved at `dist/InkEcho-0.1.0a5-x86_64.AppImage`,
SHA-256 `8a7ea103e6c299323038cb8c16e649e6608ed0dd892031c8e1755684d4f2dadb`.
Project metadata, the application version and dependency lock now identify
`0.1.0a6`; the offline lock check passed.

Runtime dependencies, provider protocol, platform input handling, icons and
appearance are unchanged by this feedback repair. Alpha5's nine-page, Ubuntu
24.04 userspace and isolated Xvfb workflow results remain prior-version baseline
evidence in [listening repair release validation](listening-repair-release.md).
They are not described as new alpha6 tests. This release instead checks the built
image's startup, exact source contents and changed audio-error behavior.

The current GNOME desktop is locked, preventing native focused-target acceptance.
This current test limitation does not establish the cause of the user's earlier
recording failure. The existing alpha5 background process was left running during
validation and replaced only after the root review below.
No unlock or focus bypass is attempted; [the current native probe record](listening-repair-validation.md)
states the actual limitation. Offscreen or controlled-error checks do not prove
native dictation. User settings, Ctrl+F4 and credentials remained outside the test
profiles.

## Focused source evidence

The implementation's focused run passed **65 tests with one opt-in microphone
check skipped**. It covers specific recorder failure codes, a safe fallback for
unknown reasons, one notification per failure, resource cleanup and consumption
of failed asynchronous results. See [the implementation report](audio-error-feedback-validation.md)
for exact commands and regression cases. No new successful native dictation claim
is made by that unit/offscreen result.

## Actual alpha6 artifact

`dist/InkEcho-0.1.0a6-x86_64.AppImage` contains 108694008 bytes, SHA-256
`827573c8b4d25d22ce5342e2f2fe2882357dfcc21b0dca180abfb9965aabbc52`.
Its adjacent checksum matched. The extracted image reports `0.1.0a6`; all 33
application source/asset files matched the frozen source byte-for-byte and all
symbolic links remained inside the extracted tree.

The actual image started and exited 0 in a private D-Bus/offscreen session:

```sh
uv sync --frozen --offline
.venv/bin/python scripts/packaging/build_appimage.py
env -u PYTHONPATH -u PYTHONHOME -u LD_LIBRARY_PATH QT_QPA_PLATFORM=offscreen \
  dbus-run-session -- ./dist/InkEcho-0.1.0a6-x86_64.AppImage \
  --appimage-extract-and-run --config-dir /tmp/inkecho-alpha6-startup/config \
  --data-dir /tmp/inkecho-alpha6-startup/data --quit-after 0.2
```

The image was then extracted to `build/audio-alpha6-extracted/squashfs-root`.
The tracked acceptance helper at `scripts/validation/audio_feedback_probe.py` asserted
that imports came from the extracted package and used a disposable configuration:

```sh
mkdir -p build/audio-alpha6-extracted
(cd build/audio-alpha6-extracted && \
  ../../dist/InkEcho-0.1.0a6-x86_64.AppImage --appimage-extract)
task_appdir="$PWD/build/audio-alpha6-extracted/squashfs-root"
env QT_QPA_PLATFORM=offscreen PYTHONHOME="$task_appdir/usr" \
  PYTHONPATH="$task_appdir/packages" PYTHONNOUSERSITE=1 \
  LD_LIBRARY_PATH="$task_appdir/usr/lib/inkecho" \
  "$task_appdir/usr/bin/python3" scripts/validation/audio_feedback_probe.py
```

Actual result: **passed**. The real packaged `Recorder` received a nonexistent
device selection through `Session.sample_audio`; it returned the specific
`microphone_unavailable` code and Chinese explanation instead of the generic
message. Separate controlled active-task signals for timeout, interruption,
empty recording and an unknown private-looking reason produced one appropriate
safe message each, reset to idle and cleared transient error state. Unknown raw
detail was not exposed. No unhandled asynchronous error remained.

Evidence: `build/audio-alpha6-feedback-result.json`. This check did not record
audio, read a credential, call a cloud service or test native input. It exercises
the changed packaged feedback boundary, with the active-task failures explicitly
controlled rather than caused by physical microphone faults. Nine-page, container
and native-desktop suites were not repeated for this unchanged packaging/runtime.

## Independent review and local deployment

The root reviewer independently verified all 33 source/asset files, contained
symbolic links and the exact image checksum. After acceptance, the stable
`dist/InkEcho-0.1.0-alpha-x86_64.AppImage` and its sidecar were replaced atomically
with the accepted alpha6 image. The alpha5 versioned image remains preserved.
The replacement background process remained alive after three seconds.

Every user configuration JSON remained byte-identical before and after
deployment. Desktop integration status was unchanged, and GNOME Ctrl+F4 remained
registered. Neither credentials nor GNOME shortcut settings were changed.

The full lint, formatting and pytest check runs once against the final committed,
clean HEAD through the existing hook workflow:

```sh
.venv/bin/python scripts/validation/workflow.py run \
  --module audio --evidence docs/audio-feedback-validation.md
```

At document freeze that post-commit receipt run had not yet completed; no new
full-suite count is claimed here. A successful exact-HEAD receipt is required
before pushing and is stored locally under `.git/validation/`.
