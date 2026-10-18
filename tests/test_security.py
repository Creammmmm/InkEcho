"""Private plaintext credential files, tested only in disposable config roots."""

import builtins
import json
import os
import traceback
from concurrent.futures import ThreadPoolExecutor

import pytest

from inkecho.provider_credentials import encode_credentials
from inkecho.security import CredentialError, FileCredentialStore


def test_plaintext_roundtrip_bundle_update_delete_and_isolation(tmp_path):
    store = FileCredentialStore(tmp_path / "config")
    other = FileCredentialStore(tmp_path / "other")
    assert store.get("provider/legacy") is None
    store.set("provider/one", "synthetic-first-key")
    bundle = encode_credentials(
        {"app_id": "synthetic-id", "api_key": "synthetic-key", "api_secret": "test"},
        ("app_id", "api_key", "api_secret"),
    )
    store.set("provider/two", bundle)
    assert store.get("provider/one") == "synthetic-first-key"
    assert store.get("provider/two") == bundle
    assert other.get("provider/one") is None
    values = json.loads(store.path.read_text())
    assert values == {
        "schema_version": 1,
        "credentials": {
            "provider/one": "synthetic-first-key",
            "provider/two": bundle,
        },
    }
    store.set("provider/one", "synthetic-updated-key")
    store.delete("provider/two")
    store.delete("provider/missing")
    assert store.get("provider/one") == "synthetic-updated-key"
    assert store.get("provider/two") is None
    assert store.root.stat().st_mode & 0o777 == 0o700
    assert store.path.stat().st_mode & 0o777 == 0o600


def test_owned_existing_permissions_are_tightened_without_touching_parent(tmp_path):
    root = tmp_path / "config"
    root.mkdir(mode=0o755)
    path = root / "credentials.json"
    path.write_text('{"schema_version":1,"credentials":{"ref":"synthetic"}}')
    path.chmod(0o644)
    parent_mode = tmp_path.stat().st_mode
    assert FileCredentialStore(root).get("ref") == "synthetic"
    assert root.stat().st_mode & 0o777 == 0o700
    assert path.stat().st_mode & 0o777 == 0o600
    assert tmp_path.stat().st_mode == parent_mode


@pytest.mark.parametrize("operation", ["get", "set", "delete"])
@pytest.mark.parametrize("kind", ["symlink", "directory", "fifo", "hardlink"])
def test_nonregular_or_linked_credential_paths_are_rejected(tmp_path, operation, kind):
    root = tmp_path / "config"
    root.mkdir()
    path = root / "credentials.json"
    target = tmp_path / "unrelated"
    target.write_text("unrelated-original")
    if kind == "symlink":
        path.symlink_to(target)
    elif kind == "directory":
        path.mkdir()
    elif kind == "fifo":
        os.mkfifo(path)
    else:
        os.link(target, path)
    store = FileCredentialStore(root)
    with pytest.raises(CredentialError):
        getattr(store, operation)("ref", *(["synthetic"] if operation == "set" else []))
    assert target.read_text() == "unrelated-original"


def test_root_symlink_is_rejected(tmp_path):
    target = tmp_path / "unrelated"
    target.mkdir(mode=0o755)
    link = tmp_path / "config"
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(CredentialError):
        FileCredentialStore(link).set("ref", "synthetic")
    assert not (target / "credentials.json").exists()
    assert target.stat().st_mode & 0o777 == 0o755


@pytest.mark.parametrize(
    "data",
    [
        "not-json-secret-do-not-leak",
        "[]",
        '{"schema_version":true,"credentials":{}}',
        '{"schema_version":2,"credentials":{}}',
        '{"schema_version":1,"credentials":{"ref":{}}}',
        '{"schema_version":1,"credentials":{"ref":"one","ref":"two"}}',
        '{"schema_version":1,"credentials":{},"extra":"synthetic-secret"}',
    ],
)
def test_bad_json_is_preserved_and_does_not_leak(tmp_path, data):
    store = FileCredentialStore(tmp_path)
    store.path.write_text(data)
    with pytest.raises(CredentialError) as caught:
        store.set("ref", "replacement-must-not-write")
    assert store.path.read_text() == data
    assert data not in "".join(traceback.format_exception(caught.value))
    assert "synthetic-secret" not in str(caught.value)


def test_atomic_failure_keeps_original_and_removes_temporary(tmp_path, monkeypatch):
    store = FileCredentialStore(tmp_path)
    store.set("ref", "original-synthetic")
    before = store.path.read_bytes()

    def fail(*_args, **_kwargs):
        raise OSError("synthetic-secret-do-not-leak")

    monkeypatch.setattr("inkecho.security.os.replace", fail)
    with pytest.raises(CredentialError) as caught:
        store.set("ref", "new-synthetic")
    assert store.path.read_bytes() == before
    assert not list(tmp_path.glob(".credentials.*"))
    assert "synthetic-secret-do-not-leak" not in "".join(
        traceback.format_exception(caught.value)
    )


def test_single_store_serializes_concurrent_updates(tmp_path):
    store = FileCredentialStore(tmp_path)
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(lambda i: store.set(f"ref/{i}", f"synthetic-{i}"), range(20)))
    assert len(json.loads(store.path.read_text())["credentials"]) == 20


def test_no_legacy_keyring_import_or_lookup(tmp_path, monkeypatch):
    original = builtins.__import__

    def guarded(name, *args, **kwargs):
        assert name.split(".")[0] not in {"keyring", "secretstorage", "jeepney"}
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded)
    assert FileCredentialStore(tmp_path).get("provider/old-keyring-ref") is None
    assert not (tmp_path / "credentials.json").exists()


def test_invalid_reference_value_and_oversize_file_are_rejected(tmp_path):
    store = FileCredentialStore(tmp_path)
    for reference in ["", " ", "r" * 201, None]:
        with pytest.raises(CredentialError):
            store.get(reference)
    for value in ["", " ", None, "x" * 65_537]:
        with pytest.raises(CredentialError):
            store.set("ref", value)
    store.path.write_bytes(b"x" * 1_000_001)
    with pytest.raises(CredentialError):
        store.get("ref")
