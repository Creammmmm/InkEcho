# Focus ID does not establish an editor

Run `bash experiments/ibus-gnome-shell/focus_id_nonwidget_probe/run.sh`. A
private session bus and IBus daemon, private xkb engine, panel, and two
synthetic contexts are created. The first context has no GUI widget or commit
handler; the second has a handler used only to count its own synthetic signal.
The monitor listens only to the engine's focus-ID method; it does not inspect
any text signal. No user's session, engine, clipboard or text is accessed.

On the tested Ubuntu 26.04 host, IBus reported a non-`fake` `FocusInId` for the
first context even though its creator provided no editor or handler. A panel
commit was then attempted to that context. After the second context acquired
focus, IBus reported a second non-`fake` ID and its handler counted one
synthetic commit signal. Process exit was 0; GI emitted a `g_object_is_floating`
warning. These synthetic contexts deliberately show that framework identity
alone does not prove a live editable widget. The positive control verifies the
test signal path, not a real application insertion or a universal behavior of
all clients. This does not validate Ubuntu 24.04 or automatic IBus routing.
