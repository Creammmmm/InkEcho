# Owned native Wayland Chrome fixture — 2026-10-15

This is **read-only metadata exploration**, not input support or end-to-end
acceptance. No keys, accessibility insertion, clipboard operation or system input
method was used. The current product and version are unchanged.

## Isolated fixture

[scripts/feasibility/owned_wayland_browser_fixture.py](../scripts/feasibility/owned_wayland_browser_fixture.py)
creates a fresh Chrome process/profile with `--ozone-platform=wayland` and removes
`DISPLAY`. XDG config/cache/data directories are temporary. The fixed local HTTP
page contains either an empty textarea or an empty contenteditable element in a
simple chat-style layout. It is not DeepSeek or any external/user page, has no
account, and never submits a message. CSP limits resources and reports to this
local origin. The page reports its own value/text and DOM focus state, making it
available for a later separately authorized fixed-text transport check.

The browser disables background networking, component updates and sync; its
host-resolver rule excludes external names and explicitly allows loopback. The
fixture uses no proxy and does not change the user's proxy configuration. These
flags are scoped to the temporary process, not a claim of a network sandbox.

`WAYLAND_DEBUG=client` is captured only in the temporary fixture directory. The
probe records booleans proving observed `wl_compositor.create_surface` and
`xdg_toplevel` activity, checks that the owned process has no `DISPLAY`, and then
deletes the raw log with the profile. The host session name alone is not taken as
proof that a browser window is native Wayland.

The context manager terminates/waits for its own browser, stops the localhost
server and removes temporary state. It does not close existing Chrome instances
or modify their profiles.

## Read-only metadata probe

[scripts/feasibility/native_browser_metadata_probe.py](../scripts/feasibility/native_browser_metadata_probe.py)
connects to the accessibility bus without registering focus listeners. It queries
only application connection PIDs until it finds the owned Chrome PID, then walks
that owned connection's tree. It reads role/interface/state metadata, not names,
URLs, text or content from other applications. It calls no action/editing method.
The page's empty-value assertion concerns only the locally created fixture.

Run only with exclusive access to create native test windows:

```sh
.venv/bin/python scripts/feasibility/native_browser_metadata_probe.py \
  --output build/native-wayland-chrome-metadata.json
```

The reusable fixture can also be launched for a bounded period without sending
input:

```sh
.venv/bin/python scripts/feasibility/owned_wayland_browser_fixture.py \
  --field contenteditable --seconds 30 --output /tmp/owned-chrome-state.json
```

Any future sender must separately prove current ownership/focus immediately before
emission. `document.activeElement` alone is insufficient: a document can retain
its selected element while its window is not focused. This metadata probe does
not authorize typing into any existing user window.

## Actual result

Chrome **154.0.8037.97** was measured on the existing GNOME Wayland host. The final
probe exited 0 and cleaned both fixtures. Receipt:
`build/native-wayland-chrome-metadata.json`.

| Observation | Textarea fixture | Contenteditable fixture |
| --- | --- | --- |
| Owned browser PID in this run | 208379 | 208586 |
| DISPLAY absent in owned process | Yes | Yes |
| Native wl_surface / xdg_toplevel observed | Yes / yes | Yes / yes |
| Owned AT-SPI nodes inspected | 201 | 206 |
| Text interfaces | 201 | 206 |
| EditableText interfaces | 0 | 0 |
| Nodes with editable state | 0 | 1 |
| DOM activeElement is the fixture field | True | True |
| document.hasFocus() at the final snapshot | False | False |
| Empty own field before and after | Yes | Yes |
| Keys or insertion calls | 0 | 0 |

These are bounded snapshots of this Chrome build and fixture configuration.
The absence of EditableText here prevents claiming that interface as an available
transport; it does not prove that every native Wayland keyboard mechanism fails.
Because neither page reported document focus, this run is not a fresh-focus or
character-delivery acceptance. No actual DeepSeek webpage or user account was
inspected. The production XWayland measurements remain separate.

