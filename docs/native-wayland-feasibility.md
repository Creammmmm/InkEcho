# Native Wayland input feasibility — 2026-10-15

This is a protocol/source audit and a read-only host registry measurement, not a
successful native Unicode input test. The current-cursor requirements apply:
no recording-time target binding, clipboard, or system input-method delivery.
Historical portal Unicode failure remains recorded in
[current-cursor validation](current-cursor-input-validation.md).

## EIS keymaps and newer text events

The current `ei_keyboard` protocol exposes `key` and `release` requests. Its
keymap is a **server-to-client event**, read-only and constant during that device's
lifetime. A sender interprets the supplied map to choose Linux keycodes; there is
no client keymap-upload request in this interface.
[Official keyboard protocol](https://libinput.pages.freedesktop.org/libei/interfaces/ei_keyboard/index.html).

Requesting another device does not change that authority: `ei_seat.request_device`
asks for already-advertised and bound capabilities, and the server chooses the
device(s). New text capability must be negotiated, advertised, bound and then
present on a server-created device before it can be used.
[Seat protocol](https://libinput.pages.freedesktop.org/libei/interfaces/ei_seat/index.html),
[device interfaces](https://libinput.pages.freedesktop.org/libei/interfaces/ei_device/index.html).

Mutter **50.1** `configure_keyboard()` serializes the backend's current XKB map,
creates an EIS keymap and adds it to the server device. Its seat advertises
keyboard/pointer/absolute/button/scroll/touch capabilities, and its event handler
dispatches keyboard keycodes to a Clutter virtual input device. It does not
advertise TEXT or implement a text-event handler in this source. Creating another
EIS keyboard therefore does not provide an independent client-defined map through
this implementation.
[Versioned Mutter source](https://raw.githubusercontent.com/GNOME/mutter/50.1/src/backends/meta-eis-client.c).

Peter Hutterer's July 22 article dates `ei_text` support to libei **1.6, May 2026**.
It makes keysyms and UTF-8 requests available when a compositor provides that
interface; installing a newer client library alone does not supply compositor
support. The author explicitly leaves keysym-to-keycode/map handling to the
compositor.
[Author's explanation](https://who-t.blogspot.com/2026/07/libei-and-keysymtext-events.html).
The official UTF-8 protocol also permits forwarding through an input-method
protocol, so availability alone would not establish compliance with InkEcho's
no-input-method constraint. Its actual compositor path would need inspection.
[Official text protocol](https://libinput.pages.freedesktop.org/libei/interfaces/ei_text/index.html).

The prior host readback was libei/libeis `1.5.0-3`, Mutter `50.1-0ubuntu2.4` and
GNOME portal `50.0-0ubuntu1`. The inspected local libei library lacked
`ei_device_text*` exports. This is a local library boundary, not a claim that every
future compositor lacks the protocol. No package was upgraded, and no EIS or
portal session was opened for this audit.

## Current host registry: read-only result

```sh
timeout 10s .venv/bin/python scripts/feasibility/wayland_registry_probe.py
```

The first sandboxed invocation could not connect (`display_unavailable`). The
approved host-socket invocation then exited **0**. It created a registry object,
performed one synchronization roundtrip, collected interface names/versions and
disconnected. It bound **zero globals** and sent **zero input requests**.
This follows the core registry discovery mechanism.
[Official Wayland registry specification](https://wayland.freedesktop.org/docs/html/apa.html#protocol-spec-wl_registry).

Relevant advertised interfaces were `wl_seat` **10**, `wl_compositor` **6**,
`gtk_shell1` **7**, and `zwp_text_input_manager_v3` **1**.
`zwp_virtual_keyboard_manager_v1` was **not advertised** to this ordinary client;
there is consequently no advertised version to bind. This observation does not
prove that no privileged/filtered interface exists. The advertised text-input
interface is not used as an input-method workaround.

No surface or keyboard object was created, no focus was changed, and no user
window title, text, microphone, credentials or clipboard data was read.

## Decision and remaining candidate

Neither a client-defined EIS keyboard map nor the newer EIS text interface is a
demonstrated native Unicode route on this host. A client-only libei adapter cannot
repair the specific missing server implementation established above. A supported
future compositor text path remains a candidate, contingent on its actual
implementation, capability negotiation and native tests.

The separate isolated-compositor investigation of Mutter `SetKeymap` must prove
exact restoration, cancellation, process-failure cleanup and behavior during
concurrent layout changes before any host proposal. This report does not approve
changing the user's seat map. Current-output-time accessibility insertion may
serve some exposed editable controls, but must not be presented as native Chrome
support without evidence. Native Wayland support remains incomplete; no
production input path was changed by this audit.

## Follow-up: executable GNOME policy restoration candidate

This follow-up is **source review only; isolated behavior remains to be tested**.
It refines the earlier fallback concern by including GNOME Shell's real policy
callbacks, rather than treating Mutter's emergency US fallback as the normal
GNOME path.

`handle_set_keymap()` with no `keymap-type` calls
`meta_backend_reset_keymap_async()`. That emits `reset-keymap-description` and
`reset-keymap-layout-index`. GNOME Shell 50.1 `KeyboardManager` answers with its
retained `_ourKeymapDescription` and `_current.groupIndex`. Thus empty reset can
restore the Shell-owned description identity and its current layout policy.
Uploading a saved map FD instead creates another session-owned description.
This policy reset is not a promise to restore an arbitrary pre-existing map
installed by another external session.
[Mutter reset implementation](https://raw.githubusercontent.com/GNOME/mutter/50.1/src/backends/meta-backend.c),
[Shell policy callbacks and `_doApply()`](https://raw.githubusercontent.com/GNOME/gnome-shell/50.1/js/misc/keyboardManager.js).

`lock-keymap=false` associates the new description with the session without
blocking ordinary layout changes. `update_current_keymap()` reports `source=1`
only when the current description is the session's last submitted object;
otherwise it reports external (`0`). A cleanup helper can check this source plus
the actual map, stop on external changes, and recheck immediately before reset.
There remains a read-to-asynchronous-write race. The `resets_owner` tag permits
overriding a lock owned by that session; it is not a conditional replacement
operation. `SetKeymapLayoutIndex` checks current session ownership but only changes
the group. These limits do not preclude an isolated prototype.
[Session handlers](https://raw.githubusercontent.com/GNOME/mutter/50.1/src/backends/meta-remote-desktop-session.c),
[seat `set_keymap()` owner checks](https://raw.githubusercontent.com/GNOME/mutter/50.1/src/backends/native/meta-seat-impl.c).

On a different description, `meta_seat_impl_update_xkb_state_in_impl_unlocked()`
copies the current latched/locked modifier masks, creates a new XKB state, sets
**depressed modifiers to zero**, and applies the supplied layout index.
`update_layout_index_unlocked()` preserves all three modifier masks only when the
description identity is unchanged. `meta_keymap_native_set_keymap_in_impl()`
propagates the resulting state; it does not reconstruct physically held keys.
`meta_seat_impl_notify_key_in_impl()` still deduplicates presses through seat key
counts, so synthesizing another Shift/Ctrl press is not a demonstrated repair.
An isolated test must cover held modifiers, Caps/Num Lock and a nonzero group.
[Seat state functions](https://raw.githubusercontent.com/GNOME/mutter/50.1/src/backends/native/meta-seat-impl.c),
[keymap propagation](https://raw.githubusercontent.com/GNOME/mutter/50.1/src/backends/native/meta-keymap-native.c).

Normal Stop and D-Bus owner disappearance reach
`meta_remote_desktop_session_close()`: devices/signals are released and the
session is unexported, with no keymap reset. Finalization merely releases its
description/owner references. An independently supervised helper that owns the
session could retain a live connection after its producer exits, release its own
keys, check ownership, reset, verify and only then Stop. This proposed lifecycle
must be measured; simultaneous helper failure is a remaining boundary.
[Close/finalize](https://raw.githubusercontent.com/GNOME/mutter/50.1/src/backends/meta-remote-desktop-session.c),
[owner disappearance](https://raw.githubusercontent.com/GNOME/mutter/50.1/src/backends/meta-dbus-session-watcher.c).

## Focus-independent modifier observation candidate

Mutter 50.1 `send_keyboard_modifiers()` reads the default seat's depressed,
latched, locked and effective-group values. It sends an initial EIS snapshot on
keyboard binding and updates on `state-changed`, without consulting a surface's
focus. `on_keymap_changed()` removes and recreates the EIS keyboard: consumers
must discard the old device/map state and await the new snapshot.
[Mutter EIS callbacks](https://raw.githubusercontent.com/GNOME/mutter/50.1/src/backends/meta-eis-client.c).

The local libei 1.5 binary exports
`ei_event_keyboard_get_xkb_mods_depressed`, `_latched`, `_locked`, and
`ei_event_keyboard_get_xkb_group` (verified read-only with `nm -D`). The protocol
allows updates from other keyboards and layout controls. Its sync mechanism
orders earlier client requests and their direct effects; it does not exclude a
later physical key press.
[Keyboard modifiers protocol](https://libinput.pages.freedesktop.org/libei/interfaces/ei_keyboard/index.html#ei_keyboardmodifiers).

This is a viable candidate for awaiting released Ctrl/Shift and obtaining the
group without focus capture, using an ordinarily authorized sender connection.
It reports aggregate **logical** state, not individual physical-device identity
or held nonmodifier keys such as F4. Zero depressed modifiers after a map change
cannot prove that physically held keys were released: the map replacement itself
clears that logical state. No EIS session was opened and no modifier test was run
on the user's desktop in this review. No XWayland state was used to infer native
physical state.

## Native Chrome non-BMP character boundary

The separate owned Chrome 154.0.8037.97 probe reported U+1F600 arriving as
U+F600. Read-only review downloaded the matching official Chromium version tag:
`XkbKeyboardLayoutEngine::XkbLookup()` receives a 32-bit character from
`xkb_state_key_get_utf32()`, and `Lookup()` creates a 32-bit `DomKey`.
[Versioned XKB engine](https://raw.githubusercontent.com/chromium/chromium/154.0.8037.97/ui/events/ozone/layout/xkb/xkb_keyboard_layout_engine.cc).
`KeyEvent::GetCharacter()` then casts that scalar to `char16_t` with only a debug
equality assertion. `GetText()`/`GetUnmodifiedText()` return this single code unit,
and `MakeWebKeyboardEvent()` assigns it to `text[0]`/`unmodified_text[0]`.
[Versioned event conversion](https://raw.githubusercontent.com/chromium/chromium/154.0.8037.97/ui/events/event.cc),
[Blink event construction](https://raw.githubusercontent.com/chromium/chromium/154.0.8037.97/ui/events/blink/web_input_event.cc).

A local library-only check returned U+1F600 from `xkb_keysym_to_utf32(0x0101f600)`;
narrowing it to 16 bits produces U+F600, consistent with the owned-target result.
This identifies a matching source-level truncation path, not a debugger trace of
the installed binary. Changing an ordinary valid Unicode keysym cannot make this
single-code-unit conversion represent a non-BMP scalar. Sending isolated surrogate
keysyms is not a validated or conforming repair. Full non-BMP support requires a
corrected target path or a separately verified alternative transport; the current
native keymap experiment must not claim arbitrary Unicode support in Chrome.
No browser, desktop input, product code or library installation was changed by
this review.
