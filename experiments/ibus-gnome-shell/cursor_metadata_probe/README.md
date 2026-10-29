# IBus panel cursor metadata probe

Run `bash experiments/ibus-gnome-shell/cursor_metadata_probe/run.sh`. It starts
its own private session bus, IBus daemon and panel; it creates a synthetic
context and submits synthetic screen coordinates, never text. It does not use
or alter the user's desktop, input method engine or panel.

On the tested 26.04 host, the panel saw the owned context become focused and
received its synthetic cursor rectangle `(11, 22, 3, 4)`. When that context
lost focus and the fake context became current, the panel received focus-in for
fake but no cursor reset or replacement. A later cursor update sent by the
unfocused owned context did not reach the panel in this trial. Script exit was
zero. This provides a counterexample to using a merely nonempty or last-seen
panel cursor rectangle as evidence of a currently usable receiver.

An implementation could invalidate cursor data on every focus transition, but
some real clients may not send a fresh rectangle promptly, and an event still
does not acknowledge delivery. This test does not establish whether such a
stricter gate helps real desktops, all clients, or Ubuntu 24.04; it must not
enable automatic routing on its own.