Two earlier attempts failed before metadata enumeration: the page did not report
readiness within 15 seconds. The first used a single-thread HTTP server; switching
to a threaded server alone did not resolve the failure. The second measured zero
page/state HTTP requests despite native surface creation. Adding the explicit
127.0.0.1 resolver exception and disabling proxy use for this temporary Chrome
then allowed both pages to load. The combined correction was tested; the two
changes were not independently isolated. Neither failed attempt sent input, and
both were cleaned. They are harness failures, not evidence of browser input
incompatibility.

Ruff lint/format checks passed for both new helpers. No product source, release
version, user setting or cloud service changed. No wider desktop matrix was run.

## Read-only activation follow-up (not executed)

A legitimate candidate is to launch the disposable Chrome child from an owned,
focused GTK launcher using its `Gdk.AppLaunchContext`, obtain the startup token,
and pass it only to that child as `XDG_ACTIVATION_TOKEN`. GTK documents this
context as the graphical launch/startup-notification path. Its current Wayland
implementation associates the request with its own focused surface and its last
implicit-grab serial. A launcher with no eligible input history may therefore
produce an ineffective token; merely creating a GTK window is not proof of
activation. Sources: [GDK launch context](https://docs.gtk.org/gdk4/class.AppLaunchContext.html)
and [GTK Wayland implementation](https://raw.githubusercontent.com/GNOME/gtk/main/gdk/wayland/gdkapplaunchcontext-wayland.c).

Current Chromium upstream reads `XDG_ACTIVATION_TOKEN` (with
`DESKTOP_STARTUP_ID` fallback), removes it from the environment after consumption,
and has an xdg-activation path that submits a token with the target surface.
This supports the proposed integration direction, but was not tested against the
installed Chrome build in this task. Sources:
[Chromium environment handling](https://chromium.googlesource.com/chromium/src/+/master/base/nix/xdg_util.cc)
and [Wayland activation](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/ui/ozone/platform/wayland/host/xdg_activation.cc).

Mutter 50.1 checks the token's seat, source surface and acceptable input serial;
when that check fails, it can request attention instead of activating the window.
Thus a successful token response alone cannot establish keyboard focus. This
matches the protocol's explicit permission for the compositor to ignore an
ineffective token. No fake serial, compositor-policy change, user-profile reuse or
forced XWayland switch is proposed. Sources:
[Mutter 50.1 activation policy](https://raw.githubusercontent.com/GNOME/mutter/50.1/src/wayland/meta-wayland-activation.c)
and [xdg-activation protocol](https://raw.githubusercontent.com/wayland-mirror/wayland-protocols/main/staging/xdg-activation/xdg-activation-v1.xml).

An alternative test arrangement is a separate GNOME headless compositor with a
private session bus, runtime directory, settings and virtual output, following
the isolation pattern in `wayland_accessibility_probe.py`. The browser would still
use native Wayland there. Natural initial focus is a hypothesis to measure, not a
guarantee; any future sender must require a fresh owned-page focus snapshot and
appropriate native ownership evidence before sending. Results from that private
compositor must remain distinct from the user's current GNOME session. No token
request, activation call, new compositor or further native window was run during
this follow-up research.

## Private-compositor adapter (prepared; acceptance separate)

`isolated_browser_fixture.py` adapts the same owned browser to
`nested_keymap_probe.py` without changing that probe. Its CLI accepts
`--target chrome-textarea|chrome-contenteditable`, `--text-output` and
`--state-output`. The text file is a JSON string. State contains `active`,
`focused`, the browser's `target_pid`, its verified direct `target_parent_pid`,
`sampled_at` and native protocol evidence. Both files are replaced atomically.

The adapter requires the private `inkecho-isolated-keymap` Wayland socket beneath
`/tmp/inkecho-isolated-keymap-*/runtime`, a session-bus environment,
and no X `DISPLAY`. The parent probe owns the wrapper and must independently
verify the reported browser parent chain. Active/focused only becomes true with
fresh page state, actual document focus and confirmed native surface evidence;
DOM activeElement alone never passes. The bounded wrapper sends no keys and cleans
its Chrome/profile/server on exit or SIGTERM. System-Python CLI loading and Ruff
checks passed; actual private-compositor transport acceptance belongs to the
separate keymap experiment, not the read-only host measurements above.

An optional `--switch-after 5` adds a second field of the same type. After the
first field's fifth Unicode codepoint, its own input handler focuses the second
field without copying or replaying either value. The text JSON concatenates the
two independently retained values; state additionally reports `first_count`,
`second_count` and `switch_done`. Focus metadata then follows the second field.
The default remains one field. Ruff and a no-browser JavaScript event check passed
for default/switch modes; actual keyboard delivery is separately measured by the
private probe. This checks output-time caret movement within one owned page, not
native/XWayland switching between windows.

## Private Chrome keycode diagnosis

The later private-compositor experiment established owned document/field focus
and native Wayland traffic. Its initial multi-slot sample received 20 of 28
codepoints; a 300 ms mapping-settle delay reproduced the same result. This is a
different run from the unfocused host metadata snapshots above. See the actual
commands, results and logs in [keymap feasibility](native-wayland-keymap-validation.md).

The official Chromium **154.0.8037.97** source was fetched read-only and matched
to the installed Chrome version. `WaylandKeyboard::DispatchKey` converts the
evdev keycode to `DomCode` and returns immediately for `NONE`, before character
lookup. Its mapping table accounts for every missing BMP character in this run.
Sources: [Wayland dispatch, lines 447–449](https://github.com/chromium/chromium/blob/154.0.8037.97/ui/ozone/platform/wayland/host/wayland_keyboard.cc#L447)
and [versioned DomCode table](https://github.com/chromium/chromium/blob/154.0.8037.97/ui/events/keycodes/dom/dom_code_data.inc).

| Fixed character | Allocated XKB / evdev keycode | Chromium DomCode | Actual initial result |
| --- | --- | --- | --- |
| é | 97 / 89 | INTL_RO | Received |
| Ω | 103 / 95 | NONE | Missing |
| 。 | 120 / 112 | NONE | Missing |
| 世 | 132 / 124 | INTL_YEN | Received |
| 二 | 149 / 141 | NONE | Missing |
| 你 | 154 / 146 | NONE | Missing |
| 好 | 168 / 160 | NONE | Missing |
| 界 | 178 / 170 | NONE | Missing |
| 第 | 183 / 175 | NONE | Missing |
| 行 | 184 / 176 | NONE | Missing |
| ！ | 197 / 189 | F19 | Received |
| ， | 202 / 194 | F24 | Received |
| 😀 | 217 / 209 | BASS_BOOST | Received U+F600, incorrect |

Thus an unused XKB slot is not automatically usable by Chromium. Reusing the
already successful, initially empty AE13 / XKB 132 slot for each BMP character
subsequently passed **26/26** in both native textarea and contenteditable, with
original map bytes restored and policy ownership returned to EXTERNAL. This
supports the dispatch diagnosis; it does not establish every keyboard layout or
arbitrary Unicode support. The 26-codepoint sample excludes emoji. Non-BMP
truncation is a separate failure after keycode dispatch, documented with the
[native feasibility findings](native-wayland-feasibility.md); selecting a usable
slot alone cannot fix it.

## Private native VTE adapter

`isolated_terminal_fixture.py` accepts the same `--text-output` / `--state-output`
contract with `--target vte-wayland`. It requires the private socket/runtime and
explicit Wayland GDK backend, verifies `GdkWaylandDisplay`, and reports its owned
PID, parent PID, fresh active/focused state and raw child readiness. The VTE child
runs only a bounded raw-PTY byte collector; it never starts a shell or interprets
the fixed sample as commands. Text and byte evidence are atomically replaced in
temporary files. Return is retained as CR according to terminal keyboard
semantics, rather than silently normalized into LF.

System-Python CLI loading and Ruff checks passed. A separate no-GUI raw-PTY check
received the complete 28-codepoint / 53-byte sample exactly, including CR. That
check validates the collector only; native VTE key delivery remains part of the
separate compositor experiment. The adapter cleans its owned child and temporary
files, without accessing existing terminals.

## Private XWayland display discovery design

No host DISPLAY may be inherited. Mutter 50.1 logs the newly reserved public X11
display in the owned compositor's log, writes its compositor PID into that
display's lock file, and creates an authorization file beneath its own runtime
directory. Source: [Mutter XWayland initialization](https://github.com/GNOME/mutter/blob/50.1/src/wayland/meta-xwayland.c).

A future adapter can parse the unique public `:N` from that particular
`shell.log`, require `/tmp/.XN-lock` to identify the probe's live compositor PID,
and require exactly one `.mutter-Xwaylandauth.*` path inside the private runtime.
Only the owned fixture receives that DISPLAY and XAUTHORITY path; cookie contents
must not be logged. Missing or conflicting evidence must stop the test. The
managed-services connection is not the public client display. A first owned
connection may start on-demand XWayland; its process ancestry and display/auth
arguments can then be checked. This is source-reviewed discovery design, not a
completed XWayland or mixed-focus acceptance.

The prepared adapter now takes the stricter existing-process route:
`isolated_terminal_fixture.py --target vte-xwayland --compositor-pid <owned-pid>`.
`private_xwayland_environment.py` requires the compositor and wrapper to have the
same owning probe parent, checks the compositor's command/private runtime/bus,
then inspects only that compositor's child list. It accepts exactly one Xwayland
child and obtains DISPLAY and the private authorization path from its actual
arguments, with the lock-file compositor PID check above. It neither inherits a
host display nor guesses a number from the log. If on-demand Xwayland has not
started, the adapter reports unavailable. It does not trigger another display.
The VTE widget verifies `GdkX11Display` and retains the same raw no-shell collector.
Static checks passed; actual private XWayland delivery and both directions of
cross-window switching remain unmeasured here.

## Actual private VTE acceptance

After explicitly selecting GDK 3, both `vte-wayland` and `vte-xwayland` passed
the 26-codepoint BMP sample using one rotating slot and policy restoration:

```sh
.venv/bin/python scripts/feasibility/nested_keymap_probe.py --run-isolated \
  --target vte-wayland --single-slot-bmp --restore-policy
.venv/bin/python scripts/feasibility/nested_keymap_probe.py --run-isolated \
  --target vte-xwayland --single-slot-bmp --restore-policy
```

Each run observed its expected GDK backend, owned active/focused state, 52 key
events, exact raw sample with Return as CR, restored original map bytes, source
EXTERNAL (0), and exit 0. Receipts are
`build/nested-keymap-vte-native-bmp-final.log` and
`build/nested-keymap-vte-xwayland-bmp-final.log`. A temporary diagnostic runner
redirected only the owned fixture's stderr to inspect startup errors; it did not
change transport behavior or the shared probe source.

Earlier attempts sent zero text events: importing GDK without a version selected
GDK 4 before GTK 3. An attempted positional-argument correction based on the
simplified GI docstring then exposed an argument error; inspection of the full GI
signature restored the required child-setup-data position. The final adapter
explicitly requires GDK 3 and uses the established VTE spawn argument shape.
These are harness startup failures, not failed terminal Unicode deliveries.

`isolated_mixed_editor_fixture.py` is prepared for the separate cross-window
test. Its coordinator verifies the private Xwayland process, then owns two GTK
children. Text JSON is `{native: string, xwayland: string}`; state contains
separate fresh PID/parent/backend/active/focused entries for each. The sender can
use private Alt+Tab and wait for the intended owned state. This helper sends no
keys, manufactures no host activation token and never copies text between editors.
Two separate VTE successes do not establish both directions of mid-output window
switching; that requires the mixed-window probe.
