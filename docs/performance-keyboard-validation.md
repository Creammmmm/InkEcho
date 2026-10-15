# Keyboard pacing and first-send timing validation

Date: 2026-10-15. This module changes only X11 pacing and first-send timing
metadata. No clipboard, input-method submission, recording-start target capture,
text replay, target pinning, or focus-change cancellation was introduced.
The previous input feasibility gates and revised current-cursor behavior remain
in `current-cursor-input-validation.md` and
`native-wayland-parent-validation.md`.

## Implementation

`KeyboardInput` now waits 20 ms after mapping, after a successful press, and after
release, rather than 40 ms at each step. No wait or cancellation check was removed.
The rejected 10 ms candidate was not selected. The selected 20 ms interval retains
a 2x margin over that failed candidate; this is a measured engineering choice,
not a universal guarantee that every X11 client has processed a mapping.

Both keyboard adapters expose `supports_first_sent_callback = True` and accept
`insert(..., on_first_sent=callback)`. The optional callback is called once per
nonempty insertion, with an absolute `time.monotonic()` timestamp only after a
successful first press. The X11 timestamp follows its checked XSendEvent call.
Callback exceptions still release owned input and restore the mapping; unsent
characters are not replayed.

The Wayland worker records its timestamp immediately after its successful press
request returns and before release/settling. The key ACK carries this timestamp;
the parent accepts only a finite number between that request's start and ACK
receipt, after checking task cancellation/deadline/process identity. It rejects
missing, malformed, past, future and nonfinite timestamps. This timestamp marks
successful transport submission, not the physical compositor event or visible
client rendering. The parent does not label ACK receipt as the press time.

Wayland's 50 ms map settling and 50 ms release settling are unchanged. Its
existing BMP-only restriction is unchanged; the X11 emoji result below does not
establish native Wayland emoji support. Streaming calls may contain multiple
insertions; the application timing collector must retain only the task's first
successful send.

## Test environments and safety boundary

Actual host: Ubuntu **26.04.1**, GNOME Wayland with real XWayland applications,
Python 3.13.15, Google Chrome **154.0.8037.97**, GTK **3.24.52**, VTE **0.84.0**.
The real host runs used newly created Chrome profiles serving fixed local pages,
new GTK TextView windows, and a new VTE with a raw-byte collector instead of a
shell. Existing Chrome accounts/pages and user documents were not used.

Every X11 test press checked the owned process PID and process start time, active
window PID and exact owned window, and current focused descendant. Chrome also
required fresh owned-page focus metadata. Release remained unconditional.
The product still follows the current cursor; this stricter focus policy exists
only in the test harness. Independent private-Xvfb runs used their own X server;
the final harness verifies that the selected Unix X socket belongs to its
launcher's private Xvfb process before publishing that private root's active-window
property. It never does this root-property setup on the host. Raw PTY child
cleanup uses a pidfd. No test sent a command to a shell.

**Ubuntu 24.04 and a standalone Xorg desktop were not available.** These results
are not claimed as Ubuntu 24.04 acceptance, standalone Xorg compatibility, or a
cloud/recognition-to-visible-character speed measurement.

## Pacing experiments and observed results

Fixed sample: 28 Unicode codepoints, including Chinese, ASCII, accented Latin,
Greek, emoji, punctuation and a newline. Candidate/final runs repeated it five
times, 140 codepoints per new host target. Each round opened fresh windows.
Results below compare seconds per codepoint and include the validation guards.

| Host target | Original 40/40/40 ms | Final 20/20/20 ms | Measured output-time reduction |
| --- | ---: | ---: | ---: |
| Chrome textarea | 0.12764 | 0.06717 | 47.4% |
| Chrome contenteditable | 0.12849 | 0.06593 | 48.7% |
| GTK TextView | 0.12960 | 0.06695 | 48.3% |
| VTE raw collector | 0.12699 | 0.06696 | 47.3% |

The final default run used **no pacing override**. All four actual client outputs
were exact, all 140 press/release pairs balanced, and the mapping restored after
each target. VTE's raw UTF-8 bytes matched the expected bytes exactly, including
Return as CR. Baseline first-successful-send times were 42.85–48.95 ms; final
first-send times were 22.65–27.16 ms. These are transport-send timestamps, not
visible-character timestamps. The overall speech/ASR/polishing pipeline was not
measured by this keyboard probe.

Evidence retained in `build/`:

- `performance-keyboard-private-baseline.json`: private Xvfb, all four actual
  clients, original 40 ms intervals, 28 codepoints each, all exact.
