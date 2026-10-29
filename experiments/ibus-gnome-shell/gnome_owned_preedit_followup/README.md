# Owned bridge: live preedit follow-up remains blocked

2026-10-29. New independent network-none/restrict-on26 overlay on previously stopped r2 guest overlay mounted readonly, original backing also readonly. Existing libpinyin success evidence was not mistaken for this new candidate's acceptance. No host desktop/IBus access, no worktree changes, no auto mode.

## Actual observations

Candidate code unchanged from integration patch9c67b507f6f937000f6d47596a3ceb7b5994e2d2d1578dfbfe6fa93e65626173.
- r1 fixture missing deployment directory, r2 present but disabled: both NameHasNoOwner before any candidate dispatch; actors2215/2214 natural0. Failures retained.
- r3/r4/r5 candidate authenticated, actual native甲乙 across2fragments, simple no_service sequence0, 丁 then cancellation refused戊 and1.3s tail actual甲乙丁. Actors2474/2730/2193 all natural0.
- Live preedit FAILED TO START: ibus engine libpinyin exits1 every time before forwarding ni. Never reached real preedit assertion, did not send己 or commit你. Therefore no new live preedit pass.
- Readonly diagnostic proves packages ARE installed: ibus-libpinyin1.16.5-2, libpinyin15 2.10.3-1, componentXML and cached debs exist; old r2 preedit.json actual你甲 exists. It is not correct to infer missing packages simply from CLI engine switch failure.
- Initial GNOME sources only xkb/us. Temporary adding ibus/libpinyin plus a normal reboot did not fix engine-switch failure. No package downloads, replacements, daemon overrides, or host engine changes attempted. engine-after-source.log's separate ad-hoc SSH CLI had insufficient full desktop environment (Can't connect), so it is NOT a daemon absence diagnosis. The actual runner uses full user-manager display/session environment and successfully reads xkb:us::eng in finally; precise engine-registration cause remains unresolved.

## Cleanup

Restored sources exactly [('xkb','us')], engine xkb:us::eng, extensions[], idle300,locktrue. Temporary two extensions removed; all own actor PIDs absent. Normal guestpoweroff/dockerwait0; final-container Runningfalse/exited0/OOMfalse. raw26.tar contains original fixture results, modified self-owned actor and restored.json. No additional samples after final blocked r5.

## Remaining work

Real preedit and pending-cancellation are still unverified for owned integration; offline gate checks cannot replace them. Need diagnose GNOME/IBus registration in a controlled fixture before any future sending. Native default GTK3 support scope does not establish GTK-owned IBus, Shell46/Ubuntu24, receipt ACK, generic app support or safe auto activation. Retain prior identity and normal input positives without widening their claims.
