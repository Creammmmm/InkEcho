# Independent IBus context focus probe

Run `bash experiments/ibus-gnome-shell/own_context_bridge_probe/run.sh`. It
starts an isolated session bus, private IBus daemon and private panel, and
creates two synthetic input context proxies with signal counters. It sends
only fixed synthetic characters and never reads signal text. It does not touch
the user's real engine, session or clipboard.

On the tested Ubuntu 26.04 host, creating the second context without focusing
it left the first context current; a private panel's synthetic commit reached
the first proxy. Calling `FocusIn` on the second context changed IBus current
focus to that context, after which a second panel commit reached the second
proxy instead of the first. Assertions passed and process exit was 0. GI
printed `g_object_is_floating` warnings for both synthetic commits. These are
proxy signal observations, not real widget insertion or acknowledgement.

An independent context therefore does not transparently forward its own input
to the prior target merely by acquiring focus; in this trial it became the
target. Creating it without focusing preserves the prior context but does not
give the new context authority to submit on behalf of the old one. The panel
used here is private to the experiment; using another primary panel in the real
session would compete with the existing desktop panel. This is not evidence
for other versions, application acceptance, or a production input route.
