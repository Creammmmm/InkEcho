# Wayland input feedback and the 40 ms setting: design experiment

On 2026-10-28 a disposable Ubuntu 26.04 GNOME Wayland guest used the extracted
r3 candidate AppImage SHA-256
`23b1b77e41e4e3a8fdd30a9a6a892d5b5babeaa9e303fdbcc3b37731e5a1e105`,
its real Fcitx bridge and private Fcitx service, and one owned GTK3 Fcitx entry.
The probe first sent `甲` and waited until the test entry's change callback
recorded it. It then SIGSTOPed only that owned target process and verified its
Linux process state was stopped before sending `乙` via the bridge.

The bridge returned one accepted character after **0.507 ms**, while the
stopped target's last recorded text remained `甲`. The probe marked the task
inactive and verified an attempted `丙` was rejected as cancelled; after an
additional **40 ms**, the target was still stopped and its recorded text still
`甲`. Only after SIGCONT did the owned entry record `甲乙`. The already
accepted `乙` could not be withdrawn. The program exited 0. This is one
controlled sample: it demonstrates that the bridge reply and an elapsed 40 ms
are not proof that this target has processed or displayed the character. The
test callback records text-buffer changes, not frame presentation; it does not
measure pixel visibility or prove a universal bound.

Raw `run.log` SHA-256
`785930de1ebb88b57054c9cb7fe529768920bb1dd4185018cb3360e29a8b5a9f`,
`probe.py.txt` SHA-256
`ca7fc7c61d748656def8d9420ce59d06eff2eb3800d94d0bb26d5d8913b7540e`.
The scripts are the exact tested files with `.txt` added; no clipboard, cloud,
real user target or input-engine switching was involved. This is an isolated
experiment, not package acceptance or a physical ESC test.

## Design consequences

* A Wayland surface's own `wl_surface.frame`/presentation feedback is tied to
  that surface, not an independent arbitrary application's surface. The
  standard [RemoteDesktop portal](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.RemoteDesktop.html)
  exposes input control through EIS or Notify calls, not a per-character
  receiving-window presentation receipt. Existing native keyboard INPUT
  round-trip measurements and bridge calls can reflect backpressure in their
  own input path, but the paused-target sample shows they cannot establish
  receiver progress. IBus has not been subject to this particular paused-target
  experiment; do not infer its exact timings from Fcitx.
* A possible meaningful **transport pacing** experiment is to observe the
  existing serial request latency (without reading target text), and apply
  bounded adaptive waiting when that input path slows. An optional 40 ms value
  could be a clearly named scheduling budget, never called frame-sync or
  receipt. This is only a design hypothesis: the paused target may show no
  backpressure, so such pacing cannot guarantee responsiveness or readability.
  No product implementation or 40 ms performance improvement is claimed here.
* Actual receiver-frame feedback would require a trusted, voluntarily
  cooperative target exposing a scoped progress signal or a desktop protocol
  with an appropriate guarantee. Such a signal must never be inferred from an
  unrelated app surface or an untrusted draw event. A 40 ms configurable bound
  may limit waiting for that signal, not certify success on timeout. On focus
  change invalidate old evidence, allow subsequent characters to follow current
  focus, recheck cancellation/deadline before sending, wake promptly on cancel,
  and never replay an already sent or uncertain character. The first target is
  not locked at recording start. This remains a design, with protocol support,
  privacy and real cross-app behavior unverified.

To reproduce, copy the candidate AppImage and retained `run.sh.txt`,
`probe.py.txt`, `target.py.txt` (remove `.txt`) to
`/tmp/inkecho-frame-hint-r1/` in an isolated 26 GNOME Wayland guest and run
`bash run.sh`. The runner creates private Fcitx data, preserves the input-method
session environment, and cleans it on exit. `cleanup.log` confirms restored IBus
variables, no Fcitx process/owner, and deleted guest files. The VM was normally
powered down with container exit 0. The owned stopped process is resumed even
on probe failure; this experiment must not run against a user's desktop.
