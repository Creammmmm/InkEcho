# Configuration and credentials

InkEcho stores settings in `$XDG_CONFIG_HOME/inkecho` when that variable is an
absolute path, otherwise in `~/.config/inkecho`. No configuration is written
inside the installed application or AppImage.

```text
inkecho/
├── config.json
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
Credentials belong in the
keyring. `key_ref`, such as `provider/qwen`, identifies an item and is not a key.

Deleting a provider record does not remove its keyring item automatically; use
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

`SecretStore` explicitly selects `keyring.backends.SecretService.Keyring` on
Linux. It does not select automatic backends or fall back to plaintext files.
Keys use service `io.github.Creammmmm.InkEcho` and the provider's `key_ref`.
Operations are `get`, `set` and `delete`; `get` returns `None` for a missing item.
Deleting a missing item is safe.

An unavailable or locked service raises a short `CredentialError`. Backend
exception details are suppressed to avoid exposing keys. A desktop Secret
Service, such as GNOME Keyring, must be available and unlocked. Tests may inject
a backend; production code uses the default constructor.

## Module validation

```sh
python -m pytest tests/test_config.py tests/test_security.py -q
```

Tests cover first-run defaults, separate records, permissions, saved settings,
prompt copies and deletion, version migration and byte-for-byte backups,
damaged/future-file preservation, atomic replacement failure, rejected credential
fields, path traversal, backend errors and absence of a plaintext fallback.
Fake backends prove application behavior, not desktop availability.

On Ubuntu 26.04.1 in the current GNOME session, actual Secret Service was tested
with a new random diagnostic reference and generated temporary credential:
create, exact read, update, exact read, delete and missing-item verification all
passed. Only that new item was addressed; existing user secrets were not
inspected. No provider request or user credential was involved. Other desktop
environments remain unverified.

Reproduce the opt-in live keyring check in a desktop session with:

```sh
python scripts/validation/credentials_probe.py --output /tmp/inkecho-keyring-check.json
```

It generates a new reference and temporary value, never prints the value, and
deletes the diagnostic item in a `finally` block. A failure exits nonzero; it
does not authorize a fallback backend or access another application's keys.
