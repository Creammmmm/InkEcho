# Normal application reachability: distinguish V2 completion from V3 target limits

2026-10-29, isolated Ubuntu26.04.1 native Wayland GNOME50.1 virtualseat;
GNOME Text Editor50.1, GTK4.22.4, GtkSourceView5.18.0. New private overlay
inkecho-normal-apps-vm, original stopped26 backing read-only.35 source/candidate/
fixture pins verified before install. Real default Shell UID/PID/executable auth.
No host GUI/config/credential changes or shared worktree edits.

This answers ordinary configured application usability, NOT the previous1ms
focus stress case. Actual GNOME Text Editor --standalone processes opened only
new private empty inkecho-qa-*.txt files. A separate fixture matched exactPID+
ownedfilename window, activated it, and used only fixedCtrlS/CtrlQ keys to save/
quit. Saved OWN synthetic files provide groundtruth, not application ACK in the
product. No arbitrary user text was read.

V3 submitted甲; V2 submitted a DIFFERENT乙 as a separate explicitly selected
output task. An uncertain/known-zero甲 was never replayed as part of乙. No implicit
V3→V2 or keyboard auto-selection has been enabled.

Actual results:

| Text Editor context | active/native/Clutter currentFocus | V3 | separate explicit V2 | actual saved own file |
|---|---|---|---|---|
| normal default Wayland | true/true/true |甲, attempts1 |乙, routeribus_delivery_unknown |甲乙 + newline |
| GTK_IM_MODULE=ibus BEFORE module installed |true/true/false |no_service, attempts0 |attempt reported, same warning |empty |
| gtk-im-context-simple negative control |true/true/false |no_service, attempts0 |attempt reported, same warning |empty |
| GTK_IM_MODULE=ibus AFTER proper GTK4 IBus module installed |true/true/false |no_service, attempts0 |乙, routeribus_delivery_unknown |乙 + newline |

All4 actual editor processes original wait returned0 (PIDs2318/2364/2390/2938).
No unstable-focus assumption is needed to explain these ordinary results.

Important dependency distinction: GTK3 im-ibus was already installed; previous
R2 GTK3 actor had no missing-module warning. GTK4 ibus-gtk4 was initially missing,
and gtk_ibus-editor.log explicitly says no matching IM module. That first GTK4
negative must NOT be described as correctly configured IBus. Guest-only APT
simulation/install added exactly ibus-gtk4 1.5.34~rc2-1 (18942B, no upgrades,
no deletions, no service restart), official cacheSHA256
88208f87c4b68592f652732c55309501c7a51b7962c0641c2a138e8e4f5b6daf.
A NEW process/file then proved genuine independently routed GTK IBus works viaV2
while Main.inputMethod.currentFocus remainsfalse. This was a controlled test
prerequisite, not an instruction to auto-install software on users' systems.

Practical product findings:
1. Existing V2 is reachable in both tested normal default and correctly configured
   GTK4 IBus contexts. Success currently appears as failure because router raises
   ibus_delivery_unknown on clean completion. Root's separate agent owns the
   outcome-classification repair: a non-fatal submitted-unconfirmed notice after
   clean completion, while actual RPC unknown/cancellation/errors remain terminal.
   Do NOT swallow all exceptions with thatcode: genuine transport errors share it.
2. V3 is a Clutter-native bridge, not a universal IBus replacement. Its false
   currentFocus correctly excludes its own API but cannot exclude the independent
   GTK IBus context. Keep an explicit V2 option; do not require unavailable24
   native keyboard fallback to make a correctly configured IBus application work.
3. This does NOT certify automatic V2 selection: the simple negative returns the
   same attempted diagnostic but receives nothing. A daemon, module setting or
   panel call is not target receipt. Never relax theV3 guard to blindCluttercommit,
   and never replay uncertain input throughV2/keyboard.
4. Packaging/install guidance can explain required target GTK IBus module and
   explicit method selection, but InkEcho cannot inject that module into other
   running applications merely by bundling it. Keep API/interface scopes clear.

Delivered fixture code: run.py (three initial contexts), run_module_ready.py
(correct installed-module context), fixture/extension.js (PID/filename guarded
fixedsavequit), manifest.json, raw archives and immutable record tests.
6test_results.py assertions pass: actual default+IBus positive saved files,
missing-module/simple negative controls, no replay, profile/process cleanup.
These tests replay preserved desktop evidence, not fresh desktop execution.
No new product implementation overlaps the other agent's completion patch.

Limitations: Ubuntu26 source-only, actual Text Editor only; no actual24 package,
terminal/browser matrix, physicalmic/hotkeys or cloud. V2 still lacks target ACK
and universal preedit/focus proof. This report does not override earlier pending
same-window losses or authorize automatic mode.

Cleanup: disabled/removed all3temporary extensions, restored actualsettings
extensions[],idle300,locktrue,engine xkb:us::eng; noowned editor remains.
Guest-only newibus-gtk4 package removal completed (APT log). The following
post-removal dpkg-query failed with empty format due fixture quoting; retain
that failure and do not claim a successful separate dpkg status readback.
Original guest poweroff/dockerwait natural0 (outer1427 natural0), container
exited0/Runningfalse/OOMKilledfalse in final-container.json. No host/backing changes.

Final raw26-final.tar SHA256:
41aba7cc808344daf21e2a52d8413f55c9d8257d59ef5256a7446a73a1a28b5d
