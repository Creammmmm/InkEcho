"""Shared normalization for text sent to desktop output backends."""


def normalize_newlines(text: str) -> str:
    """Translate CRLF and standalone CR to a single LF each."""
    return text.replace("\r\n", "\n").replace("\r", "\n")
