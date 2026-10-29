# Independent native-keyboard alternative: no universal lossless guarantee

2026-10-29, new private Ubuntu26.04.1 GNOME50.1 Wayland virtualseat overlay,
container inkecho-native-alternative-20261029. Original stopped26 backing mounted
readonly. No IBus extension enabled, no clipboard, no host input, no system
Mutter replacement.31 source snapshot files SHA verified. Current real
WaylandKeyboardInput and its real native worker used unmodified, original timing
floors and serial protocol. Explicit keyboard preselection from first scalar;
never attempted IBus and never replayed an uncertain IBus character.

Owned Gtk3 two-field actor clears selection, process-local select-on-focusfalse,
atomic groundtruth JSON. Fields alternate at scheduled1ms intervals during race;
actual events, not timer intent, describe exposure.80 distinct Unicode scalars
U+4E00..4E4F detect exact missing values rather than allowing duplicate/loss counts
to cancel out. Synthetic actor text is the only text read.

Results:
* Stationary20 scalars: received20, exact order, no extras/duplicates/deletion,
  0.569804sec insertion call. Worker2469 natural0, actor2401 natural0.
* Fast same-window focus: insert returned80, actual received68 in2.021528sec,
  no extras/duplicates or decreasing length.12 distinct scalars missing:
  19974,19975,19981,19984,20005,20006,20007,20008,20030,20031,20037,20040.
  2913 focus events recorded across the entire observation window; not all are
  within emission. Worker2570 and actor2504 natural0. This is an artificial rapid
  focus stress case, not a claim normal typing loses15%, nor direct speed/rate
  comparison to the differently paced IBus experiment.
* Cancel after first ACK/first-sent callback: actual甲 only; errorinput_cancelled,
  no乙 in1.25sec tail, worker2641/actor2573 natural0. Already sent cannot retract.

Conclusion: switching the route to existing native simulated keyboard avoids the
Clutter commit mechanism, but DOES NOT establish a universal no-loss guarantee
under fast control changes. INPUT ACK means compositor protocol handled, not an
application receipt ACK. Do not promote this as a guaranteed fix or silently
replay the12 missing scalars. Existing native backend remains useful; this scope
adds a concrete limit to its acknowledgement rather than proving broad failure.

Practical alternatives and scope:
1. Safest immediate product rule: do not auto-select the unverified IBus V3;
   preserve explicit methods, never replay unknown attempts, and communicate
   unconfirmed delivery truthfully. Warning is observability, not recovery.
2. For actual application-level confirmation, a cooperating application API must
   perform current-control lookup and insertion in one application main-loop
   transaction and reply with a nonce/count/revision after the mutation, without
   exporting user text. Examples require a dedicated editor/browser integration,
   not a generic Shell API. Known-zero unsupported can choose another route only
   before attempts. An ACK timeout still remains unknown, never replayable.
3. Existing AT-SPI EditableText has a useful limited synchronous application
   insertion path, but prior evidence already shows an in-call focus switch can
   still target the referenced old accessible. Do not repeat that known failure
   or claim universal final-focus retargeting. A narrowly explicit CALL-START
   caret integration may be feasible subject to semantics review; universal
   automatic mode, browsers/terminals and receipt guarantees remain unverified.
4. Additional sleeps, draw hints, key release ACKs, pointer/window epoch samples
   and daemon presence cannot upgrade any of these to application receipt.

No speculative code was merged as a fix. A universal guarantee for arbitrary
uncooperative applications cannot be derived from these tested APIs. This result
identifies why a bounded explicit application integration or honest unconfirmed
status is necessary instead of asserting that keyboard fallback solves all loss.

Cleanup: profile actual readback restored enabledextensions[],idle300,locktrue;
no temporary extension installed. Original workers/actors exited0. Normal guest
poweroff + dockerwait natural0, outer49443 natural0; final-container.json records
exited0 Runningfalse OOMKilledfalse. Original backing and host unchanged. Source,
raw26.tar, analysis.json and all logs are retained. No shared worktree changes,
no version/commit/package/release operation.
