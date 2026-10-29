# Private IBus extension-registration experiment

Run `bash experiments/ibus-gnome-shell/extension_registration_probe/run.sh`.
It starts a private session bus and IBus daemon and creates its own synthetic
context and two panel-service objects. It does not change a desktop, user input
engine or existing extension, and it never inspects user text. Both test service
names and the synthetic output exist only in that private daemon.

On the tested Ubuntu 26.04 host IBus, a panel service registered under a custom
`Panel.Extension.InkEcho` name received no focus notifications and a synthetic
commit through it did not reach the owned proxy. An object registered under
the built-in `Panel.Extension.Emoji` name received fake and real focus events,
and a synthetic commit reached the owned proxy. A second independent connection
requested that already-owned emoji service name with DO_NOT_QUEUE and received
the EXISTS response, leaving the original owner in place. The emoji commit
produced a Python GI/GLib `g_object_is_floating` warning. Process exit was zero;
the two commit-count assertions were added after that run and were not part of
the exact recorded run.

The [upstream daemon](https://raw.githubusercontent.com/ibus/ibus/main/bus/ibusimpl.c)
recognizes the primary panel name and one emoji extension name in its owner-change
handler, consistent with this test. A custom parallel extension is therefore not
an established hook on this version; taking over the existing emoji service
would interfere with the user's existing extension. This does not establish what
other IBus versions or future APIs can do, does not test actual application text
insertion or concurrent focus changes, and supplies no receipt acknowledgement.
