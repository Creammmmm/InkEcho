# Experimental Fcitx5 bridge candidate

The AppImage build includes one **uninstalled experimental candidate**, not an
active input method or a compatibility guarantee. Its source is the project's
MIT-licensed code in `native/fcitx5`. The binary dynamically references the
host's Fcitx5 Core/Config/Utils libraries; it does not bundle those libraries.
Fcitx5 is separately distributed under its own terms, including
LGPL-2.1-or-later; see [third-party notices](../THIRD_PARTY_NOTICES.md).

The candidate in `assets/native/fcitx5/x86_64` was built in a disposable Ubuntu
24.04.5 x86_64 VM with Fcitx 5.1.7 development headers, CMake 3.28.3, GCC
13.3.0, GNU make 4.3 and the C++20 target configured in `CMakeLists.txt`.
Build dependencies were the Ubuntu 24.04 packages `cmake`, `make`, `g++`,
`pkg-config`, `libfcitx5core-dev`, and `fcitx5-modules-dev`. The process did
not require a host Fcitx daemon, system plugin installation or clipboard.

From a clean checkout with those dependencies installed in an isolated build
environment, run:

```sh
python3 scripts/packaging/build_fcitx_candidate.py noble-check
sha256sum build/fcitx5-candidates/noble-check/candidate/libinkecho.so
```

The currently measured binary hash is
`3a3c80fb464bbfce465b52cb73e998a00705998a768c45400416daf29e89a497`;
the generated description has SHA-256
`44a1386046f2b4df4ea9ba73a43d7caf353e1039f7c14a316cc73e4c928bcb57`.
Toolchain updates or different build environments can change the binary hash.
The additive focus-v2 candidate exposes `Begin2(token, 2)` while preserving
legacy `Begin(token)`. Protocol version is separate from the descriptor addon
version `1.0.0` and the Fcitx build ABI `5.1.7`; neither is the InkEcho application
version. The package inventory records focus protocol 2 and legacy Begin support.
The exact source and binary pins must be updated together. The previous
runtime-version candidate SHA `532ef632385bfe9ae3b76312b74874a7cc562c58435bb07f430e704179ebd139` is retained
only as an owned-description retirement identity, not a selectable new payload.

The new binary was fully built using the toolchain above and tested against
real Fcitx 5.1.7 on Ubuntu24.04.5 Xorg and Fcitx 5.1.19 on Ubuntu26.04.1 native
GNOME Wayland. Real private-bus tests exercised old and new clients, no/multiple
focus statuses, sequence preservation, cancellation and conservative fallback
with a keyboard spy. Actual GTK3 targets independently received fixed text across
two owned windows on24 and two Entry controls in one native window on26. Both
first-accepted cancellation cases showed no suffix after at least1.25 seconds.
These isolated process-local fcitx tests do not prove system automatic detection,
arbitrary applications, native Wayland cross-window activation, physical ESC,
or final AppImage acceptance. Reproducible raw results and failures are retained
under `experiments/fcitx-focus-v2-private-bus-ubuntu24`,
`experiments/fcitx-focus-v2-desktop-ubuntu24` and
`experiments/fcitx-focus-v2-desktop-ubuntu26`. The26 images are owned-widget
renderings, not compositor captures. Do not replace pins from build success alone;
review the source and actual target evidence together.

An earlier binary (SHA-256 `75fac6ba32ee4f3284278f7080bb026f980fee2460dcdd6034a103043319524b`) was separately tested using disposable Fcitx
processes in Ubuntu 24.04 Xorg / Fcitx 5.1.7 and Ubuntu 26.04 native Wayland /
Fcitx 5.1.19, with an owned GTK3 editor. Both verified LF and Tab submission
after holding the task open for 125 seconds. Cancellation after LF and VTE
raw-byte behavior were tested on an earlier candidate; they have not been
retested for this exact binary. Independent
D-Bus connections verified unauthorized tokens and senders, replay, and the old
unauthenticated `Commit(s)` signature were rejected. The capability helps guard
against accidental or tokenless calls; same-user processes are not isolated. The terminal
fixture ran a dedicated byte reader, not a shell: in a real shell, LF may
submit and execute the command currently at the prompt.
Those limited tests are not an AppImage test and do not establish compatibility
with other Fcitx versions, other applications or a user's active input engine.
The current candidate metadata identifies its Ubuntu 24.04 build and Fcitx
5.1.7; the experimental staging tool does not accept a different OS or
Fcitx version based solely on a user-editable compatibility declaration.

The AppImage builder verifies fixed native source and payload hashes before
altering the existing build directory, and records the candidate in the package
inventory. These in-tree pins detect accidental or partial changes; they are
not a digital signature and cannot authenticate a modified source checkout or
AppImage. It rejects non-x86_64 builds. The candidate is data: building or
running the AppImage does not install, activate, refresh or restart Fcitx. A
user-initiated installation and a matching system runtime are still required;
an AppImage-mounted file must not be used as a persistent plugin path. A public
release still requires the same final AppImage SHA-256 to pass actual package
acceptance on both Ubuntu versions.

During a temporary loss of Fcitx focus, protocol-v2 returns3 for no target and4
for multiple targets, without calling commitString or consuming the sequence.
Legacy Begin clients continue to receive3 for both cases. The new Python client
negotiates Begin2 when advertised and retries only a confirmed-unsent scalar
within bounded, cancellable waits. Lost replies and unknown statuses are never
replayed. Automatic keyboard handoff is allowed only before any native prefix
has been accepted. After a native prefix, failure stops conservatively rather
than replaying a suffix into another backend. Transport status1 is only a
commitString attempt; actual application consumption still requires independent
verification. No finite focus wait can guarantee arbitrary target delivery.
