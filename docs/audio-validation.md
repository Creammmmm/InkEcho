# Microphone feasibility validation


```sh
timeout 12 uv run python scripts/audio_probe.py
timeout 12 uv run python scripts/audio_probe.py --record
```

The second command requests two seconds from the default microphone into an
in-memory Qt buffer. It reports only device/format/byte-count/error metadata,
stops the source and clears the buffer. It never writes audio to disk. A normal
desktop session must have access to the user's audio service. The restricted
agent sandbox denied those sockets; testing outside that sandbox succeeded.
Use the outer timeout to bound a desktop-service connection that hangs before
Qt can create the recording timer.

Measured on 2026-10-12: Logitech G PRO X Gaming Headset, 48000 Hz, mono, Int16;
initial capture 178176 bytes, then three fresh-process captures of 180224,
190464 and 200704 bytes, all `NoError`. This verifies sample delivery and
repeated resource initialization; it does not claim recognition accuracy or
same-process lifecycle validation of the future application recorder.
The reviewing agent independently repeated the live probe: 198656 bytes,
the same device/format, `NoError`, no audio saved. Four automated tests cover
missing devices, empty capture, device error, successful metadata-only output,
and memory/resource cleanup on the tested capture outcomes.
