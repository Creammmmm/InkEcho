#!/usr/bin/env python3
"""Inspect ONLY disposable InkEcho fixtures, without reading other apps' text."""

import json

import gi

gi.require_version("Atspi", "2.0")
from gi.repository import Atspi  # noqa: E402


def walk(node, depth=0):
    state = node.get_state_set()
    print(
        json.dumps(
            {
                "depth": depth,
                "name": node.get_name(),
                "role": node.get_role_name(),
                "interfaces": node.get_interfaces(),
                "focused": state.contains(Atspi.StateType.FOCUSED),
            },
            ensure_ascii=False,
        )
    )
    for i in range(node.get_child_count()):
        walk(node.get_child_at_index(i), depth + 1)


desktop = Atspi.get_desktop(0)
for i in range(desktop.get_child_count()):
    app = desktop.get_child_at_index(i)
    for j in range(app.get_child_count()):
        window = app.get_child_at_index(j)
        if "InkEcho isolated" in window.get_name():
            walk(window)
