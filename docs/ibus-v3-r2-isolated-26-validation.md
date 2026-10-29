# IBus V3 R2: isolated Ubuntu 26 source candidate validation

2026-10-29. Source-only explicit candidate, NOT enabled in product auto mode,
not an AppImage or Ubuntu24 acceptance. Candidate patch remains
r2-from-candidate.patch (relative to previous /tmp candidate, not repo root).

Environment: fresh /tmp/inkecho-ibus-v3-vm-r2/state/guest.qcow2 write layer,
original stopped Ubuntu26 backing/base/seed/key mounts readonly; separate
inkecho-ibus-v3-e2e-r2-20261029 container, no host desktop/system bus/display.
Ubuntu26.04.1 GNOME Shell50.1, actual active/unlocked native Wayland seat0.
256MiB real quota probe passed after parent freed disposable resources; overlay
stayed writable, approximately81MiB allocated during tests. No downloads/install.
31 transferred source/candidate files verified by SHA256 against manifest.

Results (all actors explicitly quit and original process wait returned0):

* Real default Shell owner authentication + current OutputRouter: native actor
 2196 received 甲 then 乙 across fragments, attempts2, one first-attempt callback.
 Router completion correctly reports ibus_delivery_unknown, NOT confirmed receipt.
* XWayland simple actor2290: known-zero V3attempts0 followed by actual existing
 KeyboardInput received甲乙, terminalcode null. Two callback events occurred
 across keyboard fragments; not presented as global callback-count conformance.
* Real libpinyin ni preedit, native actor2268: before send hasPreedit=true;
 insert remained pending after200ms with attempts0 and empty committed text.
 Candidate.cancel yielded cancelled at attempts0, preedit remained active.
 Fixed space committed你, demonstrating candidate did not overwrite composition.
* Fresh bridge then sent甲, active predicate becamefalse; next乙 insert cancelled
 with attempts1. After500ms tail actual own text你甲; no乙. Actor exited0,
 engine restored xkb:us::eng. This verifies cancel before next scalar, not a
 guarantee that an already queued scalar can be withdrawn.
* Same-window own two-field actor2615: first fragment甲 reachedA; after explicit
 user-like focus change toB, second乙 reachedB, attempts2, delivery_confirmedfalse.
 `uncertain=false` is retained evidence: focus change between calls is not a
 risk during an individual pending commit. It does NOT prove pending same-window
 ABA or same-focus/same-rectangle transitions are detected.
* Explicit GTK_IM_MODULE=ibus native actor2687: active editable field with
 currentFocus=false; compositor V3 returned no_service/attempt0, owntextempty.
 No blind Clutter commit, retry or replay. This is route exclusion, not proof
 that another IBus input-context path is unavailable. Its independent delivery
 was not re-tested here; auto certification of GTK IBus remains unresolved.

Extension is real GJS ACTIVE, candidate uses secure capability consumption and
existing default UID/PID/root-owned /usr/bin/gnome-shell verifier without override.
No trust stub or mock RPC is used in the above tests. Offline30 Python tests and
Node mocked-GI focus scenarios are separate evidence. V3 still emits attempted
statuses, not target ACK; no extra wait is being called a delivery confirmation.

Limits: no actual pending commit same-window ABA test this run; no guarantee for
unchanged focus object/rectangle and no observed event. Cursor hints can yield
false uncertainty. No all-app matrix, Ubuntu24, cloud, physical microphone,
physical hotkeys, actual AppImage or automatic selection acceptance. Known
asynchronous queued commit loss remains unresolved; this validation does not
justify globally enabling V3 auto selection.

Initial setup failure: ibus engine query without full session env returned1
before settings were changed. Corrected fixture fetched user-manager environment;
normal guest reboot discovered installed candidate. Previous quota/r1 failures
were preserved and were not counted as passes. Fixture-only separate extension
for fixedni/space checks exact ownedPID/title and does not alter V3 implementation.

Cleanup: disabled and removed both temporary extensions; settings readback
extensions@as[], idle300, locktrue, engine xkb:us::eng. ps check showed no test
actor/sender left. Normal systemctl poweroff followed by original dockerwait
returned0, outer session16605 natural0. final-container.json reports exited0,
Runningfalse, OOMKilledfalse. No host settings or original backing changed.

Raw archive raw26.tar SHA256:
89bfa8fe75823e4527d9ed340f75def51fb23dd1b4400c66d38599507505ef93
Stopped overlay SHA256:
6acfa9bf03de8f8bd3ecdbdfc9c849e838fa209b8968291754b17b307ef94b7e
