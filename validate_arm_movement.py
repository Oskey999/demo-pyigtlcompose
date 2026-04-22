#!/usr/bin/env python3
"""
Find phosphobot arm workspace limits in all directions.
Systematically tests movements and finds the maximum reach in X, Y, Z
for both positive and negative directions.
"""
import subprocess
import json
import time
import sys

# Test configuration
STEP_SIZE = 2  # cm - increment size for limit finding
MAX_DISTANCE = 20  # cm - maximum distance to test
POSITION_TOLERANCE = 0.01  # cm — threshold below which positions are considered identical
STABILIZE_INTERVAL = 0.2   # seconds between position polls while waiting for arm to settle
STABILIZE_TIMEOUT  = 8.0   # max seconds to wait for the arm to stop moving
STABILIZE_THRESHOLD = 0.01 # cm — movement smaller than this means "arm has settled"

def check_connectivity(ip_address, port=80):
    """Check if remote phosphobot is reachable"""
    import socket
    print(f"\n[NETWORK CHECK] Testing connectivity to {ip_address}:{port}...")
    
    try:
        result = subprocess.run(['ping', '-n', '1', ip_address], 
                              capture_output=True, timeout=3)
        if result.returncode == 0:
            print(f"  ✓ Ping successful to {ip_address}")
        else:
            print(f"  ✗ Ping failed - device may be offline or blocked")
            return False
    except Exception as e:
        print(f"  ⚠ Could not ping: {e}")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex((ip_address, port))
        sock.close()
        if result == 0:
            print(f"  ✓ Port {port} is open and accepting connections")
            return True
        else:
            print(f"  ✗ Port {port} is closed or blocked")
            return False
    except Exception as e:
        print(f"  ⚠ Socket check failed: {e}")
        return False

def debug_status_endpoint():
    """Debug what the status endpoint actually returns"""
    import requests
    print("\n[DEBUG] Testing status endpoint...")
    try:
        response = requests.get('http://192.168.86.27:80/status', timeout=5)
        print(f"  Status code: {response.status_code}")
        print(f"  Content-Type: {response.headers.get('content-type', 'unknown')}")
        print(f"  Response body (first 500 chars): {response.text[:500]}")
        try:
            data = response.json()
            print(f"  JSON keys: {list(data.keys())}")
            print(f"  Full JSON: {data}")
        except:
            print(f"  Could not parse as JSON")
    except Exception as e:
        print(f"  Error: {type(e).__name__}: {e}")

def get_end_effector_position():
    """Get current end-effector cartesian position via /end-effector/read"""
    import requests
    try:
        response = requests.post(
            'http://192.168.86.27:80/end-effector/read',
            json={"sync": False, "only_gripper": False},
            timeout=5
        )
        if response.status_code == 200:
            try:
                return response.json()  # {"x", "y", "z", "rx", "ry", "rz", "open"}
            except:
                return None
        return None
    except requests.exceptions.ConnectionError:
        return None
    except requests.exceptions.Timeout:
        return None
    except Exception as e:
        return None

def positions_are_equal(pos_a, pos_b, tolerance=POSITION_TOLERANCE):
    """
    Return True if two end-effector readings are effectively identical,
    meaning the arm did not move.
    Expects dicts with at least x, y, z keys.
    """
    if pos_a is None or pos_b is None:
        return False
    if isinstance(pos_a, dict) and isinstance(pos_b, dict):
        shared_keys = pos_a.keys() & pos_b.keys()
        if not shared_keys:
            return False
        return all(abs(pos_a[k] - pos_b[k]) <= tolerance for k in shared_keys)
    return pos_a == pos_b

def send_move_command(x, y, z):
    """
    Send a move command to phosphobot with sync=True so the POST blocks
    until the arm finishes moving.
    Returns (http_success, response_str) — HTTP 200 still doesn't guarantee
    movement; use wait_for_stable_position() to confirm.
    """
    import requests
    try:
        payload = {"x": x, "y": y, "z": z, "sync": True}
        response = requests.post(
            'http://192.168.86.27:80/move/absolute',
            json=payload,
            timeout=15  # longer to accommodate sync blocking
        )
        
        try:
            response_data = response.json()
            response_str = str(response_data)
        except:
            response_str = response.text[:200]
        
        http_ok = response.status_code == 200
        if not http_ok:
            print(f"      [Response: HTTP {response.status_code} | {response_str}]", end="")
        
        return http_ok, response_str
    except requests.exceptions.ConnectionError as e:
        print(f"      [ERROR: Connection refused]", end="")
        return False, "connection_refused"
    except requests.exceptions.Timeout:
        print(f"      [ERROR: Timeout]", end="")
        return False, "timeout"
    except Exception as e:
        print(f"      [ERROR: {type(e).__name__}]", end="")
        return False, str(e)

