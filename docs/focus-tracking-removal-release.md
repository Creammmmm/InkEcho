# Alpha8 focus-tracking cleanup release — 2026-10-14

This release removes the unused production AT-SPI captured-target adapter and
retains the current-cursor keyboard behavior introduced in alpha7. The detailed
[source audit](focus-tracking-removal-audit.md) distinguishes test-only ownership
guards and historical algorithms from the shipped application. The
[alpha7 measurements](current-cursor-input-validation.md) remain historical;
this report records the distinct alpha8 artifact.

## Source and build preparation

The cleanup's complete suite passed **348 tests, with 2 skipped, in 5.37 seconds**;
Ruff and format checks passed, as recorded in the source audit. The subsequent
version change touches only the application version in `pyproject.toml`,
`src/inkecho/__init__.py` and the local editable `inkecho` entry in `uv.lock`.
Parsing the lock before and after confirmed every other record unchanged.

The build verified all 12 cached system archives and the pinned AppImage runtime
before using them; no download, dependency upgrade or system installation was
needed. The build command is:

```sh
.venv/bin/python scripts/packaging/build_appimage.py
```

## Actual artifact checks

`dist/InkEcho-0.1.0a8-x86_64.AppImage` is **108,694,008 bytes**, SHA-256:

```text
fd5bcd70ee8bb7817372f7c0aacf7884c754f686f89e194790734b67f3750031
```

The final extracted inventory verified **3,885 regular files and 1,048 contained
symlinks**. All 33 current application source/asset files matched byte for byte;
there were no extra application files. Searching the complete AppDir found no
`accessibility.py`/bytecode or `historical_accessibility` module. With only the
packaged module path, the bundled Python also confirmed that neither
`inkecho.platform.accessibility` nor `historical_accessibility` was importable.
The application version is 0.1.0a8 and bundled Python is 3.13.15. The checksum
sidecar matches. Receipt: `build/current-cursor-alpha8-inventory-result.json`.

## Actual packaged current-cursor workflow: passed

After extracting the final image with `--appimage-extract` from an empty
`build/current-cursor-alpha8-extracted` directory, the reviewed helper ran on the
existing GNOME Wayland desktop using the exact packaged runtime. This is an
exclusive owned-window test; it must not share desktop focus with another probe.
Run from the repository root:

```sh
appdir="$PWD/build/current-cursor-alpha8-extracted/squashfs-root"
env QT_QPA_PLATFORM=wayland \
  QT_PLUGIN_PATH="$appdir/packages/PySide6/Qt/plugins" \
  PYTHONHOME="$appdir/usr" PYTHONPATH="$appdir/packages" \
  LD_LIBRARY_PATH="$appdir/usr/lib/inkecho" PYTHONNOUSERSITE=1 \
  "$appdir/usr/bin/python3" scripts/validation/current_cursor_workflow_probe.py \
  --package-root "$appdir/packages" --fixture-backend x11 \
  --output "$PWD/build/current-cursor-alpha8-workflow-result.json"
```

The relocated historical AT-SPI support was imported explicitly from the source
test directory for fixture confinement only. The production Session, Recorder,
MainWindow and keyboard emitter came from the package. The metadata result
reported `passed=true`, version 0.1.0a8 and the exact extracted module path:

- Recording began while an owned noneditable GTK button was focused. Focus moved
  to a second owned XWayland editor while the local ASR response was delayed;
  transcription continued and all 28 fixed Unicode code points arrived there.
- A second task was explicitly cancelled after its ASR request. Waiting beyond
  the delayed response left the editor unchanged and sent no extra key press.
  Outcomes were one success, one cancellation, zero failures and no diagnostics.
- Two real microphone captures totaled **1.276625 seconds**. Both 20,470-byte WAV
  requests went only to certificate-verified localhost HTTPS. Polishing was off.
  Fixed responses validate orchestration and transport, not speech accuracy.
- Seven production desktop notifications were accepted, with zero visible Qt
  top-level windows. The test guard observed 28 key presses, and the normalized
  whole keyboard map was restored. Both fixtures and temporary state were cleaned.
- No audio file, user credential, cloud request, clipboard or system input method
  was used. Physical shortcuts, mid-emission focus switching, partial-output
  cancellation and polishing were not rerun; their previous distinct evidence
  remains in the alpha7 report.

## Actual AppImage startup: passed

The final versioned AppImage then ran sequentially with
`--appimage-extract-and-run`, `QT_QPA_PLATFORM=wayland`, fresh temporary
`--config-dir`/`--data-dir`, development Python/library variables removed,
`--screenshot-dir build/current-cursor-alpha8-pages --quit-after 3`.
It exited 0 and produced all nine page screenshots. The home page was visually
inspected: Chinese text and layout were intact. Output contained Qt FFmpeg
information and `disableSurface` warnings; startup completed successfully.
Receipt: `build/current-cursor-alpha8-pages/result.json`. The README retains its
explicitly labelled alpha7 screenshot rather than relabelling historical pixels.

No additional Ubuntu 24.04 container or full desktop matrix was run. This cleanup
does not establish new native Wayland target, Codex, cloud or physical-shortcut
compatibility. The stable alpha7 image and versioned alpha7 backup both retained
their original checksum throughout build and acceptance.

## Deployment

The root agent independently checked the extracted adapter absence, all 33
source/asset files and final image hash, then deployed alpha8 to the stable alias
`dist/InkEcho-0.1.0-alpha-x86_64.AppImage`. Its checksum is
`fd5bcd70ee8bb7817372f7c0aacf7884c754f686f89e194790734b67f3750031`.
The versioned alpha7 image remains preserved. The stable entry started in the
background as PID 149452; diagnostics after the latest startup contained zero
ERROR records. The three user JSON hashes matched before and after, and Ctrl+F4
remained registered in GNOME. Receipt:
`build/focus-removal-deployment-result.json`. This startup/configuration check
does not claim physical-shortcut or actual user-Codex text delivery.
