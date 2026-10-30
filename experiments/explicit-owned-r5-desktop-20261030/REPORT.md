# Explicit owned IBus R5: isolated desktop evidence

Candidate: `explicit-owned-r5.patch`, SHA-256
`ff18833701e12d8ada9952d441f0e6eb84f8088b13f3b635b3b2439a735d13ca`.
This is **source-overlay qualification**, not a new AppImage, release gate, or
qualification of every application. Shared source, host desktop and host input
settings were not modified. Automatic selection remains unchanged.

## Identity and method

Tests ran sequentially on disposable Ubuntu 24.04.5/GNOME 46 Wayland and Ubuntu
26.04.1/GNOME 50.1 Wayland virtual seats. Docker used no network, dropped
capabilities, read-only host backing mounts, independent names and RAM write
layers. QEMU restricted user networking provides only the container-local SSH
control port. Parent archives and QEMU/launch configuration are in the byte
archive. No host seat or real credentials were passed through.

The published 0.14.0 AppImage SHA-256
`a79ed5409e6d935ac1d4f4420f06e5ec6bc454fc20bdfe04c6db1e8ed6def055`
provided the FUSE-mounted runtime and dependencies. Its pristine package audit
ran separately before source overlay imports. Actual InkEcho modules came from
`/mnt/input/overlay-src`, whose complete 94-file byte manifest is archived.
The candidate patch is included reversibly. The seven unchanged, reviewed
bounded bridge assets were staged only in each guest after preserving the
complete old installation; GNOME was reloaded normally. This does not inherit
whole-package qualification from 0.14.0.

The browser fixture persists `output_method='ibus-owned'` with actual ConfigStore
and runs actual `app.Session`, synthetic recorder/provider and a real
DefaultAutoOutputRouter supplied as its inputs. No selection subclass, forced
owner, capability reply, transport response or clipboard is used. This is not
physical microphone/hotkey/cloud testing. It tests Session orchestration with
an actual supplied production router, not a separate claim that the Session
constructor's default factory was exercised without inputs injection.

## Observed results on both systems

Chrome ran native Wayland with ordinary sandbox enabled. Resource audit,
actual executable, private profile, Wayland surface/toplevel/keyboard-enter,
DOM `document.hasFocus` and active field were checked. Renderer `/proc` checks
confirmed seccomp 2, no_new_privs 1 and nested namespace PIDs.

* Textarea: fixed public mixed Chinese/Unicode/LF text, 22 code points, complete;
  partial cancellation received one prefix character; pending cancellation
  received zero; moving the caret after prepare sent all 22 to the second field.
* Contenteditable: corresponding normal, partial cancellation and prepare-time
  caret switch passed. Output was observed unchanged for at least 1.3 seconds.
* Normal completed Session outcomes are `unconfirmed`. Exact owned DOM is an
  independent test observation, not a production target acknowledgement.
* Native Chrome to a newly opened, independently verified XWayland window in
  one output scope: first native target received exactly two characters,
  XWayland received zero, `ibus_delivery_unknown` carried attempts=2. No keyboard
  presses, replay or late output; resources/maps restored. This is the documented
  safe stop of the explicit native-only method, **not** continuous cross-backend
  delivery. Direct router calls, rather than Session, exercise this case.
* Real GTK Wayland/libpinyin: fixed guest hardware n/i keys produced preedit
  “你”; committing the public candidate text was refused with
  `ibus_delivery_unknown`; committed text remained empty and preedit unchanged.
  Actual owner probe succeeded, so this is not merely an absent-service test.
  Source selection and xkb:us::eng were restored.

No live provider, arbitrary application matrix, Xorg success or atomic receiver
ACK is claimed. Same-widget instantaneous focus races and in-flight cancellation
cannot be retroactively withdrawn. Nothing uncertain is replayed.

## Old V2 and limits

The old `ibus` enum/UI path is retained separately in candidate tests; new mode
never replaces it. On 26, the supplementary actual Session empty-input check
retained ConfigStore value `ibus` and the legacy factory module. Its outcome
was cancelled, zero dispatches; it does **not** prove V2 connection or successful
legacy desktop input. Its original fixture scope sentence says “actually
selected”; interpret that as the retained configuration, not positive protocol
qualification. The V2 extension remained disabled. No positive V2 desktop
compatibility has been established in this round. No attempt was made to
advertise the older protocol as having the newer protections.

## Failures retained

24 initially hit normal network-online startup delay and three SSH timeouts;
SSH became ready after the ordinary 120-second wait. Guest 9p shares required
explicit guest-only mounting; the first preparation attempt failed before any
input. Cross-focus fixture revisions failed before body dispatch because of
an existing output directory, a package-origin audit inappropriate for a source
overlay, and a historical driver observation seam. Fresh final cases used the
separate pristine package audit and current keyboard observation seam. Every
original failure and final source is retained. The final fixture does not
replace product outcomes or relax real focus guards.

24 textarea pending-cancel produced an existing dbus-next unhandled Future
BrokenPipe warning; the run exited zero, DOM remained at zero for that case and
owned browser/transport cleanup checks completed. Warning retained, not hidden.
26 shutdown's first two engine readbacks lacked proper IBus DISPLAY address
discovery and failed; with actual guest DISPLAY=:0 the original engine was
confirmed and normal poweroff succeeded. These are recorded fixture/environment
failures, not silently converted into successful samples.

## Cleanup and reproducibility

Both guests restored exact old extension assets and original enable/disable
settings, input source/engine, and FUSE mount. Owned Chrome and actor processes
were gone (the process query matches only its own shell command). GTK actors
were terminated intentionally after observing unchanged composition. Both
QEMU processes exited zero; original docker waits returned exited/PID0/exit0,
no OOM. RAM overlays were compressed, read back in full and hashed; receipts
and final container states are included. Large disks and owned screenshots
remain at external paths with explicit SHA-256/size pins. Parent images remain
read-only. The host desktop was not touched.

`raw-byte-archive.json` stores original bytes as deterministic gzip/base64 with
SHA-256 and size. Decode each entry, verify both values, then JSON-parse where
applicable. It includes both launchers, exact final fixtures, intermediate
failure receipts, source manifest, protocol metadata and result/cleanup records.
No secrets, user audio or user transcripts are included; all visible text is
fixed public fixture content. `external-retained-pins.json` explicitly names
large external artifacts; those are not falsely represented as files created
by this evidence patch.

## Independent source safety review

The final R5 patch above independently passed 201 focused output/router, bounded
protocol, installation, handoff and UI regressions. Ruff lint and formatting
checks passed. The older R4 cleanup-generation counterexample failed as expected;
final R5 passed it. Independent cleanup-OSError cases retained structured unknown
with attempted=1 and no replay, and cancellation/deadline precedence retained
zero-send safety in both explicit and existing auto preflight paths. These are
offline safety checks, separate from the real desktop observations above.
