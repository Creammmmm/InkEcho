# Provider repair release validation

Date: 2026-10-13, Asia/Shanghai. Release candidate: `0.1.0a4`.
This repair follows the provider capability-test failure reported in the user's
screenshot and applies the user-supplied logo with a coordinated navy/white
appearance. Completed source, real-provider and final package checks are recorded
below; the desktop input compatibility limits remain unchanged.

## Version and artifact preservation

Project metadata, the application version and dependency lock use `0.1.0a4`.
README, package commands and the Ubuntu 24.04 test default reference this version.
`uv lock --check --offline` passed using an isolated cache.

The alpha3 image remains at `dist/InkEcho-0.1.0a3-x86_64.AppImage`, SHA-256
`bfdd6f83c9011cee2e8d52d39d6104f3a2e275e1f2943ee596c5bff5c4d9b704`.
The stable legacy path is not changed until the new package passes acceptance.

## Evidence boundaries

Package startup checks use disposable profiles and do not access user keys or
call real providers. Root-led account diagnostics, if performed, are recorded
separately from local TLS fixtures and startup checks. Model listing alone does
not prove transcription capability; successful startup does not prove dictation.

## Actual provider capability diagnostic

The root reviewer exercised the production adapter against the user's configured
Alibaba host, using the existing Secret Service credential without printing it.
The selected non-realtime model was `qwen-audio-3.0-asr-flash`. One POST containing
a public Alibaba sample WAV (17.645 seconds, mono, 16-bit, 16000 Hz) returned a
nonempty 203-character transcript in 2.75 seconds. No user microphone recording
was used, and neither credential nor returned transcript was logged.

This is an authenticated transcription-capability check for that host, key and
model. It does not prove recognition quality for arbitrary speech or final input
into the user's editor. Provider request format and further diagnostic details
are recorded in [provider repair validation](provider-repair-validation.md).

## Provider and appearance checks

The provider module's final focused run passed 60 tests, including requests to
local HTTPS fixtures and rejection of empty WAV data before submission. These
local fixtures verify payloads, parsing and error behavior; the real account
capability check above is separate evidence.

The branding module passed 32 focused integration/UI/packaging tests. Its original
PNG artwork is retained byte-for-byte, with application icon sizes generated from
that artwork. Window, tray, sidebar, notifications and desktop integration use
the same artwork. The navy/white palette and all nine source-rendered pages were
inspected before packaging. Detailed provenance, icon migration and appearance
evidence are in [branding validation](branding-validation.md).

## Final package acceptance

The frozen source produced `dist/InkEcho-0.1.0a4-x86_64.AppImage`, 108685816 bytes
(103.65 MiB), SHA-256:
`6d8816f87089caf3b317b605baa37f2a2811da43afbc719af26e7cb9bcb40acb`.
The adjacent checksum file verified successfully.

```sh
uv sync --frozen --offline
.venv/bin/python scripts/packaging/build_appimage.py
env -u PYTHONPATH -u PYTHONHOME -u LD_LIBRARY_PATH QT_QPA_PLATFORM=offscreen \
  dbus-run-session -- .venv/bin/python scripts/validation/desktop_app_probe.py \
  --output build/provider-alpha4-final-offscreen \
  --appimage dist/InkEcho-0.1.0a4-x86_64.AppImage
scripts/packaging/check_ubuntu24.sh
env -u PYTHONPATH -u PYTHONHOME -u LD_LIBRARY_PATH QT_QPA_PLATFORM=wayland \
  ./dist/InkEcho-0.1.0a4-x86_64.AppImage \
  --config-dir /tmp/inkecho-alpha4-native/config \
  --data-dir /tmp/inkecho-alpha4-native/data \
  --screenshot-dir build/provider-alpha4-final-native --quit-after 0.5
```

Actual outcomes:

