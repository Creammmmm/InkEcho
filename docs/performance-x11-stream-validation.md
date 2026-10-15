# X11 literal Unicode and Qt streaming validation

Date: 2026-10-15–16. Follow-up to
[initial pacing validation](performance-keyboard-validation.md). The earlier
standalone `asyncio.run` tests are retained; they did not by themselves establish
correctness in the complete Qt recording/streaming workflow.

## Observed failure and controlled correction

The real local workflow uses the production `Recorder`, `Session`, Qwen realtime
transport, HTTPS SSE parser/output queue and X11 `KeyboardInput`. Its microphone
PCM is sent only to a loopback TLS WebSocket fixture, which returns fixed text;
a separate loopback HTTPS fixture streams three fixed polishing deltas with
350 ms gaps. The production keyboard sends them into a newly owned GTK TextView.
No cloud request, stored user credential, clipboard or input-method API is used.
This verifies transport and desktop integration, not real speech recognition.

With the original mixed representation (ordinary keysyms for ASCII/Latin-1,
Unicode keysyms for other characters), stable readback was **21/25** codepoints,
first difference at index **10**, despite 25 balanced press/release pairs and map
restoration. Both the 20 ms candidate/default and the original 40 ms waits
exhibited this difference. Retained original logs:

- `build/performance-package-source-live-mic.log`: first attempt; an insufficient
  probe failure report raised while comparing missing timing values. Not passed.
- `build/performance-package-source-live-mic-diagnosis.log` and `.json`: safe
  metadata report; actual text mismatch, with asynchronous-generator warnings.
- `build/performance-package-source-live-mic-managed20.log` and `.json`: managed
  Qt loop, actual 20 ms waits, same 21/25 mismatch; no generator warnings.
- `build/performance-package-source-live-mic-managed40.log` and `.json`: same
  managed-loop workflow at 40 ms, same 21/25 mismatch; no generator warnings.

The fixed expected sample contains neither CRLF nor combining-mark spellings.
The failed fields were already stable after output completion; no additional
per-character harness sleeps were introduced. Actual 20 ms-path intervals were
20.794–24.663 ms map-to-press, 20.363–21.538 ms press-to-release and
20.311–21.052 ms release-to-restore. The result did not establish pacing as the
cause. The client-side interpretation/preedit mechanism was not instrumented;
no claim about the system input method's internal behavior is made.

The only keyboard representation change uses **Unicode keysyms for every
printable codepoint, including ASCII and Latin-1**. Newline still uses Return.
No input-method setting, keyboard layout, focus routing, cancellation boundary or
Wayland pacing was changed. At the unchanged 40 ms control, the real workflow
then passed 25/25, with the second task cancelled after exactly one extra
character (26 total), balanced events and map restoration:
`build/performance-package-source-live-mic-unicode40.json` and `.log`.
The input adapter received exactly the fixed expected text. This controlled
comparison supports the correction for the measured client/session; it does not
prove a universal input-method bypass.

## Repeated final-default acceptance

With the corrected representation and the production **20/20/20 ms** default,
three separate processes and fresh GTK targets completed the same real
microphone → loopback WSS → local HTTPS SSE → production keyboard workflow.

`build/performance-package-source-live-mic-unicode20-round{1,2,3}.json` and `.log`
record, in every round:

- Positive microphone PCM upload before stop; no completed-file HTTP ASR upload.
- Final text 25/25, no differing span, and equal NFC/NFD/newline-normalized forms.
- First keyboard send before polishing completes; all timing stages populated.
- A second task cancelled immediately after its first press, with exact final
  text of 26 codepoints total, no tail after later SSE data, balanced release and
  restored mapping. The tail check waits beyond the fixture's remaining events.
- Zero provider diagnostics, no user credentials, no external ASR and no
  asynchronous-generator/traceback warnings.

