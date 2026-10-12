import shlex

import pytest

from inkecho.platform.hotkeys import (
    CUSTOM,
    MEDIA,
    OWN_NAME,
    OWN_PATH,
    GnomeShortcuts,
    ShortcutError,
    accelerator,
)


class Settings:
    def __init__(self):
        self.values = {(MEDIA, "custom-keybindings"): ["/existing/"]}
        self.values[(f"{CUSTOM}:/existing/", "binding")] = "<Primary><Alt>x"

    def command(self, *_):
        return ""

    def get(self, schema, key):
        return self.values.get((schema, key), "")

    def set(self, schema, key, value):
        self.values[(schema, key)] = value

    def reset(self, schema, key):
        self.values.pop((schema, key), None)


@pytest.mark.parametrize(
    "value,result",
    [
        ("Ctrl+Alt+K", "<Control><Alt>k"),
        ("F13", "F13"),
        ("F14", "F14"),
        ("Shift+Super+F14", "<Shift><Super>F14"),
    ],
)
def test_supported_accelerators(value, result):
    assert accelerator(value) == result


@pytest.mark.parametrize(
    "value", ["k", "Space", "Ctrl+Ctrl+K", "Alt+", "F36", "Ctrl+;"]
)
def test_invalid_shortcut_rejected(value):
    with pytest.raises(ShortcutError):
        accelerator(value)


def test_enable_disable_preserves_other_bindings_and_quotes_command():
    settings = Settings()
    adapter = GnomeShortcuts(settings)
    command = ["/usr/bin/python3", "/tmp/own path/'quoted'.py", "--toggle"]
    adapter.enable("F13", command)
    assert settings.get(MEDIA, "custom-keybindings") == ["/existing/", OWN_PATH]
    assert shlex.split(settings.get(adapter.schema, "command")) == command
    adapter.disable()
    assert settings.get(MEDIA, "custom-keybindings") == ["/existing/"]
    assert settings.get(f"{CUSTOM}:/existing/", "binding") == "<Primary><Alt>x"


def test_existing_custom_conflict_changes_nothing():
    settings = Settings()
    before = settings.values.copy()
    with pytest.raises(ShortcutError, match="already assigned"):
        GnomeShortcuts(settings).enable("Ctrl+Alt+X", ["/usr/bin/python3"])
    assert settings.values == before


def test_another_binding_in_owned_path_is_not_overwritten():
    settings = Settings()
    settings.values[(MEDIA, "custom-keybindings")].append(OWN_PATH)
    settings.values[(f"{CUSTOM}:{OWN_PATH}", "name")] = "Unrelated app"
    with pytest.raises(ShortcutError, match="another binding"):
        GnomeShortcuts(settings).enable("F14", ["/usr/bin/python3"])


def test_enable_updates_own_binding_without_duplicate_path():
    settings = Settings()
    adapter = GnomeShortcuts(settings)
    adapter.enable("F13", ["/usr/bin/python3"])
    adapter.enable("F14", ["/usr/bin/python3"])
    assert settings.get(MEDIA, "custom-keybindings").count(OWN_PATH) == 1
    assert settings.get(adapter.schema, "name") == OWN_NAME


def test_status_distinguishes_saved_empty_binding_and_registered_shortcut():
    settings = Settings()
    adapter = GnomeShortcuts(settings)
    command = ["/usr/bin/python3", "--toggle"]
    adapter.enable("F4", command)
    assert "已注册 F4" in adapter.status("F4", command)
    settings.set(adapter.schema, "binding", "")
    assert "未启用" in adapter.status("F4", command)


def test_status_detects_changed_key_or_stale_launcher_without_mutation():
    settings = Settings()
    adapter = GnomeShortcuts(settings)
    command = ["/usr/bin/python3", "--toggle"]
    adapter.enable("F4", command)
    before = settings.values.copy()
    assert "系统快捷键与当前设置不同" in adapter.status("F14", command)
    assert "路径已失效" in adapter.status("F4", ["/missing.AppImage", "--toggle"])
    assert settings.values == before


def test_recent_unrelated_binding_is_preserved():
    class ChangedSettings(Settings):
        def set(self, schema, key, value):
            if key == "name":
                self.values[(MEDIA, "custom-keybindings")].append("/recent/")
            super().set(schema, key, value)

    settings = ChangedSettings()
    GnomeShortcuts(settings).enable("F13", ["/usr/bin/python3"])
    assert settings.get(MEDIA, "custom-keybindings") == [
        "/existing/",
        "/recent/",
        OWN_PATH,
    ]


def test_failed_parent_write_restores_owned_values_and_membership():
    class FailedSettings(Settings):
        failed = False

        def set(self, schema, key, value):
            super().set(schema, key, value)
            if key == "custom-keybindings" and not self.failed:
                self.failed = True
                raise ShortcutError("readback failed")

    settings = FailedSettings()
    adapter = GnomeShortcuts(settings)
    with pytest.raises(ShortcutError):
        adapter.enable("F13", ["/usr/bin/python3"])
    assert settings.get(MEDIA, "custom-keybindings") == ["/existing/"]
    assert all(
        settings.get(adapter.schema, key) == ""
        for key in ("name", "command", "binding")
    )
