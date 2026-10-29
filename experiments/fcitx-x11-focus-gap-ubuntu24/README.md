# Ubuntu 24.04 X11 Fcitx focus gap and cancellation probes

Candidate AppImage SHA-256 `207b97eb667e5439137b51963a2aa09515c7ba50a83496d9c10070e989252685` was checked inside a disposable Ubuntu 24.04.5 GNOME X11 KVM guest. Packaged app.py and fcitx5.py were used without overlays. Original guest and backing disks were mounted read-only with a temporary QEMU snapshot; the container had no external network, host credentials were not mounted, and SSH used a dedicated disposable VM key on the host. The guest started in Activities overview; an Escape key closed it before tests. Targets are owned GTK TextView widgets and a GTK Button; all text is synthetic and transcription/recording are stubbed.

`run.log` corresponds to `run-initial.sh.txt`, `target-initial.py.txt`, and `sender.py.txt`. It reported normal Fcitx route and:

- switch: A received 54 characters and B 146, with B focus confirmed, total exactly the expected 200 in order; four `commit_status` 3 events appeared during transition;
- gap: A received 25 and B 175, with B focus confirmed and a no-target status; the initial script did not explicitly confirm the Button's focus, so its purported non-text interval alone is not sufficient proof;
- cancel: A received one character, B zero and outcome `cancelled`.

`run-confirmed.log` used `run-confirmed.sh.txt`, `target-confirmed.py.txt`, and the same sender. It explicitly waited until the Button's toplevel was active and the button had focus, then held that state for approximately 400 ms:

- gap: button focus confirmed at monotonic 210.094, B requested at 210.497; A and B together received the exact 200-character test text (25+175) and outcome was `succeeded`;
- gapcancel: button focus confirmed at 216.543, cancellation requested at 216.944; A received a 30-character expected prefix, B remained empty, outcome `cancelled`. Counts include characters already delivered during asynchronous transition before the button confirmation; no claim is made that the first character triggered an atomic switch.

The strengthened runner's stderr emitted two `XGetWindowProperty[_NET_WM_DESKTOP] failed` warnings; these were not captured in `run-confirmed.log`, but content and focus assertions passed. These are limited single-run samples, not proof for browsers, terminals, arbitrary switching races, microphone, shortcut, real cloud or the newer source tree, nor full package acceptance. Reproduce by copying the chosen script versions (remove `.txt`, name them `run.sh`, `target-focus.py`, and `sender.py`) and the exact AppImage into `/tmp/inkecho-r4-test`, then running `bash probes/run.sh 207b97eb667e5439137b51963a2aa09515c7ba50a83496d9c10070e989252685 x11` in an active unlocked test desktop. The guest received QMP `system_powerdown`, `docker wait` returned 0, and the temporary container was removed.
