# GetEngine authorization probe

Run `bash experiments/ibus-gnome-shell/engine_identity_probe/run.sh`. It creates
an isolated session bus and temporary IBus daemon and selects `xkb:us::eng` only
in that private daemon. It creates its own input context and queries only
engine names, not user text or surrounding text. A second `gdbus` process uses
a different connection to ask the same real context for its engine. The script
does not use the user's desktop session, panel, or current engine.

On the tested Ubuntu 26.04 host, the owning connection received
`xkb:us::eng` from its real context, but the other connection timed out. The
same owner connection also timed out asking the daemon's fake context. After
focus was restored to fake, the real current-path query confirmed that switch.
The two timeouts have the same observed form; they cannot distinguish a fake
context from another program's real context. An initial script failed because
it used the wrong GI deserialize symbol; the corrected version produced the
above result. Later assertions only record those already observed outcomes and
were not included in that exact run.

The [upstream source](https://raw.githubusercontent.com/ibus/ibus/main/bus/inputcontext.c)
checks whether the calling connection owns the input context before handling its
methods. This explains the tested outcome, but is not proof for Ubuntu 24.04 or
every IBus version. Timeout can also mean other failures. No implementation
should rely on a timeout as evidence that the context is fake, and the engine
lookup does not confirm that a target accepted text.
