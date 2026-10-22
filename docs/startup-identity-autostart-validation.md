# Running identity and enabled autostart validation

2026-10-23, local private-profile source checks. These are not AppImage desktop
acceptance, old/new release-binary acceptance, or the cause of the user's
reported Codex input corruption (that defect has separate receiver evidence).

## Reproduced findings

`Instance` in `src/inkecho/__main__.py` names its lock/socket from uid and resolved
config directory, without package/executable identity. On lock conflict it sends
only the requested command, returning before Session initialization and desktop
integration. There is no version response. The reviewed private QCore owner and
real `main()` client probe used different synthetic APPIMAGE paths but the same
source 0.8.7; client returned normally with exit0 and its guarded `run()` was never
reached. Owner received `show` and exited normally; neither process was signalled
and the private profile was not initialized. This demonstrates missing identity
negotiation, not a test of actual old/new release binaries. The first sandbox run
failed to create its local socket; that failure was retained, then the identical
isolated probe with normal local IPC permissions passed. No real user instance,
credentials, devices, shortcuts or desktop settings were touched.

A separate private `DesktopIntegration` reproduction created two nonexecuted
synthetic AppImage files, enabled managed autostart for the first, then called
`ensure_running_identity` for the second. The launcher pointed to the new path,
while the autostart retained the old path byte-for-byte. Thus a later login could
start an earlier image despite a newly registered application launcher.

## Implemented correction

After successfully validating/installing the current launcher and icons, startup
synchronizes the executable token of an already enabled, managed autostart entry.
It retains all profile/config/data arguments and other desktop fields, uses the
existing atomic writer, and does not create or enable autostart. Unmanaged files,
symlinks, unfamiliar command layouts and duplicate Exec entries are preserved.
An unchanged command is not rewritten. No process is started, killed or replaced.

Focused validation: `pytest -q tests/test_integration.py` reports **30 passed**.
Ruff check and formatting pass for the two changed Python files. Regression
coverage includes path changes with quoting, custom profile arguments, repeated
startup without writes, disabled autostart staying absent, unrelated content,
unknown managed layouts, duplicate Exec and existing symlink/ownership guards.

## Remaining identity boundary and release gate

No production identity protocol or automatic old-instance handoff was added.
An existing legacy owner can still receive a new image's request without a version
handshake. Do not claim that the newly invoked filename is the running version.
Release QA must record the actual processing owner PID/start identity, source or
package origins, version/build identity, and connect the tested Session to that
owner. A future handshake must retain the same profile lock, classify unknown
legacy identity explicitly, preserve active work, and avoid parallel workers or
silent force termination. This patch prevents managed autostart path drift only
once the current image actually becomes the running owner.

Reviewed reproduction artifacts (local build evidence):
`build/ubuntu24-input-pipeline/identity-ipc-r1.json`, `identity-ipc-r2.json`,
`autostart-drift-r1.json`, and `tools/instance_identity_probe.py`. Reproduce only
with unique private HOME/XDG/runtime/config paths; never use a real user profile.
