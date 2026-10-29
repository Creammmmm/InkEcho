# Native GNOME IM commit/focus ordering experiment

2026-10-29. Source-only isolated probe, not product support or an AppImage test.
No shared worktree changes. Only the existing independent Ubuntu26 VM was used;
no host desktop/user setting/input was touched. Actual GNOME50.1/Mutter50.1,
Wayland seat0; temporary extension and owned GTK native Entry + XWayland simple
Entry. Only fixed 甲 entered. No clipboard, surrounding-text reads or user input.

## Actual results

Each of five trials ran the four modes in order, no replay. Same source focus was
restored before each test; target PID/title/native protocol were checked in the
Shell callback. Actor PID2229/2230, original startticks2848/2848. Both naturally
exited0. All20 calls returned attempted; this does not mean delivery.

| mode | ordering | owned A received | owned B received |
|---|---|---:|---:|
| stable | commit then DEFAULT_IDLE callback, no switch |5/5|0|
| inline | commit then same-callback switch |0/5|0|
| idle | commit, switch only in DEFAULT_IDLE callback |5/5|0|
| contended | commit, HIGH-priority switch before DEFAULT_IDLE callback |0/5|0|

Idle mode callback2.484–4.676ms, contended6.345–19.594ms. These are callback
completion intervals, NOT time-to-display/ACK. Fixed150ms focus settle and200ms
readback were probe observation windows, not candidate production timing values.
The idle barrier improves ordering against a programmatic switch scheduled later,
but the contended counterexample disproves a general guarantee. It must never
make an ambiguous input eligible for keyboard replay.

Exact raw stdout actual26-result.log; original guest files/raw fixed results in
raw26.tar SHA256 `6df41e2b385b3908535fae12abaae3ec73d86c5a3a0e786a493fad5123391acf`.
summary.json contains numeric aggregates. setup26.log retains the initial new-UUID
enable2 failure; installation was0 and normal guest reboot enabled the extension.
No text trials were run before extension was ACTIVE. No failures were discarded.

## Why two queues matter

Mutter50.0 upstream `clutter_input_method_commit` creates an IM event and enqueues
it. The Wayland commit handler emits commit_string but schedules done on an idle
source. Its focus setter emits leave/moves resources before the later reset path
flushes done. This is a plausible source-level explanation for the existing
separate direct-focus process_event experiment still losing characters, not a
binary-instrumented proof for every package patch level.

Official source inspected:
- https://raw.githubusercontent.com/GNOME/mutter/50.0/clutter/clutter/clutter-input-method.c
- https://raw.githubusercontent.com/GNOME/mutter/50.0/src/wayland/meta-wayland-text-input.c
- https://raw.githubusercontent.com/GNOME/mutter/main/clutter/clutter/clutter-input-focus.c

## Practical options

1. App-only soft improvement: return each bridge attempt only after one main-loop
   dispatch boundary and snapshot focus generation; keep one in-flight commit,
   task absolute deadline and immediate cancel. This helps self-generated batches
   drain and bounds pending work. It does NOT pin the target or promise delivery;
   genuine higher-priority focus changes can still win, as observed. After any
   attempted/unknown character do not resend it via keyboard. An unsent subsequent
   character may be evaluated against then-current caret under a new generation.
2. Strong target/order guarantee needs a compositor-side transaction: inspect
   actual current native text-input resources, emit commit_string and matching
   done before leaving the SAME callback, then return “protocol emitted”, not
   “application displayed”. No user focus freeze and no arbitrary user-text
   acknowledgement. This requires a supported Mutter API/patch, not an ordinary
   IBus bridge toggle. It must reject preedit/bad target before invoking anything.
3. The tiny `mutter50-flush-before-leave-UNTESTED.patch` is an UPSTREAM-REVIEW
   sketch for the SECOND queue only. It flushes already emitted operations before
   moving old resources. It does not process the first queued IM event or expose
   a GNOME API; therefore it is insufficient alone. Not compiled/applied/tested,
   not a proposal to replace the user's compositor, not a compatibility claim.
   ABI-pointer tricks, stealing shared Clutter events, main-loop nested iteration,
   focus freezing, arbitrary fake keys and compositor memory offsets are excluded
   from a production approach because they introduce other ordering/user risks.

## Reproduce safely

The extension is fixed-scalar only and only accepts exact owned titles/PIDs.
Copy actor.py, extension.js and metadata.json into a NEW private directory in a
reviewed disposable GNOME guest, install only that UUID without force, preserve
settings and normal-reboot guest if the new UUID is not visible. run_guest.py
expects its fixed private guest path `/home/inkecho/ime-order-probe`, actual
user-manager graphical environment, GI, GTK3, XWayland and a working native IM.
It records natural child waits and uses a private stop file to exit GTK normally.
The provided readback only accesses files generated by these two owned widgets.
Review code and record fresh process identities before explicitly executing.
Never run this on a host/user session. It is not an automatic installer.

## Cleanup

cleanup26.json verifies temporary UUID disabled/uninstalled; original enabled
extensions[]/idle300/locktrue/xkb:us engine unchanged; no owned actors left.
Guest private experiment directory removed AFTER raw transfer. poweroff26.log
records normal system poweroff + original dockerwait0. final26-state.json:
exited/Runningfalse/ExitCode0/OOMKilledfalse. VM is available for another agent.
