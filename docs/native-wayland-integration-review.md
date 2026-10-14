# Native GNOME Wayland integration review — 2026-10-15

**Read-only design review; not an implemented or accepted native backend.**
Implementation depends on the phase-0 prototype passing its Unicode, mixed-client
routing, cancellation and resource-restoration checks. The current shipped input
backend remains X11/XWayland. No production source, version or native desktop was
changed during this review.

Reviewed: `platform/keyboard.py`, `app.py`, `core.py`, platform capabilities,
compatibility/settings/window UI and existing keyboard/Session tests. The user's
2026-10-14 semantics remain authoritative: start without a target, move freely
while processing, send to the output-time cursor, allow later characters to
follow a window switch, and stop unsent text on explicit cancellation or expiry.

## Minimal interface

Retain the existing asynchronous boundary:

```text
connect()                              # discovery/connection; no consent prompt
connected: bool                        # current transport connection state
authorize(parent_window="")            # explicit consent/setup, when needed
authorized: bool                       # current usable session/grant state
insert(text, can_continue) -> int       # normalized dispatched character count
aclose()                               # idempotent resource shutdown
```

`TaskController` and its `InputPort.inject(task_id, text, can_continue)` contract
need no target identity, focus generation or captured caret. Keep the existing
Session dependency-injection seam. Native transport mechanics should live behind
a separate backend or a small factory/facade, not inside Core or UI. Preserve
`KeyboardError`'s fixed code boundary and existing normalized CRLF/control-character
handling. A returned count means dispatched characters, not an acknowledgement
that every application edited its document.

Connection and authorization must be distinct for a native backend. The current
X11 implementation deliberately equates them; that shortcut cannot represent a
pending grant, denial, revocation or closed native session. Any optional backend
identity/capability property should serve accurate UI text, not add focus routing.

## One route for mixed native and XWayland recipients

Select an appropriate backend from the desktop/session capability and explicit
user setup, not from the window focused when recording or output begins. On a
GNOME Wayland session, the preferred candidate is one compositor-managed device
route whose events naturally follow the current seat focus for **both native and
XWayland clients**, if phase 0 actually proves this.

Do not choose XSendEvent versus native delivery by capturing the initial target.
Do not query a window's protocol before each character and then route through a
different transport: the focus may change between classification and emission.
That creates gaps, duplicate delivery or stale-target sends when moving between
native and XWayland windows. An error must not trigger replay through the other
backend, especially after an ambiguous or partially delivered prefix.

If phase 0 cannot demonstrate one route across both client types, that limitation
must remain explicit rather than claiming the full current-cursor requirement.
The existing X11 path can remain for X11 sessions or a clearly scoped supported
mode, without an automatic per-target fallback. Do not restore AT-SPI target
capture, focus/caret subscriptions or focus-change cancellation. Owned-PID/focus
checks in diagnostics remain test confinement only.

## Authorization, bounded cancellation and live state

`Session.authorize_input()` already serializes authorization with a lock and
checks `epoch` before/after waits. Its existing regressions prove a late grant
cannot start recording after cancellation. They do **not** yet prove that an OS
request and any provisional session have been closed.

- Startup `connect()` and UI recheck must not request consent. The explicit enable
  action or a recording request may authorize. No credential read or microphone
  capture should precede the successful authorization checks already enforced by
  Session.
- Authorization and service calls need bounded deadlines. Before recording starts,
  no Core task/deadline exists, so the Core timer cannot enforce that timeout.
- The enable button runs in `ui_tasks`; ordinary `Session.cancel()` currently
  cancels `pending`, not `ui_tasks`. Track the authorization child task explicitly
  or place it in the cancellable pending set. Cancelling a task must close its
  outstanding request/provisional resources; it should not indiscriminately
  cancel unrelated UI work or revoke an already established reusable grant.
- The backend needs its own session/request generation. Late replies after cancel,
  close or replacement must not resurrect an old session; dispose any late-created
  resources. Propagate cancellation after cleanup.
- `Session.connected` is presently a cached boolean set during initialization.
  Delegate to live backend state or update it on service/session closure. UI
  readiness and recheck must not stay true after revocation/disconnection.
- Mid-output revocation ends the task with a fixed actionable error. Reconnect or
  reauthorize only through the next explicit action; never resume/replay the old
  body automatically.

The existing `parent_window` parameter is enough for a parent handle if the
chosen protocol needs one. A native Qt window must use its legitimate exported
Wayland handle, not an X11 string fabricated from `winId()`. Where supported, an
empty parent handle is preferable to an invalid one. Obtaining that handle must
not capture or constrain the text recipient.

## Output and shutdown boundaries

Keep `can_continue()` checks after every asynchronous preparation wait and just
before each new press. Check closing/session generation as well. The predicate
already includes task identity, state and deadline, and can itself finish an
expired task. Avoid queueing the entire remainder into a transport that cannot
cancel unsent events.

Record ownership of an attempted press before awaiting its transport reply:
cancellation may arrive after the press was dispatched but before acknowledgement.
A corresponding release is cleanup and must still occur even when
`can_continue()` becomes false. Only unsent text is stoppable; never claim to
retract already dispatched input. Release ownership must refer to the original
pressed device/key, not change transport because a new window became focused.

`aclose()` should first prevent new authorization/output, then cancel/join those
operations, release any possibly held key, restore/release owned mapping state,
and close devices, sessions, subscriptions, descriptors and bus connections.
Cleanup must be bounded, idempotent and safe under repeated cancellation. Do not
restore an unrelated user's changed mapping or replace the entire seat map as a
shortcut. Phase 0 must establish the actual mapping ownership/restoration model,
including physical modifier/layout effects, rather than infer it from API success.

