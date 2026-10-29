# Late IBus focus-out ordering probe

Run `bash experiments/ibus-gnome-shell/focus_late_out_probe/run.sh`. It starts a
private session bus, IBus daemon, panel and two synthetic input contexts. It
observes only panel focus notifications and the no-argument client `FocusOut`
method, not any text or keystrokes. It does not access the user's session or
change a user engine.

On the tested Ubuntu 26.04 host, A gained focus, then B gained focus before A's
late `FocusOut`. The metadata monitor saw A's method call, but the private IBus
continued to report B as current and the panel received no focus transition for
the stale A call. Assertions passed, exit status 0. The monitor used fallback
eavesdropping after the modern monitoring interface was unavailable.

This distinction matters for any event observer: invalidating the current B
solely because *any* client sent `FocusOut` would discard a valid newer focus.
The observer must associate paths and account for asynchronous ordering; even
that does not prove an editable target or confirmed delivery. This is a
synthetic private-daemon test, not desktop, real-engine or Ubuntu 24 acceptance.
