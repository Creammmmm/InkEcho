# Narrow native-Wayland automatic-route candidate, not supported output

This is a NEW isolated stage0 experiment. No installation/startup occurred in this
work session. Product/shared tree is unchanged. A normal real desktop reviewer
must approve ownedreceiver/pid before --send. Never use a host user session.

## Positive design

Use capability-based routing rather than detecting a daemon: a GNOME private
bridge examines current native Wayland text focus at actual send time. First
release scope is native Wayland only. Gtk/XIM/XWayland remains keyboard. Do not
lock a target when recording. Production version would check the actual current
window, while this experiment additionally restricts exact PID and the known
owned title to ensure it cannot target unrelated windows.

`Main.inputMethod.hasPreedit()` returns a BOOLEAN without reading surrounding or
preedit content. GNOME46 upstream defines it; missing API fails closed. Busy
preedit should defer within the SAME task deadline, never reset/clear/commit the
user's composition and never fall back to keystrokes that could corrupt it.
Current probe returns busy without sending. `currentFocus` is a native capability
hint, not a delivery acknowledgement. Direct GNOME input-method commit avoids
panel round-trip/virtual-context ambiguity but remains an asynchronous Clutter
commit. This is a GNOME input-method route candidate, not proof that stock IBus
public APIs solve arbitrary cross-application output.

Policy statuses:
- not_attempted, attempts=0: can tear down bridge and route original text once to
  existing keyboard, after a fresh active/deadline check.
- busy/unsupported: no send; defer or choose keyboard before any task attempts
  only when safe. Busy composition must NOT choose keyboard.
- attempted: a commit call occurred; never claim target delivered/displayed.
- unknown: call raised, perhaps after queueing; stop, never replay.
- suffix_not_attempted: prior attempt exists. Conservative initial version stops;
  does not replay old prefix or silently hand off the suffix.
- stopped: cancelled/wrong sender/sequence; never send.

The gate checks focus on EVERY character. It does not cancel on focus changes.
A production router may re-evaluate a clean, unsent new task; no old capability
or sequence can authorize a new task. Authenticated one-use tokens and trusted
Shell owner lifecycle remain required in a product, as in existing IBus V2; this
isolated fixed-scalar experiment is not a replacement for that security layer.

## Run offline now

`node /tmp/inkecho-ibus-auto-v3/test.mjs` passes ten policy scenarios. No GI/desktop
is needed. It demonstrates replay/fallback rules, not real delivery.

## Run real desktop only in isolated GNOME guest after root review

1. Review extension.js, gate.mjs, metadata.json and SHA256SUMS, package ONLY these
   three files into a zip in a new guest-private directory, install with explicit
   gnome-extensions install (no --force), enable only this temporary UUID. Record
   preexisting enabled extensions, versions/session/env and restore afterwards.
   GNOME may require a normal guest login/reboot to see a new extension. This
   README does not authorize host setup or changing the active input engine.
2. Launch the already-reviewed actor from repository
   `experiments/ibus-gnome-shell/wayland_focus_probe/actor.py wayland` with native
   `GDK_BACKEND=wayland`. It writes only its own fixed test result, title exactly
   `InkEcho isolated wayland`. Read and bind actual actor PID/start/exe and verify
   its native protocol; review the owned window before any --send.
3. `/usr/bin/python3 client.py --owned-pid ACTUAL_PID` is read-only. To explicitly
   send ONE fixed scalar after approval: add `--send`. Same persistent DBus
   connection performs Begin/Send/Cancel; separate gdbus CLI invocations would
   have different senders and intentionally cannot send.
4. Read ONLY the actor's generated result file. Expected normal: status attempted,
   attempts1, exactly 甲. Repeat fresh extension task for each case (unload/reload
   local experiment), never re-use/replay a previous character after timeout.
5. Cases: normal native entry; native button and XWayland simple rejection;
   --cancel-before-send (stopped,0); pre-existing synthetic libpinyin composition
   (busy,0 and unchanged owned composition); asynchronous switch before/after
   queueing; owner disconnect; unknown APIs. Record received fixed codepoints and
   all original-process waits. A race may produce attempted but no character;
   that is an explicit limitation and must never trigger keyboard replay.
