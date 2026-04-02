# Container Web Server Architecture

This document explains how the two base images handle web connections differently and why the fixes address each one appropriately.

## rossim (linuxserver/webtop:ubuntu-xfce)

### Base Image
- **Source**: `linuxserver/webtop:ubuntu-xfce`
- **Purpose**: Full XFCE desktop environment with web-based VNC viewer (noVNC)
- **Web Server**: Built-in NoVNC + HTTPS self-signed certificate

### Port Mapping
- **Container Port 3000 → Host Port 3000**
- Uses **HTTPS only** with self-signed certificate
- Enforces redirect from HTTP → HTTPS

### How It Works
1. Container runs `xinitrc` which starts XFCE desktop
2. Built-in NoVNC server listens on port 3000 with HTTPS
3. When Playwright tries HTTP, server responds with 403 or redirect
4. Browser receives "requires secure connection" error

### Fix Applied
```python
"url": "https://rossim:3000",  # Use HTTPS protocol
"ignore_https_errors": True,    # Trust self-signed certificate
```

**Why this works**: Browserencryption is still working, just validating the cert internally.

### Verification
```bash
# From inside recorder container
curl -k https://rossim:3000  # Works with -k (insecure/ignore certs)
curl http://rossim:3000      # Fails - HTTP not accepted
```

---

## optimized (kasmweb/core-ubuntu-jammy)

### Base Image
- **Source**: `kasmweb/core-ubuntu-jammy:1.18.0`
- **Purpose**: Containerized application delivery (Kasm)
- **Web Servers**: Multiple services on different ports

### Port Mapping (from docker-compose.yml)
- **3002:6900** → KasmVNC HTTP web portal
- **3003:6901** → KasmVNC VNC protocol / HTTPS

### Port Details

#### Port 6900 (HTTP Web Portal)
- Standard HTTP server for browser access
- Serves KasmVNC web application
- No authentication at connection level
- **Recommended for Playwright recording** ✓

#### Port 6901 (VNC / HTTPS)
- VNC protocol (not HTTP) - binary protocol
- Can also use HTTPS for VNC stream
- **Not for direct browser access** ✗
- This is why `http://optimized:6901/vnc.html` fails with `ERR_EMPTY_RESPONSE`

### How It Works
1. Kasm daemon starts and manages VNC server (port 6901)
2. Built-in web server serves HTTP portal on port 6900
3. Portal provides web-based VNC viewer (connects to 6901 internally)
4. Browser accesses HTTP → portal → VNC internally

### Fix Applied
```python
"url": "http://optimized:6900",    # Use HTTP web portal, not VNC port
"ignore_https_errors": False,       # HTTP doesn't need SSL handling
```

**Why this works**: Port 6900 is the correct HTTP endpoint for browser access.

### Verification
```bash
# From inside recorder container
curl http://optimized:6900          # Works - HTTP portal
curl http://optimized:6901          # Fails - Returns empty or binary VNC data
curl -k https://optimized:6901      # HTTPS VNC protocol, not for HTTP
```

---

## Connection Flow Comparison

### linuxserver (rossim)
```
Playwright Browser
    ↓ (HTTPS)
Self-signed HTTPS on port 3000
    ↓
NoVNC Viewer (embedded in HTML)
    ↓ (VNC protocol)
Local XFCE Desktop
    ↓
Screenshot content
```

**Authentication**: Optional (can be configured in environment)
**Encryption**: Always HTTPS (self-signed)
**GUI Rendering**: Full desktop environment

### Kasm (optimized)
```
Playwright Browser
    ↓ (HTTP)
HTTP Web Portal on port 6900
    ↓ (HTTP auth: kasm_user/password)
KasmVNC Application Server
    ↓ (VNC protocol internally)
HTTPS Kasm Container Session on port 6901
    ↓
Slicer + ROS 2 Application
    ↓
Screenshot content
```

**Authentication**: HTTP Basic Auth (username/password)
**Encryption**: HTTPS internal to VNC stream
**GUI Rendering**: Container application (Slicer + ROS)

---

## Browser Launch Considerations

### Container Environment Issues
When running Playwright Chromium inside Docker:

```python
# ✗ FAILS in container (permission denied)
browser = p.chromium.launch(headless=True)

# ✓ WORKS in container (no sandbox)
browser = p.chromium.launch(
    headless=True,
    args=["--no-sandbox", "--disable-setuid-sandbox"]
)
```

**Why**: Chromium's sandbox requires elevated capabilities that Docker containers typically don't have. The `--no-sandbox` flag is safe here since the container is already sandboxed.

---

## Navigation Fallback Strategy

Different containers have different loading characteristics:

1. **networkidle** (Best for static sites)
   - Waits for 500ms network silence
   - May timeout on continuous GUI updates
   - Recommended first attempt

2. **load** (Good for dynamic sites)
   - Waits for page load event
   - Doesn't wait for background resources
   - Recommended second attempt

3. **commit** (Last resort - quick)
   - Waits for DOM ready only
   - Fastest but may load incomplete page
   - Recommended for continuous GUI streams

### Application Behavior
- **rossim (XFCE desktop)**: Heavy continuous rendering → likely needs `load` or `commit`
- **optimized (Slicer app)**: Continuous 3D rendering → likely needs `load` or `commit`

Both are dynamic, so fallback strategy is essential.

---

## SSL/HTTPS Handling in Playwright

### Self-Signed Certificates
```python
# Tells Playwright to trust self-signed certs
ignore_https_errors=True
```

This is **safe** because:
- Playwright still encrypts the connection
- The certificate is still validated (just self-signed)
- Only affects certificate trust, not encryption
- Common practice for containerized testing

### HTTP Context Authentication
```python
http_credentials={
    "username": "kasm_user",
    "password": "yourpassword"
}
```

This is **automatic**:
- Playwright injects HTTP Basic Auth headers
- Sent with every request to that origin
- No need for manual header manipulation

---

## Troubleshooting Guide

### ERR_EMPTY_RESPONSE
- **Likely cause**: Wrong port (6901 instead of 6900)
- **Fix**: Verify port in URL configuration
- **Test**: `curl http://optimized:6900` vs `curl http://optimized:6901`

### "requires secure connection (https)" 
- **Likely cause**: Using HTTP for HTTPS-only server
- **Fix**: Use HTTPS URL and `ignore_https_errors=True`
- **Test**: `curl -k https://rossim:3000` vs `curl http://rossim:3000`

### Navigation timeout
- **Likely cause**: Page never reaches desired load state
- **Fix**: Fallback chain handles this automatically
- **Debug**: Check logs for which state succeeded

### Blank/black screenshots
- **Likely cause**: GUI not fully initialized during screenshot
- **Fix**: Increase initialization wait time (already done: 6-8 seconds)
- **Debug**: Check if app responds to manual browser access
