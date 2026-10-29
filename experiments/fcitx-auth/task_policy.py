"""Offline authorization-state model; not connected to the Fcitx addon.

A trustworthy provisioning channel is deliberately assumed, not implemented.
This model does not establish a security boundary against same-user processes.
"""

import hmac
import math
import time


class TaskPolicy:
    """One pre-authorized task; rejected calls never modify an active task."""

    def __init__(self, sender, token, deadline, *, clock=time.monotonic):
        if not isinstance(sender, str) or not sender.startswith(":"):
            raise ValueError("invalid sender")
        if not isinstance(token, bytes) or len(token) != 32:
            raise ValueError("invalid token")
        if not math.isfinite(deadline):
            raise ValueError("invalid deadline")
        self._sender = sender
        self._token = token
        self._deadline = deadline
        self._clock = clock
        self._next = 0
        self._active = True
        self._inflight = False

    def cancel(self):
        """Called by the trusted owner; cannot retract an in-flight delivery."""
        self._active = False

    def commit(self, sender, token, sequence, scalar, deliver):
        if (
            not self._active
            or self._inflight
            or sender != self._sender
            or not isinstance(token, bytes)
            or not hmac.compare_digest(token, self._token)
            or type(sequence) is not int
            or sequence != self._next
        ):
            return False
        if self._clock() >= self._deadline:
            self._active = False
            return False
        if not isinstance(scalar, str) or len(scalar) != 1:
            self._active = False
            return False
        value = ord(scalar)
        if (
            (value < 0x20 and scalar not in "\n\t")
            or 0x7F <= value <= 0x9F
            or 0xD800 <= value <= 0xDFFF
        ):
            self._active = False
            return False
        # Consume before attempting delivery; no sequence can be retried.
        self._next += 1
        self._inflight = True
        try:
            delivered = deliver(scalar)
            if delivered is not True:
                self._active = False
                return False
            return True
        except BaseException:
            self._active = False
            return False
        finally:
            self._inflight = False