The final helper was also tightened before commit: only expected WebSocket close
or broken-pipe/reset/SSL-EOF disconnects are permitted. Unexpected listener,
TLS-handshake, request and WebSocket-handler faults become fixed error codes and
force acceptance failure. HTTP sockets have bounded timeouts; handler and server
threads are joined. The final strict-source real microphone and synthetic runs
both passed with `server_errors: []`, `fixture_threads_closed: true` and no
traceback/unraisable warnings:
`build/performance-package-source-live-mic-unicode20-strict.{json,log}` and
`build/performance-package-source-synthetic-strict-final.{json,log}`.
A deliberate handler exception was detected as `http_request`, with its server
thread joined (`build/performance-package-fixture-negative.json`).

Observed actual intervals across the three success runs: map-to-press
20.717–25.091 ms, press-to-release 20.350–21.839 ms, release-to-restore
20.233–21.127 ms. These are measurements rather than a promise that a Qt timer
fires at precisely its requested interval. The local fixture stop-to-first-send
was 27.004, 28.275 and 36.127 ms; these values do not predict cloud ASR latency or
real recognition accuracy.

## Corrected mapping on four Qt-loop clients

`keyboard_latency_probe.py --qt-loop` uses the same `ManagedQtEventLoop` as the
application. Corrected-mapping production-default runs opened four new owned
XWayland targets, each receiving 140 mixed Unicode codepoints, including emoji
and newline. Chrome textarea/contenteditable, GTK TextView and VTE raw collector
all received exact text, with balanced event pairs and restored mappings. VTE
raw UTF-8, including Return as CR, matched exactly. The Qt-loop result is retained
at `build/performance-keyboard-unicode20-qt-four-targets.json` and `.log`.

The matched corrected-mapping 40 ms Qt-loop baseline is recorded at
`build/performance-keyboard-unicode40-qt-four-targets.json` and `.log`. All four
140-character outputs and raw VTE bytes were exact, with mapping restored and
balanced press/release pairs. Matched results in seconds per codepoint:

| Target | Corrected mapping, Qt loop, 40 ms | Final default 20 ms | Reduction |
| --- | ---: | ---: | ---: |
| Chrome textarea | 0.12407 | 0.06419 | 48.3% |
| Chrome contenteditable | 0.12441 | 0.06432 | 48.3% |
| GTK TextView | 0.12474 | 0.06396 | 48.7% |
| VTE raw collector | 0.12484 | 0.06453 | 48.3% |

The baseline's first successful send was 42.04–45.33 ms after insertion began;
the final default was 21.23–25.24 ms. These are dispatch measurements, not visible
rendering times or cloud recognition timings. Each probe includes its ownership
guard overhead. The full fixed text took 17.37–17.48 s in the baseline and
8.95–9.03 s at the selected default.

Environment: Ubuntu 26.04.1 GNOME Wayland/XWayland, Chrome 154.0.8037.97,
GTK 3.24.52, VTE 0.84.0, Python 3.13.15. These are actual owned host clients,
not a standalone Xorg or Ubuntu 24.04 desktop claim. Test-only ownership guards
check PID/start time/current active window before every press. No user document
or existing browser account is opened, and no shell receives input.

Reproduction (with coordinated exclusive host use):

```sh
QT_QPA_PLATFORM=wayland .venv/bin/python scripts/validation/keyboard_latency_probe.py \
  --qt-loop --environment host-xwayland --xdotool /path/to/xdotool \
  --repeat 5 --output /tmp/qt-keyboard-default.json
QT_QPA_PLATFORM=wayland .venv/bin/python scripts/validation/performance_package_probe.py \
  --package-root src --output /tmp/local-voice-workflow.json \
  --owned-xwayland-live-mic --xdotool /path/to/xdotool
```

The latter is explicit real local microphone capture; its default without that
flag uses synthetic capture and delivery and must not be called a desktop test.
The helper's HTTP/WSS fixtures return fixed data and do not transcribe speech.
A later packaged-runtime acceptance is recorded separately. Ubuntu 24.04,
standalone Xorg, additional client configurations and heavier load remain
unmeasured. No failed or ambiguous character was retried or replayed.

Focused keyboard/Wayland regressions: **111 passed in 2.40 s**. Five added mapping
tests check literal Unicode representation and restoration for ASCII, space,
Latin-1, Greek and emoji. Ruff lint/format checks passed for the implementation,
unit tests and both validation helpers. The native Wayland input representation
and its 50 ms settling waits were not changed by this correction.
