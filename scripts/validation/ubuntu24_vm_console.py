"""Fixed ASCII provisioning commands in the owned lab guest, never product tests.

Use only after a QMP screenshot confirms a newly opened guest terminal owns the
cursor. This never connects to a host display or types recognized user speech.
"""

import argparse
import subprocess

from ubuntu24_vm import CONTAINER

DIAGNOSE = (
    "ip -j address > /mnt/output/guest-ip.json; "
    "ip -j route > /mnt/output/guest-route.json; "
    "sudo ss -tlnp > /mnt/output/guest-listeners.txt; "
    "sudo systemctl status ssh.socket ssh.service --no-pager "
    "> /mnt/output/guest-ssh-status.txt; "
    "networkctl status enp0s4 --no-pager > /mnt/output/guest-networkctl.txt; "
    "nmcli -t device > /mnt/output/guest-nm-devices.txt; "
    "echo done > /mnt/output/guest-network-diagnosis-done"
)
REPAIR = (
    "sudo netplan get > /mnt/output/guest-netplan-before.txt; "
    "sudo netplan apply > /mnt/output/guest-netplan-repair.txt; "
    "ip -j address > /mnt/output/guest-ip-after.json; "
    "ip -j route > /mnt/output/guest-route-after.json; "
    "nmcli -t device > /mnt/output/guest-nm-after.txt; "
    "echo done > /mnt/output/guest-netplan-repair-done"
)
CLIENT = r"""
import json, socket, sys, time

with socket.create_connection(("127.0.0.1", 4444), timeout=5) as connection:
    stream = connection.makefile("rwb")
    json.loads(stream.readline())

    def request(value):
        stream.write(json.dumps(value).encode() + b"\n")
        stream.flush()
        while True:
            response = json.loads(stream.readline())
            if "error" in response:
                raise RuntimeError("qmp_command_failed")
            if "return" in response:
                return

    request({"execute": "qmp_capabilities"})
    punctuation = {" ": "spc", "-": "minus", "/": "slash", ".": "dot", ";": "semicolon"}
    for character in sys.argv[1] + "\n":
        if character == "\n":
            keys = ["ret"]
        elif character == ">":
            keys = ["shift", "dot"]
        elif character.isascii() and character.isalnum():
            keys = [character]
        else:
            keys = [punctuation[character]]
        request(
            {
                "execute": "send-key",
                "arguments": {
                    "keys": [{"type": "qcode", "data": key} for key in keys],
                    "hold-time": 20,
                },
            }
        )
        time.sleep(0.035)
    print(json.dumps({"fixed_provisioning_command_sent": True}))
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["diagnose-network", "repair-network"])
    args = parser.parse_args()
    command = DIAGNOSE if args.action == "diagnose-network" else REPAIR
    subprocess.run(
        ["docker", "exec", CONTAINER, "python3", "-c", CLIENT, command],
        check=True,
    )


if __name__ == "__main__":
    main()
