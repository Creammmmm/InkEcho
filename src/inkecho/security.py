"""Store credentials only in the operating system's Secret Service."""

from typing import Protocol


class CredentialError(RuntimeError):
    """Safe-to-display credential error without backend details or key material."""


class CredentialBackend(Protocol):
    def get_password(self, service: str, username: str) -> str | None: ...
    def set_password(self, service: str, username: str, password: str) -> None: ...
    def delete_password(self, service: str, username: str) -> None: ...


class SecretStore:
    SERVICE = "io.github.Creammmmm.InkEcho"

    def __init__(self, backend: CredentialBackend | None = None):
        if backend is None:
            try:
                from keyring.backends.SecretService import Keyring

                backend = Keyring()
                # Force availability detection now; never select a fallback backend.
                if backend.priority <= 0:
                    raise CredentialError("System credential storage is unavailable.")
            except Exception:
                raise CredentialError(
                    "System credential storage is unavailable. Unlock the keyring "
                    "or start a desktop Secret Service. Keys are never saved as files."
                ) from None
        self.backend = backend

    @staticmethod
    def _check_reference(reference: str) -> None:
        if (
            not isinstance(reference, str)
            or not reference.strip()
            or len(reference) > 200
        ):
            raise CredentialError("Choose a valid credential reference.")

    def get(self, reference: str) -> str | None:
        self._check_reference(reference)
        try:
            return self.backend.get_password(self.SERVICE, reference)
        except Exception:
            raise CredentialError(
                "Cannot read the credential from the system keyring."
            ) from None

    def set(self, reference: str, value: str) -> None:
        self._check_reference(reference)
        if not isinstance(value, str) or not value.strip():
            raise CredentialError("API key must not be empty.")
        try:
            self.backend.set_password(self.SERVICE, reference, value)
        except Exception:
            raise CredentialError(
                "Cannot save the credential in the system keyring."
            ) from None

    def delete(self, reference: str) -> None:
        self._check_reference(reference)
        if self.get(reference) is None:
            return
        try:
            self.backend.delete_password(self.SERVICE, reference)
        except Exception:
            raise CredentialError(
                "Cannot delete the credential from the system keyring."
            ) from None
