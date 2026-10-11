"""Explicit GNOME custom shortcuts, preserving all unrelated user bindings."""

import ast
import json
import os
import re
import shlex
import subprocess
from collections.abc import Sequence

MEDIA = "org.gnome.settings-daemon.plugins.media-keys"
CUSTOM = "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding"
OWN_PATH = (
    "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/"
    "inkecho-voice-input/"
)
OWN_NAME = "InkEcho voice input"
CONFLICT_SCHEMAS = (
    MEDIA,
    "org.gnome.desktop.wm.keybindings",
    "org.gnome.mutter.keybindings",
    "org.gnome.mutter.wayland.keybindings",
    "org.gnome.shell.keybindings",
)


class ShortcutError(RuntimeError):
    """A shortcut could not be safely configured."""


def accelerator(shortcut: str) -> str:
    """Accept a small readable syntax and preserve extended function keys."""
    modifiers = {
        "ctrl": "Control",
        "control": "Control",
        "primary": "Control",
        "alt": "Alt",
        "shift": "Shift",
        "super": "Super",
        "meta": "Super",
    }
    parts = shortcut.strip().split("+")
    if not parts or not parts[-1]:
        raise ShortcutError("Enter a shortcut such as Ctrl+Alt+K or F13.")
    selected = set()
    for part in parts[:-1]:
        modifier = modifiers.get(part.lower())
        if modifier is None or modifier in selected:
            raise ShortcutError("The shortcut contains invalid or repeated modifiers.")
        selected.add(modifier)
    key = parts[-1]
    if re.fullmatch(r"[a-zA-Z0-9]", key):
        if not selected:
            raise ShortcutError("A letter or number shortcut needs a modifier.")
        key = key.lower()
    elif re.fullmatch(r"[fF](?:[1-9]|[12][0-9]|3[0-5])", key):
        key = key.upper()
    elif key.lower() == "space":
        key = "space"
        if not selected:
            raise ShortcutError("Space needs a modifier.")
    else:
        raise ShortcutError("Use a letter, number, Space, or function key F1–F35.")
    return (
        "".join(f"<{m}>" for m in ("Control", "Alt", "Shift", "Super") if m in selected)
        + key
    )


def canonical(binding: str) -> str:
    parts = re.findall(r"<([^>]+)>", binding)
    key = re.sub(r"<[^>]+>", "", binding)
    try:
        return accelerator("+".join([*parts, key]))
    except ShortcutError:
        return binding


class GSettings:
    def command(self, *arguments: str) -> str:
        try:
            result = subprocess.run(
                ["gsettings", *arguments],
                check=True,
                capture_output=True,
                text=True,
                timeout=3,
            )
        except (OSError, subprocess.SubprocessError):
            raise ShortcutError(
                "GNOME shortcut settings are unavailable or locked."
            ) from None
        return result.stdout.strip()

    def get(self, schema: str, key: str):
        raw = self.command("get", schema, key)
        if raw.startswith("@as "):
            raw = raw[4:]
        try:
            return ast.literal_eval(raw)
        except (ValueError, SyntaxError):
            return raw

    def set(self, schema: str, key: str, value) -> None:
        self.command("set", schema, key, json.dumps(value, ensure_ascii=False))
        if self.get(schema, key) != value:
            raise ShortcutError("GNOME did not save the requested shortcut setting.")

    def reset(self, schema: str, key: str) -> None:
        self.command("reset", schema, key)


class GnomeShortcuts:
    """Constructing this adapter never changes desktop settings.

    Call enable only after the user's explicit Save/Enable action. The application
    must debounce its --toggle IPC command; GNOME owns global key recognition.
    """

    def __init__(self, settings: GSettings | None = None):
        self.settings = settings or GSettings()
        self.schema = f"{CUSTOM}:{OWN_PATH}"

    def conflicts(self, binding: str) -> bool:
        settings = self.settings
        for path in settings.get(MEDIA, "custom-keybindings"):
            if path != OWN_PATH:
                candidate = settings.get(f"{CUSTOM}:{path}", "binding")
                if canonical(candidate) == binding:
                    return True
        available = settings.command("list-schemas").splitlines()
        for schema in CONFLICT_SCHEMAS:
            if schema not in available:
                continue
            for key in settings.command("list-keys", schema).splitlines():
                if key == "custom-keybindings":
                    continue
                values = settings.get(schema, key)
                for value in values if isinstance(values, list) else [values]:
                    if isinstance(value, str) and canonical(value) == binding:
                        return True
        return False

    def enable(self, shortcut: str, command: Sequence[str]) -> str:
        if any(
            not isinstance(item, str) or "\n" in item or "\0" in item
            for item in command
        ):
            raise ShortcutError("The shortcut command contains invalid arguments.")
        if (
            not command
            or not os.path.isabs(command[0])
            or not os.access(command[0], os.X_OK)
        ):
            raise ShortcutError(
                "The shortcut requires an existing absolute executable."
            )
        binding = accelerator(shortcut)
        if self.conflicts(binding):
            raise ShortcutError("This shortcut is already assigned in GNOME settings.")
        settings = self.settings
        paths = settings.get(MEDIA, "custom-keybindings")
        owner = settings.get(self.schema, "name")
        if owner not in ("", OWN_NAME) or (OWN_PATH in paths and owner != OWN_NAME):
            raise ShortcutError("The InkEcho shortcut path belongs to another binding.")
        old = {
            key: settings.get(self.schema, key)
            for key in ("name", "command", "binding")
        }
        try:
            settings.set(self.schema, "name", OWN_NAME)
            settings.set(self.schema, "command", shlex.join(command))
            settings.set(self.schema, "binding", binding)
            # Re-read before merging so an unrelated recent change is retained.
            current = settings.get(MEDIA, "custom-keybindings")
            if OWN_PATH not in current:
                settings.set(MEDIA, "custom-keybindings", [*current, OWN_PATH])
        except ShortcutError:
            if OWN_PATH not in paths:
                latest = settings.get(MEDIA, "custom-keybindings")
                if OWN_PATH in latest:
                    settings.set(
                        MEDIA,
                        "custom-keybindings",
                        [p for p in latest if p != OWN_PATH],
                    )
            for key, value in old.items():
                settings.set(self.schema, key, value)
            raise
        return binding

    def disable(self) -> None:
        settings = self.settings
        current = settings.get(MEDIA, "custom-keybindings")
        if OWN_PATH not in current:
            return
        if settings.get(self.schema, "name") != OWN_NAME:
            raise ShortcutError("The InkEcho shortcut path belongs to another binding.")
        settings.set(MEDIA, "custom-keybindings", [p for p in current if p != OWN_PATH])
        for key in ("name", "command", "binding"):
            settings.reset(self.schema, key)
