# IBus FocusInId late-subscription probe

Run `bash experiments/ibus-gnome-shell/engine_focus_late_probe/run.sh`. The
script uses a private IBus daemon, selects xkb only within that daemon, and
focuses a synthetic context before starting a metadata-only engine event
monitor. It then changes focus in the private daemon. It does not connect to
the user's IBus, read surrounding text or monitor keyboard events.

On the tested 26.04 host, the late monitor received no `FocusInId` while the
already-active context remained focused. After switching to fake and back to
the owned context, it received fake and real `FocusInId` and corresponding
`FocusOutId` events. It used eavesdropping after the daemon rejected the modern
monitor interface. Exit status was 0. This confirms a startup blind interval:
without a later focus change this observer cannot establish identity from
events alone. It is not an application-delivery or Ubuntu 24.04 desktop test.

For the observed version difference, the upstream [1.5.29 simple engine](https://raw.githubusercontent.com/ibus/ibus/1.5.29/src/ibusenginesimple.c)
does not contain focus-ID handlers, whereas [1.5.33](https://raw.githubusercontent.com/ibus/ibus/1.5.33/src/ibusenginesimple.c)
does. In the latter, the [engine `FocusId` getter](https://raw.githubusercontent.com/ibus/ibus/1.5.33/src/ibusengine.c)
enables the focus-ID flag for the exact simple-engine type. This is a source
clue consistent with, but not proof of, the prior Ubuntu 24 and 26 observations;
distribution patches and other engines remain unverified. The getter has an
internal side effect and cannot be treated as an innocuous generic probe.
Even a fresh focus ID does not acknowledge application receipt or eliminate
asynchronous focus races.
