# Private IBus panel commit and focus probe

Run `bash experiments/ibus-gnome-shell/panel_commit_probe/run.sh`. It starts a
private session bus, IBus daemon and panel, and creates two synthetic input
contexts. Only three fixed synthetic characters are submitted. The receivers
record their own identity on the `commit-text` signal; they do not inspect,
print, or store the signal's text. No user desktop, current input engine, or
user text is accessed.

In two runs on the Ubuntu 26.04 host, the first context received a signal while
focused, then the second context received one after focus moved to it. After
both lost focus and the daemon selected its fake context, the same panel API
call produced no additional receiver signal. The process exited zero. Python
GI/GLib printed `g_object_is_floating` assertion warnings during the first
two deliveries; retaining the synthetic text objects did not remove them.
The warnings limit interpretation and should be investigated before using
this harness for further conclusions. The synthetic event handlers verify only
signals reaching owned IBus proxies, not insertion in real application widgets.

This illustrates a current-focus handoff and a fake-focus loss through the same
panel entry point. It does not distinguish fake from real ahead of a commit,
prove ordering under concurrent focus changes, or provide a target receipt
acknowledgement. It is not package acceptance or evidence for Ubuntu 24.04.
