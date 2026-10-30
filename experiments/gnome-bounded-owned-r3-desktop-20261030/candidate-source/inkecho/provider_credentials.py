"""Credential bundles belong in the local file, never provider parameters."""

import json
from collections.abc import Mapping

from inkecho.security import CredentialError


def encode_credentials(values: Mapping[str, str], fields: tuple[str, ...]) -> str:
    """Validate an exact bundle without exposing any supplied value in errors."""
    if set(values) != set(fields) or not fields:
        raise CredentialError("Complete the required credential fields.")
    if any(
        not isinstance(v, str) or not v.strip() or "\n" in v or "\r" in v
        for v in values.values()
    ):
        raise CredentialError("Credential fields must be nonempty single-line values.")
    return json.dumps(dict(values), separators=(",", ":"))


def decode_credentials(value: str, fields: tuple[str, ...]) -> dict[str, str]:
    """Read an exact secret bundle; retain legacy single API-key values."""
    if fields == ("api_key",) and not value.startswith("{"):
        encode_credentials({"api_key": value}, fields)
        return {"api_key": value}
    try:
        result = json.loads(value)
        if not isinstance(result, dict):
            raise ValueError
        encode_credentials(result, fields)
        return result
    except (ValueError, TypeError, CredentialError):
        raise CredentialError("Saved credentials do not match this service.") from None
