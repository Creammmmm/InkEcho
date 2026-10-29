# Ubuntu 24 Wayland: compose interrupted by focus or Escape

On 2026-10-28 a disposable Ubuntu 24.04 GNOME Wayland guest used standard
keyboard-only RemoteDesktop portal consent and its actual EIS keyboard device.
The runtime was extracted from AppImage SHA-256
`e4f2c6de3450cd997607baaeba41dd1764f8365c0bda73d9b9dd7c4ac395db54`.
Targets were two isolated owned Chrome textarea pages, or two owned VTE
terminals whose child processes read bytes in raw mode and never executed
commands. No clipboard, real user data or system input-engine change was used.

Each sample first confirmed ASCII `b` in target A, started Ctrl+Shift+U and
entered the partial hexadecimal digits `4e`. For a switch, the owned fixture
requested B focus and the probe waited for B's own active/focused state before
sending the remaining `2d` and Enter. For cancellation, it sent Escape instead.

| Target | Interruption | Actual observed result |
|---|---|---|
| Chrome textareas | focus A → B | A contained `b中`, B empty |
| Chrome textarea | Escape | A contained `b` |
| VTE raw byte readers | focus A → B | A read `b`; B read `2d\r` |
| VTE raw byte reader | Escape | A read `b` |

Thus on this bounded Chrome example the composition committed to the prior
field even after B was reported focused. On the VTE example, the rest of the
sequence and carriage return reached the new terminal as literal bytes. An
actual shell could treat those bytes as a command, but this experiment did not
run a shell or execute the bytes. **This approach cannot safely be enabled as an
automatic universal fallback under the current-focus and no-replay requirements.**
Escape cancelled this one composition in the two fixtures, but does not prove
safe cancellation for other applications, focus transitions or modifier states.
The EIS observer also timed out waiting for a modifier snapshot; exact
compositor/IM internals were not traced.

The first VTE switch attempt (`wayland24-compose-r14-vte-switch.log`) failed
before sending keys because A focus was not confirmed. A separate r15 fixture
adds a delayed presentation of the same owned first window; that independent
retry yielded the stated VTE result. No failed attempt is counted as a pass.
All successful probe processes exited 0; the first failed attempt exited 1.

Raw scripts (extensions suffixed `.txt`), standard consent logs, input results,
fixture stderr, keymap and cleanup are retained. Probe SHA-256
`f6a1260f3f72aa8fbc72a497a2e7eaafbaef6686d9cf1b487609e13e8eb7aea2`;
r15 VTE fixture SHA-256
`7bf2c23060b90fbb31ca9c56d14b23f2e26752df5045405c71562e6699597992`.
Browser-switch log SHA-256
`6a572cdeb30db7cdf063f536fc64b842cbe62b1b2f78622e53ccd623d0da2cd1`;
VTE-switch retry log SHA-256
`1e94672aa4884514c96b6e982cd7a922de6e5d67ab9ab101674f412f57963eb8`.
To reproduce only in a disposable Wayland guest, follow `../compose-r13/README.md`
using `/tmp/wayland24-compose-r14/` and run `eis_probe.py browser switch`,
`browser cancel`, `vte switch`, or `vte cancel`, with fresh standard portal
consent each time; for the r15 VTE runs copy the retained r15 fixture as
`vte_fixture.py`. System GDM/account files were restored and byte-compared,
private guest files removed, and the VM shut down normally with container exit
0. This experiment is not package acceptance.
