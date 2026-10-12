# Shortcut and Wayland repair validation

Date: 2026-10-12. Release candidate: `0.1.0a2`.

## Package publication

The package version, application version and dependency lock now agree on
`0.1.0a2`. The builder reads that version for the artifact filename and inventory.
It stages the complete runtime plus SquashFS in a sibling temporary file, flushes
it and atomically replaces the destination. The checksum is prepared before image
replacement and published separately. This avoids truncating an existing image
that another application process may still have mounted.

Reproduction:

```sh
.venv/bin/python -m pytest -q tests/test_packaging.py
.venv/bin/ruff check scripts/packaging/build_appimage.py tests/test_packaging.py
.venv/bin/ruff format --check scripts/packaging/build_appimage.py tests/test_packaging.py
UV_CACHE_DIR=/tmp/inkecho-uv-cache uv lock --check --offline
```

Actual result: 3 tests passed. An open handle retained the complete previous image
after replacement; a missing payload or failed checksum preparation preserved the
old image and removed temporary files. Ruff and the offline lock check passed.
These are publication tests, not desktop or speech-recognition validation.

Before building, the existing alpha1 image was copied to
`dist/InkEcho-0.1.0a1-x86_64.AppImage`, while retaining the original
`dist/InkEcho-0.1.0-alpha-x86_64.AppImage`. The preserved image SHA-256 is
`cb35d203024538a4ee3d55c6ccb8619059ce9f4bfda387fd1b92e2291eec11a4`.

## Final package checks

The frozen application sources were built into
`dist/InkEcho-0.1.0a2-x86_64.AppImage` (102 MiB). SHA-256:
`83c075f4c911bdfb818e2502b20a8edd4a7af12a4277f6ca529fc83e44e3f0dc`.
The adjacent checksum file verified successfully. `uv sync --frozen` refreshed
the editable application metadata to `0.1.0a2`; locked runtime dependencies did
not change. The build needed a build dependency missing from the local cache.

Reproduction with fresh disposable output paths:

```sh
uv sync --frozen
.venv/bin/python scripts/packaging/build_appimage.py
env -u PYTHONPATH -u PYTHONHOME -u LD_LIBRARY_PATH QT_QPA_PLATFORM=offscreen \
  dbus-run-session -- .venv/bin/python scripts/validation/desktop_app_probe.py \
  --output build/repair-alpha2-offscreen \
  --appimage dist/InkEcho-0.1.0a2-x86_64.AppImage
scripts/packaging/check_ubuntu24.sh
env -u PYTHONPATH -u PYTHONHOME -u LD_LIBRARY_PATH QT_QPA_PLATFORM=wayland \
  ./dist/InkEcho-0.1.0a2-x86_64.AppImage \
  --config-dir /tmp/inkecho-alpha2-native/config \
  --data-dir /tmp/inkecho-alpha2-native/data \
  --screenshot-dir build/repair-alpha2-native --quit-after 0.5
```

Actual outcomes:

- Private D-Bus session with Qt offscreen: all nine 1120 × 850 page images
  rendered. Secondary `show`, `toggle`, `cancel` and `quit` commands reached the
  primary process, which exited with code 0. A deliberately damaged disposable
  configuration caused exit 1 and retained its exact bytes. Evidence:
  `build/repair-alpha2-offscreen/result.json` and its `process.log`.
- Cached Ubuntu 24.04 container: nine pages rendered and process exited 0. The
  application ran as UID 65532 with no network, read-only root/image, no user
  home, no microphone and no display socket. Evidence screenshots:
  `build/ubuntu24-qa.D973mb`. Expected absence-of-audio-server warnings remain;
  this proves userspace startup only, not an Ubuntu 24.04 desktop or audio path.
- Current Ubuntu 26.04.1 GNOME Wayland desktop: the actual AppImage displayed its
  own window, produced nine 2240 × 1700 screenshots and exited 0. All nine pages
  were visually inspected: Chinese glyphs render, the long pages scroll, and the
  About page reports `0.1.0a2`. The shortcut page clearly offers save-and-enable
  and reports a mismatch with the disposable default profile. Evidence:
  `build/repair-alpha2-native`. Qt printed nonfatal text-input surface warnings.

No real cloud provider request is part of these package checks. User API keys
and the user's existing application configuration were not read or modified.
Native Wayland startup alone does not establish target application compatibility.

The root reviewer ran the complete frozen-source suite: 229 passed and 1 skipped
in 3.71 seconds. The skipped opt-in actual microphone test passed separately below.

Input-specific reproduction and limitations are recorded separately in
[input repair validation](input-repair-validation.md).

## Actual host microphone

The root reviewer independently ran:

```sh
INKECHO_TEST_MICROPHONE=1 .venv/bin/python -m pytest -q -s \
  tests/test_audio.py::test_live_repeated_same_process_capture
```

Actual result: 1 test passed in 2.64 seconds. Three 16000 Hz captures had durations
0.7023125, 0.659625 and 0.6809375 seconds. Cancellation/restart and timeout/restart
both passed. No audio file was saved and no recording was uploaded.

## Independent root acceptance and local deployment

The root reviewer independently extracted the accepted image, verified that all
23 application Python files matched the frozen source byte-for-byte, and checked
that its symbolic links stayed inside the extracted tree. The image size was
107551224 bytes and its SHA-256 matched the value above.

After acceptance, the root reviewer atomically replaced the stable legacy path
`dist/InkEcho-0.1.0-alpha-x86_64.AppImage` with the accepted `0.1.0a2` image. The
explicit alpha1 backup remains available. A `--quit` command stopped the previous
instance before the stable path was launched with `--background`; the replacement
process remained alive after three seconds. The user's `config.json` was unchanged
byte-for-byte and no API key was accessed.

Readback showed that F4 was already registered before deployment; the registration
had changed during the repair. No GNOME shortcut settings were written as part of
deployment. This readback and process check do not by themselves prove physical
F4 delivery or an authenticated voice-to-text request.
