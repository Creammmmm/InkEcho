#!/usr/bin/env python3
"""Synthetic local-file credential roundtrip in a disposable private config."""

import argparse
import json
import secrets
import tempfile
from pathlib import Path

from inkecho.security import FileCredentialStore


def probe() -> dict:
    """Never read the user's config or a system keyring."""
    with tempfile.TemporaryDirectory(prefix="inkecho-credentials-") as directory:
        root = Path(directory) / "config"
        store = FileCredentialStore(root)
        reference = "diagnostic/local"
        value = secrets.token_urlsafe(32)
        assert store.get(reference) is None
        store.set(reference, value)
        assert store.get(reference) == value
        store.set(reference, value + "updated")
        assert store.get(reference) == value + "updated"
        assert store.path.stat().st_mode & 0o777 == 0o600
        assert root.stat().st_mode & 0o777 == 0o700
        store.delete(reference)
        assert store.get(reference) is None
    return {
        "backend": "config_directory_plaintext_json",
        "disposable_private_config": True,
        "read_exact_match": True,
        "updated_exact_match": True,
        "deleted": True,
        "real_credentials_or_keyring_accessed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = json.dumps(probe(), indent=2) + "\n"
    if args.output:
        args.output.write_text(result, encoding="utf-8")
    print(result, end="")


if __name__ == "__main__":
    main()
