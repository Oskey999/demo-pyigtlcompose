# Use an Ubuntu desktop with VNC and noVNC/web access
FROM dorowu/ubuntu-desktop-lxde-vnc:bionic

ARG Slicer_VERSION=5.8.1
ARG python_VERSION=3.7
# # Copy your pre-downloaded Slicer directory to the container
# COPY Slicer /opt/slicer

# # Install dependencies required by Slicer, the missing PulseAudio libraries,
# # and dependencies for Qt's xcb plugin including additional recommendations
# # Add xdotool for window manipulation
RUN add-apt-repository ppa:deadsnakes/ppa
RUN apt-get update && apt-get install -y \
    libglu1-mesa libxrender1 libxt6 libxi6 libsm6 libxrandr2 \
    libpulse-mainloop-glib0 \
    libx11-xcb1 \
    libxcb-shape0 libxcb-xinerama0 libxcb-xinerama0-dev \
    libxcb-icccm4-dev libxcb-image0-dev \
    libqt5widgets5 libqt5network5 libqt5gui5 libqt5core5a libqt5dbus5 \
    xdotool \  
    wget \
    git \
    cmake \
    build-essential \
    python${python_VERSION} python3-pip \
    netcat iputils-ping curl telnet iproute2 net-tools dnsutils tcpdump vim \
    && rm -rf /var/lib/apt/lists/*


ENV QT_QPA_PLATFORM_PLUGIN_PATH=/usr/lib/x86_64-linux-gnu/qt5/plugins/platforms 
# RUN ln -s /usr/bin/python3 /usr/bin/python
# # Copy your pre-downloaded Slicer directory to the container
# COPY dockerfiles/slicerGUI/Slicer /opt/slicer
# RUN ls /opt/slicer
WORKDIR /opt/slicer
# RUN tar -xvzf  /opt/slicer/slicer-${Slicer_VERSION}-linux-amd64.tar.gz 
# RUN tar -xvzf  /opt/slicer/slicer-${Slicer_VERSION}.tar.gz 
# Download is optional if tar.gz already exists; skip if not needed
# RUN cd /opt/slicer && \
#     wget https://download.slicer.org/repository/download/Slicer/${Slicer_VERSION}/Slicer-${Slicer_VERSION}-linux-amd64.tar.gz && \
#     tar -xzf Slicer-${Slicer_VERSION}-linux-amd64.tar.gz && \
#     rm Slicer-${Slicer_VERSION}-linux-amd64.tar.gz

# ARG Slicer_VERSION=5.8

RUN cd /opt/slicer && \
    wget -O Slicer-linux-amd64.tar.gz "https://download.slicer.org/download?version=${Slicer_VERSION}&os=linux&stability=release" && \
    tar -xzf Slicer-linux-amd64.tar.gz && \
    rm Slicer-linux-amd64.tar.gz
# RUN apt-get install install cmake --upgrade
# RUN apt-get update && apt-get install -y \
#     ca-certificates \
#     && rm -rf /var/lib/apt/lists/*

# RUN wget -q https://github.com/Kitware/CMake/releases/download/v3.27.9/cmake-3.27.9-linux-x86_64.sh \
#     && chmod +x cmake-3.27.9-linux-x86_64.sh \
#     && ./cmake-3.27.9-linux-x86_64.sh --skip-license --prefix=/usr/local \
#     && rm cmake-3.27.9-linux-x86_64.sh
# WORKDIR /opt
# RUN git clone --branch v5.6.2 https://github.com/Slicer/Slicer.git

# RUN mkdir /opt/Slicer-SuperBuild-Release
# WORKDIR /opt/Slicer-SuperBuild-Release

# RUN cmake \
#   -DCMAKE_BUILD_TYPE=Release \
#   -DSlicer_USE_SYSTEM_QT=OFF \
#   -DSlicer_USE_SYSTEM_OpenSSL=ON \
#   ../Slicer/SuperBuild

# RUN make -j$(nproc)
WORKDIR /root
# # Set the necessary environment variables for Slicer
ENV SLICER_HOME=/opt/slicer
ENV SLICER_VERSION=5.8.1
ENV DISPLAY=:1
ENV PATH="${SLICER_HOME}:$PATH"


# Copy slicerrc.py to the container
COPY dockerfiles/slicerGUI/slicerrc.py /root/.slicerrc.py
COPY dockerfiles/slicerGUI/installs.py /root/installs.py
COPY dockerfiles/slicerGUI/testpyigtl.py /home/ubuntu/.config/slicer.org/testpyigtl.py
# COPY dockerfiles/slicerGUI/Slicer.ini /home/ubuntu/.config/slicer.org/Slicer.ini

# # Map local directories to directories in the container
VOLUME ["/root/Documents", "/images"]

# Create a custom script to start Slicer and maximize its window
RUN echo '#!/bin/bash\n\
mkdir -p /root/Documents\n\
export DISPLAY=:1\n\
/opt/slicer/Slicer-5.8.1-linux-amd64/Slicer --no-splash \\\n\
  --additional-module-paths /opt/slicer/Slicer-5.8.1-linux-amd64/TMS/SlicerTMS \\\n\
  --additional-module-paths /opt/slicer/Slicer-5.8.1-linux-amd64/IGT \\\n\
  --additional-module-paths /tmp/Slicer-root &\n\
SLICER_PID=$!\n\
# Give Slicer time to start\n\
sleep 5\n\
# Try to maximize window if xdotool finds it\n\
xdotool search --name "3D Slicer" windowactivate windowsize 100% 100% 2>/dev/null || true\n\
wait $SLICER_PID' > /usr/local/bin/start-slicer-maximized.sh \
    && chmod +x /usr/local/bin/start-slicer-maximized.sh

# # Update Supervisor configuration to use the custom script
RUN echo '[program:slicer]' > /etc/supervisor/conf.d/slicer.conf \
    && echo 'command=/usr/local/bin/start-slicer-maximized.sh' >> /etc/supervisor/conf.d/slicer.conf \
    && echo 'environment=DISPLAY=":1.0",SLICER_VERSION="5.8.1"' >> /etc/supervisor/conf.d/slicer.conf \
    && echo 'autostart=true' >> /etc/supervisor/conf.d/slicer.conf \
    && echo 'autorestart=true' >> /etc/supervisor/conf.d/slicer.conf \
    && echo 'stderr_logfile=/var/log/slicer.err.log' >> /etc/supervisor/conf.d/slicer.conf \
    && echo 'stdout_logfile=/var/log/slicer.out.log' >> /etc/supervisor/conf.d/slicer.conf




RUN python${python_VERSION} -m pip install --upgrade pip setuptools --no-cache-dir --no-verify-ssl\
    && python${python_VERSION} -m pip install wheel --no-cache-dir\
    && python${python_VERSION} -m pip install --no-cache-dir vtk pyigtl nibabel torch configparser 2>&1 | grep -v "Hashes" || true

# Install pyigtl to Slicer's Python environment as well
RUN /opt/slicer/Slicer-5.8.1-linux-amd64/bin/PythonSlicer -m pip install --no-cache-dir pyigtl

RUN mkdir -p /tmp/Slicer-root
ARG spath=SlicerTMS
COPY ${spath}/server /app/server
COPY ${spath}/data /app/data
COPY ${spath}/client/SlicerTMS /tmp/Slicer-root/SlicerTMS

# Create directories for proper module discovery
RUN mkdir -p /opt/slicer/Slicer-5.8.1-linux-amd64/lib/Slicer-5.8/qt-scripted-modules
RUN mkdir -p /opt/slicer/Slicer-5.8.1-linux-amd64/slicer.org/Extensions-33241/SlicerTMS/lib/Slicer-5.8/qt-scripted-modules

# Copy SlicerTMS to the proper extension location
COPY ${spath}/client/SlicerTMS /opt/slicer/Slicer-5.8.1-linux-amd64/lib/Slicer-5.8/qt-scripted-modules/SlicerTMS
COPY ${spath}/client/SlicerTMS /opt/slicer/Slicer-5.8.1-linux-amd64/slicer.org/Extensions-33241/SlicerTMS/lib/Slicer-5.8/qt-scripted-modules/SlicerTMS

# CRITICAL: Override the old TMS directory that comes with Slicer tarball with our modified version
RUN rm -rf /opt/slicer/Slicer-5.8.1-linux-amd64/TMS/SlicerTMS

# Populate the volume with SlicerTMS before declaring it as a VOLUME
COPY ${spath}/client/SlicerTMS /opt/slicer/Slicer-5.8.1-linux-amd64/TMS/SlicerTMS

# # Mount SlicerTMS as a volume for flexibility in docker-compose
# VOLUME ["/opt/slicer/Slicer-5.8.1-linux-amd64/TMS/SlicerTMS"]

# Attach SlicerIGsio module directory for openIGTLinkIF dependency

# Attach openIGTLinkIF module directory due to install troubles
# RUN apt-get update && apt-get install -y \
#     ca-certificates \
#     && rm -rf /var/lib/apt/lists/*

# RUN wget -q https://github.com/Kitware/CMake/releases/download/v3.27.9/cmake-3.27.9-linux-x86_64.sh \
#     && chmod +x cmake-3.27.9-linux-x86_64.sh \
#     && ./cmake-3.27.9-linux-x86_64.sh --skip-license --prefix=/usr/local \
#     && rm cmake-3.27.9-linux-x86_64.sh


# WORKDIR /opt/slicer/Slicer-5.8.1-linux-amd64/IGTgit
# RUN git clone https://github.com/SlicerIGT/SlicerIGT.git

# RUN mkdir SlicerIGT-build
# WORKDIR SlicerIGT-build

# RUN cmake \
#     -DCMAKE_BUILD_TYPE=Release \
#     -DSlicer_DIR=/opt/slicer/Slicer-5.8.1-linux-amd64/Slicer \
#     ../SlicerIGT \
#  && make -j4 \
#  && make package \ 
# && mkdir -p /opt/slicer/Slicer-5.8.1-linux-amd64/IGT \
# && mv *.tar.gz /opt/slicer/Slicer-5.8.1-linux-amd64/IGT/

RUN /opt/slicer/Slicer-5.8.1-linux-amd64/Slicer \
    --no-splash --no-main-window \
    --python-code "import slicer; slicer.app.extensionsManagerModel().installExtensionFromName('SlicerIGT')"


COPY test_port_connectivity.py /app/test_port_connectivity.py
COPY test_network_debug.sh /app/test_network_debug.sh
WORKDIR /app

# Make test scripts executable
RUN chmod +x /app/test_network_debug.sh

EXPOSE 6080
EXPOSE 18944
EXPOSE 18945

# Install python extensions and other dependencies
RUN /opt/slicer/Slicer-${Slicer_VERSION}-linux-amd64/Slicer --no-splash --no-main-window ; exit 0
RUN /opt/slicer/slicer-${Slicer_VERSION}/Slicer --python-script "/root/installs.py" --no-splash  ; exit 0

RUN python3 -m pip install pyigtl --no-cache-dir 

# Ensure supervisor and VNC services from base image are started (MUST be last)
CMD ["/startup.sh"]