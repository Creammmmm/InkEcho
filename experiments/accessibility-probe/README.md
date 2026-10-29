# AT-SPI synthetic owned-widget probe

This is an independent accessibility API experiment, not an IBus output path.
It runs only on a disposable graphical desktop. Copy these two scripts to
`/tmp/inkecho-accessibility-probe` and run `probe.py` there as the desktop user.
The test does not change accessibility settings. It creates a GTK window, finds
its own application via PID, and examines only that owned application's
accessibility tree. It reads focus, caret and selection metadata but no user
text; the actor writes only its own synthetic widget content to a temporary file.
It calls `EditableText.insert_text` and never uses clipboard methods.

On an isolated Ubuntu 26.04 GNOME Wayland desktop, the owned GTK Entry exposed
focused, editable-text and caret interfaces. Passing synthetic `甲乙` with the
correct UTF-8 byte length (6) returned true and the owned entry contained `甲乙`.
Moving focus to the owned button made the entry's focused state false. After
setting synthetic `ABC` and selecting it all, inserting `甲` at the reported
caret returned true but yielded `ABC甲`: `InsertText` did not replace the
selection as keyboard input would.

An earlier trial incorrectly passed 2, the character count, as the API's byte
length for `甲乙`; it returned true but the owned entry remained empty. The
[official API](https://gnome.pages.gitlab.gnome.org/at-spi2-core/libatspi/method.EditableText.insert_text.html)
specifies length in bytes. This error is a useful warning that a true response
alone does not ensure the intended text appeared. The corrected script uses
the byte length. These are GTK-only experiments; real browser and terminal
accessibility, preedit, focus changes during the call, timeouts, cross-process
security, other target controls and Ubuntu 24.04 are untested. Deleting a
selection separately would introduce a non-atomic destructive operation; it
was not attempted. No product routing or IBus support claim follows.

The self-owned actor exited and temporary guest files were removed. The VM was
left running and handed to the package-audit agent; no system settings or
packages were changed in this test.

The final guest-tested probe SHA-256 was
`399f5d7a6bb97a502b6d85355eeee148962c2beaf3b7ecb0ad99dc042eed1551`;
its unchanged tested copy is retained at
`build/accessibility-probe-evidence/probe-tested.py` (an ignored build artifact).
The actor SHA-256 was
`70cee13fae853f983a3187234699db69c1539e5bd62e60ef11d1d343b5aea1c3`.
After the trial, Ruff replaced explicit UTF-8 encoding with Python's equivalent
default in the tracked probe; its SHA-256 is
`168c4428b4e4081aaf11172f3d8f0e54b984a4e58698bf14f6520a5846a92d3e`.
That formatting-only revision has not been rerun in the guest.
