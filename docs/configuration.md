# Configuration and credentials

InkEcho stores settings in `$XDG_CONFIG_HOME/inkecho` when that variable is an
absolute path, otherwise in `~/.config/inkecho`. No configuration is written
inside the installed application or AppImage.

```text
inkecho/
├── config.json
├── credentials.json  # plaintext authentication values
├── providers/
│   ├── qwen.json
│   └── deepseek.json
└── prompts/
    └── prompt-<generated-id>.json
```

Each JSON record has `schema_version: 1`. Files use owner-only permissions and a
temporary file in the same directory followed by atomic replacement. Failed
replacement leaves the previous file intact. Initial setup creates missing
defaults and does not replace existing records.

## Application settings

`Settings` records shortcut, microphone ID, audio sample rate, recording limit,
independent transcription and polishing provider IDs, selected prompt, polishing
preferences, overlay preferences and close-to-tray behavior. Defaults are F13,
the default microphone, 16,000 Hz mono audio and a 120-second recording limit.
Configured sample rates are 16,000, 24,000 and 48,000 Hz, subject to actual device
capabilities. Recording limits are 1–300 seconds.
Transcription and polishing each have an independent 5–120-second request timeout,
defaulting to 30 seconds. Existing version 1 settings receive these defaults.

Polishing starts disabled; failure fallback is enabled. The waveform overlay
defaults to bottom center, 90% opacity and a two-second result duration. Settings
do not establish desktop support; runtime adapters must validate actual session
capabilities and shortcut registration.

## Providers

`Provider` contains `id`, `name`, `role`, `adapter`, `base_url`, `model`, `key_ref`
and `parameters`. Roles are `transcription` and `polishing`. Defaults use `qwen`
for Alibaba transcription and `openai` for DeepSeek polishing. Models start empty
so the user can select a currently available model. Services need a model and
credential before use.

Base URLs require HTTPS without credentials, query strings or fragments.
Ports must be valid and nonzero. Local protocol tests also use HTTPS.
Parameters contain ordinary JSON values; recognized credential fields, including
nested `api_key`, `x-api-key`, `client_secret` or `Authorization`, are rejected.
This field-name check cannot identify a secret placed under an arbitrary name.
Credentials belong only in the dedicated plaintext credentials.json. `key_ref`, such as `provider/qwen`, identifies an item and is not a key.

Deleting a provider record does not remove its local credential value automatically; use
the explicit credential operation when the user chooses it. The caller must
update selected provider IDs when deleting a selected record.

## Prompts

The built-in `builtin-faithful` template lives in application code. Saving an
edited version creates a new user ID and returns that new `Prompt`; the built-in
template remains unchanged. Copies also receive generated IDs. Custom templates
can be updated and deleted; the built-in cannot be deleted. Templates contain a
name, description and body alongside their ID and JSON schema version. Select a
replacement before using polishing if the selected custom template is deleted.

## Migration and damaged files

Version 0 uses current record fields but may omit `schema_version`; application
settings may use `hotkey` instead of `shortcut`. A valid legacy record is checked
before migration, and its exact original bytes are preserved in a uniquely named
`.v0-<id>.bak` file. Repeated loads do not migrate it again.

Malformed JSON, unknown fields, unsupported versions, mismatched record IDs and
invalid values raise `ConfigError`. They are not replaced with defaults on load
or save. Back up and correct or move a damaged file deliberately. The application
must show the problem and a recovery path instead of discarding user data.

## Credentials

`FileCredentialStore(config_root)` uses only `<config_root>/credentials.json`.
The root is always the selected ConfigStore root, including --config-dir.
It never imports a system keyring or migrates/deletes old entries. A missing old
reference requires re-entry in the provider form. The file is intentionally
plaintext, not encrypted; copying it also copies all stored authentication data.

The schema is `{"schema_version":1,"credentials":{"provider/<id>":"value"}}`.
Single API keys remain strings; existing multi-field bundles remain JSON-encoded
strings, including AppID/APISecret/SecretID/access fields. Provider parameters
still reject credentials, and provider records retain key_ref. A preset gets its
own reference rather than reusing a different supplier's credential.

Owned config directories/files are tightened to0700/0600. Symbolic links,
hard-linked/nonregular files, wrong owners, invalid/duplicate JSON fields and
oversized data fail with sanitized CredentialError. Writes use an exclusive0600
temporary file within an opened config directory and atomic replacement. A
single store serializes concurrent operations; malformed data is preserved.

## Module validation

```sh
python -m pytest tests/test_config.py tests/test_security.py -q
```

Tests cover first-run defaults, separate records, permissions, saved settings,
prompt copies and deletion, version migration and byte-for-byte backups,
damaged/future-file preservation, atomic replacement failure, rejected credential
fields, path traversal, local storage errors, explicit config isolation and no system-keyring access.
These tests do not validate real supplier accounts.

## Historical Secret Service evidence

The following result describes the previous implementation, not current runtime
requirements. On Ubuntu26.04.1 a disposable system Secret Service item was once
created/read/updated/deleted successfully without accessing user secrets. That
historical result is retained; the current credentials_probe.py instead tests a
fresh disposable local config file and never opens a system keyring:

```sh
python scripts/validation/credentials_probe.py --output /tmp/inkecho-file-credentials-check.json
```

The probe uses only generated test values and removes its temporary directory.
Old keyring entries remain untouched and unused. Existing AppImages are not
changed by the source or project-venv update.
