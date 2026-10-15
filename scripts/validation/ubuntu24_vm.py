"""Explicit isolated Noble VM lab; no host desktop, credentials or cloud ASR.

The controller uses only a dedicated ignored build directory. QEMU runs as the
caller in its own container with /dev/kvm as its sole host device. Its SSH, QMP
and VNC listeners bind only the container loopback; no host port is published.
"""

import argparse
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAB = ROOT / "build/ubuntu24-perf-vm"
TOOLS = "inkecho-ubuntu24-perf-vm-tools:20261016"
CONTAINER = "inkecho-ubuntu24-perf-vm"
IMAGE_NAME = "noble-server-cloudimg-amd64.img"
IMAGE_BASE = "https://cloud-images.ubuntu.com/noble/20260926/"
IMAGE_SHA256 = "6a81c37564db9b1ee84e141922625e1d7c5b389b99bb3c572e0243607d5bb4d2"
ARTIFACT_SHA256 = "5c515dd0e3ceb8eb910baa45f392d8be28bfda109c5e1d59865e5a0733b7d55a"
QMP_CLIENT = """
import json,socket,sys
with socket.create_connection(('127.0.0.1',4444),timeout=5) as connection:
    stream=connection.makefile('rwb')
    json.loads(stream.readline())
    for request in [{'execute':'qmp_capabilities'},json.loads(sys.argv[1])]:
        stream.write(json.dumps(request).encode()+b'\\n');stream.flush()
        while True:
            response=json.loads(stream.readline())
            if 'return' in response or 'error' in response: break
    print(json.dumps(response))
"""


def run(command, **options):
    return subprocess.run(command, check=True, **options)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def docker(arguments, **options):
    return run(["docker", *arguments], **options)


def mounts():
    result = []
    for name in ("base", "seed", "input", "secrets", "state", "output"):
        suffix = ",readonly" if name in {"base", "seed", "input", "secrets"} else ""
        result.extend(["--mount", f"type=bind,src={LAB / name},dst=/{name}{suffix}"])
    return result


def tools(arguments, **options):
    return docker(
        [
            "run",
            "--rm",
            "--network",
            "none",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--tmpfs",
            "/tmp:rw,nosuid,nodev,size=128m",
            *mounts(),
            TOOLS,
            *arguments,
        ],
        **options,
    )


def directories():
    LAB.mkdir(mode=0o700, parents=True, exist_ok=True)
    LAB.chmod(0o700)
    for name in ("base", "seed", "input", "secrets", "state", "output"):
        path = LAB / name
        path.mkdir(mode=0o700, exist_ok=True)
        path.chmod(0o700)


