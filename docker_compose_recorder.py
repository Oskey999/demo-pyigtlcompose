#!/usr/bin/env python3
"""
Docker Compose Multi-Container Recorder with Real-time Docker Stats Overlay
Robust version with fallback recording methods
"""

import subprocess
import threading
import time
import json
import os
import signal
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import argparse
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Try to import docker SDK, fallback to CLI if not available
try:
    import docker
    DOCKER_SDK_AVAILABLE = True
except ImportError:
    DOCKER_SDK_AVAILABLE = False
    logger.warning("Docker SDK not available, falling back to Docker CLI")


class DockerStatsCollector:
    """Real-time Docker stats collection"""

    def __init__(self, container_names: List[str]):
        self.container_names = container_names
        self.stats_history = []
        self.running = False
        self.thread = None
        self._lock = threading.Lock()
        self._client = None

        if DOCKER_SDK_AVAILABLE:
            try:
                self._client = docker.from_env()
                self._client.ping()
                logger.info("Using Docker SDK for stats collection")
            except Exception as e:
                logger.warning(f"Docker SDK failed ({e}), using CLI fallback")
                self._client = None

    def start(self):
        """Start stats collection in background thread"""
        self.running = True
        if self._client and DOCKER_SDK_AVAILABLE:
            self.thread = threading.Thread(target=self._collect_sdk_loop, daemon=True)
        else:
            self.thread = threading.Thread(target=self._collect_cli_loop, daemon=True)
        self.thread.start()
        logger.info(f"Started stats collection for: {', '.join(self.container_names)}")

    def stop(self):
        """Stop stats collection"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        logger.info("Stats collection stopped")

    def _collect_sdk_loop(self):
        """Collect stats using Docker SDK"""
        while self.running:
            try:
                for name in self.container_names:
                    try:
                        container = self._client.containers.get(name)
                        stats = container.stats(stream=False)

                        # Calculate CPU percentage
                        cpu_stats = stats.get('cpu_stats', {})
                        precpu_stats = stats.get('precpu_stats', {})

                        cpu_delta = (
                            cpu_stats.get('cpu_usage', {}).get('total_usage', 0) -
                            precpu_stats.get('cpu_usage', {}).get('total_usage', 0)
                        )
                        system_delta = (
                            cpu_stats.get('system_cpu_usage', 0) -
                            precpu_stats.get('system_cpu_usage', 0)
                        )
                        online_cpus = cpu_stats.get('online_cpus', 1)

                        cpu_percent = 0.0
                        if system_delta > 0 and cpu_delta > 0:
                            cpu_percent = (cpu_delta / system_delta) * online_cpus * 100

                        # Memory stats
                        memory_stats = stats.get('memory_stats', {})
                        mem_usage = memory_stats.get('usage', 0)
                        mem_limit = memory_stats.get('limit', 1)
                        mem_percent = (mem_usage / mem_limit) * 100 if mem_limit > 0 else 0

                        # Network stats
                        networks = stats.get('networks', {})
                        net_rx = sum(n.get('rx_bytes', 0) for n in networks.values())
                        net_tx = sum(n.get('tx_bytes', 0) for n in networks.values())

                        stat_entry = {
                            'timestamp': datetime.now().isoformat(),
                            'container': name,
                            'cpu_percent': round(cpu_percent, 2),
                            'memory_usage': mem_usage,
                            'memory_limit': mem_limit,
                            'memory_percent': round(mem_percent, 2),
                            'network_rx': net_rx,
                            'network_tx': net_tx,
                            'pids': stats.get('pids_stats', {}).get('current', 0)
                        }

                        with self._lock:
                            self.stats_history.append(stat_entry)

                    except Exception as e:
                        logger.error(f"Error collecting stats for {name}: {e}")

            except Exception as e:
                logger.error(f"Stats collection error: {e}")

            time.sleep(1)

    def _collect_cli_loop(self):
        """Collect stats using Docker CLI"""
        format_str = '{"name":"{{.Name}}","cpu":"{{.CPUPerc}}","mem":"{{.MemPerc}}","mem_usage":"{{.MemUsage}}","net_io":"{{.NetIO}}","pids":"{{.PIDs}}"}'

        while self.running:
            try:
                cmd = ['docker', 'stats', '--no-stream', '--format', format_str] + self.container_names
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

                if result.returncode == 0:
                    timestamp = datetime.now().isoformat()
                    for line in result.stdout.strip().split('\n'):
                        if line:
                            try:
                                stat = json.loads(line)
                                cpu_str = stat.get('cpu', '0%').replace('%', '')
                                mem_str = stat.get('mem', '0%').replace('%', '')

                                stat_entry = {
                                    'timestamp': timestamp,
                                    'container': stat.get('name'),
                                    'cpu_percent': float(cpu_str) if cpu_str else 0.0,
                                    'memory_percent': float(mem_str) if mem_str else 0.0,
                                    'memory_usage_str': stat.get('mem_usage', '0B'),
                                    'network_io': stat.get('net_io', '0B / 0B'),
                                    'pids': int(stat.get('pids', 0))
                                }

                                with self._lock:
                                    self.stats_history.append(stat_entry)
                            except (json.JSONDecodeError, ValueError) as e:
                                pass

            except Exception as e:
                logger.error(f"CLI stats collection error: {e}")

            time.sleep(1)

    def get_latest_stats(self) -> Dict[str, dict]:
        """Get most recent stats for each container"""
        with self._lock:
            latest = {}
            for stat in reversed(self.stats_history):
                name = stat.get('container')
                if name and name not in latest:
                    latest[name] = stat
                if len(latest) == len(self.container_names):
                    break
            return latest

    def save_stats_log(self, output_dir: Path) -> Path:
        """Save stats history to JSON file"""
        stats_file = output_dir / f"docker_stats_{datetime.now():%Y%m%d_%H%M%S}.json"
        with open(stats_file, 'w') as f:
            json.dump(self.stats_history, f, indent=2)
        logger.info(f"Stats saved to: {stats_file}")
        return stats_file


class ContainerRecorder:
    """Records a single container's display output with multiple fallback methods"""

    METHOD_PRIORITY = ['vnc_direct', 'x11_forward', 'http_stream', 'manual']

    def __init__(self, name: str, host: str, port: int, 
                 output_path: str, record_type: str = 'vnc',
                 width: int = 1280, height: int = 720,
                 password: str = None, http_port: int = None):
        self.name = name
        self.host = host
        self.port = port
        self.output_path = output_path
        self.record_type = record_type
        self.width = width
        self.height = height
        self.password = password or ''
        self.http_port = http_port  # For HTTP-based recording (KasmVNC web)
        self.process = None
        self.method_used = None
        self.error_log = []

    def test_ffmpeg_vnc(self) -> bool:
        """Test if ffmpeg supports VNC input"""
        try:
            result = subprocess.run(
                ['ffmpeg', '-h', 'demuxer=vnc'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return 'VNC' in result.stdout or result.returncode == 0
        except:
            return False

    def test_vnc_connection(self) -> bool:
        """Test if VNC port is accessible"""
        import socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((self.host, self.port))
            sock.close()
            return result == 0
        except:
            return False

    def build_vnc_command(self) -> Optional[List[str]]:
        """Build ffmpeg VNC command"""
        if not self.test_ffmpeg_vnc():
            self.error_log.append("FFmpeg does not support VNC input")
            return None

        if not self.test_vnc_connection():
            self.error_log.append(f"Cannot connect to VNC at {self.host}:{self.port}")
            return None

        cmd = [
            'ffmpeg',
            '-y',
            '-hide_banner',
            '-loglevel', 'warning',
            '-f', 'vnc',
            '-i', f'{self.host}:{self.port}',
            '-r', '24',
            '-s', f'{self.width}x{self.height}',
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-pix_fmt', 'yuv420p',
            '-movflags', '+faststart',
            self.output_path
        ]
        return cmd

    def build_http_command(self) -> Optional[List[str]]:
        """Build command to capture HTTP/web interface"""
        if not self.http_port:
            return None

        # Method: Use ffmpeg with x11grab to capture browser window
        # Requires Xvfb and browser setup (complex)
        self.error_log.append("HTTP recording requires X11 setup - not implemented")
        return None

    def build_x11_command(self) -> Optional[List[str]]:
        """Build command using X11 forwarding (if available)"""
        display = os.environ.get('DISPLAY')
        if not display:
            self.error_log.append("No DISPLAY environment variable")
            return None

        # This would require the container's X11 socket mounted
        cmd = [
            'ffmpeg',
            '-y',
            '-hide_banner',
            '-loglevel', 'warning',
            '-f', 'x11grab',
            '-draw_mouse', '1',
            '-r', '24',
            '-s', f'{self.width}x{self.height}',
            '-i', display,
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-pix_fmt', 'yuv420p',
            self.output_path
        ]
        return cmd

    def start(self) -> bool:
        """Try multiple recording methods until one works"""
        logger.info(f"Starting recording for {self.name}")

        # Try methods in priority order
        methods = {
            'vnc_direct': self.build_vnc_command,
            'x11_forward': self.build_x11_command,
            'http_stream': self.build_http_command,
        }

        for method_name in self.METHOD_PRIORITY:
            if method_name == 'manual':
                break

            builder = methods.get(method_name)
            if not builder:
                continue

            cmd = builder()
            if cmd:
                logger.info(f"Trying {method_name} method...")
                if self._try_start(cmd, method_name):
                    return True

        # All automated methods failed
        logger.error(f"All recording methods failed for {self.name}")
        for err in self.error_log:
            logger.error(f"  - {err}")
        logger.info(f"Please manually record {self.name} using a VNC viewer or OBS Studio")
        return False

    def _try_start(self, cmd: List[str], method_name: str) -> bool:
        """Attempt to start recording with given command"""
        try:
            logger.debug(f"Command: {' '.join(cmd)}")

            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid
            )

            # Wait for ffmpeg to initialize
            time.sleep(3)

            # Check if process is still running
            if self.process.poll() is None:
                self.method_used = method_name
                logger.info(f"✓ Recording started for {self.name} using {method_name}")
                return True
            else:
                stdout, stderr = self.process.communicate()
                error_msg = stderr.decode() if stderr else "Unknown error"
                self.error_log.append(f"{method_name}: {error_msg[:200]}")
                self.process = None
                return False

        except Exception as e:
            self.error_log.append(f"{method_name}: {str(e)}")
            return False

    def stop(self):
        """Stop recording gracefully"""
        if self.process is None:
            return

        logger.info(f"Stopping recording for {self.name} (method: {self.method_used})")

        try:
            os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)

            try:
                self.process.wait(timeout=5)
                logger.info(f"✓ Recording stopped gracefully")
            except subprocess.TimeoutExpired:
                logger.warning(f"Force killing {self.name} recorder")
                os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                self.process.wait()

        except ProcessLookupError:
            logger.warning(f"Process already terminated")
        except Exception as e:
            logger.error(f"Error stopping {self.name}: {e}")

        # Verify output
        if os.path.exists(self.output_path):
            size = os.path.getsize(self.output_path)
            if size > 1024:  # At least 1KB
                logger.info(f"  Output: {self.output_path} ({size / 1024 / 1024:.2f} MB)")
            else:
                logger.warning(f"  Output file is too small ({size} bytes) - may be corrupt")
        else:
            logger.error(f"  Output file not created: {self.output_path}")


