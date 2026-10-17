# Full application AppImage packaging

The recipe builds `dist/InkEcho-VERSION-x86_64.AppImage` with
`python -m inkecho` as its entry. VERSION comes from checked project metadata;
do not select an older artifact merely because its filename appears in a report.
It is one Linux x86_64 artifact for both Ubuntu 24.04 and 26.04, with desktop
support limited to independently verified sessions/backends.
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
env -u SOURCE_DATE_EPOCH uv run python scripts/packaging/build_appimage.py
```

Before downloading dependencies, creating a runtime directory or removing an old
AppDir, the builder requires the version literals in `pyproject.toml`,
`src/inkecho/__init__.py` and the `inkecho` package in `uv.lock` to agree.
It reads metadata without importing/executing the application. A mismatch fails
without destroying the previous build. Update these three deliberately together;
do not bypass the check or reuse a previous package's acceptance.

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
`InkEcho-0.1.0a1-x86_64.AppImage`, `InkEcho-0.1.0a2-x86_64.AppImage`,
`InkEcho-0.1.0a3-x86_64.AppImage`, `InkEcho-0.1.0a4-x86_64.AppImage`,
`InkEcho-0.1.0a5-x86_64.AppImage`, `InkEcho-0.1.0a6-x86_64.AppImage` and
`InkEcho-0.1.0a7-x86_64.AppImage`.
The legacy `InkEcho-0.1.0-alpha-x86_64.AppImage` path points to the last accepted
deployed version and is updated atomically after acceptance. New releases are
built and validated first under distinct versioned paths.

## Verify the selected candidate

Copy the **new build's exact path** into `artifact` and keep it for both systems.
The VERSION placeholder below must be replaced; these commands do not discover
or choose a stable/older package automatically.

```sh
artifact=/absolute/path/to/InkEcho-VERSION-x86_64.AppImage
(cd "$(dirname "$artifact")" && sha256sum -c "$(basename "$artifact").sha256")
"$artifact" --appimage-extract-and-run \
  --config-dir /tmp/inkecho-qa/config --data-dir /tmp/inkecho-qa/data \
  --screenshot-dir /tmp/inkecho-qa/screenshots --quit-after 3
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
scripts/packaging/check_ubuntu24.sh "$artifact"
```

The image pins the official Ubuntu base digest and supplies desktop baseline
libraries: GLib, GL/EGL, xkbcommon, fontconfig, D-Bus and PulseAudio client libs.
The application runs non-root with read-only root/artifact, network disabled,
and temporary configuration, state and screenshots. No user home, audio device,
display socket or credentials are mounted. Qt offscreen startup on this image
proves userspace library compatibility only, not a Ubuntu 24.04 desktop session.
The argument is mandatory: an absent, missing, non-executable or non-AppImage
selection fails before Docker or output-directory creation. Only the selected
file is mounted read-only; there is no implicit historical a8 default. This
userspace smoke is supplementary to the two actual desktop acceptances below.
Older release reports preserve commands that relied on the script's former
default. They are historical transcripts, not current instructions; supply the
selected image's explicit path when using today's entry.

Linux desktops must provide compatible glibc, graphics/display libraries,
PipeWire/PulseAudio, D-Bus, Secret Service, and libX11 with an X11/XWayland
display for that keyboard backend. The experimental native GNOME Wayland backend
also needs its measured Mutter keymap APIs, libei and libxkbcommon; it is not
universal Wayland support. The measured GNOME 46 installation lacks the required
native API. See the [compatibility matrix](compatibility-matrix.md) for exact
versions and limits. The image does not provide desktop services. Initial
clean-image trials caught missing Kerberos dependencies (now bundled) and
PulseAudio client libraries (now declared in the container baseline).

The first artifact accepted under the following same-image rule is
[a14](a14-dual-ubuntu-validation.md): Ubuntu 24.04.5 GNOME 46 Xorg and
Ubuntu 26.04.1 GNOME 50.1 Wayland host with XWayland and bounded native Chrome
checks. Its local WSS flow uses synthetic capture/input; cloud capability and
deployment are recorded separately. The host stable entry later launched the
actual FUSE-mounted a14 with matching inventory and source hashes; Noble used
extracted AppRun only and did not validate FUSE. This does not establish every
session below.

## Mandatory same-artifact dual-system acceptance

Every packaging task must validate the same version and SHA-256 on Ubuntu 24.04
**and** 26.04 before it is complete or the package is promoted to the stable
entry/autostart/public download. A successfully built but incompletely validated
image remains a separate candidate. Building it is allowed before the desktop
checks; replacing a deployed package is a later step. Do not split the product
into distro-specific branches/packages without a demonstrated need.

Create one tracked report for this artifact, using the scope and retained raw
evidence style in the existing package reports. Record source version/commit,
artifact path/hash, packaged version, full inventory and actual module origins.
For each system record OS/desktop/session, target application, exact commands,
results, cleanup and limitations. Reuse the existing owned-target/local-TLS and
UI probes with the new artifact explicitly selected and audited; never relabel
an older version's result or source run as the new package.

| Required actual-package check | Ubuntu 24.04 | Ubuntu 26.04 |
| --- | --- | --- |
| Same artifact SHA/version/inventory/origins | Record actual result | Record actual result |
| Packaged startup, settings/UI and lifecycle | Record actual result | Record actual result |
| Declared provider protocol, including Qwen realtime selection and local WSS flow | Record actual result | Record actual result |
| Mixed Unicode/current-cursor input, partial cancel/no replay and cleanup | Record actual result | Record actual result |

Record Xorg, XWayland and native Wayland separately. A Wayland-host XWayland
result does not establish native Wayland delivery; an unsupported native backend
must retain its clear diagnosis, not be recorded as passed. Two distributions
with measured working paths do not imply a complete desktop matrix.

Microphone, physical shortcuts/F13/F14, overlay focus, installation/path repair,
autostart, FUSE and actual authenticated cloud capability each need their own
measured status or explicit untested limitation. Extracted AppRun or
extract-and-run is not proof of FUSE mounting. A generated-audio/local-service
flow does not establish microphone capture, cloud recognition or accuracy. A
model appearing in discovery is not proof of Qwen realtime protocol support;
HTTP and realtime WebSocket selection must be checked separately. Tests use
isolated profiles and owned targets, without clipboard or system input methods.
No step automatically authorizes cloud requests or credential reads.

Both systems' required actual-package checks must pass for that hash. If the
artifact changes, repeat them rather than carrying their results to a new hash.
The root agent reviews the report and actual evidence, then the final clean
commit runs the existing complete [workflow](DEVELOPMENT.md#local-verification-before-every-push).
That receipt binds source checks and report identity; it cannot certify the
truth of a desktop test. This package-delivery rule adds no mandatory GUI/build
check to ordinary source-only pushes and does not itself authorize publication.

## Repeatability

The builder passes explicit epoch timestamps (default zero) to `mksquashfs` and
omits xattrs. Unset inherited `SOURCE_DATE_EPOCH` for the build: supplying it as
well as those explicit timestamp flags caused the preserved a14 r1 build failure;
r2 with the variable unset succeeded. Compare two complete builds with unchanged
source and dependencies:

```sh
env -u SOURCE_DATE_EPOCH uv run python scripts/packaging/build_appimage.py
cp "$artifact.sha256" build/first.sha256
env -u SOURCE_DATE_EPOCH uv run python scripts/packaging/build_appimage.py
cmp build/first.sha256 "$artifact.sha256"
```

Python, wheels, assets, build file permissions and `mksquashfs` must also match;
this is same-host repeatability, not universal cross-host reproducibility.
Final measured results and limitations are in [release notes](release-notes.md).

## Latest same-artifact acceptance

The [a15 dual-Ubuntu report](a15-dual-ubuntu-validation.md) records the same
`0.1.0a15` AppImage and SHA-256 on the actual Ubuntu 24.04 Xorg guest and
Ubuntu 26.04 native Wayland/XWayland host. The root agent reviewed 9 guest and
20 host package modes, retained validator failures, and the stated limitations.
After the pre-deployment full checks passed, the reviewed stable entry, managed
launcher, eight icons and two normal caches were updated with backups. A private
profile then launched that stable AppImage through actual FUSE, verified version
a15 and its inventory, captured nine pages, and exited normally. User settings,
old versioned artifacts and autostart state were preserved. Guest FUSE and real
microphone/physical shortcut/cloud checks remain untested; no new GitHub release
was created. The final documentation commit still requires its own full checks.
The [a14 report](a14-dual-ubuntu-validation.md) remains the first historical
same-artifact dual-Ubuntu acceptance; its results are not reused for a15.
