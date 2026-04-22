FROM ros:jazzy-ros-base

# Install Python and pip
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-dev \
    python3-colcon-common-extensions \
    python3-scipy \
    python3-requests \
    python3-numpy \
    && rm -rf /var/lib/apt/lists/*

# Create workspace
WORKDIR /rosadapter

# Create src directory for colcon workspace
RUN mkdir -p src

# Copy the phosphobot_sync_pkg into src directory
COPY ./Rosadapter/rosadapter/phosphobot_sync_pkg ./src/phosphobot_sync_pkg

# Build workspace
RUN /bin/bash -c "source /opt/ros/jazzy/setup.bash && colcon build --symlink-install 2>&1"

# Verify build succeeded
RUN test -d install/phosphobot_sync_pkg || (echo 'Build failed!' && exit 1)

# Set environment variables for Phosphobot remote arm control
ENV PHOSPHOBOT_ENABLED=true
ENV PHOSPHOBOT_HOST=192.168.86.27
ENV PHOSPHOBOT_PORT=80

# Setup entrypoint script
RUN echo "#!/bin/bash" > /.entrypoint.sh && \
    echo "source /opt/ros/jazzy/setup.bash" >> /.entrypoint.sh && \
    echo "source /rosadapter/install/setup.bash" >> /.entrypoint.sh && \
    echo "exec ros2 run phosphobot_sync_pkg phosphobot_sync" >> /.entrypoint.sh && \
    chmod +x /.entrypoint.sh

ENTRYPOINT ["/bin/bash", "-c"]
CMD ["source /opt/ros/jazzy/setup.bash && source /rosadapter/install/setup.bash && ros2 run phosphobot_sync_pkg phosphobot_sync"]
