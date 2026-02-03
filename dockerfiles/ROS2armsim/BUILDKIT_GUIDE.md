# BuildKit Optimization Guide

## Quick Start

Build with BuildKit enabled:
```bash
DOCKER_BUILDKIT=1 docker build -f Dockerfile.buildkit -t ros2-moveit:buildkit .
```

Or set it permanently:
```bash
export DOCKER_BUILDKIT=1
docker build -f Dockerfile.buildkit -t ros2-moveit:buildkit .
```

## BuildKit Features Used

### 1. **Cache Mounts** (Massive Speed Improvement)
The key optimization! Cache mounts persist data between builds.

#### APT Cache (`/var/cache/apt` and `/var/lib/apt`)
```dockerfile
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y package-name
```
**Benefit**: Package lists and downloads are cached. Subsequent builds skip re-downloading packages.
**Speed gain**: 70-90% faster for apt operations on rebuilds

#### Git Cache (`/root/.gitcache`)
```dockerfile
RUN --mount=type=cache,target=/root/.gitcache,sharing=locked \
    git clone https://github.com/repo
```
**Benefit**: Git objects are cached, so cloning is faster
**Speed gain**: 50-80% faster for repeated git clones

#### Build Cache (`/root/ws_moveit/build`)
```dockerfile
RUN --mount=type=cache,target=/root/ws_moveit/build,sharing=locked \
    colcon build
```
**Benefit**: Compilation artifacts (object files) persist between builds
**Speed gain**: 60-95% faster for C++ compilation when source hasn't changed

#### ccache Support
```dockerfile
--cmake-args -DCMAKE_CXX_COMPILER_LAUNCHER=ccache
```
Combined with build cache mount, this provides incredible speedups for C++ projects.

### 2. **Parallel Layer Building**
BuildKit automatically parallelizes independent layers:
- ROS installation can happen while GUI packages are being prepared
- Multiple apt-get operations can run concurrently if they don't depend on each other

### 3. **Better Layer Caching**
The Dockerfile is structured so:
- Infrequently changing layers (base packages) come first
- Frequently changing layers (source code) come last
- Each major operation is in its own layer for granular caching

## Speed Comparison

### First Build (Cold Cache)
- **Without BuildKit**: ~45-60 minutes
- **With BuildKit**: ~40-55 minutes (10-15% faster due to parallel operations)

### Rebuild After Code Change (Warm Cache)
- **Without BuildKit**: ~45-60 minutes (rebuilds everything)
- **With BuildKit**: ~5-15 minutes (only rebuilds changed layers) ⚡ **75-90% faster!**

### Rebuild After No Changes (Warm Cache)
- **Without BuildKit**: ~2-5 minutes
- **With BuildKit**: ~10-30 seconds ⚡ **90-95% faster!**

## Advanced BuildKit Features

### Multi-Stage Builds (Optional Enhancement)
If you want to further optimize, you can use multi-stage builds:

```dockerfile
# syntax=docker/dockerfile:1.4

# Build stage
FROM linuxserver/webtop:ubuntu-xfce AS builder
# ... do all the building ...

# Runtime stage
FROM linuxserver/webtop:ubuntu-xfce
COPY --from=builder /root/ws_moveit/install /root/ws_moveit/install
```

### Inline Cache Export
Build and push with inline cache for CI/CD:
```bash
docker buildx build \
  --cache-to type=inline \
  --cache-from type=registry,ref=myrepo/ros2-moveit:cache \
  -t myrepo/ros2-moveit:latest \
  --push \
  -f Dockerfile.buildkit .
```

### Registry Cache (For CI/CD)
Use a registry to share cache between machines:
```bash
# Build with cache export
docker buildx build \
  --cache-to type=registry,ref=myrepo/ros2-cache,mode=max \
  --cache-from type=registry,ref=myrepo/ros2-cache \
  -t myrepo/ros2-moveit:latest \
  -f Dockerfile.buildkit .
```

## Enabling BuildKit Permanently

### For Docker CLI
Add to `~/.bashrc` or `~/.zshrc`:
```bash
export DOCKER_BUILDKIT=1
```

### For Docker Daemon (System-wide)
Edit `/etc/docker/daemon.json`:
```json
{
  "features": {
    "buildkit": true
  }
}
```
Then restart Docker:
```bash
sudo systemctl restart docker
```

### Using docker-compose
In `docker-compose.yml`:
```yaml
version: "3.8"
services:
  ros2:
    build:
      context: .
      dockerfile: Dockerfile.buildkit
    environment:
      DOCKER_BUILDKIT: 1
```

## Best Practices

### 1. Order Matters
Structure your Dockerfile from:
- Least frequently changing (base image, system packages)
- To most frequently changing (your code, configuration)

### 2. Use .dockerignore
Create a `.dockerignore` file:
```
.git
*.md
*.log
build/
install/
log/
__pycache__/
*.pyc
```

### 3. Combine Related Operations
Group related apt-get installs in the same RUN command to share cache mounts.

### 4. Don't Clear Caches Inside Cache Mounts
**Don't do this:**
```dockerfile
RUN --mount=type=cache,target=/var/cache/apt \
    apt-get update && apt-get install -y package \
    && rm -rf /var/lib/apt/lists/*  # ❌ Defeats the cache mount
```

**Do this:**
```dockerfile
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y package  # ✅ Cache persists
```

## Debugging BuildKit Builds

### See What's Being Cached
```bash
docker buildx du  # Show disk usage of build cache
```

### Clear Build Cache
```bash
docker buildx prune  # Remove all build cache
docker buildx prune -a  # Remove all cache including dangling
```

### Verbose Build Output
```bash
DOCKER_BUILDKIT=1 docker build --progress=plain -f Dockerfile.buildkit .
```

## Measuring Your Speedup

Time your builds:
```bash
# First build
time DOCKER_BUILDKIT=1 docker build -f Dockerfile.buildkit -t test1 .

# Rebuild (no changes)
time DOCKER_BUILDKIT=1 docker build -f Dockerfile.buildkit -t test2 .

# Make a small code change, then rebuild
echo "// change" >> /root/ws_moveit/src/some_file.cpp
time DOCKER_BUILDKIT=1 docker build -f Dockerfile.buildkit -t test3 .
```

## Additional Optimizations

### Install ccache in the Image
For even better build caching:
```dockerfile
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    apt-get update && apt-get install -y ccache

ENV PATH="/usr/lib/ccache:${PATH}"
ENV CCACHE_DIR=/root/.ccache
```

### Increase Parallel Workers (If You Have RAM)
If you have >16GB RAM:
```dockerfile
colcon build --parallel-workers 2  # Use 2 workers instead of 1
```

### Use tmpfs for Build Directory
For ultimate speed (requires enough RAM):
```bash
docker build --memory=16g --shm-size=4g -f Dockerfile.buildkit .
```

## Troubleshooting

### "syntax directive must be first line"
Make sure `# syntax=docker/dockerfile:1.4` is the **very first line** of your Dockerfile.

### Cache not persisting between builds
Make sure BuildKit is enabled:
```bash
docker version | grep BuildKit
```

### Out of disk space
BuildKit caches can grow large. Clean up:
```bash
docker buildx prune -f
```

## Summary

BuildKit provides:
- ✅ **75-90% faster rebuilds** with cache mounts
- ✅ **Parallel layer building** for independent operations  
- ✅ **Better cache granularity** with layer caching
- ✅ **Persistent build caches** across builds
- ✅ **Shared caches** for CI/CD with registry caching

The main win: After the first build, you'll only rebuild what actually changed!