6. The probe DOES NOT send keyboard fallback: not_attempted merely records the
   policy eligibility. Product acceptance must separately exercise the real
   OutputRouter keyboard path, same fixed absolute deadline, cancellation after
   every await, focus at output time, known-0 fallback, no fallback after unknown,
   and dual-Ubuntu SAME artifact acceptance before an auto feature claim.

## Next minimal product patch after positive stage0

New bridge capability protocol version, distinct from V2 and checked against
verified Shell owner, advertises only tested (GNOME version, Wayland) combinations.
OutputRouter auto defers selection until first actual insert (already true),
chooses native method when capability eligible, and maps authenticated zero-call
not_attempted to the existing keyboard scope. It preserves active/deadline around
all awaits and attempts before RPC; results after a call remain unconfirmed.
Do not broaden framework_detection solely from environment or process presence.

Primary source for boolean preedit method:
https://raw.githubusercontent.com/GNOME/gnome-shell/46.0/js/misc/inputMethod.js
GNOME50 fetch failed this session; runtime feature check is intentional. No new
50 or46 desktop run was performed for this candidate.

## Actual 2026-10-29 Ubuntu26 stage0 result

A later explicitly authorized run executed this probe in the existing independent
Ubuntu26 full GNOME50.1 Wayland VM, machine-id80d223263a5e4ed1b8749d7f30116d5f.
No host input/environment was changed. Only already-installed IBus/libpinyin
packages were used; the original xkb engine was restored. New UUID installed,
needed one normal guest reboot to be recognized, then ACTIVE. The original /tmp
was cleared at reboot; that first driver attempt failed before actor/input. The
same hash tar was restored to a fresh guest temp directory.

r2: button not_attempted/0, normal native received exact甲/1. CLI `ibus engine
libpinyin` returned1 and stopped the driver. Three actors naturally exited0 and
engine restored. This failed attempt is retained. Separate diagnostic showed the
CLI returned1 while actual engine subsequently read libpinyin, so r3 verifies the
actual selected engine rather than accepting or ignoring the status blindly.

r3 used a new local directory and extension lifecycle, with all real windows
owned by this probe. Native/button/simple actor PIDs3910/3911/3912. Results:
- button: supportedtrue, ownedfalse, focusedfalse, not_attempted, attempts0.
- native: supported/owned/focusedtrue, preeditfalse, attempted1; ownedEntry甲.
- synthetic ni: hasPreedittrue; Send busy, stillattempts1, Entry甲 and owned
  preedit-nonemptytrue. No text content was read from the user's environment.
- synthetic space finishes composition: Entry甲你 and hasPreeditfalse.
- next Send immediately activates owned simple after queueing: attempted,true,
  attempts2, native stays甲你, simpleempty. This particular queued甲 was lost;
  no keyboard replay occurred. A production feature must retain this limitation.
- Cancel then Send: stopped, attempts2 unchanged. All three original actors
  naturally exited0; engine readback xkb:us::eng.

Raw logs actual26-result.log (first reboot/tmp failure), actual26-r2-result.log
and actual26-r3-result.log are retained. actual26-raw.tar SHA256
`a6bc4a8df6f57a60eb03a1467a3841eab0cc3d671bbd57b5144ea71dccbb62ec`
contains guest original scripts, fixed outputs and actor logs. Stage0 does not
prove real keyboard fallback, Ubuntu24, product IBUS-V2 wire compatibility,
streaming/deadline integration, application matrix, or an AppImage. It supports
implementing a narrowly scoped experimental route, not enabling current V2 auto
based on process detection. The prototype fixed-PID restriction deliberately
protects the experiment; it is not a proposed production recording-time lock.

Cleanup disabled and uninstalled only this UUID, restored enabledextensions[],
read back original idle300/locktrue/xkb engine, confirmed no owned actor alive,
and removed both guest private temp directories. Normal poweroff/original
container wait is recorded in poweroff26.log and final-container26.json.
