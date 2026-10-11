import traceback

import pytest

from inkecho.security import CredentialError, SecretStore


class MemoryBackend:
    def __init__(self):
        self.values = {}

    def get_password(self, service, username):
        return self.values.get((service, username))

    def set_password(self, service, username, password):
        self.values[service, username] = password

    def delete_password(self, service, username):
        del self.values[service, username]


def test_credentials_roundtrip_update_and_delete():
    backend = MemoryBackend()
    store = SecretStore(backend)
    assert store.get("provider/test") is None
    store.set("provider/test", "first-test-key")
    assert store.get("provider/test") == "first-test-key"
    store.set("provider/test", "updated-test-key")
    assert store.get("provider/test") == "updated-test-key"
    store.delete("provider/test")
    store.delete("provider/test")
    assert backend.values == {}


@pytest.mark.parametrize("operation", ["get", "set", "delete"])
def test_backend_errors_do_not_expose_keys(operation):
    class BrokenBackend(MemoryBackend):
        def get_password(self, *_):
            raise RuntimeError("secret-key-that-must-not-leak")

        def set_password(self, *_):
            raise RuntimeError("secret-key-that-must-not-leak")

    store = SecretStore(BrokenBackend())
    with pytest.raises(CredentialError) as error:
        getattr(store, operation)(
            "provider/test", *(["unused"] if operation == "set" else [])
        )
    assert "secret-key-that-must-not-leak" not in "".join(
        traceback.format_exception(error.value)
    )


def test_no_plaintext_fallback_when_secret_service_unavailable(monkeypatch):
    def unavailable():
        raise RuntimeError("Secret Service missing")

    monkeypatch.setattr("keyring.backends.SecretService.Keyring", unavailable)
    with pytest.raises(CredentialError, match="never saved as files"):
        SecretStore()


def test_blank_references_and_keys_are_rejected():
    store = SecretStore(MemoryBackend())
    with pytest.raises(CredentialError):
        store.get("")
    with pytest.raises(CredentialError):
        store.set("provider/test", " ")
