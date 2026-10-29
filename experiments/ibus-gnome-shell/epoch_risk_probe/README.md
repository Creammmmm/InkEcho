# Focus-epoch risk detection candidate

Scope: detect a RISK of ambiguous queued IM delivery and stop further input;
never classify a character as definitely lost or safe to replay. No shared
worktree modification, host setting, compositor replacement or clipboard.

## Positive proposal

One in-flight bridge commit per output scope. Immediately before submitting at
the current caret, snapshot a monotonically increasing display-focus epoch.
Subscribe only during OUTPUT to notify::focus-window. Any change before the
post-dispatch completion boundary, including A→B→A, yields
unknown_focus_changed. Cancellation after invocation yields unknown_cancelled.
Both permanently stop that scope; already attempted input is never replayed.
No change yields attempted_unconfirmed, NOT delivered/displayed/confirmed.
Cancellation before calling remains known not_attempted, zero transport calls.

This does not capture recording-time focus, prevent switching or require an
unchanged window to continue a NEW unsent scope. A focus change is not task
expiry: only the in-flight character's result becomes uncertain. A future
product may let user explicitly start a new task; it must not silently retry
this task's prefix. Check normal cancellation/absolute deadline at every await.

## Validation actually performed this turn

`node test.mjs`: eight pure policy scenarios passed, including ABA, stale token
isolation, cancellation before/after invoke, overlapping attempt and conservative
false-positive when the actual character WAS received despite a focus change.

`dbus-run-session -- .venv/bin/python private_bus.py`: a REAL independent private
D-Bus daemon and two clients validated normal, ABA metadata change, cancellation
while request pending, and overlap rejection. Four cases passed, exactly ONE
attempt each, zero replay. No desktop transport or GUI was present; a bounded
50ms model delay allows testing pending-control RPCs and is NOT a production
wait, display ACK or Mutter delivery benchmark. Log private-bus-result.log.

Actual prior desktop ordering evidence exists separately at
/tmp/inkecho-ime-order-probe/actual26-result.log: stable5/5, inline-switch0/5,
idle-switch5/5, higher-priority-switch0/5. It motivates this detector but does
NOT validate that GNOME notifications cover all new epochs in this prototype.

## Desktop fixture (later run; see actual results below)

extension.js + policy.mjs + metadata.json define a fixed-scalar owned-window
probe only. Its Test modes normal/switch/aba/cancel send ONE甲 and return risk,
observed display epoch changes and attempts. Runtime window/PID/title/native
checks confine testing, not a proposed recording-time target lock. Cancel RPC
checks actual requesting unique sender. Install only in reviewed disposable
GNOME desktop, preserve enabled extensions/settings, use new private directory,
record exact hashes, natural process waits and fixed owned receiver results.

The first model-only turn did not start a VM because overlays were reserved.
A later explicit authorization released the independent original26 VM, and the
actual tests below were then run. Existing actor.py
is provided for the same owned fixed titles, not an auto-launcher. Never use
this extension on a real user desktop or claim auto IBus support from model tests.

## Limitations and integration requirements

- Display focus-window epoch does NOT cover switching controls within one
  window; currentFocus may be the same compositor object across text fields.
  Cursor-rectangle changes can conservatively over-detect, not prove identity.
- Epoch changes do not prove loss; the app may have received a character first.
  The safe action is unknown + no replay, not a fallback insertion.
- DEFAULT_IDLE completion is a scheduling boundary only. Higher-priority focus
  changes can precede it; no assumption of FIFO completion/paint acknowledgement.
- This can make errors visible and avoid continuing with a hidden gap; it does
  not eliminate the gap. A strict no-loss guarantee still needs a supported
  compositor/receiver transaction or a separately scoped application interface.
- A product scope must retain closed state after unknown, authenticate protocol
  version/unique Shell owner/one-use capability, bound waits, and clear watchers
  on close even if a reply is missing. The standalone fixture is not product auth.

All generated evidence remains under /tmp/inkecho-ime-epoch. experiment.patch
adds only this isolated prototype, not a product auto-enable patch.


## Actual isolated Ubuntu26 GNOME50.1 Wayland, 2026-10-29

Machine-id80d223263a5e4ed1b8749d7f30116d5f. A temporary local extension was installed
in the independent VM; first enable returned2 (newUUID not discovered). Normal
guest reboot then enable succeeded/ACTIVE. No host user desktop was accessed.
Source currently stored in extension.js matches the tested fixture, including
cancel_rpc with a controlled50ms delayed reply ONLY to allow a real pending
Cancel RPC to be tested. It is not a production delay/ACK/performance value.

First r1 actor grab_focus selected old content; repeated甲 could replace甲 and
produce lengthdelta0. Its raw results remain, and are NOT used to claim normal
loss. r2 cleared own selection and positioned caret at end before each case,
recording both native fields' full fixed text and total lengthdelta. Each case
ran twice in fresh owned windows PID3357/3358, startticks8959/8959:

| mode | returned status | epoch changes | native received per case |
|---|---|---:|---:|
| normal | attempted_unconfirmed |0|1,1|
| switch to owned XWayland window | unknown_focus_changed |1,1|0,0|
| requested A→B→A in same callback | unknown_focus_changed |2,2|0,0|
| real pending Cancel RPC | unknown_cancelled (Canceltrue) |0|1,1|
| within-window own A insert handler focuses B | attempted_unconfirmed |0|1,1 intoA|

ABA calls ActivateB then ActivateA, and epochs observed both changes even though
an endpoint-only comparison would miss changes. The fixture did NOT independently
return/assert the final MetaWindow==source boolean; final widget focus snapshots
were bothfalse in these ABA samples. Do not turn this into a stronger assertion
that the final native text context was restored; it is specifically evidence of
multiple changes detected, not a complete final-focus identity test. Root stopped
further experiments after existing samples were sufficient; no extra run occurred.

Cancellation AFTER queueing did not retract the actual character: both cancelled
cases received甲 already. This is why unknown_cancelled cannot trigger fallback.
Within-window field changes were real (final Afalse/Btrue) but epoch stayed0;
therefore this detector has an actual proven blind spot. It is useful conservative
risk reporting, not a universal lost-character detector or an auto-IBus guarantee.
The two synthetic actor original processes naturally exited0, probe0. Previous r1
actors2217/2218 also naturally exited0. No character was replayed because of an
unknown status. Each fixture Test uses a fresh isolated policy case, not a tested
production multi-fragment task implementation; persistent closed-on-unknown policy
was verified offline but full product integration remains necessary.

Raw stdout actual26-result.log and actual26-r2-result.log. Guest original scripts,
source, settings and fixed outputs in raw26.tar, SHA256
`ad1622db35e1cd3814c62ea4197e23612232bfd14b50fa971b5083f7f315cc4b`.
The r2 actor differs only to correct own selection/caret setup; original r1 files
are retained at raw26/actor.py and r2 at raw26/r2/actor.py.

Cleanup: temporary UUID disabled/uninstalled; settings readback exactly original
extensions[]/idle300/locktrue/xkb:us. No owned actors live; private guest experiment
directory removed after raw transfer. cleanup26.json proves these values. Normal
system poweroff plus original dockerwait and final container state recorded in
poweroff26.log/final26-state.json. No forced termination or system Mutter change.
