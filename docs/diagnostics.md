# Metadata-only diagnostics

`DiagnosticLog.record(event, code="")` accepts only fixed allowlisted state,
event and error identifiers. It cannot accept a freeform transcript, URL, key or
exception message. Known errors use ERROR level; ordinary events use INFO.
`recent` returns at most the final 32 KB for the diagnostics page. `clear`
deletes only the managed log and its two backups and permits new events;
`close` releases the handler.

Logs live under `$XDG_STATE_HOME/inkecho/logs` (or the standard home fallback),
rotate at 128 KB and retain at most two backups. New log directories/files use
private permissions. Existing symbolic-link log paths are rejected. The module
does not configure global HTTP-library debugging or log raw exceptions.

Validation on 2026-10-12: three tests passed with temporary directories, covering
levels and fixed identifiers, rejected secret/transcript text, bounded rotation,
clear/reuse, preservation of unrelated files and symbolic-link rejection.
Reproduce with `uv run pytest -q tests/test_logging.py`.
