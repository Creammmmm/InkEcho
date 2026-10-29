#!/bin/bash
set -eu
key=/home/lth/github/InkEcho/build/ubuntu24-perf-vm/secrets/testkey
host=/tmp/inkecho-8614-vm24/known_hosts
proxy='python3 /tmp/inkecho-8614-vm24/client.py'
for attempt in $(seq 1 30); do
 if timeout 8 ssh -i "$key" -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$host" -o "ProxyCommand=$proxy" inkecho@localhost 'loginctl show-session 1 -p Type -p Active -p LockedHint' > /tmp/inkecho-8614-vm24/session-after-reboot.log 2>&1; then break; fi
 sleep 5
done
cat /tmp/inkecho-8614-vm24/session-after-reboot.log
if ! grep -qx 'Type=wayland' /tmp/inkecho-8614-vm24/session-after-reboot.log || ! grep -qx 'Active=yes' /tmp/inkecho-8614-vm24/session-after-reboot.log; then echo 'Session not active Wayland, skipping'; exit 1; fi
ssh -i "$key" -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$host" -o "ProxyCommand=$proxy" inkecho@localhost 'bash /tmp/inkecho-r4-test/probes/run.sh 6d537689d5e30f4611f1e8376025705bf5fcc26c9198c9cda7c51717d434e34a wayland' > /tmp/inkecho-8614-vm24/6d-real-wayland.log 2>&1
