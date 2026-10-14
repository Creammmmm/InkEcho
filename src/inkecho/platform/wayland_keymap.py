"""Bounded XKB map transformations for a private GNOME keyboard transaction.

Only an originally empty, Chromium-compatible physical keycode is used. This
module has no display connection, focus query, clipboard or input-method API.
"""

import ctypes as c
import re
from dataclasses import dataclass

from inkecho.platform.keyboard import KeyboardError

MAX_MAP_BYTES = 4_000_000
# AE13 is the empty INTL_YEN slot exercised with native GTK and Chromium.
COMPATIBLE_CODES = (132,)


def normalize_text(text: str) -> str:
    """Reject the complete unsupported result before any output is started."""
    if not isinstance(text, str):
        raise KeyboardError("unsupported_text")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if any(
        ord(char) > 0xFFFF
        or 0xD800 <= ord(char) <= 0xDFFF
        or (ord(char) < 32 and char != "\n")
        or 0x7F <= ord(char) < 0xA0
        for char in text
    ):
        raise KeyboardError("unsupported_text")
    return text


def _library():
    try:
        lib = c.CDLL("libxkbcommon.so.0")
    except OSError:
        raise KeyboardError("display_unavailable") from None
    p, u = c.c_void_p, c.c_uint32
    specs = {
        "xkb_context_new": ([u], p),
        "xkb_context_unref": ([p], None),
        "xkb_context_set_log_fn": ([p, p], None),
        "xkb_keymap_new_from_string": ([p, c.c_char_p, u, u], p),
        "xkb_keymap_unref": ([p], None),
        "xkb_keymap_num_layouts": ([p], u),
        "xkb_keymap_key_get_name": ([p, u], c.c_char_p),
        "xkb_keymap_num_layouts_for_key": ([p, u], u),
        "xkb_keymap_num_levels_for_key": ([p, u, u], u),
        "xkb_keymap_key_get_syms_by_level": ([p, u, u, u, c.POINTER(p)], c.c_int),
        "xkb_keymap_mod_get_index": ([p, c.c_char_p], u),
        "xkb_keymap_get_as_string": ([p, u], p),
        "xkb_keysym_to_utf32": ([u], u),
    }
    for name, (arguments, result) in specs.items():
        function = getattr(lib, name)
        function.argtypes, function.restype = arguments, result
    return lib


def _symbols(lib, keymap, code):
    values = []
    for group in range(lib.xkb_keymap_num_layouts_for_key(keymap, code)):
        for level in range(lib.xkb_keymap_num_levels_for_key(keymap, code, group)):
            pointer = c.c_void_p()
            count = lib.xkb_keymap_key_get_syms_by_level(
                keymap, code, group, level, c.byref(pointer)
            )
            if count > 0:
                values.extend(c.cast(pointer, c.POINTER(c.c_uint32))[:count])
    return values


def _section_end(text):
    match = re.search(r'\bxkb_symbols(?:\s+"(?:[^"\\]|\\.)*")?\s*\{', text)
    if match is None:
        raise KeyboardError("unsupported_layout")
    depth, quoted, escaped = 1, False, False
    for index in range(match.end(), len(text)):
        char = text[index]
        if escaped:
            escaped = False
        elif quoted and char == "\\":
            escaped = True
        elif char == '"':
            quoted = not quoted
        elif not quoted:
            depth += (char == "{") - (char == "}")
            if depth == 0:
                return index
    raise KeyboardError("unsupported_layout")


@dataclass(frozen=True)
class KeyMapping:
    data: bytes
    keycode: int


