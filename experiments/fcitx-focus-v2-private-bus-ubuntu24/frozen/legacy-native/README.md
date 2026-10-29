# Experimental Fcitx5 bridge

This is an isolated, unintegrated backend. It does not enable a system input
method, install files, restart Fcitx5, or change existing InkEcho settings.

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
context at that moment. No or multiple focused contexts return status 3 without
calling `commitString`, retaining the task and sequence. Status 0 indicates a
protocol error, 1 means `commitString` was called, and 2 means delivery is
unknown. A status 3 permits a bounded, cancellable retry of that same unsent
scalar; a lost reply or exception is never retried. Status 1 does not mean an
application has processed or displayed the text. Cancelling an in-flight
call cannot withdraw a message already queued in the desktop. Newline (LF) and
tab can be submitted; other C0/C1 controls are rejected. Terminal applications
interpret LF according to their own behavior: an active shell may execute the
current command. The raw-byte fixture is not a test with a real shell.

The current source implements a candidate task capability and bus-assigned
sender binding; the previously built binary has the old unauthenticated
endpoint and must not be treated as the current source. The capability file
helps prevent accidental and tokenless calls, but does not protect against
other processes with the same user identity, which may read or race it.
A disconnected owner is watched for task cleanup. The client enforces the
actual task deadline and explicitly cancels when the task ends; the plugin does
not impose a shorter independent recording limit. A connected but stalled client
can retain the task until it disconnects or cancels. The plugin never logs
input text and does not read the clipboard; security, packaging and two-system
validation require further review before deployment. No compatibility is claimed for untested
desktop sessions, frontends, input engines or applications.
