# Native Wayland keymap feasibility

This record follows isolated GNOME 50.1 experiments and the subsequent
production-worker validation on 2026-10-15. Early prototype failures are retained
below. The final default worker passed private native Chrome; an authorized host
experiment passed the current desktop's Chrome contenteditable with libpinyin
and an empty composition. Packaging and other application acceptance are tracked
separately; this does not establish compatibility with every GNOME version or
input engine.

## Isolation and scope

`nested_keymap_probe.py --run-isolated` starts its own `dbus-run-session`, GNOME
Shell `--wayland --headless --virtual-monitor`, private runtime socket and private
XDG configuration/data/cache/state directories. A temporary keyfile settings
backend selects one US source. The original HOME is not reassigned. Every input
or SetKeymap mutation checks that the private D-Bus service belongs to the child
compositor PID. Only owned GTK, Chrome or raw-PTY VTE fixtures are opened. Cleanup terminates the owned
process group, waits, and escalates to SIGKILL only for that group if necessary.

No user document, website, microphone, API credential, cloud service, clipboard
or system input-method delivery is used. Fresh GNOME starts auxiliary services,
including IBus, but delivery uses RemoteDesktop keyboard events and the fixture
uses GTK's simple key context. No input-method commit API is called.

The headless seat initially lacks a keyboard. A balanced Shift press/release
before the fixture exists creates the private virtual keyboard. Escape exits
fresh Shell's startup overview; the fixture must independently report active and
focused before the fixed sample is sent. These are private test setup actions,
not attempts to manipulate focus on the user's desktop.

## Baseline results

Commands, using the repository virtualenv:

```sh
.venv/bin/python scripts/feasibility/nested_keymap_probe.py --run-isolated
.venv/bin/python scripts/feasibility/nested_keymap_probe.py --run-isolated --restore-policy
```

Both completed with exit 0. Each received exactly 28 characters: Chinese, ASCII,
accented Latin, Greek, emoji and a newline. The sample was sent as 56 key press /
release events. Thirteen originally empty keycode slots were assigned additional
Unicode symbols; existing mappings were preserved. The owned GTK fixture reported
active focus. The original `wl_keyboard.keymap` bytes matched after restoration.

| Restoration | Exact sample | Original map bytes | Ownership after restore |
| --- | --- | --- | --- |
| Upload saved original FD | pass, 28/28 | equal | Original description identity not established |
| Empty `SetKeymap({})` policy reset | pass, 28/28 | equal | `CurrentKeymap.source` changed SESSION (1) to EXTERNAL (0) |

Local logs: `build/nested-keymap-snapshot-pass.log` and
`build/nested-keymap-policy.log`. The original map SHA-256 was
`e9e6b45d29d38fa1d6a42847b1666d9b94c45160e61516632a326a4f10673ded`.

Early probes failed before modification because the headless seat had no keyboard
and because the initial guard expected one compiled group. GNOME appends its UI
locale group even for one configured US source; this test therefore has two
compiled groups and explicitly initializes the sole user source at index zero.
A later probe restored the map successfully but received zero characters while
startup overview held focus. Only the subsequent independently focused fixture
runs above count as Unicode acceptance.

## Gates still open after the initial baseline

This baseline does not test held modifiers, latched/locked state, a nonzero user
layout group, concurrent layout changes, explicit mid-output cancellation, helper
crash, guardian failure, native Chromium or a terminal. The byte comparison before
restoring is not an atomic compare-and-swap and cannot exclude a layout update
between comparison and mutation. Direct Mutter session creation here is restricted
to the owned compositor; it is not a production authorization design or a reason
to bypass desktop consent.

## Source facts

