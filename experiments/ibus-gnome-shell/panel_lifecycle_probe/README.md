# Isolated IBus panel lifecycle probe

Run `dbus-run-session -- bash experiments/ibus-gnome-shell/panel_lifecycle_probe/run.sh`.
The script starts a separate IBus with panel, configuration and emoji extension
disabled, using private temporary directories and a separate private bus address.
Its own test panel owns the panel name only within that isolated IBus; it does
not replace the panel, engine or settings of the user's desktop. It creates two
owned contexts and observes only paths in focus and destruction signals, never
text. It tears down its daemon and removes the temporary directory on exit.

In a 26.04 host run, this private panel received focus-in and focus-out for both
real test contexts and the virtual context. When the active test context was
destroyed, the panel received focus-out for it, focus-in for the virtual context,
and destroy-context for the old path. This complements the client-method probe,
which did not observe a client FocusOut on destruction. A GNOME extension could
observe such signals on the existing panel without installing a second panel,
but that integration and its timing have not been tested here. Signal paths do
not identify which context is virtual or establish target receipt; these events
are not evidence that automatic IBus delivery is safe.
