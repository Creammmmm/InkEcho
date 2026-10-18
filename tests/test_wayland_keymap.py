import ctypes as c

import pytest

from inkecho.platform.keyboard import KeyboardError
from inkecho.platform.wayland_keymap import Keymap, _library, _symbols, normalize_text


@pytest.fixture
def original_map():
    lib = _library()

    class Names(c.Structure):
        _fields_ = [
            (name, c.c_char_p)
            for name in ("rules", "model", "layout", "variant", "options")
        ]

    lib.xkb_keymap_new_from_names.argtypes = [c.c_void_p, c.POINTER(Names), c.c_uint32]
    lib.xkb_keymap_new_from_names.restype = c.c_void_p
    context = lib.xkb_context_new(0)
    keymap = lib.xkb_keymap_new_from_names(
        context, c.byref(Names(None, None, b"us,de", None, None)), 0
    )
    pointer = lib.xkb_keymap_get_as_string(keymap, 1)
    try:
        yield c.string_at(pointer) + b"\0"
    finally:
        free = c.CDLL(None).free
        free.argtypes, free.restype = [c.c_void_p], None
        free(pointer)
        lib.xkb_keymap_unref(keymap)
        lib.xkb_context_unref(context)


def test_single_slot_mapping_preserves_every_other_key_and_each_group(original_map):
    mapper = Keymap(original_map)
    try:
        assert mapper.groups == 2
        assert mapper.caps_mask != 0
        mapper.lib.xkb_keysym_to_utf32.argtypes = [c.c_uint32]
        mapper.lib.xkb_keysym_to_utf32.restype = c.c_uint32
        for character in ("你", "é", "Ω", "a", "A", " ", "."):
            mapping = mapper.character(character)
            changed = mapper.lib.xkb_keymap_new_from_string(
                mapper.context, mapping.data, 1, 0
            )
            try:
                assert mapping.keycode == 124
                expected = ord(character) | 0x01000000
                assert mapper.lib.xkb_keysym_to_utf32(expected) == ord(character)
                for code in range(8, 256):
                    values = _symbols(mapper.lib, changed, code)
                    if code == 132:
                        assert values == [expected, expected]
                    else:
                        assert values == _symbols(mapper.lib, mapper.pointer, code)
                assert mapper.lib.xkb_keymap_num_layouts(changed) == 2
            finally:
                mapper.lib.xkb_keymap_unref(changed)
    finally:
        mapper.close()


def test_occupied_compatible_slot_is_rejected_without_overwriting(original_map):
    mapper = Keymap(original_map)
    try:
        occupied = mapper.character("你").data
    finally:
        mapper.close()
    with pytest.raises(KeyboardError, match="unsupported_layout"):
        Keymap(occupied)


@pytest.mark.parametrize("text", ["ok😀", "x\ud800", "\t", "\x7f", "\x85"])
def test_complete_result_preflight_rejects_unsupported_unicode_and_controls(text):
    with pytest.raises(KeyboardError, match="unsupported_text"):
        normalize_text(text)


def test_normalization_keeps_bmp_and_converts_line_endings():
    assert normalize_text("中文éΩ\r\n第二行\r") == "中文éΩ\n第二行\n"


def test_newline_uses_dedicated_worker_return_path(original_map):
    mapper = Keymap(original_map)
    try:
        with pytest.raises(KeyboardError, match="unsupported_text"):
            mapper.character("\n")
    finally:
        mapper.close()


def test_malformed_xkb_never_logs_map_contents(capfd):
    with pytest.raises(KeyboardError, match="unsupported_layout"):
        Keymap(b"private-map-marker invalid grammar\0")
    assert "private-map-marker" not in capfd.readouterr().err


def test_runtime_without_direct_latin_unicode_conversion_is_rejected(
    original_map, monkeypatch
):
    from inkecho.platform import wayland_keymap

    library = _library()

    class IncompatibleLibrary:
        def __getattr__(self, name):
            return getattr(library, name)

        def xkb_keysym_to_utf32(self, symbol):
            return 0 if symbol == 0x01000061 else library.xkb_keysym_to_utf32(symbol)

    monkeypatch.setattr(wayland_keymap, "_library", IncompatibleLibrary)
    with pytest.raises(KeyboardError, match="unsupported_layout"):
        Keymap(original_map)


