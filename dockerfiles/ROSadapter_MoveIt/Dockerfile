FROM ros:jazzy-ros-base

# Install Python and pip
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install ROS2 Python development tools
RUN apt-get update && apt-get install -y \
    python3-colcon-common-extensions \
    && rm -rf /var/lib/apt/lists/*

# Install MoveIt dependencies (required for MoveIt controller)
# Also install libfastcdr-dev to ensure FastRTPS serialization libs are available
RUN apt-get update && apt-get install -y \
    ros-jazzy-moveit \
    ros-jazzy-moveit-msgs \
    ros-jazzy-moveit-core \
    ros-jazzy-geometric-shapes \
    libfastcdr-dev \
    && rm -rf /var/lib/apt/lists/*

# Create workspace
WORKDIR /rosadapter

# Create src directory for colcon workspace  
RUN mkdir -p src

# Copy only the moveit_controller_pkg into src (clean build)
COPY ./Rosadapter/rosadapter/moveit_controller_pkg ./src/moveit_controller_pkg

# Build workspace (clean, proper build)
RUN /bin/bash -c "source /opt/ros/jazzy/setup.bash && colcon build 2>&1"

# Verify build succeeded
RUN test -d install/moveit_controller_pkg || (echo 'Build failed!' && exit 1)

# Debug: Check what was actually installed
RUN echo "=== Installed structure ===" && \
    ls -la install/ && \
    echo "=== Lib directory ===" && \
    ls -la install/moveit_controller_pkg/lib/ || true && \
    echo "=== Bin directory ===" && \
    ls -la install/moveit_controller_pkg/bin/ || true && \
    echo "=== Share directory ===" && \
    ls -la install/moveit_controller_pkg/share/ || true

# Set LD_LIBRARY_PATH to ensure FastRTPS libs are found at runtime
ENV LD_LIBRARY_PATH=/opt/ros/jazzy/lib:/rosadapter/install/moveit_controller_pkg/lib:$LD_LIBRARY_PATH
ENV RMW_IMPLEMENTATION=rmw_fastrtps_cpp

# Setup entrypoint to ensure proper environment
COPY <<EOF /.entrypoint.sh
#!/bin/bash
set -e
source /opt/ros/jazzy/setup.bash
source /rosadapter/install/setup.bash
export LD_LIBRARY_PATH=/opt/ros/jazzy/lib:$LD_LIBRARY_PATH
echo "Launching MoveIt controller..."
ros2 run moveit_controller_pkg moveit_controller
EOF
RUN chmod +x /.entrypoint.sh

ENTRYPOINT ["/.entrypoint.sh"]
