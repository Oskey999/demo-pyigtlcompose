"""
TMS Stack — Container GUI Recorder (Web Browser Recording with HTTP Basic Auth)
Uses Playwright with HTTP authentication for KasmVNC.
"""

import os
import re
import signal
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict

import docker as docker_sdk
from flask import Flask, jsonify
from playwright.sync_api import sync_playwright

# ── Config ────────────────────────────────────────────────────────────────────
OUTPUT_DIR     = Path(os.getenv("OUTPUT_DIR", "/recordings"))
FPS            = int(os.getenv("FPS", "24"))
GUI_WIDTH      = int(os.getenv("GUI_WIDTH", "960"))
GUI_HEIGHT     = int(os.getenv("GUI_HEIGHT", "540"))
STATS_HEIGHT   = int(os.getenv("STATS_HEIGHT", "320"))
STATS_INTERVAL = int(os.getenv("STATS_INTERVAL", "2"))
AUTO_RECORD    = os.getenv("AUTO_RECORD", "split")
DOCKER_SOCKET  = os.getenv("DOCKER_SOCKET", "/var/run/docker.sock")
VNC_PASSWORD   = os.getenv("VNC_PASSWORD", "yourpassword")

# Web URLs for each container
# rossim (linuxserver/webtop) uses HTTP on port 3000 (nginx reverse proxy)
# optimized (KasmVNC) uses HTTPS on port 6901 (WebSocket + encrypted tunnel)
CONTAINER_URLS = {
    "rossim": {
        "url": os.getenv("ROSSIM_URL", "http://rossim:3000"),
        "auth": None,  # No auth for LinuxServer webtop
        "ignore_https_errors": False
    },
    "optimized": {
        "url": os.getenv("OPTIMIZED_URL", "https://optimized:6901"),
        "auth": {
            "username": "kasm_user",
            "password": VNC_PASSWORD
        },
        "ignore_https_errors": True  # KasmVNC uses self-signed certs
    },
}

CONTAINERS   = [c.strip() for c in os.getenv("CONTAINERS", "").split(",") if c.strip()]
SPLIT_LABELS = [l.strip() for l in os.getenv("SPLIT_LABELS", "").split(",") if l.strip()]

while len(SPLIT_LABELS) < len(CONTAINERS):
    SPLIT_LABELS.append(CONTAINERS[len(SPLIT_LABELS)])

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
STATS_FILE = Path(tempfile.gettempdir()) / "docker_stats.txt"


