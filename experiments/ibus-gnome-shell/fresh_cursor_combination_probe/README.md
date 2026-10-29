# Fresh panel cursor + real editable focus: limited detection candidate

2026-10-29. New isolated Ubuntu26.04.1/GNOME50.1 native Wayland virtualseat,
scale1. Original stopped backing readonly, newprivate overlay/container
inkecho-ibus-metadata-20261029. No host desktop, input engine replacement,
application injection/restart integration, user text, clipboard or worktree edits.
The proposed LD_PRELOAD cooperation route was NOT implemented or run, per root.

Implemented collector attaches to EXISTING Shell IBus panel FocusIn/FocusOut/
DestroyContext and cursor-location signals, no second panel or input-bus monitor.
Each context change clears prior cursor credit. Read exports path/epoch/fresh
cursor/time/activePID and scalar popup preedit visibility only; never label text.
Independent current focused AT-SPI node provides PID/editable/text-interface and
numeric widget WINDOW extents; no GetText/accessible name/surrounding APIs.
IBus.CurrentInputContext must equal fresh observed path. Relative cursor and
window-local geometry are compared ONLY for resource scale1, not guessed for
unknown/absolute/scaled coordinate spaces. No output APIs are present.

Actual same-process Gtk3 test: one explicit IBus Entry, one per-widget simple
Entry, one button, same PID2673/initial2153/finalr3PID in log. Thus merely checking
process/module would not distinguish these fields. All contents stayed empty;
NO probe character or keyboard text was dispatched in any case.

| finalr3 actual focus | verdict | observed association |
|---|---|---|
| IBus Entry |candidate_only |fresh context+relative cursor inside editable bounds |
| simple Entry |unknown |panel changed to fake; cursor explicitly invalidated |
| button |unsupported |actual focused node not editable/text |
| IBus Entry again |candidate_only |new focus epoch and fresh relative cursor |

All3actor original waits returned0. r1 preserved: comparing stage coordinates
(518,383) to GTK's purported SCREEN(26,60) rejected real IBus. GTK returned local
coordinates even for SCREEN on this Wayland target. r2 preserved: normal
extension disable/re-enable reused GJS cached source, so addedscale missing and
policy safely returned unknown_coordinate_space. One normal guest reboot loaded
saved revision; fresh r3 actor used raw relative(35,61) versus WINDOW(26,60,329,34),
observedscale1, yielding the above. No timings or text dispatch were tuned.

Verdict is deliberately candidate_only, NOT certified automatic selection:
* Current window PID is independent metadata but does not authenticate ownership
  of the IBus context. A foreign/synthetic context can submit matching numeric
  geometry. Offline test explicitly demonstrates identical metadata passes; do
  not hide this behind a claimed guarantee. No safe existing generic PID lookup
  was added; prior GetConnectionUnixProcessID failure remains relevant.
* Before a fresh focus/cursor event, startup is unknown. The collector was
  enabled before these actors; pre-existing focused application startup not
  certified. Same-location/simple target races remain possible; these signals
  never acknowledge delivery or justify replay.
* Only Gtk3 + GNOME50 scale1 was validated. GTK4, Ubuntu24/GNOME46, scale factors,
  multiple monitors, terminals, browsers and package compatibility remain open.
* Popup visible boolean gate is implemented but no real preedit trial occurred
  this round. It cannot yet be labelled a tested generic composition guard.

9offlinepolicy tests pass: strict fresh epoch/context/PID/widget, preeditfalse,
relative+scale1 bounds and the explicit unfixable-by-geometry origin limitation.
This is meaningful technical progress distinguishing normal real/simple fields,
but does not meet the full system-wide automatic route gate. No adapter factory
or transport routing was enabled. Existing V2 explicit behavior should remain;
never replay an attempted or unknown scalar through another route.

Delivered experiment source: extension/extension-r2.js (actual final GJS),
policy_r2.py, run_r3.py, actor.py, test_policy.py; original revisions/logs retained.
experiment.patch adds an isolated experimental source directory and this report;
no product changes. Its policy file is policy.py, tests adjusted only to that
file layout; recorded desktop source originals remain hash-pinned separately.

Cleanup: temporary extension disabled/removed, settings actualreadback restored
extensions[],idle300,locktrue,engine xkb:us::eng, no owned actor remains. Normal
guestpoweroff/dockerwait0, outer90430natural0, final-container.json exited0,
Runningfalse/OOMKilledfalse. Original backing unchanged; stoppedoverlay retained.
RawarchiveSHA256:
4d10adee8cfdb6bc11412066c08682dc0fd3641c5785db92b5ee243737906475
