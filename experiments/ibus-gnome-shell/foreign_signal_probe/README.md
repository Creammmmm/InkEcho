# Direct foreign IBus CommitText signal probe

Run `bash experiments/ibus-gnome-shell/foreign_signal_probe/run.sh`. The script
starts a new session bus and IBus daemon with a private temporary address. The
attacker script refuses an address outside that temporary prefix. It creates
only an owned test context and synthetic text; it does not connect to the user's
desktop, IBus, input engine or text. The receiving connection's filter records
only incoming signal header sender identities, never signal bodies.

On the tested Ubuntu 26.04 host, a second private-bus connection sent two
synthetic `CommitText` signals addressed to the owned proxy, one with no sender
header and one with a forged `org.freedesktop.IBus` sender. Both messages were
queued and arrived on the victim connection with the same actual unique sender
`:1.2`; the proxy's `commit-text` handler was not invoked. A genuine private
panel commit then invoked the handler once as a positive control. Assertions
passed on the repeat run with process exit 0. The attacker printed a GLib
reference-count warning and the positive control a GI floating-object warning;
these warnings limit interpretation, and no application widget was involved.

Thus direct external signals through this tested IBus bus do not provide an
authenticated substitute for a panel or engine integration. This does not
prove behavior of all versions, or permission to bypass sender verification,
and it does not establish application receipt or Ubuntu 24.04 compatibility.
