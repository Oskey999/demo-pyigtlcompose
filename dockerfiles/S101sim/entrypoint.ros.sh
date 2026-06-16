#!/bin/bash
# Entrypoint for the ROS stack container.
# Reads USE_REAL_HARDWARE and SERIAL_DEVICE from the environment (set in
# docker-compose.yml / .env) and launches MoveIt accordingly.
set -e

source /opt/ros/jazzy/setup.bash
source /ros2_ws/install/setup.bash

# ── If the caller passed an explicit command, run it as-is ────────────────────
# e.g.  docker compose run ros-stack bash
#        docker compose run ros-stack ros2 topic list
if [ "$#" -gt 0 ]; then
    exec "$@"
fi

# ── Decide launch mode ────────────────────────────────────────────────────────
USE_REAL_HARDWARE="${USE_REAL_HARDWARE:-false}"
SERIAL_DEVICE="${SERIAL_DEVICE:-/dev/ttyACM0}"

if [ "${USE_REAL_HARDWARE}" = "true" ]; then
    # Sanity-check: make sure the device node was passed through.
    if [ ! -e "${SERIAL_DEVICE}" ]; then
        echo ""
        echo "ERROR: USE_REAL_HARDWARE=true but '${SERIAL_DEVICE}' does not exist inside the container."
        echo ""
        echo "  Windows users: attach the USB device to WSL2 first:"
        echo "    usbipd attach --wsl --busid <BUSID>"
        echo "  Then check the device appears (in WSL2): ls /dev/ttyACM* /dev/ttyUSB*"
        echo "  Update SERIAL_DEVICE in .env to match."
        echo ""
        exit 1
    fi

    echo "[ros-stack] Real hardware mode — serial port: ${SERIAL_DEVICE}"
    # so101_moveit.launch.py forwards the 'port' arg to the ros2_control
    # hardware interface, which passes it to the Feetech servo SDK.
    exec ros2 launch lerobot_moveit so101_moveit.launch.py \
        port:="${SERIAL_DEVICE}"
else
    echo "[ros-stack] Simulation mode — no serial port opened."
    exec ros2 launch lerobot_moveit so101_moveit.launch.py \
        use_fake_hardware:=true
fi
