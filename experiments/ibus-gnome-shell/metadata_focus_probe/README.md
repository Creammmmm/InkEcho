# Isolated IBus focus metadata experiment

Run `dbus-run-session -- bash experiments/ibus-gnome-shell/metadata_focus_probe/run.sh`
on a system with IBus, `dbus-monitor`, and Python GI. The script creates a
private home, runtime directory and IBus address; it starts no panel and
removes that directory on exit. Its match rules select only the no-argument
`InputContext.FocusIn` and `FocusOut` calls. It creates its own contexts and
never sends or reads text. It does not use the user's IBus bus or desktop.

In one Ubuntu 26.04 host run of the equivalent temporary script, context A was
focused before monitoring started. No initial FocusIn was received for it.
Thereafter its FocusOut, B's FocusIn and FocusOut, and A's new FocusIn were
observed. CurrentInputContext followed A, B, fake, A, fake as expected. When A
was destroyed, CurrentInputContext became fake, but the monitor saw no FocusOut
method from A. The private IBus bus rejected the modern monitoring interface and
`dbus-monitor` reported a fallback to eavesdropping. These are lab results,
not real desktop delivery or package acceptance.

The candidate idea is to compare freshly observed FocusIn path and sender to
the current context while invalidating on FocusOut or owner loss. The experiment
demonstrates limitations: pre-existing focus has no initial observation, object
destruction needs independent invalidation, and polling/monitoring is subject
to races. Equal paths still do not acknowledge actual client receipt; a later
focus change can happen between check and commit. No automatic routing or
fallback after an attempted commit is justified by this experiment.
