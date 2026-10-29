# GTK IBus context-name correlation probe

Run `bash experiments/ibus-gnome-shell/gtk_client_name_probe/run.sh` where
`broadwayd`, GTK 3, IBus and Python GI are installed. It starts a private
session bus, IBus daemon and Broadway server on a temporary Unix socket. Two
separate owned GTK processes use the private `GTK_IM_MODULE=ibus` and the same
synthetic program name, create and focus a GTK IM context, and exit. The bus
monitor matches only `CreateInputContext` calls; it records the synthetic
client-name argument and sender metadata, not keys, surrounding text or
commits. No user desktop, existing IBus session, engine or settings are touched.

On the tested Ubuntu 26.04 host, both different GTK processes exited 0. The
monitor observed two different unique senders but the exact same client name
`gtk3-im:inkecho-synthetic-same-name`. Assertions passed on a second run. The
isolated GTK processes caused an accessibility registry to start on their
private session bus; the test did not change system accessibility settings.
IBus lacked the modern monitoring interface and `dbus-monitor` fell back to
eavesdropping.

The [upstream GTK client](https://raw.githubusercontent.com/ibus/ibus/main/client/gtk2/ibusimcontext.c)
constructs its context name from its program name, using a PID fallback when
that name is absent. This experiment confirms the common name is not a unique
process or window identity, so matching it to an accessible application name
alone is unsafe. No actual keyboard focus, application text receipt, Ubuntu
24.04 desktop or real-world multi-process application was validated here.