@pytest.mark.parametrize("hint", ["é", "éΩ文"])
def test_prepared_slots_preserve_all_other_keys_and_groups(original_map, hint):
    mapper = Keymap(original_map)
    try:
        mapping = mapper.prepare("中", hint)
        expected = tuple(zip("中" + hint, (124, 89, 189, 194), strict=False))
        assert mapping.prepared == expected
        changed_values = {code + 8: value for value, code in expected}
        changed = mapper.lib.xkb_keymap_new_from_string(
            mapper.context, mapping.data, 1, 0
        )
        try:
            assert mapper.lib.xkb_keymap_num_layouts(changed) == mapper.groups
            for name in ("xkb_keymap_min_keycode", "xkb_keymap_max_keycode"):
                function = getattr(mapper.lib, name)
                function.argtypes, function.restype = [c.c_void_p], c.c_uint32
            minimum = mapper.lib.xkb_keymap_min_keycode(mapper.pointer)
            maximum = mapper.lib.xkb_keymap_max_keycode(mapper.pointer)
            assert mapper.lib.xkb_keymap_min_keycode(changed) == minimum
            assert mapper.lib.xkb_keymap_max_keycode(changed) == maximum
            for code in range(minimum, maximum + 1):
                actual = _symbols(mapper.lib, changed, code)
                if code in changed_values:
                    value = changed_values[code]
                    assert actual == [ord(value) | 0x01000000] * mapper.groups
                else:
                    assert actual == _symbols(mapper.lib, mapper.pointer, code)
                    assert mapper.lib.xkb_keymap_num_layouts_for_key(
                        changed, code
                    ) == mapper.lib.xkb_keymap_num_layouts_for_key(mapper.pointer, code)
                    for group in range(
                        mapper.lib.xkb_keymap_num_layouts_for_key(changed, code)
                    ):
                        assert mapper.lib.xkb_keymap_num_levels_for_key(
                            changed, code, group
                        ) == mapper.lib.xkb_keymap_num_levels_for_key(
                            mapper.pointer, code, group
                        )
                        for level in range(
                            mapper.lib.xkb_keymap_num_levels_for_key(
                                changed, code, group
                            )
                        ):
                            values = []
                            for pointer in (mapper.pointer, changed):
                                symbols = c.c_void_p()
                                count = mapper.lib.xkb_keymap_key_get_syms_by_level(
                                    pointer, code, group, level, c.byref(symbols)
                                )
                                values.append(
                                    list(c.cast(symbols, c.POINTER(c.c_uint32))[:count])
                                    if count
                                    else []
                                )
                            assert values[0] == values[1]
        finally:
            mapper.lib.xkb_keymap_unref(changed)
        assert mapper.prepare("a", "a").prepared == (("a", 124),)
        assert mapper.prepare("a").prepared == (("a", 124),)
    finally:
        mapper.close()


@pytest.mark.parametrize("hint", ["", "abcd", "a\nb", "\n", "😀", 1, False, [], {}])
def test_prepared_mapping_rejects_entire_invalid_hint(original_map, hint):
    mapper = Keymap(original_map)
    try:
        with pytest.raises(KeyboardError, match="unsupported_text"):
            mapper.prepare("a", hint)
        assert mapper.original == original_map
    finally:
        mapper.close()


def test_nonempty_second_slot_is_preserved_and_falls_back_to_one(
    original_map, monkeypatch
):
    from inkecho.platform import wayland_keymap

    mapper = Keymap(original_map)
    try:
        monkeypatch.setattr(wayland_keymap, "LOOKAHEAD_CODES", (38,))  # Existing AC01.
        assert any(_symbols(mapper.lib, mapper.pointer, 38))
        mapping = mapper.prepare("中", "é")
        assert mapping.prepared == (("中", 124),)
        changed = mapper.lib.xkb_keymap_new_from_string(
            mapper.context, mapping.data, 1, 0
        )
        try:
            assert _symbols(mapper.lib, changed, 38) == _symbols(
                mapper.lib, mapper.pointer, 38
            )
        finally:
            mapper.lib.xkb_keymap_unref(changed)
    finally:
        mapper.close()


def test_four_slots_deduplicate_and_omit_nonempty_or_missing_slots(
    original_map, monkeypatch
):
    from inkecho.platform import wayland_keymap

    mapper = Keymap(original_map)
    try:
        assert mapper.prepare("中", "中éé").prepared == (("中", 124), ("é", 89))
        monkeypatch.setattr(wayland_keymap, "LOOKAHEAD_CODES", (38, 0, 197, 202))
        mapping = mapper.prepare("中", "éΩ文")
        assert mapping.prepared == (("中", 124), ("é", 189), ("Ω", 194))
        assert len(mapping.prepared) <= 4
    finally:
        mapper.close()
