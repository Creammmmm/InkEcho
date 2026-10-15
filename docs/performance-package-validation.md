# Alpha10 local package validation

Date: 2026-10-16. The final local preview package passed the checks below. This
is **not a published release or a cloud speech-quality acceptance**. No
installation, Git push, deployment, user configuration change or stable-artifact
replacement was performed.

## Artifact and source identity

- File: `dist/InkEcho-0.1.0a10-x86_64.AppImage`.
- SHA-256: `5c515dd0e3ceb8eb910baa45f392d8be28bfda109c5e1d59865e5a0733b7d55a`.
- Size: 108,907,000 bytes.
- Frozen product source: `b9638791b9fe006e56d716928f5192450f6ae3b8`.
- Metadata: `build/performance-a10-r2-artifact.json`.
- Source hashes: `build/performance-a10-source-r2-build.json`.
- Build/extraction logs: `build/performance-a10-r2-build.log` and
  `build/performance-a10-r2-extract.log`.

The 43 application source hashes matched before and after construction and again
at the end of package acceptance. The artifact's extracted interpreter was used
for both pipeline runs; ten application/runtime modules were verified as loaded
from its `packages` directory. Its inventory verified 3,958 file hashes, 1,048
internal symbolic links, all 43 application files and both websockets 15.0.1
BSD-3-Clause license copies. UI acceptance independently recorded the same
AppImage SHA-256.

Earlier artifacts remain historical checkpoints, not final artifacts:

| SHA-256 | Reason superseded |
| --- | --- |
| `fb48779477b2a4b635ac71d503d2025de9e9876a3563b7459031656415bb22a6` | Predates provider-save realtime URL preflight |
| `2f8d2ecaca12df41783384f30ed96cfe30eb8623a02eaff07ac99b244b990ddf` | Predates corrections for actual official realtime event metadata |

The latter checkpoint's 49 receipts, logs, source manifest, UI/container
screenshots and report are preserved in
`build/performance-a10-checkpoint-2f8d2ec/`, with
`checkpoint-evidence-sha256.json`. Its original extracted AppDir also remains at
its independent path recorded in the archived metadata. Final-round evidence
uses the distinct `r2` names below and did not overwrite the archived checks.

## Actual package checks

| Check | Actual result | Local evidence |
| --- | --- | --- |
| Packaged synthetic pipeline | Strict local HTTPS/WSS, HTTP connection reuse, two realtime sessions, exact 25-character output and cancellation after one additional character without a tail | `build/performance-a10-package-synthetic-r2.{json,log}` |
| Packaged microphone and desktop pipeline | Actual Recorder, local WSS fixed ASR, local HTTPS SSE fixed polish, production X11 keyboard backend into a newly owned GTK field under XWayland; exact 25 characters, cancelled task adds exactly one character; balanced events and restored mapping | `build/performance-a10-package-live-mic-r2.{json,log}` |
| Native Wayland package UI | Nine pages, IPC show/toggle/cancel/quit, normal exit; corrupt disposable configuration preserved on exit 1 | `build/performance-a10-ui-native-r2/result.json`, page PNGs and logs |
| Offscreen package UI | Same nine pages and lifecycle checks | `build/performance-a10-ui-offscreen-r2/result.json`, page PNGs and logs |
| Ubuntu 24.04 userspace | Existing pinned container, no network, non-root, no host home/display/audio; package UI smoke and nine screenshots passed | `build/performance-a10-ubuntu24-r2.log`, `build/ubuntu24-qa.t9TepB/` |

Both package pipelines explicitly exercise a manual-mode confirmation without
`turn_detection`, a pre-commit placeholder `item={type:message}` without ID/role,
and an early `.text` preview. These are **local simulated events** based on the
separately observed official event categories. The fixture subsequently provides
a valid matching commit-ACK ID and final transcript, retaining coverage of
provided-ID consistency. This does not establish the actual values of omitted
cloud fields. Stable target readback before stop remained unchanged in both
tasks, and the local polishing service received only the fixed final ASR body.
Receipts record these checks as booleans, without printing either body.

Each pipeline's `server_errors` is empty and `fixture_threads_closed` is true.
Both pipeline and UI logs were checked for tracebacks, unraisable-generator
failures, destroyed tasks and runtime warnings; none were present. Fixtures use
bounded socket timeouts, joined HTTP handler threads, and safe fixed failure
codes for unexpected server exceptions.

