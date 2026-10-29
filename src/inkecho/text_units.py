"""Bounded real-neighbor units; this module sends no events."""


class TextUnitError(ValueError):
    pass


class NeighborPlanner:
    def __init__(self):
        self.pending = ""
        self.closed = False

    def feed(self, text):
        if self.closed:
            raise RuntimeError("closed")
        combined = self.pending + text
        units = []
        offset = 0
        length = len(combined)
        while length - offset >= 2:
            size = 2 if combined[offset] == "\n" else 1
            remaining = length - offset - size
            if not remaining or (remaining == 1 and combined[-1] == "\n"):
                break
            units.append(combined[offset : offset + size])
            offset += size
        self.pending = combined[offset:]
        assert len(self.pending) <= 3
        return units

    def finish(self):
        if self.closed:
            raise RuntimeError("closed")
        self.closed = True
        text, self.pending = self.pending, ""
        if text == "\n":
            raise TextUnitError("standalone LF has no real neighbor")
        return [text] if "\n" in text else list(text)

    def cancel(self):
        self.pending = ""
        self.closed = True


def iter_text_units(text):
    """Lazy complete-text units; caller checks cancellation before each send."""
    if text == "\n":
        raise TextUnitError("standalone LF has no real neighbor")
    offset = 0
    length = len(text)
    while length - offset >= 2:
        size = 2 if text[offset] == "\n" else 1
        remaining = length - offset - size
        if not remaining or (remaining == 1 and text[-1] == "\n"):
            break
        yield text[offset : offset + size]
        offset += size
    pending = text[offset:]
    if "\n" in pending:
        yield pending
    else:
        yield from pending


def text_units(text):
    return list(iter_text_units(text))
