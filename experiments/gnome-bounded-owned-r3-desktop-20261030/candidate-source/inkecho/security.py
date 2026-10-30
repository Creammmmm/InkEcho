"""Plaintext credentials in the selected configuration directory."""

import json
import os
import secrets
import stat
import threading
from pathlib import Path

MAX_BYTES = 1_000_000


class CredentialError(RuntimeError):
    """Safe-to-display credential error without key material or backend details."""


class FileCredentialStore:
    """A private, atomic JSON file; values remain plaintext, not encrypted."""

    def __init__(self, config_root: Path):
        self.root = Path(config_root)
        self.path = self.root / "credentials.json"
        self._lock = threading.RLock()

    @staticmethod
    def _check_reference(reference: str) -> None:
        if (
            not isinstance(reference, str)
            or not reference.strip()
            or len(reference) > 200
        ):
            raise CredentialError("Choose a valid credential reference.")

    @staticmethod
    def _check_value(value: str) -> None:
        if not isinstance(value, str) or not value.strip() or len(value) > 65_536:
            raise CredentialError("Credential must be nonempty text within the limit.")

    def _directory(self) -> int:
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            info = os.fstat(descriptor)
            if info.st_uid != os.getuid():
                raise ValueError("owner")
            os.fchmod(descriptor, 0o700)
            return descriptor
        except Exception:
            os.close(descriptor)
            raise

    @staticmethod
    def _pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate")
            result[key] = value
        return result

    def _read(self, directory: int) -> dict[str, str]:
        try:
            descriptor = os.open(
                "credentials.json",
                os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                dir_fd=directory,
            )
        except FileNotFoundError:
            return {}
        try:
            info = os.fstat(descriptor)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or info.st_nlink != 1
                or info.st_size > MAX_BYTES
            ):
                raise ValueError("credential_file")
            os.fchmod(descriptor, 0o600)
        except Exception:
            os.close(descriptor)
            raise
        with os.fdopen(descriptor, "rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("size")
        data = json.loads(raw, object_pairs_hook=self._pairs)
        if (
            not isinstance(data, dict)
            or set(data) != {"schema_version", "credentials"}
            or type(data["schema_version"]) is not int
            or data["schema_version"] != 1
            or not isinstance(data["credentials"], dict)
        ):
            raise ValueError("schema")
        for reference, value in data["credentials"].items():
            self._check_reference(reference)
            self._check_value(value)
        return data["credentials"]

    def _write(self, directory: int, values: dict[str, str]) -> None:
        data = (
            json.dumps({"schema_version": 1, "credentials": values}, ensure_ascii=False)
            + "\n"
        ).encode()
        if len(data) > MAX_BYTES:
            raise ValueError("size")
        temporary = ".credentials." + secrets.token_hex(16)
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=directory,
        )
        try:
            with os.fdopen(descriptor, "wb") as stream:
                os.fchmod(stream.fileno(), 0o600)
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(
                temporary,
                "credentials.json",
                src_dir_fd=directory,
                dst_dir_fd=directory,
            )
            os.fsync(directory)
        finally:
            try:
                os.unlink(temporary, dir_fd=directory)
            except FileNotFoundError:
                pass

    def _operate(self, reference: str, operation: str, value: str | None = None):
        self._check_reference(reference)
        if operation == "set":
            self._check_value(value)
        with self._lock:
            directory = None
            try:
                directory = self._directory()
                values = self._read(directory)
                if operation == "get":
                    return values.get(reference)
                if operation == "delete":
                    if reference not in values:
                        return None
                    del values[reference]
                else:
                    values[reference] = value
                self._write(directory, values)
            except Exception:
                raise CredentialError(
                    "Cannot access local credentials.json. Check its format, "
                    "ownership and permissions; existing data was not imported."
                ) from None
            finally:
                if directory is not None:
                    os.close(directory)
        return None

    def get(self, reference: str) -> str | None:
        """Read only from this config root; never import an old system keyring."""
        return self._operate(reference, "get")

    def set(self, reference: str, value: str) -> None:
        """Persist a raw API key or existing credential-bundle string."""
        self._operate(reference, "set", value)

    def delete(self, reference: str) -> None:
        """Delete only the named local reference, leaving other providers intact."""
        self._operate(reference, "delete")
