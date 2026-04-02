# GUI Recorder Fixes - Summary

## Issues Resolved

### 1. **optimized (KasmVNC) - ERR_EMPTY_RESPONSE**
**Problem**: Trying to access port 6901 with HTTP, but KasmVNC's VNC protocol port doesn't serve HTTP traffic
**Fix**: Changed URL from `http://optimized:6901/vnc.html` to `http://optimized:6900`
- Port 6900: HTTP web portal (where browsers connect)
- Port 6901: VNC protocol / HTTPS (not for HTTP web access)

### 2. **rossim (linuxserver webtop) - "requires secure connection"**
**Problem**: Container enforces HTTPS but recorder was using HTTP
**Fix**: Changed URL from `http://rossim:3000` to `https://rossim:3000`
- linuxserver/webtop uses self-signed HTTPS certificates by default
- Playwright now ignores HTTPS errors for webtop

### 3. **Browser Context Issues**
**Problems**:
- Missing HTTPS error handling
- No sandbox mode causing issues in container
- Navigation timeouts on continuous GUI apps

**Fixes**:
- Added `ignore_https_errors` parameter to browser context (handles self-signed certs)
- Added `--no-sandbox` and `--disable-setuid-sandbox` flags to Chromium launch
- Added fallback navigation strategies:
  1. Try `networkidle` (best for static pages)
  2. Fall back to `load` (good for dynamic pages)
  3. Fall back to `commit` (last resort - page DOM ready)

### 4. **GUI Initialization Delays**
**Problem**: Different containers need different amounts of time to initialize their web interfaces

**Fix**: Container-specific wait times:
- **KasmVNC (optimized)**: 8 seconds - needs time for VNC stream to activate
- **linuxserver webtop (rossim)**: 6 seconds - XFCE desktop rendering
- **Other GUIs**: 3 seconds default

## Files Modified

### 1. **docker-compose.yml**
```yaml
# OLD:
- ROSSIM_URL=http://rossim:3000
- OPTIMIZED_URL=http://optimized:6901/vnc.html

# NEW:
- ROSSIM_URL=https://rossim:3000
- OPTIMIZED_URL=http://optimized:6900
```

### 2. **dockerfiles/recorder/recorder.py**

#### Configuration
```python
CONTAINER_URLS = {
    "rossim": {
        "url": os.getenv("ROSSIM_URL", "https://rossim:3000"),  # HTTPS for webtop
        "auth": None,
        "ignore_https_errors": True  # Self-signed certs
    },
    "optimized": {
        "url": os.getenv("OPTIMIZED_URL", "http://optimized:6900"),  # Port 6900 (HTTP portal)
        "auth": {"username": "kasm_user", "password": VNC_PASSWORD},
        "ignore_https_errors": False  # HTTP doesn't need this
    },
}
```

#### Browser Launch
```python
browser = p.chromium.launch(
    headless=True,
    args=["--no-sandbox", "--disable-setuid-sandbox"]  # Container-safe launch
)
```

#### Context Creation
```python
context = browser.new_context(
    viewport={"width": self.width, "height": self.height},
    ignore_https_errors=self.ignore_https_errors,  # Per-container setting
    http_credentials=self.auth if self.auth else None  # HTTP Basic Auth for KasmVNC
)
```

#### Navigation with Fallbacks
```python
try:
    page.goto(self.url, wait_until="networkidle", timeout=30000)
except Exception as e:
    try:
        page.goto(self.url, wait_until="load", timeout=30000)
    except Exception as e2:
        page.goto(self.url, wait_until="commit", timeout=30000)  # Last resort
```

### 3. **dockerfiles/recorder/Dockerfile**

Added SSL/HTTPS support packages:
```dockerfile
RUN apt-get update && apt-get install -y \
    ffmpeg \
    fonts-dejavu-core \
    chromium \
    chromium-driver \
    ca-certificates \      # Certificate validation
    openssl \              # SSL/TLS support
    libssl3 \              # OpenSSL library
    libnss3 \              # NSS crypto library
    && rm -rf /var/lib/apt/lists/*
```

## Testing

To test the fixes:

```bash
# 1. Rebuild containers
docker-compose build recorder

# 2. Start containers
docker-compose up -d rossim optimized recorder

# 3. Wait 20 seconds for services to initialize
sleep 20

# 4. Check recorder status
curl http://localhost:8080/status

# 5. Start split-screen recording
curl -X POST http://localhost:8080/record_split

# 6. Let it record for 30 seconds
sleep 30

# 7. Stop recording
curl -X POST http://localhost:8080/stop_split

# 8. Check the output
ls -lh recordings/
```

## Expected Output

When working correctly, you should see:
- `[recorder] Navigating to https://rossim:3000` - initiates webtop connection
- `[recorder] Waiting 6s for linuxserver webtop desktop to initialize...` - waits for XFCE
- `[recorder] Navigating to http://optimized:6900` - initiates KasmVNC connection
- `[recorder] Waiting 8s for KasmVNC web portal to initialize...` - waits for VNC stream
- `[recorder] Captured X frames for ...` - streaming frames every 30 frames
- `[recorder] Video saved: /recordings/...` - successful encoding

## Troubleshooting

### If you still get "ERR_EMPTY_RESPONSE"
1. Verify port mapping: `docker ps | grep optimized`
   - Should show `3002->6900` (HTTP web portal)
2. Test manually: `curl -k http://localhost:3002` from host or `curl http://optimized:6900` from recorder container

### If you get "requires secure connection"
1. Verify wording in error message
2. This is expected for rossim - recorder now ignores HTTPS errors
3. Check logs: `docker logs recorder` for HTTPS error handling proof

### If recordings are blank/black
1. Increase wait times in recorder.py (GUI not fully initialized)
2. Check docker logs: `docker logs rossim` and `docker logs optimized`
3. Verify containers are healthy: `docker ps` (should show "healthy" or "running")

### If Playlist browser crashes
1. Check memory: containers may need more RAM
2. Ensure `--no-sandbox` is in browser launch args (it is)
3. Check recorder logs for specific errors

## Technical Details

- **KasmVNC** (optimized): Uses port 6900 for HTTP web portal, 6901 for VNC protocol
- **linuxserver webtop** (rossim): Uses HTTPS with self-signed certificates on port 3000
- **Playwright**: Automatically handles HTTPS errors when `ignore_https_errors=True`
- **Chromium in Docker**: Requires `--no-sandbox` flag to run as unprivileged user
