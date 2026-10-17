"""Packaging selection/version gates; no image builds, containers or network."""

import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def builder(monkeypatch):
    scripts = ROOT / "scripts/packaging"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location(
        "dual_ubuntu_builder_test", scripts / "build_appimage.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def metadata(tmp_path):
    (tmp_path / "src/inkecho").mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text('[project]\nversion="0.1.0a13"\n')
    (tmp_path / "src/inkecho/__init__.py").write_text('__version__="0.1.0a13"\n')
    (tmp_path / "uv.lock").write_text(
        '[[package]]\nname="inkecho"\nversion="0.1.0a13"\n'
    )
    return tmp_path


def test_version_gate_reads_literals_without_importing_application(builder, metadata):
    source = metadata / "src/inkecho/__init__.py"
    source.write_text(
        'raise RuntimeError("must not execute")\n__version__="0.1.0a13"\n'
    )
    assert builder.project_version(metadata) == "0.1.0a13"


@pytest.mark.parametrize(
    "name,contents",
    [
        ("pyproject.toml", '[project]\nversion="0.1.0a12"\n'),
        ("src/inkecho/__init__.py", '__version__="0.1.0a12"\n'),
        ("uv.lock", '[[package]]\nname="inkecho"\nversion="0.1.0a12"\n'),
        ("src/inkecho/__init__.py", "__version__=get_version()\n"),
        ("src/inkecho/__init__.py", '__version__="0.1.0a13"\n__version__="0.1.0a13"\n'),
        ("uv.lock", '[[package]]\nname="other"\nversion="0.1.0a13"\n'),
        ("uv.lock", '[[package]]\nname="inkecho"\n'),
        ("uv.lock", 'package=["inkecho"]\n'),
        ("uv.lock", '[package]\nname="inkecho"\nversion="0.1.0a13"\n'),
        ("pyproject.toml", "[project\n"),
    ],
)
def test_version_mismatch_fails_before_download_or_old_appdir_removal(
    builder, metadata, monkeypatch, name, contents
):
    (metadata / name).write_text(contents)
    appdir = metadata / "build/InkEcho.AppDir"
    appdir.mkdir(parents=True)
    sentinel = appdir / "old-build-marker"
    sentinel.write_bytes(b"preserve existing build")
    monkeypatch.setattr(builder, "ROOT", metadata)
    monkeypatch.setattr(builder, "APPDIR", appdir)
    monkeypatch.setattr(builder, "RUNTIME", metadata / "uncreated/runtime")
    monkeypatch.setattr(
        builder.urllib.request,
        "urlretrieve",
        lambda *_a: pytest.fail("version rejection must precede download"),
    )
    monkeypatch.setattr(
        builder.shutil,
        "rmtree",
        lambda *_a, **_k: pytest.fail("must preserve old AppDir"),
    )
    with pytest.raises(SystemExit, match="Version metadata must agree"):
        builder.main()
    assert sentinel.read_bytes() == b"preserve existing build"
    assert not (metadata / "uncreated").exists()


def test_duplicate_locked_application_version_is_rejected(builder, metadata):
    lock = metadata / "uv.lock"
    lock.write_text(lock.read_text() * 2)
    with pytest.raises(SystemExit, match="Version metadata must agree"):
        builder.project_version(metadata)


@pytest.fixture
def userspace_check(tmp_path):
    # Copy only this shell entry into a disposable repository-shaped directory.
    # A local Docker double records argv and creates nine synthetic PNG markers.
    scripts = tmp_path / "scripts/packaging"
    scripts.mkdir(parents=True)
    (tmp_path / "build").mkdir()
    entry = scripts / "check_ubuntu24.sh"
    shutil.copyfile(ROOT / "scripts/packaging/check_ubuntu24.sh", entry)
    commands = tmp_path / "docker-argv.jsonl"
    binaries = tmp_path / "bin"
    binaries.mkdir()
    docker = binaries / "docker"
    docker.write_text(
        "#!/usr/bin/python3\nimport json,os,sys\nfrom pathlib import Path\n"
        "with open(os.environ['FAKE_DOCKER_COMMANDS'],'a') as out:\n"
        " out.write(json.dumps(sys.argv[1:])+'\\n')\n"
        "if sys.argv[1]=='run':\n"
        " output=next(arg.split(':',1)[0] for arg in sys.argv[2:] "
        "if arg.endswith(':/output'))\n"
        " for number in range(9):\n"
        "  (Path(output)/f'page-{number}.png').write_bytes(b'fixture-only')\n"
    )
    docker.chmod(0o755)
    return (
        entry,
        commands,
        {
            **os.environ,
            "PATH": f"{binaries}:/usr/bin:/bin",
            "FAKE_DOCKER_COMMANDS": str(commands),
        },
    )


@pytest.mark.parametrize(
    "selection", ["absent", "missing", "not-executable", "wrong-type"]
)
def test_userspace_check_rejects_missing_or_wrong_artifact_before_docker(
    userspace_check, tmp_path, selection
):
    entry, commands, env = userspace_check
    arguments = []
    if selection != "absent":
        artifact = tmp_path / (
            "wrong.txt" if selection == "wrong-type" else "missing.AppImage"
        )
        if selection != "missing":
            artifact.write_bytes(b"synthetic artifact marker")
            artifact.chmod(0o644 if selection == "not-executable" else 0o755)
        arguments = [str(artifact)]
    result = subprocess.run(
        ["/bin/sh", str(entry), *arguments], env=env, capture_output=True, check=False
    )
    assert result.returncode != 0
    assert not commands.exists()
    assert list((tmp_path / "build").iterdir()) == []


def test_userspace_check_uses_only_the_explicit_selected_image(
    userspace_check, tmp_path
):
    entry, commands, env = userspace_check
    artifact = tmp_path / "versioned build/InkEcho-selected-x86_64.AppImage"
    artifact.parent.mkdir()
    artifact.write_bytes(b"selected marker, not an executable application")
    artifact.chmod(0o755)
    result = subprocess.run(
        ["/bin/sh", str(entry), str(artifact)],
        env=env,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr.decode()
    calls = [json.loads(line) for line in commands.read_text().splitlines()]
    assert len(calls) == 2 and calls[0][0] == "build" and calls[1][0] == "run"
    assert f"{artifact.resolve()}:/input/InkEcho.AppImage:ro" in calls[1]
    assert "/input/InkEcho.AppImage" in calls[1]
    assert (
        "--network" in calls[1] and calls[1][calls[1].index("--network") + 1] == "none"
    )
    assert artifact.read_bytes().startswith(b"selected marker")
