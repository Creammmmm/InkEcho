# Direct input alternatives: bounded feasibility audit

Checked on 2026-10-13 against [the project specification](PROJECT_SPEC.md),
[existing transport experiments](feasibility-report.md), and
[the Codex target investigation](codex-input-validation.md). This audit concerns
Linux input protocols, not Codex product settings. Upstream `main` and published
API documentation are evidence of their documented contracts, not proof of the
exact installed application's implementation.

**Decision:** no reviewed alternative is ready to replace the current backend
for Codex while preserving the existing scope and safety requirements. There is
a concrete newer Unicode transport worth recording, but its availability and
control-target safety are separate unresolved requirements. This is a bounded
finding about the interfaces below, not a proof that no possible implementation
or future protocol can work.

## Current local evidence

The root agent independently rechecked the current desktop process: PID 6479,
`/usr/lib/chatgpt/ChatGPT`, among 13 registered applications. Its tree still had
one application, three frames and a null reference; four `Text` interfaces,
zero `EditableText` interfaces, one active frame, and no focused/editable
control. Each frame returned only null; the null reference returned
`UnknownMethod` for all four queried metadata methods. A previous single
runtime `IsEnabled=true` experiment did not change this tree and restored both
original status values. No repeat was needed for this audit.

The root agent also read installed package metadata:

| Package | Installed version |
| --- | --- |
| libei1 / libeis1 | 1.5.0-3 |
| mutter-common | 50.1-0ubuntu2.4 |
| xdg-desktop-portal-gnome | 50.0-0ubuntu1 |

`dpkg -L libei1` identified `/usr/lib/x86_64-linux-gnu/libei.so.1.5.0`.
Filtering its defined dynamic symbols for `ei_device_(text|keyboard|start_emulating|frame)`
found `frame`, `keyboard_get_keymap`, `keyboard_key` and `start_emulating`, but
no text helpers. This establishes the installed library's missing newer helper
API, not the capabilities of every possible server or alternative client.

## Object interfaces do not supply a replacement string operation

| Reviewed interface | Defined operation | Consequence for this target |
| --- | --- | --- |
| AT-SPI Action | `do_action(object, integer_index)` invokes an advertised action; no text payload. | Does not carry arbitrary transcription text. A container exposing Action is not evidence of a writable editor. |
| AT-SPI Value | `set_current_value(object, double)` sets a scalar. | It is not a text-value setter; the separate readable text description does not change this. |
| AT-SPI Text | Text queries, selection/caret changes and scrolling. | Its method list has no string insertion operation. Selection cannot substitute for inserting text. |

Sources: GNOME's [Action signature](https://gnome.pages.gitlab.gnome.org/at-spi2-core/libatspi/method.Action.do_action.html),
[Value signature](https://gnome.pages.gitlab.gnome.org/at-spi2-core/libatspi/method.Value.set_current_value.html),
and [Text interface](https://gnome.pages.gitlab.gnome.org/at-spi2-core/libatspi/iface.Text.html).

Chromium's inspected Linux [ATK interface registration](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/ui/accessibility/platform/ax_platform_node_auralinux.cc#2435)
includes `Text`, not `EditableText`. This source fact complements the actual
metadata result; it does not replace a test of a different binary. None of the
reviewed alternative object interfaces provides a conditional string insertion
with a captured focus/cancellation token.

## Portal and compositor keyboard paths

The documented RemoteDesktop keyboard calls take a session, options, keycode or
keysym, and press/release state. The listed contract supplies neither a captured
editor object nor a condition requiring that editor to remain focused.
`ConnectToEIS` provides an EIS connection; it does not itself establish an editor
binding. The `parent_window` on session start is an application window identifier,
not a keyboard-call target argument. These distinctions come from the actual
[RemoteDesktop API](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.RemoteDesktop.html).

Mutter's published [RemoteDesktop session XML](https://github.com/GNOME/mutter/blob/main/data/dbus-interfaces/org.gnome.Mutter.RemoteDesktop.xml)
also describes keycode/keysym events, without a captured control or focus
predicate. Core Wayland's [keyboard protocol](https://wayland.freedesktop.org/docs/html/apa.html#protocol-spec-wl_keyboard)
delivers compositor events to the surface with keyboard focus; it is not a
client request to insert Unicode into another application's captured control.

Consequently, checking AT-SPI focus and then sending global emulated keys has no
atomic check-and-deliver guarantee in these reviewed contracts. Another focus
change can occur between the operations. Existing local portal evidence only
proved consent/session setup, not safe Unicode delivery; XTest transport success
was already classified as diagnostic. No portal session or input event was
started during this audit.

## libei text transport and the remaining safety question

The official [sender API](https://libinput.pages.freedesktop.org/libei/api/group__libei-sender.html)
adds `ei_device_text_utf8` and `EI_DEVICE_CAP_TEXT` in version 1.6. It is incorrect
to describe all EIS versions as supporting only keycodes. The
[ei_text protocol](https://libinput.pages.freedesktop.org/libei/interfaces/ei_text/index.html)
accepts UTF-8 text and permits the compositor to deliver it without synthesizing
keyboard activity. Negotiation and a server-provided capability are required.
No local text-capability negotiation or Unicode test has been performed. The
installed 1.5 library lacks this helper; no dependency was upgraded.

The [seat contract](https://libinput.pages.freedesktop.org/libei/interfaces/ei_seat/index.html)
groups input devices, usually sharing pointer and keyboard focus. Binding
capabilities requests device functions, not an application/control target.

The [device contract](https://libinput.pages.freedesktop.org/libei/interfaces/ei_device/index.html)
defines pause/resume as permission to emulate events. Paused devices accept no
further events until resumed, and their logical input state is reset. Requests
carry the last server serial; `start_emulating` also carries a sequence identifying
the emulation transaction. The documented transaction may span an entire remote
desktop session. Neither serial nor sequence is defined as a captured editor
identity or a focus epoch. The contract does not require a pause on every window
or intra-window control focus change. Whether this installed compositor applies
such a policy has **not been verified**; no such guarantee is assumed.

This does not rule out a compositor implementing stronger restrictions. The
[EI architecture](https://libinput.pages.freedesktop.org/libei/)
explicitly allows compositor-side access control. A suitable implementation
would still need evidence that loss of the captured control invalidates pending
text before delivery, including focus-away-and-back and cancellation. Protocol
support for UTF-8 alone is insufficient evidence of that behavior.

## What can proceed within the current scope

Keep the existing per-target backend and the truthful unsupported-target result
for this running Codex instance. New deployment code is not justified by this
audit. A future compatible target-provided editor interface, or a compositor
contract with verified control binding and stale-event rejection, could enable
further implementation without adopting clipboard input or a system input-method
role. Neither is established here. libei text is a specific research candidate,
not a supported replacement or a reason to upgrade the user's desktop.

No clipboard access, input-method registration, remote debugging, application
restart, settings mutation, user-text read or insertion occurred in this audit.
Only this report was added. Validation consisted of reviewing the cited primary
contracts and existing/local read-only evidence; no new runtime compatibility
claim or product test is made.