# ── Docker stats collector ────────────────────────────────────────────────────
class StatsCollector:
    HEADER    = (
        f"{'CONTAINER':<22} {'CPU %':>7}  {'MEM USAGE / LIMIT':<24} "
        f"{'MEM %':>6}  {'NET I/O':<20}  {'BLOCK I/O':<18}"
    )
    SEPARATOR = "─" * 100

    def __init__(self):
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._client = None

    def start(self) -> None:
        if not Path(DOCKER_SOCKET).exists():
            self._write_placeholder()
            return
        try:
            self._client = docker_sdk.DockerClient(base_url=f"unix://{DOCKER_SOCKET}")
            self._client.ping()
        except Exception as exc:
            print(f"[stats] Docker error: {exc}", flush=True)
            self._write_placeholder()
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._refresh()
            except Exception as exc:
                print(f"[stats] Refresh error: {exc}", flush=True)
            self._stop_event.wait(STATS_INTERVAL)

    def _refresh(self) -> None:
        try:
            containers = self._client.containers.list()
            lines = [self.HEADER, self.SEPARATOR]
            for container in containers:
                try:
                    raw = container.stats(stream=False)
                    name = container.name
                    cpu_delta = (raw["cpu_stats"]["cpu_usage"]["total_usage"] -
                                raw["precpu_stats"]["cpu_usage"]["total_usage"])
                    system_delta = (raw["cpu_stats"]["system_cpu_usage"] -
                                   raw["precpu_stats"].get("system_cpu_usage", 0))
                    num_cpus = raw["cpu_stats"].get("online_cpus") or 1
                    cpu_pct = (cpu_delta / system_delta * num_cpus * 100.0 
                              if system_delta > 0 else 0.0)
                    cpu_str = f"{cpu_pct:.2f}%"
                    
                    mem_stats = raw["memory_stats"]
                    mem_usage = mem_stats.get("usage", 0)
                    mem_limit = mem_stats.get("limit", 1)
                    cache = mem_stats.get("stats", {}).get("cache", 0)
                    mem_real = mem_usage - cache
                    mem_pct = (mem_real / mem_limit * 100.0) if mem_limit > 0 else 0.0
                    mem_str = f"{self._fmt_bytes(mem_real)} / {self._fmt_bytes(mem_limit)}"
                    mem_pct_str = f"{mem_pct:.2f}%"
                    
                    net_rx, net_tx = 0, 0
                    for iface in raw.get("networks", {}).values():
                        net_rx += iface.get("rx_bytes", 0)
                        net_tx += iface.get("tx_bytes", 0)
                    net_str = f"{self._fmt_bytes(net_rx)} / {self._fmt_bytes(net_tx)}"
                    
                    blk_read, blk_write = 0, 0
                    for entry in raw.get("blkio_stats", {}).get("io_service_bytes_recursive") or []:
                        if entry.get("op") == "Read":
                            blk_read += entry.get("value", 0)
                        elif entry.get("op") == "Write":
                            blk_write += entry.get("value", 0)
                    blk_str = f"{self._fmt_bytes(blk_read)} / {self._fmt_bytes(blk_write)}"
                    
                    lines.append(f"{name:<22} {cpu_str:>7}  {mem_str:<24} {mem_pct_str:>6}  {net_str:<20}  {blk_str:<18}")
                except Exception:
                    pass
            if len(lines) == 2:
                lines.append("  (no running containers)")
            ts = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
            lines += [self.SEPARATOR, f"  Updated: {ts}"]
            STATS_FILE.write_text("\n".join(lines), encoding="utf-8")
        except Exception as e:
            print(f"[stats] Error: {e}", flush=True)

    def _write_placeholder(self) -> None:
        placeholder = f"{self.HEADER}\n{self.SEPARATOR}\n  Stats unavailable\n{self.SEPARATOR}"
        STATS_FILE.write_text(placeholder, encoding="utf-8")

    @staticmethod
    def _fmt_bytes(n: int) -> str:
        for unit in ("B", "kB", "MB", "GB", "TB"):
            if n < 1024:
                return f"{n:.2f}{unit}" if unit != "B" else f"{n}{unit}"
            n /= 1024
        return f"{n:.2f}PB"


