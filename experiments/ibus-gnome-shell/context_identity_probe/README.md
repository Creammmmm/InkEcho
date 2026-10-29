# InputContext identity and capabilities probe

Run `bash experiments/ibus-gnome-shell/context_identity_probe/run.sh`. This uses
an isolated session bus and isolated IBus daemon. It obtains the daemon's fake
context and creates one separate test context with the same focus, preedit and
surrounding-text capability flags that upstream sets on its fake context. It
does not set or query surrounding text, use an engine or access the desktop.

In one 26.04 host run, both contexts' introspection declared exactly the same
properties: write-only `ClientCommitPreedit`, `ContentType`, and
`EffectivePostProcessKeyEvent`, plus readable `PostProcessKeyEvent`. Individual
read attempts for `Client`, `ClientName`, `Fake`, and `Capabilities` returned
the same `InvalidArgs` error for both contexts. The probe deliberately does not
read `PostProcessKeyEvent`, since its queued data can contain text. The two
independent object introspection responses are the positive control for the
queries; they establish that the paths and interface exist, not that another
implementation could never expose additional properties.

Thus neither capability similarity nor those proposed public property names
distinguishes these contexts on the tested IBus. This is not a desktop delivery
test, an exhaustive search of all possible APIs, or evidence for 24.04. No
automatic routing should rely on the missing identity properties.
