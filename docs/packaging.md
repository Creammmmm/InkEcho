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
Inspect all five screenshots for Chinese glyphs, clipping and page content.
Without FUSE, the runtime's native extract-and-run option works. The automated
[desktop acceptance driver](../scripts/validation/desktop_app_probe.py) also
checks single-instance show/quit commands, then verifies that cold toggle/cancel/quit
commands do not restart the application. It preserves its disposable profile and
original process exit evidence, including damaged-configuration checks.
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
PipeWire/PulseAudio, D-Bus, and libX11 with an X11/XWayland
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

## Formal v0.2.0 release identity

The formal release is prepared as application version `0.2.0` in all three
metadata files and built at that exact commit. It must pass the existing same-SHA
Ubuntu 24.04 Xorg and Ubuntu 26.04 native Wayland/XWayland package gates before
publishing. GNOME 46 native Wayland remains unsupported. Reuse the verified a18
readiness and local pipeline checks; a renamed a18 image is not a 0.2.0 build.

Ordinary subsequent commits, including package-report commits, increment only
the patch version under the [development version policy](DEVELOPMENT.md#per-commit-application-versions).
Future release-preparation commits instead keep X, increment Y by one and reset
Z to zero (`bump --release`); X changes only when explicitly specified by the
user. This does not automatically build or publish a release.
Thus a 0.2.1 report successor may document the frozen 0.2.0 release artifact;
the release tag still targets its exact 0.2.0 product commit. Do not rebuild
0.2.1 merely to make the development HEAD equal the released version.

Publish only the validated versioned AppImage and its matching SHA-256 sidecar.
Prepare release notes in a file, then use an explicit exact commit target for
`v0.2.0`; the formal release is not a prerelease and is marked latest. Existing
pre-push tag restrictions remain. Publication requires an independently reviewed
artifact/commit binding and both actual OS results, not just a source receipt.


## Formal v0.3.0 provider release

The release-preparation branch starts at accepted main `c6c0b119e5c06ad13a8134052086e067256eba0a`.
An explicit `versioning.py bump --release` synchronizes the three fields from
0.2.14 to 0.3.0; the release adds no new protocol behavior beyond the accepted
provider implementation. Keep all v0.2.0 and 0.2.10 artifacts and evidence.

Build a fresh versioned 0.3.0 AppImage from its exact clean preparation commit,
freeze all 55 product files and the complete tracked validation snapshot, and
bind its own inventory and SHA-256. Reuse the reviewed isolated package protocol
runner (226 selected local TLS/WSS/SSE tests) on both OSes, host 25 desktop gates,
and guest extraction plus collection/tests and nine Xorg desktop gates. The
same-SHA candidate must also pass the private-profile real FUSE observation.
Old package results are reference methods, not acceptance of this new artifact.
Do not update the stable entry before both actual OS results and candidate FUSE
are reviewed; only the two stable artifact/sidecar files may then change.

A focused report successor uses 0.3.1 without rebuilding the frozen 0.3.0 package.
Before publication, merge the validated source into main and verify that the
exact 0.3.0 tag target is reachable from it. Create a draft release with only the
versioned AppImage and matching SHA-256 sidecar, verify remote assets against
local hashes, then publish as formal/latest after review. Preserve old releases;
unknown publication results require a read-only state check, not blind retries.
The official-account and GNOME46 native-Wayland limitations in the release notes
remain explicit.


The 2026-10-19 source revision removes the keyring runtime dependency. Supplier
credentials use the selected config root's plaintext credentials.json. This does
not retrofit historical AppImages: a new same-SHA dual-Ubuntu candidate must be
accepted before updating the stable entry; old versioned packages stay intact.


## Formal v0.4.0 plaintext-credential release

Prepare on `codex/release-0.4.0` from accepted main
`50d096f70be1b4c89c1e33ae9ed54aa2724252ed`, using the explicit release bump
from 0.3.3 to 0.4.0. This changes metadata and release documentation only; retain
all old artifacts and evidence. Build a genuine new 0.4.0 package from its exact
clean source commit, with all 55 source files and complete inventory bound by SHA.

Reuse the reviewed 0.3.2 minimal acceptance: both actual Ubuntu systems run the
private file/Session/ProviderPage nine-check gate, verify the eleven removed
modules/distributions are absent, and capture nine AppRun pages. Host GNOME
Wayland checks real factory native and XWayland normal/cancel output; guest
Ubuntu24.04 Xorg checks normal/cancel. Then observe one private versioned
candidate's real FUSE mount. Do not repeat unchanged protocol/performance suites
or substitute old package results. Preserve real credentials.json by hash only,
never read its body or copy it into frozen/build materials; user-driven edits
require a fresh baseline, never restoration over the user's new value.

Only after both OSes, candidate FUSE and report review may the stable artifact
and sidecar be updated with backups and all other protected paths unchanged.
The focused successor report uses 0.4.1; it does not rebuild the frozen 0.4.0
package. Before GitHub publication the exact release commit must be reachable
from main. Draft only the versioned AppImage and SHA-256 sidecar, verify remote
download hashes, then publish formal/latest after review, preserving v0.3.0.
No real keyring, cloud account, microphone or user-window control is involved.


## Formal v0.6.0 guided configuration release

Prepare on `codex/release-0.6.0` from accepted main
`1c982b0dd471a03cf9f01f9ebbbc4742ed1bcca5`. The explicit release helper moves
0.5.13 to 0.6.0 in all three metadata fields. This preparation changes only
version metadata and release documentation; do not alter product behavior or
rename the already accepted 0.5.12 artifact.

Build a new versioned 0.6.0 AppImage from the exact clean release-source commit.
Freeze the tracked source and validation materials, bind the inventory and SHA,
and rerun the reviewed 0.5.12 actual-package gates on that same artifact in both
Ubuntu systems: 26.04 native Wayland and XWayland, and 24.04 GNOME 46 Xorg.
Include the actual AppRun startup path, five pages/new layout/API guidance,
private configuration and desktop integration, local manual/VAD protocol cases,
current-cursor mixed Unicode normal/cancel paths, overlay focus and cleanup,
control lifecycle and virtual onset checks. Then independently verify private
real FUSE startup. Preserve real configuration/credentials by hash observation
only. Old acceptance is a method reference, not acceptance of the new hash.

Do not update stable entries or publish before both actual OS results and FUSE
are independently reviewed. Preserve existing versioned artifacts and releases.
The report successor increments to 0.6.1 without rebuilding the 0.6.0 package.
Before publication, merge the exact release source into main and verify ancestry;
create a draft with only the versioned AppImage and matching SHA sidecar, verify
both remote asset hashes, then publish formal/latest after review. Bind the tag
to the exact 0.6.0 source commit, not the report successor. Keep GNOME 46 native
Wayland, real cloud/physical microphone/physical shortcut and Unicode limitations
explicit in the final notes. No candidate-only pass or old hash may be substituted.


## Formal v0.7.0 Ubuntu input repair release

Prepare on `codex/release-0.7.0` from clean accepted main
`0dd7a3b` (development version 0.6.9). Use
`python3 scripts/validation/versioning.py bump --release` to synchronize
`pyproject.toml`, `src/inkecho/__init__.py` and `uv.lock` to 0.7.0. This preparation
changes only metadata and release documentation; do not relabel 0.6.8 or reuse
its acceptance as proof of the new artifact.

Commit the reviewed preparation, build from that exact clean source, and freeze
one manifest binding its source commit, AppImage SHA-256, full package inventory
and validation helpers. Rebind all 0.6.8 fixture paths, version and hash assertions
to 0.7.0; a stale assertion must fail before input, not be disabled. Run that same
new SHA on Ubuntu 24.04.5 / GNOME 46 Xorg and Ubuntu 26.04.1 / GNOME 50 native
Wayland plus XWayland. Required gates cover actual AppRun/configuration pages,
local manual/realtime/VAD protocols, real Recorder onset and overlay timing,
actual Dock identity, real Files and Text Editor progressive Unicode input,
and actual Codex/Claude private offline TUI checks specifically on 24.04 Xorg.
Distinguish progressive complete output from strict one-character render frames.
On 26.04 require controlled native/XWayland normal/cancel/current-cursor targets,
UI/protocol/audio gates and one private actual FUSE startup; do not claim fresh
Files, CLI or Dock application certification there. On 24.04 verify extraction
and actual package execution without claiming guest FUSE mounting. Both systems
require complete mapping/key cleanup. Physical microphone/cloud accuracy remain
unverified unless separately measured; do not copy personal credentials.

Keep the 26.04 intermittent field-blur failures and subsequent controls visible.
Do not add focus forcing or loosen guards to produce a pass. Record original
process exits, raw result versus tool-result files and all residual limitations
in `docs/release-0.7.0-validation.md`. Pending or failed gates are not approval.
The publication target is GitHub only; keep this machine's existing stable
entry unchanged. Require the same-artifact dual-system and host FUSE review
before publication. Preserve previous releases and artifacts. Merge the exact
release-source commit into main before tagging. Draft only the versioned
AppImage and matching checksum sidecar, verify remote downloads against local
hashes, then publish formal/latest. The report successor uses 0.7.1 without
rebuilding the validated 0.7.0 artifact; the tag stays on the exact release source.
