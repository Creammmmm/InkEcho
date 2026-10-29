# Ubuntu 24 Wayland: owned Chrome and terminal compose boundaries

On 2026-10-28, a disposable Ubuntu 24.04 GNOME Wayland guest tested keyboard
sequences through the standard keyboard-only RemoteDesktop portal consent and
ConnectToEIS. The runtime was extracted from candidate SHA-256
`e4f2c6de3450cd997607baaeba41dd1764f8365c0bda73d9b9dd7c4ac395db54`.
The Chrome process used its own temporary profile and isolated loopback page;
the terminal was an owned VTE widget with a raw-mode byte reader, not a shell.
No input was executed as a command; no clipboard, user profile, user data or
input-engine switching was used. Probe SHA-256 is
`1f00da0af9669df7bb03d5bf079dd6ae7e47d810fd33e0e49839ebc31c1460d6`.

* In the owned Chrome textarea, ASCII `b` was read back as `b`; then
  Ctrl+Shift+U, `4e2d`, Enter produced `b中` (probe exit 0).
* In another owned Chrome textarea, page code initialized `SEED` and selected
  it. The ASCII `b` replaced that selection, and the same composition produced
  `b中` (probe exit 0). The first attempt at this case timed out at the portal
  authorization step; its failure and action logs are retained. An independent
  retry obtained standard consent and produced the stated result.
* The terminal's raw-mode child read ASCII `b`. After Ctrl+Shift+U followed by
  Escape, the child still read `b` (probe exit 0): no composed character or
  command was delivered in this one fixture. A previous independent plain VTE
  case in `../compose-r12/` observed `b中` for the full composition.

Cross-window switching during the sequence and Escape in Chrome were **not
executed**, even though the retained probe contains experimental branches for
them. No claim can be made about those cases. Browser selection was prepared by
owned page JavaScript; no arbitrary existing selection or state was inspected.
The keymap lacks a direct `中` key and modifier-state observation timed out.
Shortcut handling depends on the target and input context: hex digits and Enter
could become literal input or commands in unsupported applications, an existing
selection may be replaced, and changing focus may split a sequence. These
bounded results do not justify a universal production fallback or claim that a
real shell, Codex CLI, other editor or browser uses the same behavior. Pending
or uncertain text must not be replayed.

Raw scripts (with `.txt` appended) and logs are retained. Chrome plain log
SHA-256 `d11a3139c05173a30d7dc890fdb0c473e269a5be23f38ccef11106ae422abd40`;
first selection authorization failure `cb897203354056c2ad986f8e137119307990770f3b28f6669fd9c93b947b964a`;
selection retry `b49171d5d280c2d1b77888307f60f5c99573c03f0e90c86fa0ba23ee276a3b01`;
VTE cancel `49d692b58815279300ff8494aae74f81b0129a81066febceb15a4d65800efece`.
Reproduce in a disposable Wayland guest by copying these scripts without the
`.txt` suffix and the candidate AppImage to `/tmp/wayland24-compose-r13/`,
extracting it, setting the session and runtime variables as described in
`../compose-r12/README.md`, and running bundled Python `eis_probe.py browser
plain`, `browser selection`, or `vte cancel`. Each case requires fresh consent
through the normal portal dialog. The original GDM/account configuration was
restored and compared byte-for-byte, the guest test directory removed, and the
VM normally shut down with container exit 0; see the restore log. This is an
exploratory comparison, not package acceptance.
