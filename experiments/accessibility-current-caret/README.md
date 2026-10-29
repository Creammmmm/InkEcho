# Independent AT-SPI current-caret candidate: actual isolated trial

This is NOT IBus. It is a separate application accessibility interface examined
as a potential pre-send alternative. No clipboard/IME switch, settings change,
package install or host input occurred. No shared worktree file was modified.

## Actual Ubuntu26 GNOME50.1 Wayland result, 2026-10-29

Owned GTK actorPID2304/startticks2135, one native window containing EntryA,
EntryB and a button. Every send re-enumerates only that PID's accessible tree,
checks focused/editable interfaces and zero selections, reads numeric caret,
then rechecks active and focused before calling insert_text with UTF8 BYTE count.
It never calls GetText, get_name, descriptions, clipboard copy/cut/paste, or
set_text_contents. The OWN actor writes fixed synthetic contents for groundtruth.

Results (raw actual26-result.log / raw26/rows.json):

| case | API result / calls total | owned outcome |
|---|---|---|
| initial currentA | called true /1 | A甲, Bempty |
| focusB | called true /2 | A甲, B乙 |
| focusA caret0 | called true /3 | A丙甲, B乙 |
| cancelled before send | not attempted /3 | unchanged |
| button focused | unsupported, not attempted /3 | unchanged |
| nonempty selection | reject, not attempted /3 | selection not deleted |
| focus changes IN insert-text | called true /4 | A丁丙甲, B乙, final focusB |

Actor original process naturally exited0; probe0. The in-call focus switch is a
purpose-built owned GTK signal handler before the default insertion. It shows
AT-SPI inserts into the referenced accessible even after focus moved. No text
was lost here, but the output did NOT follow final current focus. This does not provide an atomic follow-any-future-focus transaction. Under a
weaker and practical output-dispatch-time definition, A was the current caret
when that call began; this race alone does not disprove keyboard-like semantics.
The next call must reacquire the current focused accessible, never keep A for the
whole recording/task. Rechecking metadata does not make the RPC conditional.

Prior repository evidence additionally shows ordinary EditableText insertion
does not replace a selection, and real Chromium/VTE controls may not expose the
interface. This probe rejects selections instead of adding a destructive separate
DeleteText. It does not validate browser/terminal availability, preedit, stalled
RPC cancellation, Ubuntu24 or a same-hash dual-system AppImage.

## Deployment conclusion

A useful narrowly scoped explicit application-integration mode could insert
Unicode without depending on Mutter IM queues. It would need an explicit
user-facing distinction that each call targets the accessible selected at call
start. If the required semantics are current caret at each output CALL start, the
A→B→A result is a positive basis for a scoped candidate. If the requirement is
retargeting even an already-started RPC, this interface cannot promise it. The
root reviewer must distinguish these definitions before integration. Neither
definition justifies universal compatibility or replaying an uncertain IBus character.

For a future explicit mode, known zero-call unsupported/no-target can choose the
existing keyboard before any attempts; selection/preedit must be deferred or
explicitly rejected, not automatically fed keystrokes. Any RPC timeout/exception
is unknown, and no success boolean is a delivered/displayed acknowledgement.
Cancellation is checked before lookup and again immediately before insertion;
an RPC already dispatched cannot be recalled. The tested cancellation case is
before-send only, not proof of interrupting a blocked in-flight RPC.

## Reproduce and privacy boundary

Review actor.py/probe.py first. Only run in a disposable guest with Gtk3,
Atspi2 GI and working native Wayland desktop. Copy into a NEW0700 private dir,
set actual desktop-user environment and run `/usr/bin/python3 probe.py DIR`.
Both field focus changes and synthetic content are created by the actor. A
production global focus locator was NOT tested; this implementation deliberately
limits all enumeration to the known owned actor PID. Do not infer support for
other user processes or broaden scanning/text reads from this fixture.

raw26.tar SHA256 `826facd26ea47a3a5632abe8230aff05f7f473f89aa266ed4bb449e204fbc47b`.
cleanup26.json compares before/after extensions[]/idle300/locktrue/xkbengine equal
and confirms no owned actor remains. Private guest files removed after transfer.
Normal system poweroff and original dockerwait are in poweroff26.log; final
container state is recorded separately. No force kill or host configuration.
