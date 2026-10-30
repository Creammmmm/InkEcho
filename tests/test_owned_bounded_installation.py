"""Exact new/legacy asset sets and explicit upgrade safety, without GNOME calls."""

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from inkecho.platform import owned_extension, owned_installation
from inkecho.platform.ibus_extension import ExtensionError
from inkecho.platform.output_router import OutputRouterError


def installed(tmp_path, monkeypatch, *, legacy=False):
    root = tmp_path / "extension"
    root.mkdir(mode=0o700)
    source = Path(owned_extension.__file__).with_name("ibus_owned_candidate")
    old = {}
    for name in owned_installation.FILES:
        data = (source / name).read_bytes()
        # Two changed members ensure a mixed set cannot match either complete set.
        if name in {"extension.js", "owned_gate.js"}:
            data = b"old fixture member\n"
        old[name] = {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
        data = data if legacy else (source / name).read_bytes()
        target = root / name
        target.write_bytes(data)
        target.chmod(0o600)
    monkeypatch.setattr(owned_installation, "LEGACY_FILES", old)
    monkeypatch.setattr(owned_extension, "installed_directory", lambda: root)
    monkeypatch.setattr(
        owned_extension,
        "verified_installation",
        lambda: owned_installation.verified_installation(root),
    )
    return root, source


def runner(root, calls):
    def run(arguments, **_):
        calls.append(arguments)
        return SimpleNamespace(returncode=0, stdout=f"Path: {root}\n", stderr="")

    return run


@pytest.mark.parametrize("legacy", [False, True])
def test_complete_set_is_detected_but_only_current_can_be_enabled(
    tmp_path, monkeypatch, legacy
):
    root, source = installed(tmp_path, monkeypatch, legacy=legacy)
    assert owned_installation.verified_installation(root)
    calls = []
    manager = owned_extension.OwnedExtensionManager(
        source=source, runner=runner(root, calls)
    )
    if legacy:
        before = {p.name: p.read_bytes() for p in root.iterdir()}
        for action in [manager.enable, manager.install]:
            with pytest.raises(ExtensionError, match="旧版"):
                action()
        assert all(c[1] != "enable" and c[1] != "install" for c in calls)
        assert before == {p.name: p.read_bytes() for p in root.iterdir()}
        assert "旧版" in manager.status()
    else:
        manager.enable()
        assert calls[-1][1] == "enable"
        with pytest.raises(ExtensionError, match="已安装"):
            manager.install()
        assert not any(c[1] == "install" for c in calls)


@pytest.mark.parametrize("change", ["mixed", "symlink", "writable"])
def test_invalid_assets_never_enable_or_install(tmp_path, monkeypatch, change):
    root, source = installed(tmp_path, monkeypatch, legacy=True)
    target = root / "owned_gate.js"
    if change == "mixed":
        target.write_bytes((source / target.name).read_bytes())
    elif change == "symlink":
        target.unlink()
        target.symlink_to(source / target.name)
    else:
        target.chmod(0o666)
    with pytest.raises(OutputRouterError, match="input_capability_unknown"):
        owned_installation.verified_installation(root)
    calls = []
    manager = owned_extension.OwnedExtensionManager(
        source=source, runner=runner(root, calls)
    )
    for action in [manager.enable, manager.install]:
        with pytest.raises(ExtensionError):
            action()
    assert not any(c[1] in {"enable", "install"} for c in calls)


def test_manifest_is_exact_current_asset_set():
    import json

    root = Path(owned_extension.__file__).parent
    assert (
        json.loads((root / "owned_asset_manifest.json").read_text())
        == owned_installation.FILES
    )
    assert owned_installation.FILES != owned_installation.LEGACY_FILES
    owned_extension.OwnedExtensionManager._verified(root / "ibus_owned_candidate")