def download():
    directories()
    sums = LAB / "base/SHA256SUMS"
    with urllib.request.urlopen(IMAGE_BASE + "SHA256SUMS", timeout=60) as response:
        data = response.read(65536)
    entries = {
        line.split()[1].lstrip("*"): line.split()[0]
        for line in data.decode().splitlines()
    }
    if entries.get(IMAGE_NAME) != IMAGE_SHA256:
        raise RuntimeError("Official pinned image checksum changed")
    sums.write_bytes(data)
    image = LAB / "base" / IMAGE_NAME
    if not image.exists():
        temporary = image.with_suffix(".part")
        try:
            with urllib.request.urlopen(
                IMAGE_BASE + IMAGE_NAME, timeout=60
            ) as response:
                if not response.url.startswith(IMAGE_BASE):
                    raise RuntimeError("Image redirected outside pinned source")
                with temporary.open("wb") as stream:
                    total = 0
                    while block := response.read(1024 * 1024):
                        total += len(block)
                        if total > 900 * 1024 * 1024:
                            raise RuntimeError("Image exceeds download bound")
                        stream.write(block)
            if digest(temporary) != IMAGE_SHA256:
                raise RuntimeError("Downloaded image checksum mismatch")
            temporary.replace(image)
        finally:
            temporary.unlink(missing_ok=True)
    if digest(image) != IMAGE_SHA256:
        raise RuntimeError("Cached image checksum mismatch")
    manifest = {
        "image_url": IMAGE_BASE + IMAGE_NAME,
        "sha256sums_url": IMAGE_BASE + "SHA256SUMS",
        "sha256sums_sha256": digest(sums),
        "image_sha256": digest(image),
        "image_bytes": image.stat().st_size,
        "verification": "HTTPS official dated manifest and pinned SHA256",
    }
    (LAB / "image-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest))


def build():
    directories()
    docker(["build", "--tag", TOOLS, str(ROOT / "scripts/validation/ubuntu24-vm")])
    result = docker(
        ["image", "inspect", "--format", "{{.Id}}", TOOLS],
        capture_output=True,
        text=True,
    )
    (LAB / "tools-image-id.txt").write_text(result.stdout)


def prepare():
    state = docker(
        [
            "ps",
            "--all",
            "--filter",
            f"name=^/{CONTAINER}$",
            "--format",
            "{{.State}}",
        ],
        capture_output=True,
        text=True,
    ).stdout.strip()
    if state not in {"", "created", "exited", "dead"}:
        raise RuntimeError("Stop the lab VM before changing its disk, seed or inputs")
    directories()
    image = LAB / "base" / IMAGE_NAME
    if not image.exists() or digest(image) != IMAGE_SHA256:
        raise RuntimeError("Run download and verify the official image first")
    key = LAB / "secrets/testkey"
    if not key.exists():
        run(
            [
                "ssh-keygen",
                "-q",
                "-t",
                "ed25519",
                "-N",
                "",
                "-C",
                "inkecho-disposable-vm",
                "-f",
                str(key),
            ]
        )
    key.chmod(0o600)
    public_key = key.with_suffix(".pub").read_text().strip()
    config = {
        "hostname": "inkecho-noble-perf",
        "manage_etc_hosts": True,
        "ssh_pwauth": False,
        "disable_root": True,
        "users": [
            {
                "name": "inkecho",
                "groups": ["sudo"],
                "shell": "/bin/bash",
                "sudo": "ALL=(ALL) NOPASSWD:ALL",
                "lock_passwd": True,
                "ssh_authorized_keys": [public_key],
            }
        ],
        "package_update": True,
        "package_upgrade": False,
        "packages": [
            "ubuntu-desktop-minimal",
            "xserver-xorg-video-dummy",
            "xvfb",
            "x11-utils",
            "xdotool",
            "python3-gi",
            "gir1.2-gtk-3.0",
            "gir1.2-vte-2.91",
            "dbus-x11",
            "fonts-noto-cjk",
            "mesa-utils",
            "epiphany-browser",
        ],
        "write_files": [
            {
                "path": "/etc/gdm3/custom.conf",
                "defer": True,
                "content": (
                    "[daemon]\nAutomaticLoginEnable=true\nAutomaticLogin=inkecho\n"
                ),
            },
            {
                "path": "/var/lib/AccountsService/users/inkecho",
                "defer": True,
                "content": "[User]\nSession=ubuntu\nSystemAccount=false\n",
            },
        ],
        "runcmd": [
            ["netplan", "apply"],
            ["mkdir", "-p", "/mnt/input", "/mnt/output"],
            [
                "mount",
                "-t",
                "9p",
                "-o",
                "trans=virtio,version=9p2000.L,ro",
                "inkecho_input",
                "/mnt/input",
            ],
            [
                "mount",
                "-t",
                "9p",
                "-o",
                "trans=virtio,version=9p2000.L",
                "inkecho_output",
                "/mnt/output",
            ],
            ["systemctl", "set-default", "graphical.target"],
            ["systemctl", "enable", "gdm3"],
            ["systemctl", "restart", "gdm3"],
        ],
        "final_message": "InkEcho disposable Noble VM initialization finished",
    }
    (LAB / "seed/user-data").write_text(
        "#cloud-config\n" + json.dumps(config, indent=2) + "\n"
    )
    (LAB / "seed/meta-data").write_text(
        "instance-id: inkecho-noble-perf-v1\nlocal-hostname: inkecho-noble-perf\n"
    )
    artifact = ROOT / "dist/InkEcho-0.1.0a10-x86_64.AppImage"
    if digest(artifact) != ARTIFACT_SHA256:
        raise RuntimeError("Unexpected preview artifact")
    shutil.copy2(artifact, LAB / "input/InkEcho.AppImage")
    for relative in ["src/inkecho", "scripts/validation", "scripts/feasibility"]:
        target = LAB / "input" / relative
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(
            ROOT / relative, target, ignore=shutil.ignore_patterns("__pycache__")
        )
    disk = LAB / "state/guest.qcow2"
    if not disk.exists():
        tools(
            [
                "qemu-img",
                "create",
                "-f",
                "qcow2",
                "-F",
                "qcow2",
                "-b",
                f"/base/{IMAGE_NAME}",
                "/state/guest.qcow2",
                "32G",
            ]
        )
    tools(
        [
            "genisoimage",
            "-quiet",
            "-output",
            "/state/seed.iso",
            "-volid",
            "cidata",
            "-joliet",
            "-rock",
            "/seed/user-data",
            "/seed/meta-data",
        ]
    )
    shutil.copy2(LAB / "state/seed.iso", LAB / "seed/seed.iso")
    print(
        json.dumps(
            {
                "prepared": True,
                "private_key_mode": "0600",
                "private_key_directory_mode": "0700",
                "input_artifact_sha256": ARTIFACT_SHA256,
            }
        )
    )


def qemu_arguments():
    return [
        "qemu-system-x86_64",
        "-accel",
        "kvm",
        "-machine",
        "q35",
        "-cpu",
        "host",
        "-smp",
        "4",
        "-m",
        "4096",
        "-drive",
        "file=/state/guest.qcow2,if=virtio,format=qcow2",
        "-drive",
        "file=/seed/seed.iso,format=raw,media=cdrom,readonly=on",
        "-virtfs",
        "local,path=/input,mount_tag=inkecho_input,security_model=none,readonly=on,id=inshare",
        "-virtfs",
        "local,path=/output,mount_tag=inkecho_output,security_model=none,id=outshare",
        "-device",
        "virtio-vga",
        "-device",
        "virtio-net-pci,netdev=n1",
        "-netdev",
        "user,id=n1,hostfwd=tcp:127.0.0.1:2222-:22",
        "-vnc",
        "127.0.0.1:0",
        "-qmp",
        "tcp:127.0.0.1:4444,server=on,wait=off",
        "-serial",
        "file:/state/serial.log",
        "-monitor",
        "none",
    ]


def start_arguments():
    return [
        "run",
        "--detach",
        "--name",
        CONTAINER,
        "--network",
        "bridge",
        "--memory",
        "5g",
        "--cpus",
        "4",
        "--pids-limit",
        "256",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--device",
        "/dev/kvm",
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "--group-add",
        str(Path("/dev/kvm").stat().st_gid),
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,size=256m",
        *mounts(),
        TOOLS,
        *qemu_arguments(),
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=[
            "download",
            "build",
            "prepare",
            "show-start",
            "start",
            "ssh",
            "qmp",
            "isolate",
            "stop",
        ],
    )
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.action == "download":
        download()
    elif args.action == "build":
        build()
    elif args.action == "prepare":
        prepare()
    elif args.action == "show-start":
        print(json.dumps(start_arguments(), indent=2))
    elif args.action == "start":
        docker(start_arguments())
    elif args.action == "ssh":
        command = args.command[1:] if args.command[:1] == ["--"] else args.command
        docker(
            [
                "exec",
                "--interactive",
                CONTAINER,
                "ssh",
                "-i",
                "/secrets/testkey",
                "-p",
                "2222",
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=20",
                "-o",
                "StrictHostKeyChecking=accept-new",
                "-o",
                "UserKnownHostsFile=/state/known_hosts",
                "inkecho@127.0.0.1",
                shlex.join(command),
            ]
        )
    elif args.action == "qmp":
        name = args.command[0] if args.command else "query-status"
        if name not in {
            "query-status",
            "query-kvm",
            "screendump",
            "system_powerdown",
            "network-info",
        }:
            parser.error("Unsupported lab QMP command")
        request = {"execute": name}
        if name == "screendump":
            request["arguments"] = {"filename": "/output/guest-desktop.ppm"}
        elif name == "network-info":
            request = {
                "execute": "human-monitor-command",
                "arguments": {"command-line": "info usernet"},
            }
        docker(
            [
                "exec",
                CONTAINER,
                "python3",
                "-c",
                QMP_CLIENT,
                json.dumps(request),
            ]
        )
    elif args.action == "isolate":
        docker(["network", "disconnect", "bridge", CONTAINER])
    elif args.action == "stop":
        docker(["stop", "--time", "20", CONTAINER])


if __name__ == "__main__":
    main()