# ── Web Recorder Thread ─────────────────────────────────────────────────────
class WebRecorderThread(threading.Thread):
    """Records a web page using Playwright with optional HTTP Basic Auth and HTTPS support."""
    
    def __init__(self, url: str, output_path: str, width: int, height: int, fps: int, auth: Optional[Dict] = None, ignore_https_errors: bool = True):
        super().__init__(daemon=True)
        self.url = url
        self.output_path = output_path
        self.width = width
        self.height = height
        self.fps = fps
        self.auth = auth  # Dict with 'username' and 'password' or None
        self.ignore_https_errors = ignore_https_errors
        self.stop_event = threading.Event()
        self.frames_dir = Path(tempfile.gettempdir()) / f"frames_{int(time.time())}"
        self.error: Optional[str] = None
        
    def run(self):
        try:
            self.frames_dir.mkdir(exist_ok=True)
            
            # LOG THE URL BEING USED BY THIS THREAD - CRITICAL DEBUG INFO
            print(f"[recorder] WebRecorderThread starting for: URL={self.url}, OUTPUT={self.output_path}", flush=True)
            
            with sync_playwright() as p:
                # Launch browser with no sandbox for container environments
                browser = p.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-setuid-sandbox"]
                )
                
                print(f"[recorder] Browser launched for {self.url}. Browser ID: {id(browser)}", flush=True)
                
                # Create context with auth if provided
                context_options = {
                    "viewport": {"width": self.width, "height": self.height},
                    "ignore_https_errors": self.ignore_https_errors,  # Use instance setting
                }
                if self.auth:
                    context_options["http_credentials"] = {
                        "username": self.auth["username"],
                        "password": self.auth["password"]
                    }
                    print(f"[recorder] Using HTTP auth for {self.url}", flush=True)
                
                context = browser.new_context(**context_options)
                page = context.new_page()
                
                # Handle SSL certificate errors for self-signed certs
                context.set_extra_http_headers({"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"})
                
                # Navigate to URL with retry logic (services may not be ready yet)
                print(f"[recorder] Navigating to {self.url}", flush=True)
                
                max_retries = 3
                retry_delay = 5
                navigation_success = False
                
                for attempt in range(1, max_retries + 1):
                    try:
                        response = None
                        try:
                            # Try with networkidle first (good for GUI apps)
                            response = page.goto(self.url, wait_until="networkidle", timeout=30000)
                        except Exception as e:
                            # networkidle can timeout on continuous GUI apps, try load state
                            print(f"[recorder] networkidle timed out, trying load state: {str(e)[:100]}", flush=True)
                            try:
                                response = page.goto(self.url, wait_until="load", timeout=30000)
                            except Exception as e2:
                                # Last resort: commit state (page structure loaded, not full resources)
                                print(f"[recorder] load failed, trying commit state: {str(e2)[:100]}", flush=True)
                                response = page.goto(self.url, wait_until="commit", timeout=30000)
                        
                        # Check response status
                        if response:
                            status = response.status
                            print(f"[recorder] Navigation to {self.url} response status: {status}", flush=True)
                            if status >= 400:
                                raise Exception(f"HTTP {status} error loading {self.url}")
                        else:
                            print(f"[recorder] WARNING: No response from {self.url}, page may not have loaded", flush=True)
                        
                        # Verify page actually loaded content (check title or body)
                        try:
                            title = page.title()
                            body_html = page.content()[:500]  # Get first 500 chars of body
                            print(f"[recorder] Page title: {title}", flush=True)
                            print(f"[recorder] Page HTML (first 500 chars): {body_html[:100]}...", flush=True)
                        except Exception as e:
                            print(f"[recorder] Could not get page content: {e}", flush=True)
                        
                        navigation_success = True
                        break
                    except Exception as e:
                        if attempt < max_retries:
                            error_msg = str(e)
                            if "CONNECTION_REFUSED" in error_msg or "SSL_PROTOCOL_ERROR" in error_msg:
                                print(f"[recorder] Attempt {attempt}/{max_retries} failed (service not ready). Retrying in {retry_delay}s...", flush=True)
                                time.sleep(retry_delay)
                                retry_delay = min(retry_delay + 5, 15)  # Exponential backoff, max 15s
                            else:
                                raise
                        else:
                            raise
                
                if not navigation_success:
                    raise Exception(f"Failed to navigate to {self.url} after {max_retries} attempts")
                
                # Additional wait for GUI to fully initialize
                # KasmVNC (optimized) is SLOW - needs significant time for VNC stream to establish
                # linuxserver webtop (rossim) needs time for XFCE desktop to render
                if "6901" in self.url or "optimized" in self.url.lower():
                    print(f"[recorder] Waiting 25s for KasmVNC HTTPS portal content to fully initialize...", flush=True)
                    time.sleep(5)  # Let page settle
                    try:
                        page.wait_for_load_state("networkidle", timeout=5000)
                        print(f"[recorder] Network idle reached for optimized", flush=True)
                    except:
                        print(f"[recorder] Network idle timeout for optimized, continuing", flush=True)
                    time.sleep(20)  # Additional time for VNC stream to render
                elif "3000" in self.url or "rossim" in self.url.lower() or "webtop" in self.url.lower():
                    print(f"[recorder] Waiting 25s total for linuxserver webtop desktop to initialize...", flush=True)
                    # First try to wait for network idle
                    try:
                        page.wait_for_load_state("networkidle", timeout=8000)
                        print(f"[recorder] Network idle reached for rossim", flush=True)
                    except Exception as e:
                        print(f"[recorder] Network idle timeout for rossim: {str(e)[:80]}, continuing anyway", flush=True)
                    # Reload the page to ensure fresh render
                    try:
                        print(f"[recorder] Reloading page to ensure content renders...", flush=True)
                        page.reload(wait_until="domcontentloaded")
                        print(f"[recorder] Page reloaded for {self.url}", flush=True)
                    except:
                        print(f"[recorder] Page reload failed, continuing with current state", flush=True)
                    time.sleep(15)  # Give it time to render everything after reload
                else:
                    print(f"[recorder] Waiting 10s for page to settle...", flush=True)
                    time.sleep(10)
                
                frame_count = 0
                frame_interval = 1.0 / self.fps
                next_frame = time.time()
                
                # Capture first frame for debugging
                first_frame_path = self.frames_dir / "frame_000000.png"
                first_screenshot = True
                
                # Get viewport info
                try:
                    viewport = page.viewport
                    print(f"[recorder] Page viewport: {viewport}", flush=True)
                except Exception as e:
                    print(f"[recorder] Could not get viewport: {e}", flush=True)
                
                while not self.stop_event.is_set():
                    try:
                        # Screenshot
                        frame_path = self.frames_dir / f"frame_{frame_count:06d}.png"
                        page.screenshot(path=str(frame_path), full_page=False)
                        
                        #Log first frame capture to check what we're actually recording
                        if first_screenshot:
                            size_kb = Path(frame_path).stat().st_size / 1024
                            print(f"[recorder] First frame captured: {size_kb:.1f} KB from {self.url}", flush=True)
                            
                            # Save a copy for inspection
                            debug_dir = Path("/tmp/first_frames_debug")
                            debug_dir.mkdir(exist_ok=True)
                            safe_name = self.url.replace("://", "_").replace(":", "_").replace("/", "_")[:50]
                            debug_copy = debug_dir / f"first_{safe_name}.png"
                            try:
                                import shutil
                                shutil.copy(str(frame_path), str(debug_copy))
                                print(f"[recorder] Debug copy saved to: {debug_copy}", flush=True)
                            except Exception as e:
                                print(f"[recorder] Could not save debug copy: {e}", flush=True)
                            
                            first_screenshot = False
                        
                        frame_count += 1
                        
                        # Log progress every 30 frames
                        if frame_count % 30 == 0:
                            print(f"[recorder] Captured {frame_count} frames for {self.url}", flush=True)
                        
                        # Maintain FPS
                        next_frame += frame_interval
                        sleep_time = next_frame - time.time()
                        if sleep_time > 0:
                            time.sleep(sleep_time)
                            
                    except Exception as e:
                        print(f"[recorder] Frame capture error: {e}", flush=True)
                        time.sleep(0.1)
                
                browser.close()
            
            if frame_count == 0:
                self.error = "No frames captured"
                return
            
            # Encode frames to video using FFmpeg
            print(f"[recorder] Encoding {frame_count} frames to video...", flush=True)
            cmd = [
                "ffmpeg", "-y",
                "-framerate", str(self.fps),
                "-i", str(self.frames_dir / "frame_%06d.png"),
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-crf", "23",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                self.output_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"[recorder] FFmpeg error: {result.stderr}", flush=True)
                self.error = f"FFmpeg encoding failed: {result.stderr[:200]}"
            else:
                print(f"[recorder] Video saved: {self.output_path}", flush=True)
            
        except Exception as e:
            self.error = str(e)
            print(f"[recorder] Web recording error: {e}", flush=True)
        finally:
            # Clean up frames
            for f in self.frames_dir.glob("*.png"):
                try:
                    f.unlink()
                except:
                    pass
            try:
                self.frames_dir.rmdir()
            except:
                pass
                
    def stop(self):
        self.stop_event.set()


# ── Session ───────────────────────────────────────────────────────────────────
@dataclass
class Session:
    name: str
    output_path: str
    thread: Optional[WebRecorderThread] = field(default=None, repr=False)
    threads: List[WebRecorderThread] = field(default_factory=list, repr=False)
    process: Optional[subprocess.Popen] = field(default=None, repr=False)
    temp_files: List[str] = field(default_factory=list, repr=False)
    start_time: float = field(default_factory=time.time)
    kind: str = "individual"


# ── Recorder ──────────────────────────────────────────────────────────────────
class Recorder:

    def __init__(self):
        self.sessions: Dict[str, Session] = {}
        self._lock = threading.Lock()
        self.stats = StatsCollector()
        self._verify_output_dir()

    def _verify_output_dir(self) -> None:
        try:
            test_file = OUTPUT_DIR / ".write_test"
            test_file.write_text("test")
            test_file.unlink()
            print(f"[recorder] Output directory ready: {OUTPUT_DIR}", flush=True)
        except (PermissionError, OSError) as e:
            print(f"[recorder] CRITICAL: Cannot write to {OUTPUT_DIR}: {e}", flush=True)
            raise

    def _stop_process(self, proc: Optional[subprocess.Popen], timeout: int = 120) -> str:
        if proc is None:
            return ""
        if proc.poll() is not None:
            # Process already finished - read any captured stderr
            try:
                _, stderr = proc.communicate(timeout=1)
                return stderr.decode('utf-8', errors='ignore') if stderr else ""
            except:
                return ""
        try:
            # Wait for process to complete normally (for FFmpeg encoding to finish)
            _, stderr = proc.communicate(timeout=timeout)
            print(f"[recorder] Process completed successfully", flush=True)
            return stderr.decode('utf-8', errors='ignore') if stderr else ""
        except subprocess.TimeoutExpired:
            print(f"[recorder] Process timeout after {timeout}s, terminating...", flush=True)
            proc.terminate()
            try:
                _, stderr = proc.communicate(timeout=10)
                return stderr.decode('utf-8', errors='ignore') if stderr else ""
            except subprocess.TimeoutExpired:
                print(f"[recorder] Force killing process", flush=True)
                proc.kill()
                _, stderr = proc.communicate()
                return stderr.decode('utf-8', errors='ignore') if stderr else ""

    def start(self, container_name: str) -> dict:
        """Record a single container's web interface."""
        with self._lock:
            if container_name in self.sessions:
                return {"error": f"Already recording '{container_name}'"}

        # Get URL and auth for this container
        config = CONTAINER_URLS.get(container_name)
        if not config:
            return {"error": f"No URL configured for '{container_name}'"}
        
        url = config["url"]
        auth = config.get("auth")
        ignore_https = config.get("ignore_https_errors", True)

        out = self._output_path(container_name)

        # Create and start web recorder thread
        thread = WebRecorderThread(
            url=url,
            output_path=out,
            width=GUI_WIDTH,
            height=GUI_HEIGHT,
            fps=FPS,
            auth=auth,
            ignore_https_errors=ignore_https
        )
        
        session = Session(name=container_name, output_path=out, thread=thread, kind="individual")
        
        with self._lock:
            self.sessions[container_name] = session
            
        thread.start()
        
        # Wait a moment to check for immediate errors
        time.sleep(2)
        if thread.error:
            with self._lock:
                self.sessions.pop(container_name, None)
            return {"error": f"Failed to start recording: {thread.error}"}
        
        if not thread.is_alive():
            with self._lock:
                self.sessions.pop(container_name, None)
            return {"error": "Recording thread died immediately"}
        
        print(f"[recorder] Started web recording for '{container_name}' -> {out}", flush=True)
        return {
            "started": container_name, 
            "kind": "individual", 
            "output": out, 
            "url": url,
            "auth": "enabled" if auth else "none"
        }

    def start_split(self, containers: Optional[List[str]] = None, labels: Optional[List[str]] = None) -> dict:
        """
        Split-screen recording using web capture for each container.
        """
        session_key = "__split__"
        with self._lock:
            if session_key in self.sessions:
                return {"error": "Split-screen recording already active"}

        targets = containers or CONTAINERS
        lbls = labels or SPLIT_LABELS
        
        if len(targets) < 2:
            return {"error": "Split-screen requires at least 2 containers"}

        self.stats.start()
        if not STATS_FILE.exists():
            STATS_FILE.write_text("Collecting stats...", encoding="utf-8")

        out = self._output_path("splitscreen")
        total_width = GUI_WIDTH * len(targets)
        total_height = GUI_HEIGHT
        font_path = self._find_font()
        font_size = max(14, STATS_HEIGHT // 18)
        label_size = max(18, GUI_HEIGHT // 22)
        
        # Stats bar configuration
        stats_bar_height = 40  # Height in pixels for stats overlay
        stats_y = GUI_HEIGHT - stats_bar_height  # Position at bottom of each panel

        # Start individual web recorders for each target
        temp_files = []
        threads = []
        file_to_container = {}  # Map temp file to container name for proper ordering
        
        for i, name in enumerate(targets):
            config = CONTAINER_URLS.get(name)
            if not config:
                # Stop already started threads
                for t in threads:
                    t.stop()
                    t.join(timeout=5)
                return {"error": f"No URL configured for '{name}'"}
            
            url = config["url"]
            auth = config.get("auth")
            ignore_https = config.get("ignore_https_errors", True)
            
            temp_file = str(OUTPUT_DIR / f"temp_{name}_{int(time.time())}.mp4")
            temp_files.append(temp_file)
            file_to_container[temp_file] = name  # Track which container produced which file
            
            # Start web recorder thread
            thread = WebRecorderThread(
                url=url,
                output_path=temp_file,
                width=GUI_WIDTH,
                height=GUI_HEIGHT,
                fps=FPS,
                auth=auth,
                ignore_https_errors=ignore_https
            )
            threads.append(thread)
            thread.start()
            print(f"[recorder] Started web recording for '{name}' (auth: {auth is not None}) -> {temp_file}", flush=True)

        # Wait for all recordings to initialize and capture video
        # Increased time to allow retry logic and actual recording
        # Note: KasmVNC takes ~20s to initialize, plus need time to record
        print(f"[recorder] Waiting 90s for recordings to capture frames (includes container init time)...", flush=True)
        time.sleep(90)
        
        # Stop all recording threads so they finish encoding their individual videos
        print(f"[recorder] Stopping recording threads to finalize video encoding...", flush=True)
        for thread in threads:
            thread.stop()
        
        # Wait for threads to finish (encoding can take time)
        print(f"[recorder] Waiting up to 60s for video encoding to complete...", flush=True)
        for i, thread in enumerate(threads):
            thread.join(timeout=60)
            if thread.is_alive():
                print(f"[recorder] WARNING: Thread {targets[i]} is still alive after timeout", flush=True)
        
        # Check for errors after threads have finished
        errors = []
        for i, thread in enumerate(threads):
            if thread.error:
                errors.append(f"{targets[i]}: {thread.error}")
        
        if errors:
            # Stop all threads
            for t in threads:
                t.stop()
                t.join(timeout=5)
            return {"error": f"Recording errors: {'; '.join(errors)}"}

        # Check if files exist and have content - preserve container order
        valid_files = []
        valid_containers = []
        for temp_file in temp_files:
            if Path(temp_file).exists() and Path(temp_file).stat().st_size > 1024:
                valid_files.append(temp_file)
                valid_containers.append(file_to_container[temp_file])
                file_size_mb = Path(temp_file).stat().st_size / (1024*1024)
                print(f"[recorder] Valid recording: {temp_file} ({file_to_container[temp_file]}) - {file_size_mb:.2f} MB", flush=True)
            else:
                print(f"[recorder] Invalid or missing file: {temp_file}", flush=True)
        
        print(f"[recorder] Recording order -> Containers: {valid_containers}", flush=True)
        print(f"[recorder] Target order: {targets}", flush=True)
        
        if len(valid_files) < 2:
            # Stop all threads and return error
            for t in threads:
                t.stop()
                t.join(timeout=5)
            return {"error": f"Not enough valid recordings. Found {len(valid_files)}, need 2"}

        # Now combine all MP4s into split-screen with proper container ordering
        inputs = []
        filter_parts = []
        
        for i, (temp_file, container_name) in enumerate(zip(valid_files, valid_containers)):
            inputs.extend(["-i", temp_file])
            # Use container name as label, not the generic label from SPLIT_LABELS
            safe_label = container_name.replace("'", "'\\\\''")
            # Build filter chain: scale -> pad to target size -> add label
            filter_str = (
                f"[{i}:v]"
                f"scale={GUI_WIDTH}:{GUI_HEIGHT}:force_original_aspect_ratio=decrease,"
                f"pad={GUI_WIDTH}:{GUI_HEIGHT}:(ow-iw)/2:(oh-ih)/2,"
                f"drawbox=x=0:y=0:w={GUI_WIDTH}:h={label_size + 12}:color=black@0.6:t=fill,"
                f"drawtext=fontfile={font_path}:text='{safe_label}':fontsize={label_size}:fontcolor=white:x=10:y=6"
                f"[gui{i}]"
            )
            filter_parts.append(filter_str)
            print(f"[recorder] Filter [{i}] (from {temp_file}): label='{safe_label}'", flush=True)
        
        # Horizontal stack with final output scaling
        gui_tags = "".join([f"[gui{i}]" for i in range(len(valid_files))])
        filter_complex = f"{';'.join(filter_parts)};{gui_tags}hstack=inputs={len(valid_files)}[stacked];[stacked]scale={total_width}:{GUI_HEIGHT}[out]"
        
        print(f"[recorder] FFmpeg filter: {filter_complex[:200]}...", flush=True)

        # Build FFmpeg command
        cmd = [
            "ffmpeg", "-y",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", "[out]",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "20",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            out
        ]

        print(f"[recorder] FFmpeg inputs: {inputs}", flush=True)
        print(f"[recorder] Starting FFmpeg video composition...", flush=True)
        print(f"[recorder] Output: {out} ({total_width}x{GUI_HEIGHT})", flush=True)
        
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        
        session = Session(
            name=session_key, 
            output_path=out, 
            process=proc,
            temp_files=temp_files,
            threads=threads,
            kind="split"
        )
        
        with self._lock:
            self.sessions[session_key] = session

        return {
            "started": "split-screen",
            "containers": targets,
            "output": out,
            "resolution": f"{total_width}x{total_height}",
            "temp_files": temp_files,
            "valid_files": len(valid_files)
        }

    def stop(self, container_name: str) -> dict:
        with self._lock:
            session = self.sessions.get(container_name)
        if not session:
            return {"error": f"No active recording for '{container_name}'"}

        # Stop web recorder threads
        if session.threads:
            for thread in session.threads:
                if thread.is_alive():
                    thread.stop()
                    thread.join(timeout=30)
        elif session.thread:
            if session.thread.is_alive():
                session.thread.stop()
                session.thread.join(timeout=30)

        # Wait for FFmpeg process to finish (critical for split-screen)
        if session.process:
            print(f"[recorder] Waiting for FFmpeg to finish encoding...", flush=True)
            stderr_output = self._stop_process(session.process, timeout=300)  # Allow up to 5 minutes for encoding
            if stderr_output:
                # Log the last 20 lines of FFmpeg output
                lines = stderr_output.split('\n')
                relevant_lines = [l for l in lines if 'error' in l.lower() or 'frame=' in l or 'muxing overhead' in l]
                if relevant_lines:
                    print(f"[recorder] FFmpeg output (last lines):", flush=True)
                    for line in relevant_lines[-10:]:
                        print(f"  {line}", flush=True)
            print(f"[recorder] FFmpeg encoding complete", flush=True)

        if session.kind == "split":
            self.stats.stop()
            # Clean up temp files AFTER FFmpeg finishes
            print(f"[recorder] Cleaning up temporary files...", flush=True)
            for temp_file in session.temp_files:
                try:
                    Path(temp_file).unlink(missing_ok=True)
                    print(f"[recorder] Deleted: {temp_file}", flush=True)
                except Exception as e:
                    print(f"[recorder] Failed to delete {temp_file}: {e}", flush=True)

        elapsed = round(time.time() - session.start_time, 1)
        
        out_path = Path(session.output_path)
        file_info = "not found"
        if out_path.exists():
            size_mb = out_path.stat().st_size / (1024 * 1024)
            file_info = f"{size_mb:.2f} MB"

        with self._lock:
            self.sessions.pop(container_name, None)

        return {
            "stopped": container_name,
            "duration_seconds": elapsed,
            "output": session.output_path,
            "file_info": file_info,
        }

    def stop_split(self) -> dict:
        return self.stop("__split__")

    def stop_all(self) -> list:
        return [self.stop(name) for name in list(self.sessions.keys())]

    def status(self) -> dict:
        with self._lock:
            result = {}
            for name, s in self.sessions.items():
                out_path = Path(s.output_path)
                file_info = None
                if out_path.exists():
                    file_info = {
                        "size_mb": round(out_path.stat().st_size / (1024 * 1024), 2),
                        "modified": datetime.fromtimestamp(out_path.stat().st_mtime).isoformat()
                    }
                
                is_alive = False
                if s.threads:
                    is_alive = any(t.is_alive() for t in s.threads)
                elif s.thread:
                    is_alive = s.thread.is_alive()
                
                result[name] = {
                    "kind": s.kind,
                    "output": s.output_path,
                    "running_seconds": round(time.time() - s.start_time, 1),
                    "alive": is_alive,
                    "file_info": file_info,
                }
            return result

    @staticmethod
    def _output_path(label: str) -> str:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe = re.sub(r"[^\w\-]", "_", label)
        return str(OUTPUT_DIR / f"{safe}_{ts}.mp4")

    @staticmethod
    def _find_font() -> str:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
            "/usr/share/fonts/dejavu/DejaVuSansMono.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
        ]
        for path in candidates:
            if Path(path).exists():
                return path
        return candidates[0]


# ── Flask API ─────────────────────────────────────────────────────────────────
recorder = Recorder()
app = Flask(__name__)

@app.get("/status")
def api_status():
    return jsonify(recorder.status())

@app.post("/record/<name>")
def api_record(name):
    return jsonify(recorder.start(name))

@app.post("/stop/<name>")
def api_stop(name):
    return jsonify(recorder.stop(name))

@app.post("/stop_all")
def api_stop_all():
    return jsonify(recorder.stop_all())

@app.post("/record_split")
def api_record_split():
    return jsonify(recorder.start_split())

@app.post("/stop_split")
def api_stop_split():
    return jsonify(recorder.stop_split())

# ── Entry point ───────────────────────────────────────────────────────────────
def _auto_start():
    print("[recorder] Waiting 30s for web servers to fully initialize...", flush=True)
    time.sleep(30)
    
    if AUTO_RECORD == "split":
        print("[recorder] Auto-starting split-screen...", flush=True)
        result = recorder.start_split()
        print(f"[recorder] Result: {result}", flush=True)
    elif AUTO_RECORD == "individual":
        for name in CONTAINERS:
            result = recorder.start(name)
            print(f"[recorder] Result for {name}: {result}", flush=True)

if __name__ == "__main__":
    if AUTO_RECORD and CONTAINERS:
        threading.Thread(target=_auto_start, daemon=True).start()
    
    def _shutdown(sig, frame):
        print("\n[recorder] SIGTERM received — stopping...", flush=True)
        recorder.stop_all()
        raise SystemExit(0)
    
    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)
    app.run(host="0.0.0.0", port=8080)