class DockerComposeRecorder:
    """Main orchestrator"""

    def __init__(self, output_dir: str = "./recordings", compose_file: str = "docker-compose.yml"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.compose_file = compose_file
        self.recorders: Dict[str, ContainerRecorder] = {}
        self.stats_collector: Optional[DockerStatsCollector] = None
        self.running = False
        self.start_time = None

        # Container configurations
        self.container_configs = {
            'optimized': {
                'name': 'SlicerApp',
                'type': 'kasmvnc',
                'host': 'localhost',
                'vnc_port': 3003,
                'http_port': 3002,  # KasmVNC web interface
                'width': 1280,
                'height': 720,
                'password': 'yourpassword'
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

    def setup_recorders(self):
        """Initialize recorders"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        for container_name, config in self.container_configs.items():
            output_file = self.output_dir / f"{config['name']}_{timestamp}.mp4"

            recorder = ContainerRecorder(
                name=config['name'],
                host=config['host'],
                port=config['vnc_port'],
                output_path=str(output_file),
                record_type=config['type'],
                width=config['width'],
                height=config['height'],
                password=config['password'],
                http_port=config.get('http_port')
            )

            self.recorders[container_name] = recorder
            logger.info(f"Configured recorder for {config['name']} -> {output_file}")

    def start_recording(self, duration: Optional[int] = None, 
                       stats_only: bool = False):
        """Start recording session"""
        logger.info("=" * 60)
        logger.info("Docker Compose Multi-Container Recorder")
        logger.info("=" * 60)

        self.start_time = datetime.now()

        # Start stats collection
        container_names = list(self.container_configs.keys())
        self.stats_collector = DockerStatsCollector(container_names)
        self.stats_collector.start()

        # Setup recorders
        if not stats_only:
            self.setup_recorders()

            # Start recorders
            for name, recorder in self.recorders.items():
                try:
                    success = recorder.start()
                    if not success:
                        logger.warning(f"Could not auto-record {name} - use manual method")
                except Exception as e:
                    logger.error(f"Failed to start recorder for {name}: {e}")
        else:
            logger.info("Stats-only mode: collecting Docker metrics without video")

        self.running = True

        # Signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        logger.info("\n✓ Session started")
        logger.info(f"  Output: {self.output_dir.absolute()}")
        logger.info(f"  Containers: {', '.join(self.container_configs.keys())}")
        logger.info("\nPress Ctrl+C to stop\n")

        try:
            if duration:
                logger.info(f"Recording for {duration} seconds...")
                self._recording_loop(duration)
            else:
                self._recording_loop()
        except KeyboardInterrupt:
            logger.info("\nInterrupted by user")
        finally:
            self.stop_recording()

    def _recording_loop(self, duration: Optional[int] = None):
        """Main loop with stats display"""
        start = time.time()

        while self.running:
            os.system('clear')

            elapsed = time.time() - start
            print(f"Recording in progress - Elapsed: {int(elapsed)}s")
            print("=" * 70)

            stats = self.stats_collector.get_latest_stats()
            print(f"{'Container':<15} {'CPU %':<10} {'Memory %':<12} {'PIDs':<8} {'Status':<15}")
            print("-" * 70)

            for name in self.container_configs.keys():
                if name in stats:
                    s = stats[name]
                    status = "✓ Recording"
                    if name in self.recorders:
                        rec = self.recorders[name]
                        if rec.process is None:
                            status = "✗ Not started"
                        elif rec.process.poll() is not None:
                            status = "✗ Stopped"
                        elif rec.method_used:
                            status = f"✓ {rec.method_used}"
                    print(f"{name:<15} {s.get('cpu_percent', 0):<10.1f} "
                          f"{s.get('memory_percent', 0):<12.1f} {s.get('pids', 0):<8} {status:<15}")
                else:
                    print(f"{name:<15} {'N/A':<10} {'N/A':<12} {'N/A':<8} {'Waiting':<15}")

            print("=" * 70)
            print("\nPress Ctrl+C to stop")

            if duration and elapsed >= duration:
                logger.info(f"\nReached duration limit: {duration}s")
                break

            time.sleep(1)

    def stop_recording(self):
        """Stop all recordings"""
        if not self.running:
            return

        logger.info("\nStopping recording session...")
        self.running = False

        # Stop recorders
        for name, recorder in self.recorders.items():
            try:
                recorder.stop()
            except Exception as e:
                logger.error(f"Error stopping {name}: {e}")

        # Stop stats collection
        if self.stats_collector:
            self.stats_collector.stop()
            stats_file = self.stats_collector.save_stats_log(self.output_dir)

        self._print_summary()

    def _print_summary(self):
        """Print summary"""
        logger.info("\n" + "=" * 60)
        logger.info("Recording Session Summary")
        logger.info("=" * 60)

        if self.start_time:
            duration = datetime.now() - self.start_time
            logger.info(f"Duration: {duration}")

        logger.info(f"Output directory: {self.output_dir.absolute()}")
        logger.info("\nOutput files:")

        found_files = False
        for name, recorder in self.recorders.items():
            if os.path.exists(recorder.output_path):
                size = os.path.getsize(recorder.output_path)
                if size > 1024:
                    logger.info(f"  ✓ {recorder.output_path} ({size / 1024 / 1024:.2f} MB)")
                    found_files = True
                else:
                    logger.warning(f"  ⚠ {recorder.output_path} ({size} bytes - possibly empty)")
            else:
                logger.warning(f"  ✗ {recorder.output_path} - Not found")

        if not found_files:
            logger.warning("\nNo video files were created. Possible reasons:")
            logger.warning("  - FFmpeg doesn't have VNC support")
            logger.warning("  - VNC ports are not accessible")
            logger.warning("  - Try using --stats-only mode and record manually with OBS")

        stats_files = list(self.output_dir.glob("docker_stats_*.json"))
        if stats_files:
            latest = max(stats_files, key=os.path.getctime)
            logger.info(f"\nStats log: {latest}")

        logger.info("=" * 60)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"\n\nReceived signal {signum}")
        self.running = False


def check_prerequisites():
    """Check prerequisites"""
    required = ['docker']

    for cmd in required:
        if subprocess.run(['which', cmd], capture_output=True).returncode != 0:
            logger.error(f"Missing: {cmd}")
            sys.exit(1)

    # Check Docker running
    try:
        subprocess.run(['docker', 'ps'], capture_output=True, check=True)
        logger.info("✓ Docker is running")
    except subprocess.CalledProcessError:
        logger.error("Docker is not running")
        sys.exit(1)

    # Check ffmpeg
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        logger.info("✓ FFmpeg is installed")

        # Check VNC support
        result = subprocess.run(['ffmpeg', '-h', 'demuxer=vnc'], 
                               capture_output=True, text=True)
        if 'VNC' in result.stdout:
            logger.info("✓ FFmpeg has VNC support")
        else:
            logger.warning("✗ FFmpeg does not have VNC support - video recording will fail")
            logger.info("  Install: sudo apt-get install ffmpeg (with VNC support)")
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.error("FFmpeg not found")
        sys.exit(1)

    logger.info("✓ Prerequisites satisfied")


def main():
    parser = argparse.ArgumentParser(
        description="Record Docker Compose containers with Docker stats overlay"
    )

    parser.add_argument('-o', '--output', default='./recordings', help='Output directory')
    parser.add_argument('-d', '--duration', type=int, default=None, help='Duration in seconds')
    parser.add_argument('--stats-only', action='store_true', help='Only collect stats')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose logging')

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    check_prerequisites()

    recorder = DockerComposeRecorder(output_dir=args.output)

    try:
        recorder.start_recording(duration=args.duration, stats_only=args.stats_only)
    except Exception as e:
        logger.exception("Recording failed")
        sys.exit(1)


if __name__ == "__main__":
    main()