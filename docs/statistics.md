# Private local usage statistics

`Statistics.record` stores one terminal task outcome plus numeric recording,
character, service-call, latency and optional polishing-token aggregates.
`today` returns the current local calendar day's totals; `clear` resets all
statistics. Storage follows `$XDG_STATE_HOME/inkecho/statistics.json` with the
standard home fallback and atomic writes. No transcript, prompt, key, target
window or audio is accepted or saved.

Character count means Python Unicode code points (`len(text)`), not UTF-8 bytes,
words or visible grapheme clusters. The caller supplies that count. Dates use
the user's current local timezone through `date.today()`. Successful, failed and
cancelled attempts are separate counters. Polishing token counts are exact
supplier values only. If any counted polishing call lacks a token value, that
day's corresponding total becomes `None` (unknown); subsequent known values
cannot make the incomplete total exact. No estimates are silently invented.

Corrupt or unsupported data raises `StatisticsError` and is preserved. The UI
can offer explicit `clear` as recovery; reads and new records never silently
overwrite a corrupt file. Clearing statistics does not touch configuration,
credentials or logs.

Validation on 2026-10-12: `uv run pytest -q tests/test_statistics.py` passed nine
tests covering persistence, Unicode counts, local midnight rollover, unknown
usage, nonfinite/negative counters, corruption preservation and explicit reset.
All files were inside temporary test directories. This is local file behavior,
not evidence of real supplier token-accounting correctness.
