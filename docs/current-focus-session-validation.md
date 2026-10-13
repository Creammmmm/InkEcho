# Current-focus task lifecycle — 2026-10-14

The user's revised requirement replaces the previous captured-target policy:
recording begins without locating a text field; focus changes during recording,
transcription, polishing and typing are permitted. Delivery acts like a keyboard
at the current focus. Explicit cancellation, task expiry and stale replies still
stop subsequent delivery. Clipboard and system input method integration are not
used.

## Implementation boundary

`TaskController` owns task IDs, deadlines and processing states, but no desktop
target or focus generation. The input callback receives only text and a predicate
for whether that exact task may continue. Cancellation, timeout, new tasks and
terminal states invalidate old callbacks.

`Session.initialize()` connects/checks the keyboard service without requesting
consent. The X11/XWayland backend becomes ready when connected and does not require portal
consent. The first explicit recording action, or the compatibility page's enable
button, checks readiness before recording starts. Concurrent preparation requests
are serialized and a ready connection is reused. A cancellation while
permission or credentials are pending prevents late recording startup. Delivery
never opens a permission dialog after recognition; an unavailable session produces
a fixed, actionable diagnostic instead. UI instructions no longer require a text
field to be selected before recording.

The AT-SPI backend and its focused-target tests remain historical/explicit-adapter
coverage; they do not establish the new keyboard semantics. Older alpha6 probes
that import the old packaged orchestration are historical, not current source
acceptance for this change.

## Unit validation

Core fake-adapter tests: **25 passed**. They include focus switches in each
processing phase, delivery moving from the first to the second window between
characters, explicit cancellation stopping remaining characters, timeout, stale
ASR/polishing replies, and late injection completion after a new task starts.
The combined core, Session, orchestration, UI and logging run completed with
**94 passed in 2.40 seconds**. It also covers no-input-field recording startup,
authorization reuse without startup prompts, cancellation during authorization
(including a late denial), and an interrupted keyboard delivery that cannot write
or finish a newer task. The input fake deliberately has no capture/target API.
A separate qasync test retains the actual threaded credential lookup boundary.
UI unit tests isolate device enumeration so they do not inspect host audio devices. These checks use simulated inputs; no desktop keyboard
events, OS permission requests, microphone, cloud calls or user configuration were
used.

Following the independent owned GTK and Chrome XWayland Unicode measurements,
`Session` now defaults to `KeyboardInput`; it no longer constructs `AccessibilityInput`.
A production-class test supplies a display driver with no focus/mapping/send API:
connection and recording still start, and closing releases the driver. Missing
display connection fails visibly before credentials or audio. Delivery errors for
unsupported targets and changed mappings produce a single specific notice, with
no replay. The UI identifies native Wayland applications, including native GNOME
Text Editor, as unsupported by this new route, while distinguishing XWayland
applications running in a Wayland desktop.

The complete source suite at this integration checkpoint completed with **323
passed, 2 skipped in 5.43 seconds** using `QT_QPA_PLATFORM=offscreen` and localhost
socket permission for isolated HTTPS fixtures. The first sandboxed run could not
bind those fixture sockets; the successful rerun did not use cloud services or
credentials. Ruff and diff whitespace checks passed. The keyboard backend remains
under separate review, and this checkpoint does not establish packaged workflow
acceptance. The unsuccessful portal keysym route is not enabled. Do not infer
native desktop or application compatibility from these unit tests.

## Delivery status and counting

The completed-state UI says that keyboard events were sent; it does not claim
that every application accepted or edited text. Statistics use the backend's
returned sent-code-point count after newline normalization. A Session regression
checks that a four-code-point provider result containing CRLF records three sent
code points, and that completion reports `按键已发送`. This does not change
historical validation reports or introduce retries for ambiguous delivery.
