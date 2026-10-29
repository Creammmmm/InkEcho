# Optional IBus engine focus-ID probe

Run `bash experiments/ibus-gnome-shell/engine_focus_id_probe/run.sh`. The script
starts a separate session bus and IBus daemon, sets engines only inside that
daemon, and creates an owned synthetic input context. It uses restricted match
rules for the engine's `FocusIn`, `FocusInId`, and `FocusOutId` method calls;
it does not observe keystrokes, surrounding text or commit text. The client
names in this experiment are synthetic. No user desktop, existing engine or
input context is touched.

On the tested Ubuntu 26.04 host, selecting `xkb:us::eng` succeeded. The isolated
bus delivered `FocusInId` for fake (`InputContext_1`, client `fake`), then an
out event and `FocusInId` for the owned real context (`InputContext_2`, the
synthetic client name), then an out event and a new fake focus event. This is a
positive control for the event filter and a potentially useful version/engine
dependent real-versus-fake signal. In contrast, an earlier real Ubuntu 24.04
GNOME 46 X11 experiment with xkb/us observed only ordinary `FocusIn`, no
`FocusInId`; see `docs/automatic-framework-detection-research.md`. The engine
and IBus versions differ; the cause has not been isolated. Attempting to select
`libpinyin` in this separate daemon timed out, so its behavior is **unknown**.
The monitor reported modern monitoring unavailable and used eavesdropping.
The script exited 0, and the private daemon and its temporary home were removed.

This signal is optional, is unavailable to a late-starting listener until a
new focus event occurs, and must be invalidated on engine, owner or session
changes. Even a current, genuine focus-ID event cannot prove a later panel
commit was delivered to that same target, or that the application applied it;
focus and IBus signal ordering remain asynchronous. Do not inspect user text,
persist user client metadata, replay ambiguous sends, or enable automatic
routing solely on this experiment. It is not an AppImage or desktop test.