- The private D-Bus/offscreen run rendered all nine 1120 × 850 pages. Secondary
  show/toggle/cancel/quit commands reached the primary process, which exited 0.
  A deliberately malformed disposable configuration exited 1 while retaining
  the exact original bytes. Evidence: `build/provider-alpha4-final-offscreen`.
- The cached Ubuntu 24.04 container rendered nine pages and exited 0. It ran
  without network, user home, microphone or display sockets, with read-only root
  and image as UID 65532. Expected missing-audio-service warnings remain. Evidence:
  `build/ubuntu24-qa.hODGIP`. This establishes userspace startup, not a full desktop.
- The actual GNOME Wayland desktop rendered nine 2240 × 1700 pages with a visible
  application window and exit 0. All nine packaged pages were visually inspected:
  original logo, navy/white palette, readable Chinese, normal scrolling on long
  pages, and About version `0.1.0a4`. Nonfatal Qt text-input surface warnings
  occurred. Evidence: `build/provider-alpha4-final-native`. Its Home screenshot
  was copied unchanged into `docs/images/inkecho-home.png` for README.

## Packaged artwork and native notifications

The final image was extracted under `build/provider-alpha4-final-extracted` using
`--appimage-extract`. The inventory reports version `0.1.0a4`. All nine PNG assets
(the original plus eight sizes) matched their recorded checksums. The original
matched the source bytes, `.DirIcon` resolves to `inkecho.png`, and that top-level
PNG matches the 256-pixel icon. The obsolete SVG is absent from AppDir and bundled
application assets.

```sh
task_appdir="$PWD/build/provider-alpha4-final-extracted/squashfs-root"
env PYTHONHOME="$task_appdir/usr" PYTHONPATH="$task_appdir/packages" \
  LD_LIBRARY_PATH="$task_appdir/usr/lib/inkecho" PYTHONNOUSERSITE=1 \
  "$task_appdir/usr/bin/python3" scripts/validation/notifications_probe.py
```

The final image's Python and module code reached the actual GNOME notification
service: recording and completion notices were accepted, the existing notice was
replaced, zero Qt application windows were created, and the probe closed its own
notification before exiting 0. Physical notification-action clicks were not tested.

The root reviewer independently checked the accepted image's exact size/hash,
matched all 33 source and asset files byte-for-byte, verified all symbolic links
stayed inside the extracted tree, confirmed the PNG `.DirIcon` and absent SVG,
and visually inspected the actual packaged Home page.

## Local deployment

After acceptance, the root reviewer sent `--quit` to the old instance and
atomically replaced the stable `dist/InkEcho-0.1.0-alpha-x86_64.AppImage` path and
its checksum sidecar with the accepted alpha4 image. The versioned alpha3 backup
remains preserved. A background launch of the stable path remained alive after
three seconds.

Only the transcription provider's model was changed to the actually verified
`qwen-audio-3.0-asr-flash`; all other provider fields were checked unchanged. The
application `config.json` stayed byte-identical, and the existing Ctrl+F4 GNOME
shortcut registration remained valid.

The user's desktop launcher was previously absent. The root reviewer installed
the launcher plus all eight PNG icon sizes and verified their bytes against the
accepted artwork. Autostart remained disabled. The source original artwork and
all eight legacy icon hashes were independently checked before deployment.

## Final push gate

The root reviewer ran the final source suite: **279 passed, 2 skipped in
5.77 seconds**. The two skips are the opt-in microphone and AT-SPI PID checks,
whose unchanged paths were exercised in the earlier focus-repair validation.
This suite result does not constitute a new complete dictation acceptance test.

The final full-suite run must validate the committed clean HEAD, after this
report is committed:

```sh
.venv/bin/python scripts/validation/workflow.py run \
  --module providers --evidence docs/provider-repair-release.md
```

At the time this report was frozen, that exact-HEAD receipt run had not yet
completed. The hook's successful receipt is required before push and is retained
locally under `.git/validation/`.
