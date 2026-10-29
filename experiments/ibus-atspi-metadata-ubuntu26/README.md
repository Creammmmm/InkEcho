# AT-SPI focus metadata versus IBus module on Ubuntu 26.04

Hypothesis: a read-only, output-time query of the focused widget's AT-SPI role and editable state could identify a real IBus receiver without reading text or capturing focus at the start of recording. Ubuntu 26.04.1 GNOME Wayland ran in a network-isolated QEMU `-snapshot` guest with the original disk, base image and test input share mounted read-only. The active unlocked session used its original xkb US engine. No existing input method was switched; no text was sent or read, no surrounding text was queried, and no clipboard, real microphone, cloud service or host user data was used. An independent observer queried only AT-SPI process identifiers to select the owned fixture, its role and focused/editable state, plus the current IBus object path.

The raw `run.log` contains three cases, each with the owned actor confirming its window active and widget focused:

| Widget and GTK module | AT-SPI focused role | Editable | Current IBus path in this run |
|---|---|---|---|
| Entry, `ibus` | text | true | `InputContext_3` |
| Entry, `gtk-im-context-simple` | text | true | `InputContext_1` |
| Button, `ibus` environment | button | false | `InputContext_1` |

Thus this metadata can identify this sample button as non-editable, but the IBus and simple text entries expose the same role and editable state despite choosing different input modules. Their current IBus paths differ; the simple and button cases share a path, but object numbering is not a stable identity or proof of a fake/real client. Existing private-bus experiments show fake contexts can be current and the public identity properties do not reliably identify them. This experiment sends no text, so it does not itself establish whether either widget receives a panel commit. It also does not prove all non-text widgets report these states, all applications expose AT-SPI, or that a focus check remains valid until dispatch. A null or stale accessibility response cannot establish the absence of a target.

Consequently role/editability alone cannot reliably select IBus for arbitrary targets, and this experiment does not justify automatic routing, fallback after an uncertain send, or broad support claims. No product code was added.

To reproduce only inside a disposable Ubuntu 26.04 GNOME Wayland guest, copy the exact `actor.py.txt`, `observer.py.txt`, and `run.sh.txt` files without `.txt` to a read-only 9p share tagged `inkecho_input`, then run `bash run.sh` as the graphical-session user. The actor and observer SHA-256 values are recorded in `run.log`; the observer reads no text interface or window titles. The guest shut down normally, Docker wait returned 0, and the container and temporary VM SSH key were removed.
