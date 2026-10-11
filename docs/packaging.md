# AppImage packaging — stage 0

This artifact is a **runtime feasibility probe**, not the voice input application.
It displays a small Qt window and explicitly labels unimplemented functionality.
It does not record audio, contact cloud services, inject text, or access the
clipboard. Passing this check proves only that the bundled runtime launches in
the measured environment. Full application delivery remains outstanding.

## Build

Prerequisites: Linux x86_64, `uv`, `squashfs-tools`, network access for the first
dependency/runtime download. Build with an uv-managed standalone CPython; a
system interpreter is rejected because copying it does not provide a portable
Python runtime. No root installation or PyInstaller is required.

```sh
uv python install 3.13.15
uv sync --frozen --python 3.13.15
uv run python scripts/packaging/build_appimage.py
```

The script copies standalone Python, locked PySide6/shiboken6 runtime packages,
their distribution metadata/licenses, and project source into `build/InkEcho.AppDir`.
It includes a `.desktop` entry, SVG icon, Qt plugins, and an `AppRun` launcher.
`mksquashfs` produces the embedded filesystem; the official type-2 AppImage ELF
runtime is prepended. This is a real AppImage, not a shell script named AppImage.
Outputs and downloaded tools stay in ignored `build/` and `dist/` directories.

This is a repeatable build recipe, **not a byte-identical reproducible-build
claim**. `SOURCE_DATE_EPOCH` currently controls the filesystem creation time;
file timestamps and build-host inputs are not normalized. The recipe currently
includes the complete PySide6 runtime and is intentionally unoptimized.

## Runtime provenance

Official upstream: [AppImage/type2-runtime](https://github.com/AppImage/type2-runtime).
Asset: [runtime-x86_64, continuous](https://github.com/AppImage/type2-runtime/releases/download/continuous/runtime-x86_64).
The official [release asset metadata](https://github.com/AppImage/type2-runtime/releases/expanded_assets/continuous)
inspected on 2026-10-12 published SHA-256:

```text
156f4bdbde9c52d01814600013e0a273f0118dc2de98975f3c8c63427ec79074
```

The downloaded runtime matched that digest. The build verifies it before use,
including cached files, and stops on mismatch. Upstream `continuous` is mutable;
if it changes, review the new official release metadata, update the pinned
digest deliberately, and repeat all artifact tests. Do not remove verification
to make an upstream change pass. The cached validated runtime allows rebuilding
the same pinned version while available locally. This is checksum verification,
not an independent signing-key trust claim.
The downloaded runtime reports upstream commit `8f39b89` via
`--appimage-version`.

## Verify the artifact itself

```sh
cd dist
sha256sum -c InkEcho-0.1.0-stage0-x86_64.AppImage.sha256
./InkEcho-0.1.0-stage0-x86_64.AppImage --appimage-version
./InkEcho-0.1.0-stage0-x86_64.AppImage --smoke-test --screenshot /tmp/inkecho.png
```

The smoke result must show `packaged: true`, `visible: true`, the real desktop
platform, and a Python executable inside the AppImage mount/extraction directory.
Inspect the screenshot for clipped text and missing widgets. Without FUSE, use
the runtime's native `--appimage-extract-and-run` option. An offscreen test only
checks runtime startup, not real display integration. Run outside the source
checkout with an empty Python environment to detect accidental source imports.

On this development machine, Ubuntu 26.04.1 / GNOME Wayland / x86_64, the source
probe and real microphone capture passed. The final 242 MiB artifact was rebuilt
after the packaging source changes, its checksum passed, and it launched with
`packaged: true`, `visible: true`, `platform: wayland` from `/tmp` after clearing
`PYTHONPATH` and `PYTHONHOME`. Its interpreter was inside `/tmp/.mount_…/usr/bin/`.
The screenshot `build/appimage-wayland.png` was visually inspected successfully.
Native `--appimage-extract-and-run` also passed the offscreen smoke test with
its interpreter inside `/tmp/appimage_extracted_…/usr/bin/`.
Artifact SHA-256 for that measured build:

```text
64cb0552f3dbd8b177cbabf3a249decbd2ee89c3434beb0ac3568db699941041
```

Ubuntu 24.04, clean-machine operation, X11
desktop integration, desktop installation and autostart are not proven by this
stage-zero build. The host must provide compatible glibc, display/graphics
libraries, a Wayland or X11 desktop and (for subsequent recording features)
PipeWire/PulseAudio. Those host dependencies require a clean-machine audit in
stage 4.

For the separate RAM-only microphone probe, see [audio validation](audio-validation.md).
