# Full application AppImage packaging

The current recipe builds `dist/InkEcho-0.1.0a3-x86_64.AppImage` with
`python -m inkecho` as its entry. It is a Linux x86_64 preview application.
The preserved [stage-zero probe record](packaging-stage0.md) describes the
separate older artifact; its successful tests do not substitute for these tests.

## Build and contents

Use Linux x86_64, `uv`, `squashfs-tools`, `binutils` (`readelf`) and `dpkg-deb`.
Initial dependency downloads require network access. No host root installation
is performed by the recipe. The builder rejects a system Python because it
needs the uv-managed standalone runtime:

```sh
uv python install 3.13.15
uv sync --frozen --python 3.13.15
uv run python scripts/packaging/build_appimage.py
```

The type-2 AppImage contains standalone CPython, runtime dependency wheels and
their distribution metadata/licenses, application code/icons, Chinese Noto Sans
CJK Regular font, and selected Qt modules/plugins. Core, GUI, Widgets, Network,
Multimedia, Svg and DBus bindings remain; recursive ELF dependencies retain
needed Qt, ICU and FFmpeg libraries. QML, WebEngine, PDF, Charts and development
headers are excluded. XCB, Wayland and offscreen platform plugins remain.

Pinned Ubuntu 24.04 packages provide XCB utility and Kerberos leaf libraries
plus Noto. `scripts/packaging/system-deps.json` records exact URLs and SHA-256;
archives were also checked against APT repository SHA-512 on acquisition.
The builder checks every cached/downloaded archive and the official AppImage
runtime before use, failing on any mismatch. It extracts only required assets
and original copyright notices, and does not bundle host glibc or graphics drivers.

`usr/share/doc/inkecho/inventory.json` inside the image lists wheel versions,
selected Qt libraries, downloaded asset hashes, and every regular file checksum
and symbolic-link target except the inventory itself. The adjacent license
folders and `THIRD_PARTY_NOTICES.md` retain attribution and source links.
The runtime is pinned to upstream commit `8f39b89`, SHA-256
`156f4bdbde9c52d01814600013e0a273f0118dc2de98975f3c8c63427ec79074`.
Its upstream `continuous` URL can change; inspect new official release metadata
and deliberately update the hash before accepting a replacement.

The filename and inventory application version come from `pyproject.toml`. Image
publication uses a complete temporary sibling, flushes it, then atomically replaces
the destination. Failed payload or checksum preparation leaves the old image intact;
a mounted old image keeps its original inode. The SHA-256 sidecar is replaced
separately, so consumers must always verify it against the image.

Previous releases remain preserved locally at the explicit versioned paths
`InkEcho-0.1.0a1-x86_64.AppImage` and `InkEcho-0.1.0a2-x86_64.AppImage`.
The legacy `InkEcho-0.1.0-alpha-x86_64.AppImage` path points to the last accepted
deployed version and is updated atomically after acceptance. New releases are
built and validated first under distinct versioned paths.

## Verify the actual application

```sh
(cd dist && sha256sum -c InkEcho-0.1.0a3-x86_64.AppImage.sha256)
./dist/InkEcho-0.1.0a3-x86_64.AppImage --appimage-extract-and-run \
  --config-dir /tmp/inkecho-qa/config --data-dir /tmp/inkecho-qa/data \
  --screenshot-dir /tmp/inkecho-qa/screenshots --quit-after 1
```

Use a fresh temporary directory and an actual test display. Clear `PYTHONPATH`,
`PYTHONHOME` and `LD_LIBRARY_PATH` inherited from development before launching.
Inspect all nine screenshots for Chinese glyphs, clipping and page content.
Without FUSE, the runtime's native extract-and-run option works. The automated
[desktop acceptance driver](../scripts/validation/desktop_app_probe.py) also
checks single-instance show/cancel/quit commands against the actual artifact.
These startup checks do not prove voice transcription or target delivery.

For an offline Ubuntu 24.04 userspace check with an existing Docker daemon:

```sh
scripts/packaging/check_ubuntu24.sh
```

The image pins the official Ubuntu base digest and supplies desktop baseline
libraries: GLib, GL/EGL, xkbcommon, fontconfig, D-Bus and PulseAudio client libs.
The application runs non-root with read-only root/artifact, network disabled,
and temporary configuration, state and screenshots. No user home, audio device,
display socket or credentials are mounted. Qt offscreen startup on this image
proves userspace library compatibility only, not a Ubuntu 24.04 desktop session.

Linux desktops must provide compatible glibc, graphics/display libraries,
PipeWire/PulseAudio, D-Bus and the AT-SPI/Secret Service facilities needed by
selected features. The image does not provide those desktop services. Initial
clean-image trials caught missing Kerberos dependencies (now bundled) and
PulseAudio client libraries (now declared in the container baseline).

## Repeatability

`SOURCE_DATE_EPOCH` normalizes filesystem/inode times (default zero) and xattrs
are omitted. Compare two complete builds with unchanged source and dependencies:

```sh
uv run python scripts/packaging/build_appimage.py
cp dist/InkEcho-0.1.0a3-x86_64.AppImage.sha256 build/first.sha256
uv run python scripts/packaging/build_appimage.py
cmp build/first.sha256 dist/InkEcho-0.1.0a3-x86_64.AppImage.sha256
```

Python, wheels, assets, build file permissions and `mksquashfs` must also match;
this is same-host repeatability, not universal cross-host reproducibility.
Final measured results and limitations are in [release notes](release-notes.md).
