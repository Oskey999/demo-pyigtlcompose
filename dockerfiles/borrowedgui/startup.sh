#!/usr/bin/env bash
set -e

echo "Starting container..."

# Source ROS (important for rosmed base image)
source /opt/ros/*/setup.bash || true

# Optional: Slicer environment
export PATH=/root/slicer/Slicer-SuperBuild-Release/Slicer-build/Slicer-bin:$PATH

# Drop into shell (or replace with Slicer launch command)
exec "$@"



# #!/bin/bash
# set -e

# echo "Starting container services..."

# # Fix line endings in ALL scripts
# find /usr/local/lib/web -type f -exec sed -i 's/\r$//' {} \; 2>/dev/null || true
# find /etc/supervisor -type f -exec sed -i 's/\r$//' {} \; 2>/dev/null || true

# # Fix placeholders in supervisord.conf (ONLY in supervisord.conf, not slicer.conf!)
# sed -i 's/%USER%/root/g' /etc/supervisor/conf.d/supervisord.conf
# sed -i 's/%HOME%/\/root/g' /etc/supervisor/conf.d/supervisord.conf  
# sed -i 's/%PASSWORD%/password/g' /etc/supervisor/conf.d/supervisord.conf

# # Remove only xvfb, novnc, x11vnc from supervisord.conf (leave slicer.conf alone!)
# sed -i '/^\[program:xvfb\]/,/^$/d' /etc/supervisor/conf.d/supervisord.conf
# sed -i '/^\[program:novnc\]/,/^$/d' /etc/supervisor/conf.d/supervisord.conf
# sed -i '/^\[program:x11vnc\]/,/^$/d' /etc/supervisor/conf.d/supervisord.conf
# sed -i '/^depends_on=/d' /etc/supervisor/conf.d/supervisord.conf
# sed -i 's/,xvfb//g; s/xvfb,//g; s/,novnc//g; s/novnc,//g; s/,x11vnc//g; s/x11vnc,//g' /etc/supervisor/conf.d/supervisord.conf

# # Clean up lock files
# rm -f /tmp/.X1-lock /tmp/.X11-unix/X1
# mkdir -p /tmp/.X11-unix
# chmod 1777 /tmp/.X11-unix

# # Start Xvfb
# echo "Starting Xvfb..."
# Xvfb :1 -screen 0 1920x1080x24 &
# sleep 3
# export DISPLAY=:1

# # Start x11vnc
# echo "Starting x11vnc..."
# x11vnc -display :1 -forever -shared -rfbport 5900 -nopw &
# sleep 2

# echo "Starting supervisord..."
# exec /usr/bin/supervisord -n -c /etc/supervisor/supervisord.conf