def wait_for_stable_position():
    """
    Poll /end-effector/read until the position stops changing between two
    consecutive reads (within STABILIZE_THRESHOLD), or until STABILIZE_TIMEOUT
    is exceeded.  Returns the stable position dict, or None on failure.
    """
    deadline = time.time() + STABILIZE_TIMEOUT
    prev = get_end_effector_position()

    while time.time() < deadline:
        time.sleep(STABILIZE_INTERVAL)
        curr = get_end_effector_position()
        if curr is None:
            prev = curr
            continue
        if prev is not None and positions_are_equal(prev, curr, tolerance=STABILIZE_THRESHOLD):
            return curr  # position has settled
        prev = curr

    return prev  # best effort after timeout

def find_limit_in_direction(axis, positive):
    """
    Sweep from 0 to MAX_DISTANCE in STEP_SIZE increments on one axis,
    keeping the other two axes at 0. Reports whether each step moved or not
    without stopping early — there may be a minimum as well as a maximum.
    Returns a list of distances (cm) where movement was confirmed.
    """
    direction = "+" if positive else "-"
    axis_name = axis.upper()
    print(f"\n  [Testing {axis_name}{direction}]")

    reachable = []

    for distance in range(STEP_SIZE, MAX_DISTANCE + STEP_SIZE, STEP_SIZE):
        value = distance if positive else -distance
        move_cmd = {"x": 0, "y": 0, "z": 0, axis: value}

        pos_before = get_end_effector_position()
        http_ok, _ = send_move_command(move_cmd["x"], move_cmd["y"], move_cmd["z"])

        print(f"    {axis_name}{direction} {distance:3d}cm ", end="")

        if not http_ok:
            print(f"✗ (HTTP error)")
            continue

        pos_after = wait_for_stable_position()

        if pos_before is None or pos_after is None:
            reachable.append(distance)
            print(f"✓ (position unreadable — assuming moved)")
            continue

        if positions_are_equal(pos_before, pos_after):
            print(f"✗ (arm did not move — out of bounds)")
            continue

        reachable.append(distance)
        print(f"✓ pos=({pos_after.get('x'):.4f}, {pos_after.get('y'):.4f}, {pos_after.get('z'):.4f})")

    return reachable

def move_to_position(x, y, z, description=""):
    """Move to a specific position and log the result"""
    print(f"\n  Moving to ({x}, {y}, {z}) {description}...", end=" ")
    
    pos_before = get_end_effector_position()
    http_ok, response_str = send_move_command(x, y, z)
    
    if not http_ok:
        print(f"✗ (HTTP error)")
        return False
    
    pos_after = wait_for_stable_position()
    
    if pos_before is None or pos_after is None:
        print(f"✓ (sent, position unreadable — status unknown)")
        return True
    
    if positions_are_equal(pos_before, pos_after):
        print(f"✗ (HTTP 200 but arm did not move — out of bounds)")
        return False
    
    print(f"✓ (moved)")
    print(f"    Position: ({pos_after.get('x')}, {pos_after.get('y')}, {pos_after.get('z')})")
    return True

def main():
    print("=" * 70)
    print("PHOSPHOBOT ARM WORKSPACE LIMIT FINDER")
    print("=" * 70)
    
    if not check_connectivity('192.168.86.27', 80):
        print("\n⚠ NETWORK ISSUE: Cannot reach phosphobot at 192.168.86.27:80")
        sys.exit(1)
    
    debug_status_endpoint()
    
    print("\n[INITIAL STATE]")
    initial_pos = get_end_effector_position()
    if initial_pos:
        print(f"  Current position: ({initial_pos.get('x'):.4f}, {initial_pos.get('y'):.4f}, {initial_pos.get('z'):.4f})")
    else:
        print("  ⚠ Could not read initial position")

    print("\n[FINDING WORKSPACE LIMITS]")
    limits = {}

    for axis in ['x', 'y', 'z']:
        print(f"\n{axis.upper()}-AXIS LIMITS:")
        limits[f"{axis}_pos"] = find_limit_in_direction(axis, positive=True)
        if axis != 'z':
            limits[f"{axis}_neg"] = find_limit_in_direction(axis, positive=False)

    print("\n" + "=" * 70)
    print("WORKSPACE LIMITS FOUND (in cm):")
    print("=" * 70)
    for axis in ['x', 'y', 'z']:
        directions = [('+', f"{axis}_pos")]
        if axis != 'z':
            directions.append(('-', f"{axis}_neg"))
        for sign, key in directions:
            vals = limits[key]
            if vals:
                print(f"  {axis.upper()}{sign}: reachable at {vals} cm  |  min={min(vals)}  max={max(vals)}")
            else:
                print(f"  {axis.upper()}{sign}: no reachable positions found")
    print("=" * 70)

    print("\n[RETURNING TO ORIGIN]")
    move_to_position(0, 0, 0, "(origin)")

    print("\n" + "=" * 70)
    print("SUMMARY:")
    for axis in ['x', 'y', 'z']:
        directions = [('+', f"{axis}_pos")]
        if axis != 'z':
            directions.append(('-', f"{axis}_neg"))
        for sign, key in directions:
            vals = limits[key]
            if vals:
                print(f"  {axis.upper()}{sign}: [{min(vals)} – {max(vals)}] cm reachable")
            else:
                print(f"  {axis.upper()}{sign}: no reachable positions")
    print("=" * 70)

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)