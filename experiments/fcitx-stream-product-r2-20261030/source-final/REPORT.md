# Fcitx LF product candidate R2 — isolated source validation

This is an unmerged source candidate, not a qualified AppImage or a general compatibility claim. No shared repository file, production asset pin, version, or host input environment was changed.

## Implementation

The actual Session uses a route-scoped preparation hook. Only a live, authenticated Fcitx bridge negotiating the complete Begin4/CommitBatch/Cancel signatures enables the neighbor planner. Keyboard and IBus retain their existing streaming timing. Old Begin3 remains usable for ordinary text, but LF fails before an attempt with a registered diagnostic. Malformed new protocol advertisements fail closed. Direct and original-fallback inputs use lazy linear partitioning rather than a full preplanned list.

The planner retains at most three real codepoints and combines LF with adjacent real characters; it inserts no filler, CR, synthetic key or deletion. Buffered text is never flushed after cancellation or unknown delivery. Task-scoped preparation restores the original-text fallback only before any attempt. Native attempt sequence and logical character counts remain separate. Streaming transient retention is the existing 128-codepoint chunk plus at most three held codepoints.

## Actual validation

The complete candidate source inventory c579575e8eee662403818db5395f9a5d2ceab57b002b9135289bff9910fdccfd ran in an isolated Ubuntu 24.04.5 GNOME Xorg guest using the real default Router and real Session. Its interpreter came from the audited release AppImage SHA 51d20c74a31beb7f01008378a76876a491fd8a3cdc6b61bda440a79bf11c966f, but candidate sources and a private test-only addon f67c6b5f2cb7ecd7c915c8062efd3b70284c74b97ced4a597d942c4b39594e44 were overlaid. This is explicitly NOT unmodified package acceptance.

Chrome 154 owned receivers passed all 11 recorded checks: leading/trailing LF, pure triple-LF tail, synchronous output, original fallback, mixed 22-codepoint text, first-send cancellation, buffered cancellation with zero output, preparation/live focus switches, and keyboard timing control. Exact DOM state stayed stable for 1.3 seconds. The keyboard control dispatched its first scalar before the next provider delta; existing mapping startup still delayed its actual key callback. Nested Router direct-insert wrappers produce two telemetry entries, not duplicate native attempts.

GTK3 TextView with the real Fcitx pinyin frontend passed normal input, genuine two-character ni preedit, composition rejection with zero native attempts and unchanged text/preedit/key observations, Space completion, subsequent LF-neighbor input, and first-batch cancellation without a late tail. Current actor PID and actual active-window PID were checked before each controlled key.

Targeted tests imported the candidate source (origin asserted): 233 passed in 3.52 seconds. Earlier failed fixture/test attempts remain preserved separately; the old globally replaced consumer and its Session regressions are not this implementation.

## Limits and deployment

Fcitx may hold the final one to three characters until a later provider delta, stream completion, or the existing absolute deadline. This latency is user-visible; it is not a throughput improvement claim. A two/three-codepoint native commit is one cancellation/focus boundary, so characters inside that commit cannot individually follow a later focus change. An ACK only proves transport handling, never display completion.

Native sources require a rebuilt, pinned and activated addon before deployment. An already running Begin3 addon cannot gain Begin4 merely because a staged file changed. Activation/restart must not interrupt a user composition and must not be automated by this candidate. No production ELF/pin update is included. Ubuntu 26, native Wayland for this candidate, all frontend variants, full repository checks and same-SHA dual-system package acceptance remain outstanding. No physical microphone, cloud provider, global shortcut, or universal application support was tested.

The private guest exited normally: docker wait 0; Running=false, Pid=0, ExitCode=0, OOMKilled=false, FinishedAt 2026-10-29T23:01:11.226004798Z. Owned browser/addon/FUSE resources were checked and cleanup records retained. No additional desktop tests are planned in this round.