GNOME's [50.1 keyboard manager](https://raw.githubusercontent.com/GNOME/gnome-shell/50.1/js/misc/keyboardManager.js)
retains its own description, supplies it to reset-keymap-description, supplies the
current user group to reset-keymap-layout-index, and appends the locale group.
The [Mutter 50.1 RemoteDesktop interface](https://raw.githubusercontent.com/GNOME/mutter/50.1/data/dbus-interfaces/org.gnome.Mutter.RemoteDesktop.xml)
defines empty SetKeymap as display-server policy reset and distinguishes the
session's current map from external maps. These are private version-specific APIs.

## Cancellation and native Chrome follow-up

The GTK policy-reset experiment stopped after five characters in two separate
runs: explicit cancellation, and an actual SIGTERM delivered to the controller.
Both exited 0 after restoring the original map. Exactly five characters / ten key
events were delivered; the remaining 23 characters were not sent, and delayed
readback found no additional output. Logs are `build/nested-keymap-cancel.log` and
`build/nested-keymap-terminate.log`. This is graceful signal handling, not recovery
from SIGKILL or proof of a separate guardian.

The first native Chrome textarea run **failed**: only 20 of 28 expected characters
arrived, and U+1F600 became U+F600. The wrapper independently established native
Wayland surface/toplevel traffic, absent DISPLAY and owned document/field focus.
Adding a 300 ms delay after SetKeymap produced exactly the same wrong result;
that delay does not solve the failure. Failure evidence is retained in
`build/nested-keymap-chrome-diagnostic.log` and
`build/nested-keymap-chrome-settle.log`, including only synthetic sample codepoints
and their assigned empty slots.

Reusing the single originally empty AE13 / XKB keycode 132 for each missing BMP
character **passed** both native Chrome textarea and contenteditable: 26/26
characters, including Chinese, accented Latin, Greek, ASCII and newline. Each
map change completed before the associated key press. This sample deliberately
excluded non-BMP characters; it does not establish emoji support. Both runs
restored the original map bytes and returned policy ownership to EXTERNAL.
Logs: `build/nested-keymap-chrome-single-bmp.log` and
`build/nested-keymap-chrome-contenteditable-bmp.log`.

The map rotation bounds the number of occupied empty slots rather than requiring
one slot per unique character in a long result. Production performance, state
preservation, concurrent changes and crash recovery are still separate gates.

## Additional isolated gates and observed limits

The following follow-ups used Ubuntu 26.04.1 LTS, GNOME/Mutter 50.1 and Chrome
154. They are not claims about other desktop versions. The earlier “Remaining
gates” section describes the initial baseline; the table records subsequent
checks. Every listed passing run exited 0 and used an owned private compositor.

| Check | Actual result | Local evidence under `build/` |
| --- | --- | --- |
| Native Chrome, restore saved snapshot | 26/26 BMP characters; original map bytes restored | `nested-keymap-chrome-snapshot.log` |
| Producer SIGKILL after character 5 | Producer exit -9; guardian remained alive, stopped 21 remaining characters and restored map; no delayed output | `nested-keymap-producer-crash.log` |
| Fresh EIS state after map replacement | Device generation 1 → 3 → 5; actual group 0 and locked mask 16 preserved | `nested-keymap-eis-refresh.log` |
| Cancellation while map request awaits | Zero characters and zero text key events; original map restored | `nested-keymap-map-cancel.log` |
| Second session changes map after character 5 | Remaining 21 characters stopped; newer external map preserved | `nested-keymap-external-complete.log` |
| Current cursor moves between Chrome fields | First field 5 characters, second field 21; no replay | `nested-keymap-cursor-switch.log` |
| Shift held before output | Zero text and no map change; `keys_held` | `nested-keymap-held-guard.log` |
| Caps Lock enabled | Zero text and no map change; `caps_lock` | `nested-keymap-caps-guard.log` |
| Shift pressed during output | Five characters only; waited about 0.285 seconds for the test's actual release, then restored map/state | `nested-keymap-mid-shift.log` |
| Nonzero layout group | Actual EIS group 1, with US/German/locale groups; 26/26 Chrome BMP characters; map and group preserved | `nested-keymap-nonzero-refresh.log` |
| Native Wayland VTE raw PTY | 26/26 BMP characters; Return correctly received as CR; original map restored | `nested-keymap-vte-native-bmp-final.log` |
| Private XWayland VTE raw PTY | 26/26 BMP characters; Return received as CR; original map restored | `nested-keymap-vte-xwayland-bmp-final.log` |

The held-modifier restriction comes from observed failures, not speculation.
Unprotected Shift and Ctrl tests lost their depressed state during a keymap
replacement. Caps Lock preserved its lock bit but changed the requested case,
even with the attempted ONE_LEVEL/direct-keycode variant. These failures remain
in `nested-keymap-modifier-shift.log`, `nested-keymap-modifier-control.log`,
`nested-keymap-modifier-caps.log` and `nested-keymap-direct-caps.log`. Num Lock on
and off both passed; it is not rejected. The implementation must wait for real
release of depressed/latched modifiers, reject Caps Lock using the map's actual
Lock mask, and never release or toggle the user's physical keys or locks.

EIS keymap replacement does not necessarily emit a new modifier event when the
aggregate state is unchanged. The observer therefore unbinds/rebinds only its
metadata keyboard and waits for a fresh device generation and actual modifier
snapshot. It does not start emulation or synthesize a modifier to obtain state.
Mutter's EIS map FD uses `strlen(data)` without a terminating NUL, unlike the
Wayland keymap FD. Production validation now accepts that verified format and
adds exactly one terminator in memory; internal NULs and malformed UTF-8 remain
invalid. See [Mutter 50.1 EIS client](https://raw.githubusercontent.com/GNOME/mutter/50.1/src/backends/meta-eis-client.c).

## Production worker boundary under validation

The worker owns the D-Bus session, original map and recovery state. Its parent
sends one character and waits for an acknowledgement; there is no queued text
tail. Cancel, stdin EOF and the task's absolute monotonic deadline stop future
presses, including after asynchronous map requests. Each attempted press has a
release in `finally`. Pending and confirmed maps are distinct so an ambiguous
SetKeymap timeout is not mistaken for a confirmed write.

The production implementation restores the saved original map, not a blind
Shell policy reset. Initial `CurrentKeymap.source == EXTERNAL` does not prove that
the baseline is Shell's own policy; another remote session can own that map.
Only a still-owned, recognized map may be restored. An observed external change
stops output and is preserved. Source/hash checks followed by SetKeymap are not
an atomic compare-and-swap; a narrow concurrent layout/modifier race remains.

If modifiers or unavailable observations prevent safe cleanup, a request returns
`cleanup_pending`. The guardian preserves recovery information, rejects new
transactions and may outlive its parent while waiting for a real release. Each
I/O is bounded; it does not force a key release or emit further text. The
producer-SIGKILL check does not prove recovery after the guardian itself is
SIGKILLed. Likewise, externally stopping/revoking its Mutter session can leave
that session unable to restore its map while the compositor still exists. This
case remains pending, is reported as closed, and is not treated as compositor
death or silently retried through a new authorization. The worker subscribes to
that session's `Closed` signal so parent readiness is invalidated immediately.
EOF retains cleanup responsibility; only confirmed disappearance of the unique
compositor owner proves that the old seat no longer exists.

At this point private production integration is still being tested. Isolated
prototype results above must not be presented as a completed packaged or host
production acceptance run.

## Production worker acceptance in the isolated desktop

The first complete production run subsequently **passed**. This exercised
`inkecho.platform.wayland_worker`, its production EIS observer and map builder,
rather than the prototype's direct transport. Native Chrome contenteditable
received all 26 BMP sample characters, including Chinese and the real Return key.
The saved original keymap bytes matched after completion and the compositor
remained alive until deliberate cleanup. Command:

```sh
.venv/bin/python scripts/feasibility/nested_keymap_probe.py --run-isolated --target chrome-contenteditable --single-slot-bmp --production-worker
```

The successful log is `build/nested-keymap-production-compatible-seals.log`.
Early production failures are retained: the EIS FD terminator assumption failed
before output; the portable Python runtime omitted named Linux seal constants;
and adding `F_SEAL_SEAL` caused the private Mutter compositor to fail during
SetKeymap. Mutter 50.1's [sealed-FD implementation](https://raw.githubusercontent.com/GNOME/mutter/50.1/src/core/meta-sealed-fd.c)
adds its WRITE/GROW/SHRINK seals even when they already exist. A seal preventing
further seals makes that operation fail, and the SetKeymap path does not safely
handle the resulting null description. Production now sends immutable
WRITE/GROW/SHRINK-sealed memory without F_SEAL_SEAL, allowing Mutter to repeat the
same seals. A real local memfd regression checks that this repeated sealing
succeeds while writes, growth and truncation remain forbidden. No host desktop
was used to discover or reproduce this failure.

Production cancellation after character 5 also **passed** with exit 0: five
characters received, 21 not sent, no delayed output, original map restored and
compositor still alive. Add `--cancel-after 5` to the command above; evidence is
`build/nested-keymap-production-cancel.log`. These observed checks supplement the
mocked asynchronous-boundary tests: the mocks cover cancellation and deadline
expiry while map/source/press awaits, ambiguous map requests, new held modifiers,
metadata reconnect failures, stale queued operations and provisional-authority
cancellation. They are not described as physical-device race tests.

Production requester EOF after character 5 also **passed** with exit 0. The
worker received closed stdin, restored its original map, exited normally and
left exactly the five-character prefix with no late output. Reproduce with
`--production-worker --single-slot-bmp --worker-eof-after 5` and the same owned
Chrome target. Evidence: `build/nested-keymap-production-eof.log`. The independent
producer SIGKILL experiment above remains separate; closing stdin is not labeled
as killing the production guardian.

The first real host source-worker run did **not** pass: the owned native Chrome
contenteditable received 19/26 characters despite 26 attempted press/release
pairs and continuously owned focus. The original map and modifier state were
restored exactly. Evidence is `build/native-wayland-host-source.json`. The
prototype sent at a 20 ms character interval, whereas the initial production
worker omitted that interval. Native event queue/client processing timing is a
hypothesis under investigation; private acceptance must not conceal this host
failure or be taken as support approval.

The host 20 ms pacing control also failed with 19/26 characters. Fixed-sample
codepoints showed substitutions rather than merely missing events. Read-only
host metadata identified the current source and engine as `ibus/libpinyin`;
neither its state nor configuration was changed. This disproves delay alone as
the remedy and identifies ordinary Latin keyvals being processed by the active
input engine as the next hypothesis.

A separately marked experiment maps *all* printable characters to Unicode
keysyms, including Latin-1 and ASCII, while Return remains the real Return key.
The existing/default representation is unchanged pending host validation. The
installed libxkbcommon is 1.13.1. Its [versioned conversion source](https://raw.githubusercontent.com/xkbcommon/libxkbcommon/xkbcommon-1.13.1/src/keysym-utf.c)
explicitly retains the extended ASCII representation for longstanding backwards
compatibility, despite it not being the preferred canonical encoding. Pure
library tests verify that these numeric keysyms survive serialization/reparsing,
decode to exactly the intended UTF-32 codepoint and leave every other key and
layout group unchanged.

This experiment passed the private native Chrome contenteditable sample,
26/26 with no late output and exact map restoration; evidence is
`build/nested-keymap-production-unicode-latin.log`. The experimental run used the then-existing `--unicode-latin` option; that
option was removed when this representation became the default below. It sends
keyboard events; it does not call
an input-method commit API or switch the active engine. This private pass is not
proof that every input engine will pass such events through.

## Adopted representation and limited host result

The authorized host experiment then **passed**: the native Chrome
contenteditable received all 26 characters, with 26 balanced press/release pairs,
no focus loss and the exact original map/modifier snapshot restored. It used no
added pacing delay and did not change the input source or engine. The evidence is
`build/native-wayland-host-unicode-latin.json`. This tests the current host's
libpinyin configuration with an initially empty composition; it does not establish
a universal input-engine bypass. Engines that remap by physical keycode, or an
already active preedit that consumes Return, remain limitations. The implementation
neither reads user preedit text nor changes engine state to conceal those cases.

All printable BMP characters now use direct Unicode keysyms in the product;
the temporary experiment option was removed. A runtime conversion self-check
rejects libraries that cannot decode the extended Latin representation. Return
uses its existing real key path. The default worker was re-run in private native
Chrome without experimental flags and **passed** 26/26, no late output, original
map restored and normal compositor cleanup:
`build/nested-keymap-production-unicode-default.log`. The focused map, worker and
EIS suite passed **79 tests**, and Ruff passed. This is the source freeze point;
a separate packaged acceptance still has to use that exact final implementation.

The final default representation was then rechecked for both production
interruption cases. `build/nested-keymap-production-unicode-cancel.log` and
`build/nested-keymap-production-unicode-eof.log` each exited 0: exactly five
characters arrived, 21 remained unsent, delayed readback was unchanged, the
original map matched and the compositor was still alive before cleanup. Thus
these interruption results also cover the adopted Unicode default, not only the
earlier representation.

The final default source implementation also passed the authorized host's native
Chrome **textarea**, without any experimental flag or pacing delay:
`build/native-wayland-host-default.json`. It received 26/26 characters with balanced
press/releases, maintained owned fixture focus and restored map/modifiers exactly.
Together with the earlier contenteditable experiment this establishes the stated
current-host evidence; it still does not claim arbitrary input engines, existing
preedit, non-BMP text or all application types are supported.
