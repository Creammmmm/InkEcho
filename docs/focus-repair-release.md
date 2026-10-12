# Focus repair release validation

Release candidate: `0.1.0a3`. This follow-up addresses the user's report that F4
displayed an InkEcho-own-window rejection while GNOME Text Editor was visible.

## Version and previous artifact

Project metadata, the application About version and `uv.lock` now use `0.1.0a3`.
README/package commands and the Ubuntu 24.04 test default reference the new
versioned artifact. `uv lock --check --offline` passed with an isolated cache.

The alpha2 artifact is preserved at `dist/InkEcho-0.1.0a2-x86_64.AppImage`, with
SHA-256 `83c075f4c911bdfb818e2502b20a8edd4a7af12a4277f6ca529fc83e44e3f0dc`.
The stable legacy path is not changed before final package acceptance.

## Acceptance boundaries

Package tests use disposable profiles and do not call a real cloud provider or
access user API keys. Offscreen or container startup does not prove native focus,
physical shortcut delivery or transcription quality. Any native focus evidence
must state the actual target and session tested.

## Source and actual host checks

The target boundary now checks the real owner PID of the unique accessibility
connection and rejects InkEcho's own PID. It no longer treats Qt's cached local
active-window pointer as proof of global foreground focus. Wayland feedback now
uses the desktop notification service rather than creating an application popup
that could receive focus. Notification stop/cancel actions retain a task identity
and stale actions are ignored. Failures retain their original sanitized reason
even if the notification service is unavailable.

See [focus repair validation](focus-repair-validation.md) for focused regression
tests, notification behavior and limitations. The root reviewer independently ran
the two opt-in live tests together: actual microphone capture/restart plus actual
AT-SPI PID ownership checks; **2 passed in 2.67 seconds**. The ownership test uses
only its own and a disposable child's connections, not the user's editor contents.
The recordings are neither saved nor uploaded.

The root reviewer ran the final complete suite: **244 passed, 2 skipped in
4.57 seconds**. Both skipped opt-in live checks passed independently as recorded
above; no automated skip was treated as successful native acceptance.

## Final rebuilt AppImage

The final frozen source, including the notification-service failure message fix,
was rebuilt into `dist/InkEcho-0.1.0a3-x86_64.AppImage`. Size: 107551224 bytes
(102.57 MiB). SHA-256:
`bfdd6f83c9011cee2e8d52d39d6104f3a2e275e1f2943ee596c5bff5c4d9b704`.
The adjacent checksum verified successfully. Earlier candidate checks were
superseded; all checks below ran again against this final hash.

```sh
uv sync --frozen --offline
.venv/bin/python scripts/packaging/build_appimage.py
env -u PYTHONPATH -u PYTHONHOME -u LD_LIBRARY_PATH QT_QPA_PLATFORM=offscreen \
  dbus-run-session -- .venv/bin/python scripts/validation/desktop_app_probe.py \
  --output build/focus-alpha3-final-offscreen \
  --appimage dist/InkEcho-0.1.0a3-x86_64.AppImage
scripts/packaging/check_ubuntu24.sh
env -u PYTHONPATH -u PYTHONHOME -u LD_LIBRARY_PATH QT_QPA_PLATFORM=wayland \
  ./dist/InkEcho-0.1.0a3-x86_64.AppImage \
  --config-dir /tmp/inkecho-alpha3-final-native/config \
  --data-dir /tmp/inkecho-alpha3-final-native/data \
  --screenshot-dir build/focus-alpha3-final-native --quit-after 0.5
```

Actual results:

- Private D-Bus/offscreen package: nine 1120 × 850 pages rendered; secondary
  show/toggle/cancel/quit commands reached the primary instance, which exited 0.
  A malformed disposable configuration exited 1 and retained its exact bytes.
  Evidence: `build/focus-alpha3-final-offscreen/result.json`.
- Ubuntu 24.04 cached container: nine pages rendered, exit 0. It ran as UID 65532
  without network, user home, audio or display sockets, with a read-only root and
  image. Expected no-audio-server warnings remain. Evidence screenshots:
  `build/ubuntu24-qa.0pkhkz`. This is userspace startup compatibility only.
- Current GNOME Wayland: actual package window visible, nine 2240 × 1700 pages
  rendered, exit 0. Home, compatibility and About screenshots were inspected;
  Chinese text renders and the About version is `0.1.0a3`. Nonfatal Qt text-input
  surface warnings occurred. Evidence: `build/focus-alpha3-final-native`.

## Actual packaged notification module

The final AppImage was extracted into `build/focus-alpha3-final-extracted` with
its `--appimage-extract` command. The probe used that image's Python runtime and
module directory, with no source-tree import path:

```sh
task_appdir="$PWD/build/focus-alpha3-final-extracted/squashfs-root"
env PYTHONHOME="$task_appdir/usr" PYTHONPATH="$task_appdir/packages" \
  LD_LIBRARY_PATH="$task_appdir/usr/lib/inkecho" PYTHONNOUSERSITE=1 \
  "$task_appdir/usr/bin/python3" scripts/validation/notifications_probe.py
```

The actual GNOME notification service accepted both recording and completion
notices and replaced the existing notice. The probe created **zero application
windows**, then closed its own notification before exiting 0. This validates
native notification transport from the packaged module without Qt popups; physical
notification-action clicks were not tested. It did not record audio, read a key,
inspect the user's document or make a cloud request.

## Independent acceptance and local deployment

The root reviewer checked the final extracted image independently: all 24
application Python files matched the frozen source byte-for-byte, all symbolic
links remained within the extracted tree, and the image size and SHA-256 matched
the values above.

After acceptance, the stable `dist/InkEcho-0.1.0-alpha-x86_64.AppImage` path was
atomically replaced with this alpha3 image. The new package's `--quit` command
stopped the previous instance before a background restart; the new process
remained alive after three seconds. The explicit alpha2 image remains preserved.

F4 remained registered before and after deployment. The user's `config.json` was
unchanged byte-for-byte. No GNOME settings writes or API-key access were performed.
Process survival and shortcut readback do not establish a physical F4 activation
or a real cloud dictation result.