Keep cleanup failures separate from the primary operation outcome where possible;
do not let them turn cancellation into a replayable generic failure. Only fixed
sanitized diagnostics cross UI/log boundaries: no text, activation/authorization
tokens or raw service error bodies. `Session.close()` already catches fixed
keyboard cleanup errors; its pending-task join also depends on the backend
actually responding to cancellation rather than waiting indefinitely.

## Minimal keymap guardian proposal

This is a design for the next isolated experiment, **not a production safety
claim**. The current prototype's graceful SIGTERM cleanup does not cover parent
SIGKILL or guardian failure.

- A small child guardian owns the D-Bus connection, native input session/device,
  map observer and all mapping writes. The GUI parent never writes or restores
  the map independently. Keep the original snapshot in an in-memory sealed FD,
  along with its source/layout metadata; no keymap dump or user text belongs in
  logs. Record attempted mutation before awaiting its result.
- Use a dedicated pipe/socket whose parent endpoint is not inherited by further
  children. EOF, explicit cancellation and deadline expiry permanently stop new
  presses for that operation, discard queued text and release any possibly held
  key. Do not buffer an unbounded text stream ahead of cancellation. Keep a
  monotonic operation generation so late parent messages/replies cannot revive it.
- Track the service's unique owner, session generation, observed map source and
  canonical hash of the last map installed by this guardian. Immediately before
  restoration, obtain a fresh snapshot and require the same service/session,
  session-owned source and matching hash. If another actor changed the source or
  content, stop output and do not upload the old snapshot over that change.
- Where verified safe, release the session override through the compositor's
  policy reset so current Shell policy regains ownership. Uploading old bytes can
  reproduce text mappings while leaving ownership with the remote session. Keep
  the saved FD for bounded recovery/diagnosis, not as an unconditional overwrite.
- Cleanup releases keys first, then conditionally releases/restores mapping,
  stops the session and closes observers/FDs/bus. Bound each wait, preserve the
  original failure and report cleanup failure separately. Close is idempotent.

Source plus hash is **not** an ownership token. Another session may install the
same bytes, and a layout change may race the gap between the last observation and
SetKeymap. The current interface has no demonstrated compare-and-swap guarantee.
The guardian cannot make a check-then-write sequence atomic. Phase 0 must prove
which session owns an override, whether session Stop/disconnect only releases
that session's override, and what happens when the compositor or guardian dies.
If these guarantees cannot be established, this design remains insufficient for
modifying the user's live keyboard map.

Required isolated failure cases include parent SIGKILL/pipe EOF during mapping
and between press/release; guardian SIGKILL; compositor restart; external layout
or same-byte ownership changes before and during cleanup; hung calls and late
replies; inherited endpoint leakage; and cleanup cancellation. Observe both map
bytes/source and held/latched/locked modifiers/layout state afterward. A passed
parent-EOF test must not be described as passed guardian-crash recovery. None of
these tests should use the user's desktop to discover their failure behavior.

## UI changes after feasibility passes

The compatibility page currently hard-codes X11/XWayland-only support and no
remote-control authorization. Replace those strings with the selected backend's
measured scope and current connection/authorization state. Keep “enable” explicit
and “recheck” non-authorizing. Distinguish connection unavailable, authorization
required, denied/revoked and ready without presenting hypothetical compatibility
as supported. Preserve “keys sent” semantics and avoid promising receiver editing.

The UI must continue to allow recording without an editable target and permit
focus changes during every processing phase. No focus watcher belongs in the UI.

## Required additional tests

| Area | Required regression/acceptance |
| --- | --- |
| Authorization | Denial, timeout, cancellation, close, late success after each, simultaneous enable/toggle, reuse of a valid grant; request/provisional-session cleanup as well as no late recording |
| Live state | Service/session closure immediately invalidates readiness; recheck is non-authorizing; only explicit later action can reauthorize |
| Cancellation/expiry | Cancel, deadline and replaced task during mapping wait, press send/ack, release and inter-character wait; no remaining text, exactly matching release for a possible press |
| Shutdown | Close concurrent with authorize/insert, repeated close, second cancellation during cleanup, connection loss, cleanup errors; no hung join or reopened session |
| Unicode/counting | Chinese, accented Latin, Greek, emoji, newline/CRLF normalization, unsupported controls and normalized dispatched count; no automatic retry after partial/ambiguous delivery |
| Mixed-client routing | The same backend sends to native GTK, native owned Chrome and XWayland; both directions of window switching during output route the suffix to new focus without prefix replay |
| Desktop resources | Owned mapping/device cleanup, modifier/layout behavior, no unrelated map overwrite, no clipboard or system-input-method operation |
| UI/Session | Start with no editable target; move during recording/transcription/polishing; denied authorization precedes secrets/audio; updated state/error wording and windowless notifications |
| Existing X11 path | Retained X11 behavior works without native Wayland services; no per-target fallback or new permission requirement is accidentally introduced |

Use deterministic fake service/device tests for lifecycle races, then separately
record actual owned-window phase-0 and packaged Session results. The current
Chrome fixture report has `document.hasFocus=false`; it cannot be reused as
keyboard-focus acceptance. Its native protocol/AT-SPI metadata is in
[native browser fixture evidence](native-wayland-browser-fixture.md). No host
input or compositor experiment was performed for this review.
