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

`SOURCE_DATE_EPOCH` controls the filesystem and all inode timestamps (default
zero), and host extended attributes are omitted. Two consecutive complete
builds on the measured host produced byte-identical artifacts after this
normalization. This establishes same-host repeatability with unchanged inputs,
not a universal cross-host reproducibility claim: the standalone Python,
locked wheels, source, `mksquashfs` version and build file permissions must also
match. The measured builder was `mksquashfs 4.7.5`. The recipe currently includes
the complete PySide6 runtime and is intentionally unoptimized.

To repeat the comparison with unchanged source and dependencies:

```sh
uv run python scripts/packaging/build_appimage.py
cp dist/InkEcho-0.1.0-stage0-x86_64.AppImage.sha256 build/first.sha256
uv run python scripts/packaging/build_appimage.py
cmp build/first.sha256 dist/InkEcho-0.1.0-stage0-x86_64.AppImage.sha256
```

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
6f4b889b326a0af1e5893bab861045ca5f288f3fcf9b1cf068f154dc9abb363f
```

Ubuntu 24.04 desktop operation, X11 desktop integration, desktop installation
and autostart are not proven by this stage-zero build. The host must provide
compatible glibc, display/graphics
libraries, a Wayland or X11 desktop and (for subsequent recording features)
PipeWire/PulseAudio. Those host dependencies require a clean-machine audit in
stage 4.

For the separate RAM-only microphone probe, see [audio validation](audio-validation.md).

## Ubuntu 24.04 userspace smoke test

```sh
scripts/packaging/check_ubuntu24.sh
```

This uses an already available Docker daemon; it does not install a host
service. The Dockerfile pins the official Ubuntu 24.04 base image digest and
installs only basic Qt runtime dependencies inside the test image. Package
versions are resolved from Ubuntu repositories when building that image; this
container image itself is not claimed to be reproducible.

The artifact then runs as UID 65532 with networking disabled, a read-only root
filesystem and artifact mount, and an executable temporary filesystem. No
host display socket, audio device, home directory or credentials are mounted.
The raw minimal Ubuntu image failed with missing `libglib-2.0.so.0`; the test
image supplies `libglib2.0-0t64`, `libgl1`, `libegl1`, `libxkbcommon0`,
`libfontconfig1`, `libdbus-1-3` and `fonts-dejavu-core` with their dependencies.

The final normalized artifact passed on 2026-10-12: `platform: offscreen`,
`visible: true`, `packaged: true`, and bundled Python under
`/tmp/appimage_extracted_…/usr/bin/python3`. This is a real Ubuntu 24.04 userspace
launch with the host kernel. It does **not** establish Ubuntu 24.04 Wayland/X11
desktop compatibility, input injection, FUSE mounting, microphone operation,
or a complete clean-desktop acceptance test.
