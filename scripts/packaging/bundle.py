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

# These exact source and binary hashes are bound to the documented standalone
# plugin experiments, not to AppImage acceptance or a general support claim.
FCITX5_PLUGIN_SHA256 = (
    "f67c6b5f2cb7ecd7c915c8062efd3b70284c74b97ced4a597d942c4b39594e44"
)
FCITX5_CONF_SHA256 = "44a1386046f2b4df4ea9ba73a43d7caf353e1039f7c14a316cc73e4c928bcb57"
FCITX5_SOURCE_SHA256 = {
    "CMakeLists.txt": (
        "30cf333e2a67288c76b2d5b9dbf9095c8b68cde61c108653c277d8ef46faa850"
    ),
    "focused_context.h": (
        "a87ede2283d65c8a3a47ee3f08e7f2a05c6e107c00237e9abcb28068e3fdc8f2"
    ),
    "inkecho.conf.in": (
        "4911bd724fbd1035fb3d24dbe6e872ceb3e20fc38976a1db8af244ca0c689b0e"
    ),
    "inkecho.cpp": "bea763a76a694503f8e5f605ff7a53be21c9f82c5a4338fff4218ac6714fc783",
    "task_gate.h": "59e2cb07f0d038aad491db45f9f7fa157b21764ae9d1a8a7b67b65addbc8e024",
    "utf8_scalar.h": "1b3567c7b7d64696dacbd310b818a23c38ddb2d0f05b295e9c573fd273ac92ac",
}


def verified_fcitx5_candidate(root):
    """Freeze the experimentally verified candidate; never read compatibility claims."""
    source = root / "native/fcitx5"
    assets = root / "assets/native/fcitx5/x86_64"
    try:
        for name, expected in FCITX5_SOURCE_SHA256.items():
            path = source / name
            if (
                path.is_symlink()
                or hashlib.sha256(path.read_bytes()).hexdigest() != expected
            ):
                raise ValueError("source mismatch")
        library = assets / "libinkecho.so"
        config = assets / "inkecho.conf"
        if library.is_symlink() or config.is_symlink():
            raise ValueError("candidate symlink")
        library_bytes, config_bytes = library.read_bytes(), config.read_bytes()
        if (
            hashlib.sha256(library_bytes).hexdigest() != FCITX5_PLUGIN_SHA256
            or hashlib.sha256(config_bytes).hexdigest() != FCITX5_CONF_SHA256
            or len(library_bytes) < 64
            or library_bytes[:6] != b"\x7fELF\x02\x01"
            or int.from_bytes(library_bytes[16:18], "little") != 3
            or int.from_bytes(library_bytes[18:20], "little") != 62
        ):
            raise ValueError("candidate mismatch")
    except (OSError, ValueError):
        raise SystemExit(
            "Fcitx5 candidate or pinned source mismatch; rebuild and revalidate."
        ) from None
    return library_bytes, config_bytes


def install_fcitx5_candidate(appdir, candidate):
    """Copy the verified data to AppDir; this does not install or activate Fcitx."""
    library, config = candidate
    if (
        hashlib.sha256(library).hexdigest() != FCITX5_PLUGIN_SHA256
        or hashlib.sha256(config).hexdigest() != FCITX5_CONF_SHA256
    ):
        raise ValueError("Fcitx5 candidate changed after verification")
    base = appdir / "usr/share/inkecho/fcitx5/x86_64"
    payload = base / "candidate"
    payload.mkdir(parents=True)
    # Staging rejects group-writable inputs. Do not inherit a permissive umask.
    base.chmod(0o755)
    payload.chmod(0o755)
    (payload / "libinkecho.so").write_bytes(library)
    (payload / "inkecho.conf").write_bytes(config)
    (payload / "libinkecho.so").chmod(0o644)
    (payload / "inkecho.conf").chmod(0o644)
    metadata = {
        "status": "uninstalled-candidate",
        "architecture": "x86_64",
        "os_id": "ubuntu",
        "os_version": "24.04",
        "fcitx5_core_version": "5.1.7",
        "focus_protocol_version": 3,
        "composition_guard_protocol_version": 3,
        "neighbor_batch_protocol_version": 4,
        "legacy_begin_supported": True,
        "files_sha256": {
            "libinkecho.so": FCITX5_PLUGIN_SHA256,
            "inkecho.conf": FCITX5_CONF_SHA256,
        },
        "source_sha256": FCITX5_SOURCE_SHA256,
    }
    (base / "manifest.json").write_text(json.dumps(metadata, indent=2) + "\n")
    (base / "manifest.json").chmod(0o644)
    return metadata


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
