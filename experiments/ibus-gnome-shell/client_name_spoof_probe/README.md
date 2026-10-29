# IBus focus client-name identity probe

Run `bash experiments/ibus-gnome-shell/client_name_spoof_probe/run.sh`. The
script creates an isolated session bus, private IBus and xkb engine, and an
ordinary synthetic input context. It chooses the client-name string
`gnome-shell` without creating or contacting GNOME Shell. It observes only
the engine's `FocusInId` metadata and does not read or send user text.

On the tested Ubuntu 26.04 host, the event reported both the synthetic
context path and the supplied `gnome-shell` string; the assertion passed and
the process exited 0. The monitor used eavesdropping because modern monitoring
was unsupported by this IBus bus. [IBus's upstream `CreateInputContext`
implementation](https://raw.githubusercontent.com/ibus/ibus/main/bus/ibusimpl.c)
passes the caller-provided client name into the new context, consistent with
the observation. A `FocusInId` client string alone therefore does not
authenticate the GNOME Shell process, prove a native Wayland target, or prove
receipt. Exact object-path association to an independently authenticated
Shell context may still be a useful separate condition, but is subject to the
previously documented focus and delivery races. Ubuntu 24 and actual application
delivery were not tested here.
