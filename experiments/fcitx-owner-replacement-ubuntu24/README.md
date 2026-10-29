# Ubuntu 24.04 Fcitx owner replacement: corrected isolated probe

The earlier candidate f6 failure is preserved in
[`../candidate-f6-ubuntu24/`](../candidate-f6-ubuntu24/README.md). Its injected
sender calls `int(result)` on dbus-next's `RequestNameReply` enum after sending
SIGTERM and requesting the replacement name. In the candidate runtime that
conversion raises `TypeError`, so the wrapper itself can fail before returning
the successful first Commit response to the product. The old log therefore
does not prove that the replacement acquired the name or that product owner
change detection failed; the product conservatively returned
`delivery_unknown` and did not retry.

This rerun used the same candidate AppImage SHA-256
`f6ceb6311069f85b180bafd446f546247b5e592735ba26035455a571c5eb5164`
on Ubuntu 24.04.5 with GNOME Xorg and native GNOME Wayland, in a KVM VM using a
new `/tmp` copy-on-write overlay with the original image and backing image
mounted read-only. The QEMU container had no external network and used a
private test configuration, test Fcitx, owned GTK text controls, fixed
synthetic input, and stub recording and transcription. No real microphone,
cloud recognition, physical shortcut, browser, or terminal was tested.

The corrected probe compares `RequestNameReply.PRIMARY_OWNER` directly. After
first successful Commit it also queries the old unique owner, terminates the
private Fcitx process, acquires the well-known name with a replacement test
connection, verifies that the new owner is the replacement and that the old
unique connection no longer owns any name, and checks the target text plus
sender events. Each actual run verified the candidate digest and extracted
`fcitx5.py` hash. Source files use `.txt` suffix and are the scripts actually
used; `launch.sh.txt` records the VM setup and is environment-specific.

- `x11-run.log` and `x11-run-r2.log` failed before any text sending because
  the owned target could not obtain focus while GNOME's initial Activities
  overview was open. They are retained rather than reported as product passes.
  After dismissing overview, `x11-run-r3.log` passed: old owner `:1.124`, new
  owner `:1.142`, old owner no longer present, exactly one character in the
  target, product `owner_changed` with accepted count 1, no keyboard fallback.
- `wayland-run.log` passed under the same assertions: old owner `:1.94`, new
  owner `:1.115`, old owner no longer present, exactly one character in the
  target, `owner_changed` with accepted count 1, no keyboard fallback.

The fake replacement does not implement the bridge and this sequence changes
owner between Commit responses, not at every possible instant inside a D-Bus
call. It does not rule out concurrent change/send races and does not establish
blanket system support or complete candidate package acceptance. The VM shut
down via QMP powerdown with container exit 0. Test Fcitx and addon were confined
to the disposable guest; the overlay and temporary key copy were discarded.
