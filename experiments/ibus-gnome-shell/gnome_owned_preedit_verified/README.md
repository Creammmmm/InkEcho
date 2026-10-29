# Live owned-bridge preedit verified, bounded scope

2026-10-29 follow-up supersedes the earlier environment-blocked conclusion, not its raw failures. Same independent network-none26 GNOME50.1 VM; same candidate source patch9c67b507f6f937000f6d47596a3ceb7b5994e2d2d1578dfbfe6fa93e65626173, unchanged. No host input method, clipboard, shared worktree or auto mode changes.

## Root cause actually established

registration-diagnostic-r2.log proves libpinyin listed and package component valid. switch-diagnostic.log proves `ibus engine libpinyin` exits1 even though immediately querying `ibus engine` reports libpinyin. Thus CLI exit1 does NOT establish failure to change engine in this environment. Earlier check=True fixture assertions aborted before live preedit; they are retained, not reclassified as successful tests. We have not determined the CLI's internal reason for exit1 and do not claim one. The fixture now records exit code and checks actual engine state before continuing. No product or system IBus code changed.

## Actual complete r7

actual-r7.log, raw26-r7.tar; original outer session52938 natural0:
- Default authenticated Shell owner :1.17, own nativeGTK3 receiver2427.
- Separate甲 and乙 fragments actually甲乙, sequence2.
- Simple widget returns no_service/sequence0 and empty field, then close_after_no_service.
- Native丁 submitted, activefalse rejects戊 with cancelled;1.3s tail actual甲乙丁.
- Switch command returns1 but actual engine libpinyin verified. Fixture fixed n/i produces real currentFocus/preedit[true,true].
- Candidate insert己 returns delivery_unknown, sequence0, actual text stays甲乙丁. Its preedit policy deliberately blocks known-zero keyboard fallback.
- Closing bridge leaves real preedit true. Fixedspace commits actual你; final own field甲乙丁你, no己. Thus composition survives rejected output and bridge close.
- Actor2427 natural0; engine restoredxkb:us::eng. r6 NameHasNoOwner (extension activation fixture) before text remains preserved, actor2118 natural0.

## Limits and shutdown

This proves self-owned default nativeGTK3 on26/Shell50 only. It does not validate genericGTK-owned IBus context,24/Shell46/package, actual keyboard fallback delivery, target receipt, same-widget pending-focus race or live cancellation during an asynchronous context query. Between-fragment cancellation and live preedit-close are established; pending-query cancellation remains offline only. No auto route justified without explicit scoped design/review.

cleanup-r7.log confirms sources[('xkb','us')], engineus, extensions[],idle300,locktrue, actorPIDsabsent; temporarycandidate+fixtureextensions deleted. Normalpoweroff/dockerwait0; final-container-r7.json exited0/Runningfalse/OOMfalse. No additional samples.
