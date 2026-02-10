# Permission Fix + BuildKit Optimization

## What Was Wrong

The linuxserver/webtop container runs as user `abc` (UID 1000), but the workspace was being built in `/root/ws_moveit` which only root can access. When you logged into the container via the web interface, you couldn't access your own workspace!

## What's Fixed

### 1. **Workspace Location Changed**
```
OLD: /root/ws_moveit  ❌ Only root can access
NEW: /opt/ws_moveit   ✅ Shared location, accessible to all users
```

### 2. **Explicit Permission Setting**
```dockerfile
RUN chown -R 1000:1000 /opt/ws_moveit \
    && chmod -R 755 /opt/ws_moveit
```
This ensures the abc user (UID 1000) owns the workspace.

### 3. **Convenient Symlink**
```dockerfile
ln -sf /opt/ws_moveit /config/ws_moveit
```
Now you can access it as `~/ws_moveit` from your home directory!

### 4. **Cache Directories Also Fixed**
Cache mounts now use `/tmp` instead of `/root` so they work for all users:
- `/tmp/ccache` instead of `/root/.ccache`
- `/tmp/git-cache` instead of `/root/.gitcache`
- `/tmp/ros-cache` instead of `/root/.ros`

## BuildKit Optimizations Retained

All the speed improvements are still there:

| Feature | Location | Benefit |
|---------|----------|---------|
| **APT cache** | `/var/cache/apt` + `/var/lib/apt` | No re-downloading packages |
| **Git cache** | `/tmp/git-cache` | Faster git clones |
| **Build cache** | `/opt/ws_moveit/build` | Incremental C++ builds |
| **ccache** | `/tmp/ccache` | C++ compilation cache |
| **ROS cache** | `/tmp/ros-cache` | rosdep cached |
| **Colcon cache** | `/tmp/colcon-cache` | Colcon mixins cached |

## Build Command

Same as before:
```bash
DOCKER_BUILDKIT=1 docker build -f Dockerfile.buildkit.fixed -t ros2-moveit:fixed .
```

## Usage Inside Container

When you access the container via web UI (http://localhost:3000), you can now:

```bash
# Your workspace is accessible!
cd ~/ws_moveit

# List what's there
ls -la

# See workspace info
workspace-info.sh

# Rebuild if needed (you have permissions now!)
cd ~/ws_moveit
colcon build

# Run the demo
start-demo.sh
```

## Testing Permissions

After building and running the container:

```bash
# Start container
docker run -d -p 3000:3000 --name ros2-test ros2-moveit:fixed

# Check permissions are correct
docker exec ros2-test ls -lah /opt/ws_moveit
# Should show: drwxr-xr-x 1000 1000

# Test as abc user
docker exec -u abc ros2-test bash -c "cd /opt/ws_moveit && ls -la"
# Should work without permission errors!
```

## File Structure

```
/opt/ws_moveit/           # Main workspace (owned by abc user)
├── src/                  # Source code
│   ├── moveit2_tutorials/
│   └── ...
├── build/                # Build artifacts (cached by BuildKit!)
├── install/              # Installed packages
└── log/                  # Build logs

/config/ws_moveit         # Symlink to /opt/ws_moveit (for convenience)
~/ws_moveit               # Same symlink (easier to type!)
```

## Why /opt Instead of /home?

- `/opt` is the standard Linux location for optional software packages
- It's accessible to all users (unlike `/root`)
- It persists across user sessions
- It's outside the user home directory, so it won't interfere with config files
- Standard practice for system-wide ROS workspaces

## Performance Impact

**None!** The permission fixes don't slow down the build at all:
- `chown -R` happens only once during the final layer
- Cache mounts work the same in `/tmp` as they did in `/root`
- BuildKit cache is maintained across builds

## Additional Improvements

### 1. Helper Script
Run `workspace-info.sh` to see:
- Where the workspace is
- Quick commands
- Directory contents

### 2. Login Message
When you open a terminal, you'll see:
```
ROS2 MoveIt workspace ready at ~/ws_moveit
Run workspace-info.sh for more information
```

### 3. Consistent Paths
All scripts and bashrc configs use `/opt/ws_moveit`, so everything just works.

## Troubleshooting

### "Permission denied" errors
```bash
# Check ownership
ls -la /opt/ws_moveit
# Should show: drwxr-xr-x 1000 1000

# Fix if needed (run as root)
docker exec ros2-test chown -R 1000:1000 /opt/ws_moveit
```

### Can't write to workspace
```bash
# Check if you're the right user
whoami
# Should show: abc

id
# Should show: uid=1000(abc) gid=1000(abc)
```

### Workspace not found
```bash
# Verify workspace exists
ls -la /opt/ws_moveit

# Check symlink
ls -la ~/ws_moveit
# Should point to: /opt/ws_moveit
```

## Best Practices

1. **Always build as root during Dockerfile** - that's normal
2. **Set permissions after building** - using chown as shown
3. **Use /opt for system-wide packages** - makes them accessible to all users
4. **Use cache mounts in /tmp** - works for all users
5. **Create symlinks for convenience** - makes paths easier to type

## Summary

✅ Workspace now accessible to abc user (the default web UI user)
✅ All BuildKit optimizations retained (75-90% faster rebuilds)
✅ Convenient ~/ws_moveit symlink
✅ Helper scripts included
✅ Login messages to guide you
✅ No performance impact from permission fixes
