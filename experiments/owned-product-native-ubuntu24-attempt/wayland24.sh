#!/bin/bash
set -eu
sudo sed -i 's/^WaylandEnable=false/#WaylandEnable=false/' /etc/gdm3/custom.conf
sudo reboot
