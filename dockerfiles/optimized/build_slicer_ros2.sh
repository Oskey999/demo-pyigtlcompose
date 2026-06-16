#!/bin/bash
set -e

source /opt/ros/humble/setup.bash

mkdir -p /root/ros2_ws/build/slicer_ros2_cmake
cd /root/ros2_ws/build/slicer_ros2_cmake

cmake \
    -DSlicer_DIR=/root/slicer/Slicer-SuperBuild-Release/Slicer-build \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_EXE_LINKER_FLAGS="-fuse-ld=mold" \
    -DCMAKE_SHARED_LINKER_FLAGS="-fuse-ld=mold" \
    /root/ros2_ws/src/slicer_ros2_module

make -j2

mkdir -p /root/slicer/ros2_loadable_modules

LIB_DIR="/root/ros2_ws/build/slicer_ros2_cmake/root/ros2_ws/build/slicer_ros2_cmake/lib"

echo "=== Copying .so files to ros2_loadable_modules ==="
cp "${LIB_DIR}"/*.so /root/slicer/ros2_loadable_modules/
echo "=== Installed modules ==="
ls /root/slicer/ros2_loadable_modules/