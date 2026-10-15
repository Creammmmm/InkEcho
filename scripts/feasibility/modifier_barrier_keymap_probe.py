"""Pure libxkbcommon experiment; sends no desktop keys and opens no connection."""

import ctypes as c
import json
import re

from inkecho.platform.wayland_keymap import Keymap, _library, _section_end


def modifier_barrier_mapping(mapper, mapping):
    """Add a test-only momentary Mod2 action; leave symbols and locks intact."""
    text = mapping.data[:-1].decode()
    groups = ", ".join(
        f"actions[Group{group}]=[SetMods(modifiers=Mod2,clearLocks=false)]"
        for group in range(1, mapper.groups + 1)
    )
    index = _section_end(text)
    candidate = (
        text[:index] + f"key <{mapper.name}> {{ {groups} }};" + text[index:]
    ).encode()
    lib = mapper.lib
    compiled = lib.xkb_keymap_new_from_string(mapper.context, candidate, 1, 0)
    if not compiled:
        raise RuntimeError("experimental_action_map_did_not_compile")
    pointer = None
    try:
        pointer = lib.xkb_keymap_get_as_string(compiled, 1)
        if not pointer:
            raise RuntimeError("experimental_action_map_did_not_serialize")
        return c.string_at(pointer) + b"\0"
    finally:
        if pointer:
            free = c.CDLL(None).free
            free.argtypes = [c.c_void_p]
            free(pointer)
        lib.xkb_keymap_unref(compiled)


def run():
    lib = _library()
    p, u = c.c_void_p, c.c_uint32

    class Names(c.Structure):
        _fields_ = [
            (name, c.c_char_p)
            for name in ("rules", "model", "layout", "variant", "options")
        ]

    for name, args, result in (
        ("xkb_keymap_new_from_names", [p, c.POINTER(Names), u], p),
        ("xkb_state_new", [p], p),
        ("xkb_state_unref", [p], None),
        ("xkb_state_update_key", [p, u, u], u),
        ("xkb_state_update_mask", [p, u, u, u, u, u, u], u),
        ("xkb_state_serialize_mods", [p, u], u),
        ("xkb_state_serialize_layout", [p, u], u),
        ("xkb_state_key_get_utf32", [p, u], u),
    ):
        function = getattr(lib, name)
        function.argtypes, function.restype = args, result
    context = lib.xkb_context_new(0)
    original = lib.xkb_keymap_new_from_names(
        context, c.byref(Names(None, None, b"us,de", None, None)), 0
    )
    pointer = lib.xkb_keymap_get_as_string(original, 1)
    mapper = None
    try:
        mapper = Keymap(c.string_at(pointer) + b"\0")
        data = modifier_barrier_mapping(mapper, mapper.character("你"))
        compiled = lib.xkb_keymap_new_from_string(context, data, 1, 0)
        mod2_index = lib.xkb_keymap_mod_get_index(compiled, b"Mod2")
        if mod2_index >= 32:
            raise RuntimeError("mod2_unavailable")
        mod2 = 1 << mod2_index
        report = {
            "passed": True,
            "pure_library_only": True,
            "desktop_keys_sent": 0,
            "mod2_mask": mod2,
            "cases": [],
        }
        try:
            for locked in (0, mod2):
                for group in (0, 1):
                    state = lib.xkb_state_new(compiled)
                    try:
                        lib.xkb_state_update_mask(state, 0, 0, locked, 0, 0, group)
                        snapshots = []
                        for pressed in (None, True, False):
                            if pressed is not None:
                                lib.xkb_state_update_key(state, 132, int(pressed))
                            snapshots.append(
                                {
                                    "depressed": lib.xkb_state_serialize_mods(state, 1),
                                    "latched": lib.xkb_state_serialize_mods(state, 2),
                                    "locked": lib.xkb_state_serialize_mods(state, 4),
                                    "effective": lib.xkb_state_serialize_mods(state, 8),
                                    "group": lib.xkb_state_serialize_layout(state, 128),
                                    "character_utf32": lib.xkb_state_key_get_utf32(
                                        state, 132
                                    ),
                                }
                            )
                        passed = [item["depressed"] for item in snapshots] == [
                            0,
                            mod2,
                            0,
                        ] and all(
                            item["latched"] == 0
                            and item["locked"] == locked
                            and item["group"] == group
                            and item["character_utf32"] == ord("你")
                            for item in snapshots
                        )
                        report["cases"].append(
                            {
                                "initial_locked": locked,
                                "initial_group": group,
                                "states": snapshots,
                                "passed": passed,
                            }
                        )
                        report["passed"] &= passed
                    finally:
                        lib.xkb_state_unref(state)
        finally:
            lib.xkb_keymap_unref(compiled)
        key = re.search(r"key <AE13>\s*\{.*?\};", data.decode(), re.S)
        report["experimental_ae13_definition"] = key.group(0) if key else None
        print(json.dumps(report, sort_keys=True))
        return report["passed"]
    finally:
        if mapper:
            mapper.close()
        free = c.CDLL(None).free
        free.argtypes = [p]
        free(pointer)
        lib.xkb_keymap_unref(original)
        lib.xkb_context_unref(context)


if __name__ == "__main__":
    raise SystemExit(0 if run() else 1)
