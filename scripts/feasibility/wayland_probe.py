#!/usr/bin/env python3
"""Read/test only the explicitly named disposable native-Wayland fixtures.

Run with the system Python (python3-gi and gir1.2-atspi-2.0 are required).
Transport mode deliberately reports, rather than claims to validate, focus safety.
It is a laboratory capability probe, never the application's injection backend.
"""

import argparse
import json

import gi

gi.require_version("Atspi", "2.0")
from gi.repository import Atspi  # noqa: E402

SAMPLE = "你好 InkEcho，世界！ café Ω 😀\n第二行。"
TITLES = {
    "editor": "InkEcho-isolated-wayland.txt",
    "browser": "InkEcho isolated browser",
    "terminal": "InkEcho isolated terminal",
}


def descendants(node):
    if node is None:
        return
    yield node
    for index in range(node.get_child_count()):
        yield from descendants(node.get_child_at_index(index))


def targets(kind):
    desktop = Atspi.get_desktop(0)
    for index in range(desktop.get_child_count()):
        app = desktop.get_child_at_index(index)
        for window_index in range(app.get_child_count()):
            window = app.get_child_at_index(window_index)
            if TITLES[kind] not in window.get_name():
                continue
            for node in descendants(window):
                role = node.get_role_name()
                if (
                    kind == "browser"
                    and node.get_name() != "Disposable Unicode input target"
                ):
                    continue
                if kind == "editor" and role != "text":
                    continue
                if kind == "terminal" and role != "terminal":
                    continue
                if "Text" in node.get_interfaces():
                    yield node


def inspect(kind, transport=False):
    records = []
    for node in targets(kind):
        interfaces = node.get_interfaces()
        focused = node.get_state_set().contains(Atspi.StateType.FOCUSED)
        record = {"target": kind, "interfaces": interfaces, "focused": focused}
        if "EditableText" not in interfaces:
            record["result"] = "unsupported: target has no EditableText interface"
        elif transport:
            # Never overwrite contents, even in a fixture with a reused title.
            if Atspi.Text.get_character_count(node):
                record["result"] = "refused: fixture must be empty"
            else:
                inserted = Atspi.EditableText.insert_text(
                    node, 0, SAMPLE, len(SAMPLE.encode())
                )
                received = Atspi.Text.get_text(node, 0, -1)
                record.update(insert_returned=inserted, exact_match=received == SAMPLE)
                record["result"] = "transport only; production focus gate not exercised"
        else:
            record["result"] = "editable capability present; insertion not attempted"
        records.append(record)
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", choices=TITLES)
    parser.add_argument(
        "--transport", action="store_true", help="Insert into an EMPTY own fixture"
    )
    args = parser.parse_args()
    records = inspect(args.target, args.transport)
    print(json.dumps(records, ensure_ascii=False, indent=2))
    return 0 if records else 1


if __name__ == "__main__":
    raise SystemExit(main())
