# R2 pending same-window focus/cancel experiment — actual loss remains

2026-10-29, fresh independent Ubuntu26.04.1/GNOME50.1 Wayland overlay,
inkecho-ibus-v3-pending-20261029. No host desktop/bus/config or original backing
writes. Existing R2 bridge authenticates actual Shell using its default verifier.
No product automatic selection or shared worktree changes.

Instrumentation: exact R2 extension logic with only a Trace D-Bus signal after
s.pending assignment and before its idle reply. Trace contains sequence,
monotonic timestamp, epoch and pending/finish stage, never text. No added sleep,
priority override, focus change or queue flush in candidate. Emitting signals can
perturb scheduling; these are instrumented real desktop observations, not a
performance benchmark or proof of uninstrumented timing frequency. GTK actor
focus events and Shell signals use the same guest GLib monotonic clock.

The self-owned native GTK window alternates between two owned Entry fields at
1ms scheduled intervals. Actual focus events, not intended timer scheduling,
define the exposure. 80 sequential fixed甲 commits, original finite8sec deadline.
No replay. Actor history contains only synthetic owned texts/lengths/events.

Valid corrected run (actual-atomic.log, analysis-atomic.json):
* 80 attempted, 74 received (A39+B35), all changed lengths monotonically increase;
  zero deletion/length-decrease events. Therefore unlike initial run this shortfall
  is not explained by GTK selecting/replacing earlier characters.
* 52 individual pending intervals contain actual actor focus events; 27 contain
  at least2, and18 end in the same actor field as the last focus before pending
  (explicit field-ABA return criterion; see exact sequence IDs in analysis).
* Replies67 attempted_focus_changed,13 attempted_stable_window.
* Sequence56: pending101944364us, own field0focus101945185us,
  finish101945201us; Shell epoch2011 stayed unchanged and reply was stable.
  App focus event preceding finish does not prove compositor had processed its
  protocol notification at that instant. It does prove observing Shell window/
  cursor hints is insufficient to confirm no same-window control change.
* No receipt ACK exists; delivery_confirmedfalse remains truthful. 6 scalar
  losses cannot safely be replayed because no per-scalar receiver ACK identifies
  which attempts reached which field. No attempt to recover them was made.

Pending cancel, two independent owned actors:
* On real pending Trace receive, local candidate.cancel was invoked.
* Each actor actually received乙, but client had attempts0/sequence0 because its
  pending RPC was cancelled before accounting a reply. uncertain=true records
  this, so zero-count must NOT be treated as zero-attempt fallback permission.
* Queued乙 cannot be withdrawn. The remaining丙 was not sent; explicit next call
  was refused closed;>=1.3sec tail unchanged and extra Trace count0. No replay.
* All completed actor original waits returned0 (exact PIDs in actual logs).

Preserved failed/invalid fixtures:
1. actual-r1.log is SSH reset during normal guest reboot; no script execution.
2. actual-r2.log/raw26.tar initial actor allowed default GtkEntry focus selectall;
   text lengths repeatedly0→1, so final length2 is NOT a78-character-loss result.
   Its timing events remain available but corrected result is used above.
3. actual-noselect.log actor2591 JSON reader saw a half-written file before input,
   then exited0. actor_atomic uses per-process GtkSettings select-on-focusfalse,
   clears selection after grabs, and writes JSON with atomic replacement. These
   are fixture corrections, not product tuning. Original failure is retained.

Repair assessment:
The safety mechanisms that stop/reject after cancellation and forbid replay are
working in these samples. The unsolved defect is capability/receipt observability:
window/cursor events and currentFocus identity cannot universally detect GTK
same-context field switches before their asynchronous messages reach Shell.
A stable-window reply must never become confirmed delivery or eligibility for
replay. R2 must stay explicit/experimental; do not enable auto for these targets.
Renaming stable-window to no-observed-change could clarify semantics, but cannot
fix the6 losses. Marking every attempt unconfirmed is already the router's final
behavior. Increasing fixed sleeps does not establish ACK, and hooking Shell
vfuncs does not provide app-receipt confirmation. No speculative product change
was applied as a claimed fix.

Cleanup: no more input after corrected run; disabled/removed temporary extension;
actual settings restored extensions[],idle300,locktrue,engine xkb:us::eng.
Original systemctl poweroff/dockerwait both natural0, outer70047 natural0,
final-container.json exited0 Runningfalse OOMKilledfalse. Raw results/settings
retained in raw26-restored.tar. Own overlay is stopped and retained, backing RO.
