# Wayland text-input-v3 done is not a delivery acknowledgement

The official [text-input-v3 protocol](https://raw.githubusercontent.com/wayland-mirror/wayland-protocols/main/unstable/text-input/text-input-unstable-v3.xml)
describes `commit_string` and `done` as compositor-to-client events: `done`
directs the application to apply buffered changes. Its serial is the count of
the client's prior state-commit requests, not an acknowledgement from that
client that it applied the new text. The protocol says that after a serial
mismatch the client should send and commit pending state, but a future state
commit is not identified as an acknowledgement for a particular injected text
fragment; the absence of a state commit also does not prove failed receipt.
No surrounding-text payload should be inspected to infer success.

In [Mutter's Clutter input method](https://raw.githubusercontent.com/GNOME/mutter/main/clutter/clutter/clutter-input-method.c),
`commit()` queues an input-method event; it does not itself wait for an editor
to apply it. These are source and protocol observations, not a new desktop
experiment. Existing isolated focus-change trials in
`wayland_race_probe/` demonstrate that focus can change after a check. The
sources do not justify replaying an attempted commit or declaring confirmed
receipt, nor do they exclude a different future compositor API.
