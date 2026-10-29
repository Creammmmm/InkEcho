# IBus portal ownership research — STOPPED, isolation failure retained

2026-10-29. No VM, no GUI/window or text/keystroke submission. Approximately
0.5MiB evidence/source only. Shared worktree unmodified. Do not run the preserved
portal_probe_r1.py/portal_probe.py scripts again: they have a known activation
environment isolation defect. They are evidence, not approved reproducers.

Official upstream portal.c shows a per-context sessionbus unique owner and
an authorization check rejecting a different sender. Standard sessionbus can
query a client's real Unix PID, unlike previously tested custom private IBus.
Portal-local object paths and underlying private IBus paths are allocated
independently; no public mapping/ownership property was established. Source:
https://raw.githubusercontent.com/ibus/ibus/main/portal/portal.c
https://raw.githubusercontent.com/ibus/ibus/main/src/ibusbus.c
Source snapshots retained with hashes in pins.json; main is source evidence,
not assumed to equal installed distribution binary.

Actual retained attempts:
* r1: synthetic portal context lacked FOCUS capability; FocusIn was rejected.
  Child quit; fixture cleanup then hit BrokenPipe. Private dbus-run-session
  ended. Known daemon661701 was independently confirmed absent afterward.
* r2: FOCUS capability supplied. Child portal clientPID661786, session unique
  :1.3, standardbus GetConnectionUnixProcessID returned661786 (positive identity
  observation). Another connection's FocusIn on its portal object was denied.
  Local portal path InputContext_1; the newly created private daemon continued
  reporting its fake InputContext_1 before/after portalFocusIn/Out. The intended
  cross-bus mapping assertion therefore failed; no pass claim.
* Child cleanup Destroy returned UnknownMethod and child exited1. Own private
  daemon returned-15 after explicit SIGTERM; private session bus exited.

CRITICAL ISOLATION LIMIT: the launcher started dbus-run-session BEFORE Python
changed HOME/XDG_RUNTIME_DIR/IBUS_ADDRESS. D-Bus service activation can retain the
outer startup environment rather than those later process-local changes. The
autoactivated ibus-portal may therefore have connected the DEFAULT HOST IBUS
instead of the intended private daemon. No proof excludes that possibility;
private current remaining fake is consistent with it. Do NOT claim this round
never touched the host input context. Synthetic FocusIn/Out may have affected
that default context. No CommitText, key event, engine switch, clipboard or
surrounding-text access was performed. Host input state/restoration was not
verified; no further host queries or corrective focus calls were attempted.

Root instructed stop/no retry, followed immediately. Known own PID checks
661699/661701/661765/661767/661786 all absent. Stale owned socket
private-lab-r2/ibus.sock removed only after recorded daemon absence. Its log,
source, errors, result JSON and private-directory metadata remain. Portal PID
was not recorded, so cannot claim an individually waited portal exit; its
private session bus lifetime ended, but only the listed PID absence is directly
verified. No unrelated process was terminated or configuration changed.

This does not provide a deployable automatic detector. A future proposal would
need complete private activation environment established BEFORE private D-Bus
startup, independent endpoint verification, and an authenticated mapping from
portal context to active IBus path, not temporal/geometry guesswork. Such work
requires separate review. No additional tests or retries were run after stop.
