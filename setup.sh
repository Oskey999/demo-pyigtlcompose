#!/bin/bash
# Setup script for Docker Compose Recorder
# Installs dependencies and configures the environment

set -e

echo "Docker Compose Recorder Setup"
echo "=============================="

# Check if running on Linux
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    echo "Warning: This script is optimized for Linux"
fi

# Install system dependencies
echo "Installing system dependencies..."
if command -v apt-get &> /dev/null; then
    # Debian/Ubuntu
    sudo apt-get update
    sudo apt-get install -y \
        ffmpeg \
        x11vnc \
        xvfb \
        chromium-browser \
        python3-pip \
        python3-venv \
        docker.io \
        docker-compose
elif command -v yum &> /dev/null; then
    # RHEL/CentOS/Fedora
    sudo yum install -y \
        ffmpeg \
        x11vnc \
        Xvfb \
        chromium \
        python3-pip \
        docker \
        docker-compose
elif command -v pacman &> /dev/null; then
    # Arch
    sudo pacman -S --noconfirm \
        ffmpeg \
        x11vnc \
        xorg-server-xvfb \
        chromium \
        python-pip \
        docker \
        docker-compose
else
    echo "Please install manually: ffmpeg, x11vnc, xvfb, chromium, python3-pip, docker, docker-compose"
fi

# Install Python dependencies
echo "Installing Python packages..."
pip3 install --user docker requests

# Create recordings directory
mkdir -p recordings

# Check Docker permissions
echo "Checking Docker access..."
if ! groups | grep -q docker; then
    echo "Adding user to docker group..."
    sudo usermod -aG docker $USER
    echo "Please log out and back in for Docker permissions to take effect"
fi

echo ""
echo "Setup complete! Usage:"
echo "  python3 docker_compose_recorder.py --duration 60"
echo ""
echo "Make sure your docker-compose services are running:"
echo "  docker-compose up -d SlicerApp ROSsim"