class Keymap:
    """A transaction's immutable original map and verified empty keycode."""

    def __init__(self, data: bytes):
        if (
            not isinstance(data, bytes)
            or not 1 < len(data) <= MAX_MAP_BYTES
            or not data.endswith(b"\0")
            or b"\0" in data[:-1]
        ):
            raise KeyboardError("unsupported_layout")
        self.original = data
        self.lib = _library()
        self.context = self.lib.xkb_context_new(0)
        self.pointer = None
        self._log_callback = c.CFUNCTYPE(
            None, c.c_void_p, c.c_int, c.c_char_p, c.c_void_p
        )(lambda *_args: None)
        if not self.context:
            raise KeyboardError("display_unavailable")
        self.lib.xkb_context_set_log_fn(
            self.context, c.cast(self._log_callback, c.c_void_p)
        )
        try:
            # libxkbcommon deliberately preserves direct Unicode encodings for
            # Latin-1 as well. Refuse an incompatible runtime before output.
            if any(
                self.lib.xkb_keysym_to_utf32(0x01000000 | point) != point
                for point in (*range(32, 127), *range(160, 256))
            ):
                raise KeyboardError("unsupported_layout")
            self.pointer = self.lib.xkb_keymap_new_from_string(self.context, data, 1, 0)
            if not self.pointer:
                raise KeyboardError("unsupported_layout")
            self.groups = self.lib.xkb_keymap_num_layouts(self.pointer)
            if not 1 <= self.groups <= 4:
                raise KeyboardError("unsupported_layout")
            caps = self.lib.xkb_keymap_mod_get_index(self.pointer, b"Lock")
            if caps >= 32:
                raise KeyboardError("unsupported_layout")
            self.caps_mask = 1 << caps
            self.slot = None
            for code in COMPATIBLE_CODES:
                name = self.lib.xkb_keymap_key_get_name(self.pointer, code)
                if name and not any(_symbols(self.lib, self.pointer, code)):
                    self.slot, self.name = code, name.decode("ascii")
                    break
            if self.slot is None or not re.fullmatch(r"[A-Za-z0-9_]+", self.name):
                raise KeyboardError("unsupported_layout")
            self.text = data[:-1].decode("utf-8")
            self.end = _section_end(self.text)
        except BaseException:
            self.close()
            raise

    def character(self, character: str) -> KeyMapping:
        """Return a canonical map assigning the same one-level key in all groups."""
        if (
            normalize_text(character) != character
            or len(character) != 1
            or character == "\n"
        ):
            raise KeyboardError("unsupported_text")
        # Direct Unicode keysyms avoid ordinary Latin keyvals being interpreted
        # as new composition in the verified host libpinyin configuration.
        symbol = ord(character) | 0x01000000
        if self.lib.xkb_keysym_to_utf32(symbol) != ord(character):
            raise KeyboardError("unsupported_text")
        entries = ", ".join(
            f'type[Group{group}]="ONE_LEVEL", symbols[Group{group}]=[0x{symbol:08x}]'
            for group in range(1, self.groups + 1)
        )
        addition = f"key <{self.name}> {{ {entries} }};\n"
        raw = (
            self.text[: self.end] + addition + self.text[self.end :]
        ).encode() + b"\0"
        candidate = self.lib.xkb_keymap_new_from_string(self.context, raw, 1, 0)
        if not candidate:
            raise KeyboardError("unsupported_layout")
        serialized = None
        try:
            if self.lib.xkb_keymap_num_layouts(candidate) != self.groups or set(
                _symbols(self.lib, candidate, self.slot)
            ) != {symbol}:
                raise KeyboardError("unsupported_layout")
            serialized = self.lib.xkb_keymap_get_as_string(candidate, 1)
            if not serialized:
                raise KeyboardError("unsupported_layout")
            result = c.string_at(serialized) + b"\0"
            if len(result) > MAX_MAP_BYTES:
                raise KeyboardError("unsupported_layout")
            return KeyMapping(result, self.slot - 8)
        finally:
            if serialized:
                free = c.CDLL(None).free
                free.argtypes, free.restype = [c.c_void_p], None
                free(serialized)
            self.lib.xkb_keymap_unref(candidate)

    def close(self):
        if self.pointer:
            self.lib.xkb_keymap_unref(self.pointer)
            self.pointer = None
        if self.context:
            self.lib.xkb_context_unref(self.context)
            self.context = None
