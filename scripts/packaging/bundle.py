"""Collect runtime wheels, selected Qt ELF dependencies and pinned system assets."""

import hashlib
import importlib.metadata as metadata
import json
import re
import shutil
import subprocess
import urllib.request
from pathlib import Path

from packaging.requirements import Requirement

QT_MODULES = {"Core", "Gui", "Widgets", "Network", "Multimedia", "Svg", "DBus"}
QT_PLUGINS = {
    "platforms",
    "platforminputcontexts",
    "platformthemes",
    "imageformats",
    "iconengines",
    "multimedia",
    "tls",
    "networkinformation",
    "xcbglintegrations",
    "wayland-decoration-client",
    "wayland-graphics-integration-client",
    "wayland-shell-integration",
}


def runtime_distributions():
    pending = [Requirement(item) for item in metadata.requires("inkecho") or []]
    found = {}
    while pending:
        requirement = pending.pop()
        if requirement.marker and not requirement.marker.evaluate({"extra": ""}):
            continue
        distribution = metadata.distribution(requirement.name)
        name = distribution.metadata["Name"]
        if name in found:
            continue
        found[name] = distribution
        pending.extend(Requirement(item) for item in distribution.requires or [])
    return found


def collect_python(packages):
    distributions = runtime_distributions()
    for distribution in distributions.values():
        for relative in distribution.files or []:
            # Console scripts and editable-install links are not application modules.
            if ".." in relative.parts or "__pycache__" in relative.parts:
                continue
            source = Path(distribution.locate_file(relative))
            if source.is_file():
                target = packages / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
    return {name: dist.version for name, dist in sorted(distributions.items())}


def needed(path):
    result = subprocess.run(
        ["readelf", "-d", str(path)], capture_output=True, text=True, check=True
    )
    return re.findall(r"\(NEEDED\).*?\[(.+?)\]", result.stdout)


def trim_qt(packages):
    qt = packages / "PySide6"
    for path in qt.glob("Qt*"):
        if path.name == "Qt":
            continue
        if not any(
            path.name in {f"Qt{name}.abi3.so", f"Qt{name}.pyi"} for name in QT_MODULES
        ):
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
    for name in ("include", "typesystems", "glue", "scripts"):
        shutil.rmtree(qt / name, ignore_errors=True)
    for child in (qt / "Qt").iterdir():
        if child.name not in {"lib", "plugins"}:
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    plugins = qt / "Qt/plugins"
    for child in plugins.iterdir():
        if child.name not in QT_PLUGINS:
            shutil.rmtree(child)
    for plugin in (plugins / "platforms").iterdir():
        if plugin.name not in {"libqxcb.so", "libqwayland.so", "libqoffscreen.so"}:
            plugin.unlink()
    libraries = qt / "Qt/lib"
    pending = list(qt.glob("*.so*")) + list(plugins.rglob("*.so"))
    keep = set()
    while pending:
        path = pending.pop()
        for soname in needed(path):
            candidate = libraries / soname
            if candidate.exists() and soname not in keep:
                keep.add(soname)
                pending.append(candidate)
    for child in libraries.iterdir():
        if child.name not in keep:
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    return sorted(keep)


def system_assets(root, appdir):
    manifest = json.loads((root / "scripts/packaging/system-deps.json").read_text())
    cache = root / "build/system-deps"
    cache.mkdir(parents=True, exist_ok=True)
    destination = appdir / "usr/lib/inkecho"
    destination.mkdir(parents=True, exist_ok=True)
    notices = appdir / "usr/share/doc/inkecho/system"
    for item in manifest:
        archive = cache / item["filename"]
        if not archive.exists():
            urllib.request.urlretrieve(item["url"], archive)
        if hashlib.sha256(archive.read_bytes()).hexdigest() != item["sha256"]:
            raise SystemExit(f"Checksum mismatch: {archive.name}")
        extracted = cache / (archive.name + ".extracted")
        if extracted.exists():
            shutil.rmtree(extracted)
        subprocess.run(["dpkg-deb", "-x", str(archive), str(extracted)], check=True)
        for library in extracted.glob("usr/lib/x86_64-linux-gnu/*.so*"):
            shutil.copy2(library, destination / library.name)
        for copyright_file in extracted.glob("usr/share/doc/*/copyright"):
            target = notices / copyright_file.parent.name
            target.mkdir(parents=True, exist_ok=True)
            shutil.copy2(copyright_file, target / "copyright")
        font = extracted / "usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
        if font.exists():
            target = appdir / "usr/share/fonts"
            target.mkdir(parents=True, exist_ok=True)
            shutil.copy2(font, target / font.name)
    return manifest


def write_inventory(appdir, details):
    details["files"] = {
        str(path.relative_to(appdir)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(appdir.rglob("*"))
        if path.is_file() and not path.is_symlink()
    }
    details["symlinks"] = {
        str(path.relative_to(appdir)): str(path.readlink())
        for path in sorted(appdir.rglob("*"))
        if path.is_symlink()
    }
    destination = appdir / "usr/share/doc/inkecho/inventory.json"
    destination.write_text(json.dumps(details, indent=2, sort_keys=True) + "\n")
