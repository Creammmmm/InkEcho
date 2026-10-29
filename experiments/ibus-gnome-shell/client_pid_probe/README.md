# IBus client process lookup probe

Candidate: match the sender of a real `FocusIn` method to the focused window's
process on X11, so a stale unrelated IBus context would not be treated as the
active target. This assumes the private IBus bus exposes the sender's PID and
does not establish receipt; different applications and desktop bridges can also
use multiple processes or share an intermediary. This candidate must fail closed
when it cannot match.

Run `bash experiments/ibus-gnome-shell/client_pid_probe/run.sh`. The script starts
its own session bus and IBus daemon, with a temporary home and private IBus
socket. It queries only its own unique name, no user application or text.
The 26.04 host's IBus returns the correct value from `GetNameOwner` (positive
control) but returns `org.freedesktop.DBus.Error.UnknownMethod` for
`GetConnectionUnixProcessID`. Exit status is zero. It cleans up its daemon and
temporary directory. The exact process lookup query is not proof of behavior on
24.04. The [upstream implementation](https://raw.githubusercontent.com/ibus/ibus/main/bus/dbusimpl.c)
advertises the method in introspection but does not dispatch it in the method
table. This rules out relying on that PID query for this tested implementation;
the existence of the advertised method alone must not enable automatic routing.
