#!/usr/bin/env bash

# source /opt/ros/humble/setup.bash

# if the file exists, then run it
if [ -f /root/slicer/packages/Slicer-5.8.1-2025-03-02-linux-amd64/Slicer ]; then
    /root/slicer/packages/Slicer-5.8.1-2025-03-02-linux-amd64/Slicer
elif [ -f /root/slicer/Slicer-SuperBuild-Release/Slicer-build/Slicer ]; then
    /root/slicer/Slicer-SuperBuild-Release/Slicer-build/Slicer
fi
