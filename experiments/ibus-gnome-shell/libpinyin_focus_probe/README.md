# Isolated libpinyin focus-ID experiment

Run `bash experiments/ibus-gnome-shell/libpinyin_focus_probe/run.sh` on a host
with `ibus-engine-libpinyin` and `ibus-memconf`. The script creates a private
session bus, home and IBus socket; starts a separate in-memory IBus config
service and the installed libpinyin binary; selects libpinyin only on this
private daemon; and creates an owned synthetic input context. It listens only
for engine focus methods, with no keystrokes, surrounding text or commit text.
It does not change the user's current engine, session or real configuration.

The earlier isolated attempt timed out because the test daemon disabled its
config component: starting libpinyin directly exited with `IBus config
component is not ready`. In the corrected Ubuntu 26.04 host run, the private
memory config stayed alive, libpinyin stayed alive, and selecting it succeeded.
The monitor was started after focusing the owned context and observed no focus
event until a transition. After switching to fake and then back, the selected
engine remained `libpinyin`; the daemon's current context paths changed as
expected, but the monitor saw two ordinary `FocusIn` calls and no `FocusInId`
or `FocusOutId`. The monitor fell back from unsupported modern monitoring to
eavesdropping. The same observations and their assertions passed on a second
run; exit status was 0.

The engine printed warnings about missing Lua and user configuration paths in
the intentionally empty temporary home; this limits the result to engine startup
and focus metadata, not Chinese composition quality. No real desktop, GTK
widget insertion, application receipt, AppImage or Ubuntu 24.04 behavior was
tested. This shows that observing FocusInId cannot support all current IBus
engines even on the newer tested host; absence must not be taken as fake or
delivery failure. Never replay a submitted fragment based on this signal.
