# Experimental Fcitx5 bridge

This is the optional Fcitx5 output bridge. Building or bundling it does not
install or enable it, restart Fcitx5, or change existing InkEcho settings.
Installation and enablement require the explicit application controls or staging
procedure below; the live addon must still pass protocol negotiation.

Build on the target Fcitx5 ABI with CMake, a C++20 compiler, and the Fcitx5
core, utils, and module development packages:

```sh
cmake -S native/fcitx5 -B build/fcitx5-addon
cmake --build build/fcitx5-addon
```

Alternatively, on the target build environment run
`python3 scripts/packaging/build_fcitx_candidate.py NAME`. It builds into a
fresh project `build/fcitx5-candidates/NAME` directory and records source hashes,
artifact hashes, architecture, OS version and the Fcitx core version. A failed
build is never marked as a candidate. It does not install system packages or
modify, start or restart the host input method.

The resulting library and addon metadata require a separately designed and
reviewed host installation and loading procedure. Bundling them in an AppImage
does not make the running Fcitx5 process load them. An OS-labelled build does
not itself establish compatibility with other OS or Fcitx versions. The build
does not install them automatically or restart Fcitx5.

An experimental explicit user-data staging helper is available in
`scripts/packaging/stage_fcitx_candidate.py`. It publishes an owned addon
description without replacing an existing one and checks candidate hashes,
ELF architecture and recorded build metadata. Its metadata is not a signature
or proof of ABI compatibility, so use only a trusted candidate. It does not
call `Refresh` or modify any Fcitx process. Deactivation removes only the
matching owned description; the versioned library is retained because a live
Fcitx process can continue using it until that process exits. Therefore neither
staging nor deactivation claims immediate activation or unloading. Concurrent
changes by unrelated processes with the same user identity are not prevented by
Fcitx and require additional review before product integration.

Each D-Bus call accepts exactly one Unicode scalar and resolves the focused input
context at that moment. Legacy `Begin(token)` returns status3 for no or multiple focused contexts.
The additive `Begin2(token, 2)` returns3 for no focus and4 for multiple focus;
both mean unsent and retain the task and sequence without calling `commitString`. Status 0 indicates a
protocol error, 1 means `commitString` was called, and 2 means delivery is
unknown. A status 3 permits a bounded, cancellable retry of that same unsent
scalar; a lost reply or exception is never retried. Status 1 does not mean an
application has processed or displayed the text. Cancelling an in-flight
call cannot withdraw a message already queued in the desktop. Newline (LF) and
tab can be submitted; other C0/C1 controls are rejected. Terminal applications
interpret LF according to their own behavior: an active shell may execute the
current command. The raw-byte fixture is not a test with a real shell.

The current source and pinned candidate implement a task capability and
bus-assigned sender binding. New clients require `Begin3(token, 3)` from the
running daemon before creating the capability. Missing protection stops with
`composition_guard_unavailable`; rejected negotiation stops with
`authorization_failed`. Neither condition authorizes keyboard or owned-IBus
fallback. Updating a file does not update a daemon's already-loaded addon.

Before each scalar, the addon rejects a non-empty public input panel or pending
client events without calling `commitString`, resetting composition or changing
the engine. A panel includes server/client preedit, candidates and auxiliary UI.
Guarded status5 terminates the native task; old Begin/Begin2 clients receive
terminal status2 for the same condition. The Python client does not retry or
replay a blocked tail, even after composition clears. Private engine/client state
not exposed by these APIs remains unproven; the guard is not a target receipt.
No-target and keyboard behavior retain their existing, narrower guarantees.

The pinned native SHA has Ubuntu 24 SDK/Core/private-bus verification and real
Pinyin composition, normal auto output and partial-cancel checks in Ubuntu 24
X11/GTK3 and Ubuntu 26 Wayland/XWayland GTK3. Both used the identical native SHA.
The staging allowlist authorizes only Ubuntu 24.04/Fcitx 5.1.7 and Ubuntu
26.04/Fcitx 5.1.19 on x86_64. This is bounded addon qualification, not AppImage
acceptance or a guarantee for every session, engine or application. Exact
results, retained failures and limits are in
[the validation record](../../docs/fcitx-preedit-guard-validation.md).
Clients must not infer activation from a staged file. The capability file
helps prevent accidental and tokenless calls, but does not protect against
other processes with the same user identity, which may read or race it.
A disconnected owner is watched for task cleanup. The client enforces the
actual task deadline and explicitly cancels when the task ends; the plugin does
not impose a shorter independent recording limit. A connected but stalled client
can retain the task until it disconnects or cancels. The plugin never logs
input text and does not read the clipboard. A new AppImage still requires
same-SHA actual package acceptance on both Ubuntu systems before deployment.
No compatibility is claimed for untested
desktop sessions, frontends, input engines or applications.
