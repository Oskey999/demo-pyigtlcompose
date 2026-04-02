# Docker Compose Multi-Container Recorder

A Python tool to simultaneously record multiple Docker containers (SlicerApp/KasmVNC and ROSsim/webtop) with real-time Docker stats overlay.

## Features

- **Multi-Container Recording**: Record SlicerApp (KasmVNC) and ROSsim (webtop) simultaneously
- **Real-time Stats**: Collects CPU, memory, network, and PID stats using Docker SDK for Python
- **Side-by-Side Composition**: Creates split-screen videos with container stats burned in
- **Flexible Output**: Individual container videos + combined composition
- **Live Monitoring**: Real-time terminal display of container resource usage during recording

## Prerequisites

### System Dependencies

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y ffmpeg x11vnc xvfb python3-pip docker.io docker-compose

# macOS (using Homebrew)
brew install ffmpeg docker docker-compose

# Install Python dependencies
pip3 install docker
```

### Docker Containers

Ensure your containers from docker-compose.yml are running:

```bash
docker-compose up -d SlicerApp ROSsim
```

Verify containers are accessible:
- **SlicerApp (KasmVNC)**: http://localhost:3003 (VNC password: `yourpassword`)
- **ROSsim (webtop)**: VNC on localhost:5900

## Usage

### Basic Recording

Record for 60 seconds:
```bash
python3 docker_compose_recorder.py -d 60
```

Record indefinitely (press Ctrl+C to stop):
```bash
python3 docker_compose_recorder.py
```

### With Side-by-Side Composition

Record and automatically create a combined video:
```bash
python3 docker_compose_recorder.py -d 120 --compose
```

### Custom Output Directory

```bash
python3 docker_compose_recorder.py -o /path/to/recordings -d 60
```

### Check Prerequisites

```bash
python3 docker_compose_recorder.py --check
```

## Configuration

Edit the `container_configs` dictionary in the script to match your setup:

```python
self.container_configs = {
    'optimized': {  # Container name from docker-compose
        'name': 'SlicerApp',
        'type': 'kasmvnc',
        'host': 'localhost',
        'vnc_port': 3003,  # Host port mapped to container's 6901
        'width': 1280,
        'height': 720,
        'password': 'yourpassword'  # Must match VNC_PW env var
    },
    'rossim': {
        'name': 'ROSsim',
        'type': 'vnc',
        'host': 'localhost',
        'vnc_port': 5900,
        'width': 1280,
        'height': 720,
        'password': ''
    }
}
```

## Output Files

After recording, you'll find in the output directory:

- `SlicerApp_YYYYMMDD_HHMMSS.mp4` - Individual SlicerApp recording
- `ROSsim_YYYYMMDD_HHMMSS.mp4` - Individual ROSsim recording
- `combined_YYYYMMDD_HHMMSS.mp4` - Side-by-side composition (if --compose used)
- `docker_stats_YYYYMMDD_HHMMSS.json` - Raw Docker stats data

## Docker Stats Data Format

The JSON stats file contains:

```json
{
  "timestamp": "2024-01-15T10:30:45.123456",
  "container": "optimized",
  "cpu_percent": 12.5,
  "memory_usage": 2147483648,
  "memory_limit": 4294967296,
  "memory_percent": 50.0,
  "network_rx": 1024000,
  "network_tx": 512000,
  "pids": 42
}
```

## Troubleshooting

### FFmpeg VNC Input Not Available

If your ffmpeg doesn't support VNC input, use the X11 capture method:

1. Install `x11vnc` to bridge VNC to X11
2. Modify the recorder to use `x11grab` input format
3. Or use the browser-based HTTP recording method

### Permission Denied

Ensure your user is in the docker group:
```bash
sudo usermod -aG docker $USER
# Log out and back in for changes to take effect
```

### Containers Not Found

Verify container names match your docker-compose.yml:
```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
```

### Connection Refused

Check port mappings in docker-compose.yml:
- SlicerApp: Port 3003 should map to 6901
- ROSsim: Port 5900 should be exposed

## Advanced Usage

### Custom Stats Processing

The stats JSON can be processed for visualization:

```python
import json
import pandas as pd

with open('docker_stats_20240115_103045.json') as f:
    data = json.load(f)

df = pd.DataFrame(data)
# Create plots, analyze resource usage, etc.
```

### Post-Processing Composition

Create custom layouts using ffmpeg directly:

```bash
ffmpeg -i SlicerApp_video.mp4 -i ROSsim_video.mp4 \
  -filter_complex "[0:v][1:v]hstack=inputs=2[v]; \
                   [v]drawtext=text='SlicerApp CPU: 12%':x=10:y=10:fontsize=24:fontcolor=white[s]" \
  -map "[s]" output.mp4
```

## License

MIT License - Feel free to modify for your needs.
