# Bounded owned context integration: actual desktop evidence

2026-10-29, independent Ubuntu26 GNOME50.1 virtual seat, Docker network none/QEMU restrict=on, stopped original backing readonly. New candidate patch unchanged: SHA9c67b507f6f937000f6d47596a3ceb7b5994e2d2d1578dfbfe6fa93e65626173. No host input method/bus/desktop interaction, shared worktree changes, automatic selection, or real user content. Only fixed test characters to self-owned receiver.

## Actual outcomes

- New distinct IBusOwnedCandidateV1 Client/Bridge connected using existing default GNOME Shell UID/PID/root-owned executable authentication; unique owner :1.17.
- Native GTK3 default input method: two fragments returned1 each, sequence2, actual receiver text甲乙.
- Same native window simple widget: actual no_service sequence0, empty simple field. close_after_no_service succeeded. This proves known-zero API behavior, not actual keyboard fallback delivery.
- Returned native field, 丁 submitted then activefalse refused 戊 with cancelled; after1.3s actual甲乙丁. This is between-fragment cancellation, not a real cancellation during pending current-context query (that case remains offline tested).
- First actor2233 test failed because GTK focus reacquisition selects all, replacing甲乙 with丁. Original actual.log retained; no loss claim. Fixed only self-owned actor gtk-entry-select-on-focus=false; actor2468 verified actual甲乙丁 in actual-r2.log. Candidate source unchanged.
- Live preedit remains NOT VALIDATED. New backing does not expose libpinyin: ibus engine libpinyin returned nonzero; original run fails there, before forwarding ni or sending己. Do not mark entire suite passed. Offline preedit true/unknown rejection is not actual composition acceptance.

Both actors exited naturally0; engine restored xkb:us::eng. Temporary candidate/fixture extensions disabled and deleted. enabled-extensions[],idle300,locktrue; actors absent. Original normal guestpoweroff/dockerwait0; final-container Runningfalse/exited0/OOMfalse. All failures retained.

## Scope limits

Only self-owned GTK3 native default GNOME input path on26/Shell50 verified, not GTK ownIBus, Ubuntu24/Shell46, arbitrary applications, end-to-end router UI/package, actual keyboard fallback, physical hotkey/mic, pending live cancellation, live composition, or application receipt protocol. Same-window widget changes and enqueue-time focus race remain. No auto mode activation justified. The new bridge emits submitted attempts, not guaranteed delivery ACK. Existing V2 remains untouched.

Sources: run.py, payload/actor.py (first fixture), raw26.tar actor.py (corrected fixture), payload/source and extension, fixture, original logs. Candidate integration patch stays in /tmp/inkecho-gnome-owned-integration/experiment.patch, not applied. evidence.patch adds only review notes and runner to a unique experiment directory; git apply --check succeeds, not applied.