- `performance-keyboard-private-candidate10.json`: private Xvfb, all four clients,
  10 ms intervals, 84 codepoints each, all exact (33.94–34.42 ms/codepoint).
- `performance-keyboard-host-baseline.json`: actual host baseline, all exact.
- `performance-keyboard-host-candidate10-round1.json`: host 10 ms, four targets
  with 140 codepoints each, all exact.
- `performance-keyboard-host-candidate10-round2.json`: **rejected** host 10 ms
  candidate. The new Chrome textarea received **139/140** codepoints even though
  the event pairs balanced and mapping restored. The other three targets were
  exact. That run did not retain the missing character's position; no cause or
  first-character diagnosis is inferred. A private-server pass or server-accepted
  key events alone therefore did not justify choosing this interval.
- `performance-keyboard-host-candidate20-round1.json` and `round2.json`: both
  fresh-window 20 ms rounds passed all four clients, 140 codepoints each, with
  exact text/raw bytes, balanced events and restored mappings.
- `performance-keyboard-host-default20-final.json`: final production default,
  no override, the table above. Across the two candidate rounds and final round,
  **1,680** codepoints were checked exactly on actual host targets.
- `performance-keyboard-default20-controls.log`: actual production-default
  legacy owned-GTK control probe passed mixed Unicode, two-window current-focus
  switching, cancellation with exactly one press/release and no tail, a destroyed
  window's sanitized failure, and mapping restoration.
- `performance-keyboard-private-guard-final.json`: after strengthening the
  Xvfb socket-ownership guard and pidfd cleanup, private GTK and VTE were retested
  at the final default with exact 28-codepoint output, balanced events and restore.

## Independent Wayland callback acceptance

`performance-keyboard-wayland-callback.json` records a real host contenteditable
transaction through the existing reviewed native-Wayland/XWayland guard. Native
Chrome received the first five characters; new owned XWayland Chrome received
five; native Chrome received the remaining sixteen. All **26** characters were
exact, both focus transitions passed, 26 presses/releases balanced, zero guard
rejections occurred, and the map, group and modifier snapshot restored exactly.
The first-send callback ran **once**. Its receipt was **52.07 ms after** the
worker's successful-press timestamp, consistent with retained release settling.
No additional map/key waits were applied by the harness.

## Reproduction

With exclusive, coordinated host desktop use and an available `xdotool`:

```sh
.venv/bin/python scripts/validation/keyboard_latency_probe.py \
  --environment host-xwayland --xdotool /path/to/xdotool \
  --repeat 5 --output /tmp/keyboard-default.json
.venv/bin/python scripts/validation/keyboard_latency_probe.py \
  --environment host-xwayland --xdotool /path/to/xdotool \
  --pacing 0.04 0.04 0.04 --output /tmp/keyboard-baseline.json
.venv/bin/python scripts/validation/keyboard_latency_probe.py \
  --wayland-callback --output /tmp/wayland-first-send.json
PYTHONPATH=src:scripts/feasibility .venv/bin/python \
  scripts/feasibility/keyboard_backend_probe.py --xdotool /path/to/xdotool
.venv/bin/pytest -q tests/test_keyboard.py tests/test_wayland_keyboard.py tests/test_wayland_worker.py --tb=short
```

For a private run, the same launcher must spawn
`build/listening-test-tools/root/usr/bin/Xvfb -displayfd <inherited-fd>`, read its
allocated display number, then launch this probe with that `DISPLAY`,
`INKECHO_PRIVATE_XVFB=<server-pid>`, no `WAYLAND_DISPLAY`, and
`--environment private-xvfb`. Stop only that owned server afterwards. The local
xdotool and Xvfb tools require the corresponding extracted
`build/listening-test-tools/root/usr/lib/x86_64-linux-gnu` library path; do not
install them globally or replace the user's desktop server.

Focused result: **106 passed in 2.41 s**, plus the actual client runs above.
Ruff lint and formatting passed for all seven implementation/test/probe files.
Unit checks cover callback order/exactly-once behavior, callback failure cleanup,
no callback after failed press, worker timestamp validation (including delayed
ACK), successful press before release, unchanged Wayland release settling, and
cancellation/deadline/process-generation boundaries. Passing units alone were
not used to approve the pacing default.

Remaining: Ubuntu 24.04 and standalone Xorg acceptance, other applications and
heavy-load conditions, packaged-runtime verification of this change, and full
speech pipeline latency. No new application-wide speed guarantee is made.
