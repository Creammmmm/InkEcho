#!/usr/bin/env python3
"""Opt-in live Secret Service check using only a disposable unique credential."""

import argparse
import json
import secrets
import uuid
from pathlib import Path

from inkecho.security import SecretStore


def probe() -> dict:
    store = SecretStore()
    reference = "diagnostic/" + uuid.uuid4().hex
    value = secrets.token_urlsafe(32)
    if store.get(reference) is not None:
        raise RuntimeError("The new diagnostic reference unexpectedly exists.")
    try:
        store.set(reference, value)
        if store.get(reference) != value:
            raise RuntimeError("The saved diagnostic credential could not be verified.")
        store.set(reference, value + "updated")
        if store.get(reference) != value + "updated":
            raise RuntimeError(
                "The updated diagnostic credential could not be verified."
            )
    finally:
        store.delete(reference)
    if store.get(reference) is not None:
        raise RuntimeError("The diagnostic credential was not deleted.")
    return {
        "backend": type(store.backend).__module__ + "." + type(store.backend).__name__,
        "created_unique_disposable_item": True,
        "read_exact_match": True,
        "updated_exact_match": True,
        "deleted": True,
        "unrelated_items_accessed": False,
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