All 18 native/offscreen page images were visually inspected. Chinese labels,
controls and palette remain readable; long provider/Prompt/statistics pages
scroll intentionally. The disposable default profile's F13 label does not
change the user's configured shortcut. Ubuntu's container emitted expected
missing-audio-backend warnings; it has no desktop or microphone and is **not
Ubuntu 24.04 desktop acceptance**. The existing container image is
`sha256:2c3b496bde583a825cc90f81a670e2b91b0796f87fbd5d7bc5a868a205461a5b`,
built from the pinned Ubuntu 24.04 base in the packaging recipe.

## Measured scope and remaining gates

The real microphone run uploaded 3,200 PCM bytes before stop in each task. Its
first successful key press preceded SSE completion. Stop-to-first-press was
28.628 ms and stop-to-output-complete 1,793.176 ms for the fixed 25-character
fixture. These are local fixture timings, **not cloud latency**. Actual Qt-loop
map/press/release waits were 21.001–23.420, 20.253–21.509 and 20.320–20.857 ms.
The full results and cancellation timeline remain in the receipt.

The host was Ubuntu 26.04.1 GNOME Wayland. This pipeline deliberately exercised
the production X11 backend into XWayland. It does not establish a native Wayland
microphone-to-input pipeline or standalone Xorg support. Independent native
Wayland callback checks and the four-target Qt-loop keyboard comparison are in
[keyboard validation](performance-keyboard-validation.md) and the
[streamed-input correction](performance-x11-stream-validation.md).

No package probe read user credentials or issued a cloud request. Separately,
the source transport's official generated-silence test completed the protocol:
`build/performance-realtime-silence-optional-metadata.json` records
`protocol_finished_without_speech`, ten frames, acknowledged commit and finished
session, with configuration unchanged. It validates neither speech recognition
accuracy nor an authenticated request from this built AppImage. Earlier live
failures and the narrow metadata corrections are documented in
[realtime validation](performance-realtime-validation.md). The public speech
sample request previously rejected by automatic approval was not retried or
bypassed. Actual cloud speech acceptance remains pending.

## Reproduction

Build with `.venv/bin/python scripts/packaging/build_appimage.py` after the
product-source freeze, extract the artifact into a fresh directory with
`--appimage-extract`, and use that directory's `usr/bin/python3` for
`scripts/validation/performance_package_probe.py --package-root APPDIR/packages
--output RECEIPT.json`. Set `APPDIR`, `PYTHONHOME=APPDIR/usr`,
`PYTHONPATH=APPDIR/packages`, `PYTHONNOUSERSITE=1`,
`QT_PLUGIN_PATH=APPDIR/packages/PySide6/Qt/plugins` and
`LD_LIBRARY_PATH=APPDIR/usr/lib/inkecho` to the extracted directory. Use
`QT_QPA_PLATFORM=offscreen` for the synthetic case.

For the explicitly local microphone/desktop case, use the same packaged
interpreter and add `--owned-xwayland-live-mic --xdotool XDO_TOOL_WRAPPER` in the
host session. The helper creates its own empty GTK target and checks its PID,
process start time and active window before each press. This test guard is not a
product focus lock. Do not run desktop acceptance concurrently with other
desktop automation. Final runs omit `--pacing` and use production settling times.

Run `scripts/validation/desktop_app_probe.py --appimage ARTIFACT --output DIR`
with a fresh output directory for each Qt platform. For native Wayland, preserve
an absolute host Wayland socket path because the helper isolates its runtime
directory. Run `scripts/packaging/check_ubuntu24.sh
InkEcho-0.1.0a10-x86_64.AppImage` for the isolated userspace smoke. No test sends
fixture text to an existing user document or shell.

## User-state preservation

`build/performance-package-preserved-before.json` stores only hashes of the three
existing user JSON files and the alpha9/stable artifacts. Rechecking after all
final local acceptance confirmed `configuration_unchanged=true` and
`a9_and_stable_unchanged=true`; receipt:
`build/performance-package-preserved-r2-result.json`.

The retained alpha9 and stable alias SHA-256 remains
`3c18b8773ec95632fd864ffc21a63a08c465b4780c939237f5f27e2dddfc1d07`.
No preview was installed, no shortcut was registered, no integration or autostart
setting was changed, and all owned test windows and temporary recorders closed.
