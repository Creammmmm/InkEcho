# Codex input target: read-only accessibility validation

On 2026-10-13, the unlocked native GNOME Wayland session was inspected without
changing focus, settings, or application state. The existing Codex desktop
surface ran as PID 6479, executable `/usr/lib/chatgpt/ChatGPT`. This process
identity was checked without reading its command line.

## Observed result

The process was present in the AT-SPI registry. Its application root exposed
three `frame` children, one with the `ACTIVE` state. Each frame's `GetChildren`
returned only `/org/a11y/atspi/null`; no actual input control was exposed.

The application and three frames exposed `Text`, but neither `EditableText` nor
`EDITABLE`/`FOCUSED` state. The null reference independently returned
`org.freedesktop.DBus.Error.UnknownMethod` for each of `GetRoleName`, `GetState`,
`GetInterfaces`, and `GetChildren`. These calls were independent: a failed role
query did not prevent inspection of state, interfaces, or descendants. Repeated
snapshots agreed.

The production input adapter would traverse from the active frame to the same
null reference, where its `GetState` call also fails. Thus the current exposed
tree provides no safely capturable Codex input target. This is evidence about
this running instance, **not** proof that every Codex version or accessibility
configuration lacks an editable input interface. Those alternatives remain
unverified. Earlier Chrome textarea results in [the feasibility report](feasibility-report.md)
are separate evidence and cannot establish Codex compatibility.

## Reproduction and limits

Identify the intended application's PID without reading its command line, then
run from the repository in that application's desktop session:

```sh
.venv/bin/python scripts/feasibility/accessibility_metadata.py --pid <PID>
```

The retained [probe](../scripts/feasibility/accessibility_metadata.py) selects
only the explicitly supplied PID. It reads registry/PID metadata and accessible
roles, interfaces, states, and child references. It prints protocol error names,
never error bodies. It does not read names, titles, text, caret positions, API
keys, or command lines; register event listeners; enable accessibility settings;
restart applications; change focus; or invoke input actions.

Calls have a two-second timeout, the whole probe a 40-second limit, and each
application tree a 4096-node limit. Detailed control output is capped at 64
entries; interface totals cover all visited nodes. A null reference is reported
as incomplete metadata rather than silently discarded. A complete registry scan
is distinct from each application's metadata completeness.

The root agent independently reran the retained probe with `--pid 6479` and
confirmed the executable identity. The command exited successfully: 12 registry
applications, five visited target nodes (one application, three frames, one null
reference), four `Text` interfaces, zero `EditableText` interfaces, one active
frame, and one null child per frame. All four null-reference queries returned
the same `UnknownMethod` error; `registry_errors` was empty. This agrees with
the earlier precursor probe. Ruff lint/format checks, Python compilation, and
the `--help` path also passed. No product code changed and no insertion,
clipboard access, recording, or cloud request was performed for this check.

## Accessibility activation follow-up

A read-only `org.freedesktop.DBus.Properties.Get` query on `org.a11y.Bus`, path
`/org/a11y/bus`, interface `org.a11y.Status`, returned `IsEnabled=false` and
`ScreenReaderEnabled=false`. Neither property was changed; no application was
restarted.

Official Chromium `main` sources checked on 2026-10-13 distinguish exposing the
tree from offering an editing interface:

- [Bridge activation](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/ui/accessibility/platform/atk_util_auralinux.cc#129)
  checks environment overrides and `IsEnabled`.
- [Native object creation](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/ui/accessibility/platform/ax_platform_node_auralinux.cc#2571)
  can retain application/top-level window objects while returning null for other
  objects when `kNativeAPIs` is disabled. The observed tree is consistent with
  this condition, but the running binary's exact implementation and cause have
  not been established.
- [ATK interface registration](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/ui/accessibility/platform/ax_platform_node_auralinux.cc#2435)
  registers `Text` but no `EditableText`. Enabling tree visibility therefore does
  not establish availability of the `EditableText.InsertText` operation required
  by InkEcho's current backend.

These are upstream source observations, not an activation experiment or proof
about every Codex build. No verified repair consisting solely of enabling a
setting has been established. Safe targeted input still requires an editing
interface exposed by the target application. No settings, focus, user content,
or product code were changed during this follow-up.

## One temporary activation experiment

After the read-only checks, one explicitly authorized reversible experiment
verified that `IsEnabled` was writable and temporarily changed it from `false`
to `true`. A readback confirmed `true` before the existing metadata probe ran
against the same verified process, PID 6479. The tree was unchanged: one
application, three frames each returning only a null child, four `Text`
interfaces, zero `EditableText` interfaces, and the same four `UnknownMethod`
responses on the null reference. The probe exited successfully.

The experiment's `finally` block restored `IsEnabled=false`. A separate D-Bus
connection independently read back `IsEnabled=false` and
`ScreenReaderEnabled=false`, matching the initial values. The screen-reader
property was never written. No newly started Orca process or unexpected
screen-reader state change was detected. No application restart, focus change,
user-content read, or input operation occurred. The root agent reviewed the
script's restoration path and accepted the observed result; no repeat was run.

This rules out this single runtime switch change as a sufficient fix for the
current instance. It does not establish behavior after a restart, with other
settings, or in another version. The temporary mutation script remains outside
the repository; the tracked metadata probe remains read-only. The Codex process
hosting the current task was not restarted.
