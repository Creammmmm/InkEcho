# Ubuntu 24.04 GNOME Wayland EIS retest (2026-10-28)

This is an isolated experiment, not a package acceptance test or a claim of
production support. The prior r6 probe failed during cleanup because its
`pressed` set was overwritten by a boolean in the key press/release loop. This
probe renames that loop variable and retains full tracebacks for future errors.
Its SHA-256 is `935fc37e573fee929770599d44e43e0856085ff2914511b3f71f6c43d7ae78f7`.

The candidate runtime was `InkEcho-0.10.2-x86_64.AppImage`, SHA-256
`e4f2c6de3450cd997607baaeba41dd1764f8365c0bda73d9b9dd7c4ac395db54`.
The standard keyboard-only portal consent dialog was operated using its normal
checkbox and Share button. No clipboard, system input method, or real user
application was used. The test-owned GTK3 editor used `gtk-im-context-simple`.

The portal granted the session; ConnectToEIS returned a resumed keyboard and a
68,405-byte canonicalized keymap (`keymap.xkb`, SHA-256
`7f05616da2b8268871bb8b0a45fce919615a260e8bd307016db9e217514fcfe3`).
The observer still timed out waiting for a modifier snapshot. Scanning all
keycodes 9–708, groups and levels found ASCII `b` at keycode 56 and no direct
mapping for `中` or `😀`. Sending `b` through EIS reached the owned editor.
Then sending the ordinary Ctrl+Shift+U, `4e2d`, Enter key sequence through EIS
produced `中` in that GTK simple editor, so its final text was `b中`. This is a
client-side GTK composition feature, not evidence that EIS can send arbitrary
Unicode, nor evidence that other applications, terminals or browsers support it.
The corrected probe completed with exit status 0; the initial modifier snapshot
remained unavailable, so this does not validate production modifier handling.

Reproduction follows the procedure in `../eis-r6/README.md`, using the r7
probe, runtime and retained fixture copies in this directory. Run with the
isolated user's Wayland and D-Bus session variables; approve the standard portal
dialog only for the test. `wayland24-r7-portal.log` contains the observed results,
and the action logs record the consent controls. The original configuration of
GDM and the account session was restored and byte-compared with the backups;
the guest's private test files were deleted (`wayland24-r7-restore.log`), and
normal QMP shutdown was requested.
