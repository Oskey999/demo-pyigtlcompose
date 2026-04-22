#!/usr/bin/env python3
"""
Phosphobot Synchronization Controller
======================================
Subscribes to /magfield_transform (geometry_msgs/Pose) and sends synchronized
commands to a physical arm running the phosphobot HTTP API.

This node focuses exclusively on physical arm synchronization while other
nodes handle MoveIt simulation planning.

Configuration:
  PHOSPHOBOT_ENABLED      - Enable/disable synchronization (env: PHOSPHOBOT_ENABLED)
  PHOSPHOBOT_HOST         - Arm IP address (env: PHOSPHOBOT_HOST)
  PHOSPHOBOT_PORT         - Arm HTTP port (env: PHOSPHOBOT_PORT)
  PHOSPHOBOT_DISTANCE_SCALE - Scale movement commands to 1/10th by default

Usage:
  # Terminal 1 — MoveIt demo
  ros2 launch moveit2_tutorials demo.launch.py

  # Terminal 2 — MoveIt controller node
  ros2 run moveit_controller_pkg moveit_controller

  # Terminal 3 — Phosphobot sync node
  ros2 run phosphobot_sync_pkg phosphobot_sync

  # Terminal 4 — publish a test pose
  ros2 topic pub --once /magfield_transform geometry_msgs/msg/Pose \
    "{position: {x: 0.004, y: 0.0, z: 0.004}, \
      orientation: {x: 0.0, y: 1.0, z: 0.0, w: 0.0}}"
"""

import os
import requests
import numpy as np
from scipy.spatial.transform import Rotation

import rclpy
from rclpy.node import Node

from geometry_msgs.msg import Pose


# ── Phosphobot Physical Arm Configuration ──────────────────────────────────────
#
# Settings for sending synchronized commands to a physical arm running phosphobot.
# Incoming poses are converted: metres → centimetres (× 100), then scaled to 1/10th.
#
PHOSPHOBOT_ENABLED      = os.getenv("PHOSPHOBOT_ENABLED", "true").lower() == "true"
PHOSPHOBOT_HOST         = os.getenv("PHOSPHOBOT_HOST", "localhost")
PHOSPHOBOT_PORT         = int(os.getenv("PHOSPHOBOT_PORT", "80"))
PHOSPHOBOT_BASE_URL     = f"http://{PHOSPHOBOT_HOST}:{PHOSPHOBOT_PORT}"
PHOSPHOBOT_DISTANCE_SCALE = 1.0 / 20.0  # Move 1/20th of prescribed distance
PHOSPHOBOT_TIMEOUT      = 5.0  # seconds

# ── Axis Mapping Configuration ─────────────────────────────────────────────────
# Maps input axes to physical arm axes with direction control.
# Format: 'input_axis': (physical_axis, direction_multiplier)
# direction_multiplier: 1 = normal, -1 = inverted/flipped
#
# Current mapping (adjustable based on your control scheme):
#   Input X (In/Out)   → Phosphobot Y (Left/Right physical), normal direction
#   Input Y (Left/Right) → Phosphobot Z (Up/Down physical), normal direction
#   Input Z (Up/Down)  → Phosphobot X (Forward/Back physical), normal direction
#
# To flip an axis, change the multiplier to -1:
#   Example: 'input_y': ('z', -1)  # Left/Right inverted
#
AXIS_MAP = {
    'input_x': ('y', -1),    # In/Out input → Left/Right movement (1=normal, -1=flip)
    'input_y': ('x', 1),    # Left/Right input → Up/Down movement (1=normal, -1=flip)
    'input_z': ('z', 1),    # Up/Down input → Forward/Back movement (1=normal, -1=flip)
}

# ── Gripper Leveling Configuration ────────────────────────────────────────────
#
# After each position move, the wrist pitch joint is driven to cancel out the
# accumulated pitch from the rest of the kinematic chain, keeping the gripper
# as flat (horizontal) as possible relative to the ground.
#
# GRIPPER_LEVELING_ENABLED
#   Set to False to disable the feature entirely.
#
# WRIST_PITCH_JOINT_INDEX
#   0-based index of the joint to control — the last pitch joint before the
#   gripper.  For the S101 this is joint 3 (shoulder=1, elbow=2, wrist=3).
#   Adjust if your arm numbers joints differently.
#
# WRIST_PITCH_CONTRIBUTING_JOINTS
#   0-based indices of every joint whose rotation contributes to the gripper's
#   pitch angle.  The wrist is set to the negative sum of these so the net
#   pitch is zero.  For the S101: shoulder (1) + elbow (2).
#
# WRIST_FLAT_OFFSET_RAD
#   Fine-tuning offset in radians applied on top of the compensation.
#   Positive values tilt the gripper nose-up; negative values tilt nose-down.
#   Start at 0.0 and adjust if the gripper is not quite level in practice.
#
GRIPPER_LEVELING_ENABLED        = True
WRIST_PITCH_JOINT_INDEX         = 4        # last pitch joint before the gripper
WRIST_PITCH_CONTRIBUTING_JOINTS = [2, 3]   # shoulder + elbow
WRIST_FLAT_OFFSET_RAD           = 0.0      # fine-tune offset (radians)


# ── Node ──────────────────────────────────────────────────────────────────────

class PhosphotbotSync(Node):

    def __init__(self):
        super().__init__("phosphobot_sync")

        self.get_logger().info(f"Phosphobot Synchronization Node")
        if PHOSPHOBOT_ENABLED:
            self.get_logger().info(f"  Host: {PHOSPHOBOT_HOST}:{PHOSPHOBOT_PORT}")
            self.get_logger().info(f"  Base URL: {PHOSPHOBOT_BASE_URL}")
            self.get_logger().info(f"  Distance Scale: {PHOSPHOBOT_DISTANCE_SCALE}")
            self.get_logger().info(
                f"  Gripper leveling: {'ENABLED' if GRIPPER_LEVELING_ENABLED else 'DISABLED'} "
                f"(wrist joint {WRIST_PITCH_JOINT_INDEX}, "
                f"contributing joints {WRIST_PITCH_CONTRIBUTING_JOINTS}, "
                f"offset {np.degrees(WRIST_FLAT_OFFSET_RAD):.2f}°)"
            )
        else:
            self.get_logger().warn("  *** DISABLED - will not send commands to physical arm ***")

        # Home arm on startup
        self.get_logger().info("Homing arm on startup...")
        self._home_phosphobot_arm()

        self.create_subscription(
            Pose,
            "/magfield_transform",
            self._pose_callback,
            10,
        )
        self.get_logger().info("Listening on /magfield_transform ...")

    # ── Rotation compensation ──────────────────────────────────────────────────

    def _rotate_position_by_quaternion(self, position, quaternion):
        """
        Rotate a position vector by the given quaternion.
        This compensates for coil rotation, rotating the position back to a canonical frame.
        
        Args:
            position: dict with 'x', 'y', 'z' keys (in metres)
            quaternion: dict with 'x', 'y', 'z', 'w' keys (from Pose.orientation)
            
        Returns:
            dict with rotated 'x', 'y', 'z' values
        """
        # Convert position to numpy array
        pos_vec = np.array([position['x'], position['y'], position['z']])
        
        # Create rotation from quaternion (note: scipy uses [x, y, z, w] format)
        quat = np.array([quaternion['x'], quaternion['y'], quaternion['z'], quaternion['w']])
        
        # Normalize quaternion (in case it's not normalized)
        quat = quat / np.linalg.norm(quat)
        
        try:
            # Create rotation object and invert it (we want to de-rotate the position)
            rot = Rotation.from_quat(quat)
            rot_inv = rot.inv()
            
            # Apply inverse rotation to position vector
            rotated = rot_inv.apply(pos_vec)
            
            return {
                'x': rotated[0],
                'y': rotated[1],
                'z': rotated[2],
            }
        except Exception as e:
            self.get_logger().warn(f"Quaternion rotation failed: {e}, using unrotated position")
            return position

    # ── Phosphobot synchronization ─────────────────────────────────────────────

    def _home_phosphobot_arm(self):
        """
        Home the phosphobot arm to its center position before any moves.
        
        Home position (center point for movements):
          X: -15.0 cm
          Y: 0.0 cm
          Z: 15.0 cm
        """
        if not PHOSPHOBOT_ENABLED:
            self.get_logger().warn("Phosphobot homing skipped - PHOSPHOBOT_ENABLED=false")
            return
            
        try:
            # Center position for movements
            home_x = -15.0  # Your chosen center position
            home_y = 0.0    # Center
            home_z = 15.0   # Height
            
            home_payload = {
                "x": home_x,
                "y": home_y,
                "z": home_z,
                "sync": True  # Block until arm settles
            }
            
            self.get_logger().info(
                f"HOMING phosphobot arm to center: x={home_x:.2f}cm, y={home_y:.2f}cm, z={home_z:.2f}cm"
            )
            
            url = f"{PHOSPHOBOT_BASE_URL}/move/absolute"
            self.get_logger().info(f"Sending POST to {url}")
            self.get_logger().info(f"Payload: {home_payload}")
            
            response = requests.post(url, json=home_payload, timeout=PHOSPHOBOT_TIMEOUT + 15)
            
            self.get_logger().info(f"Response status: {response.status_code}")
            self.get_logger().info(f"Response body: {response.text[:500]}")
            
            response.raise_for_status()
            
            self.get_logger().info("✓ PHOSPHOBOT ARM HOMED to midpoint")

            # Level the gripper at the home position too
            self._apply_gripper_leveling()
            
        except requests.exceptions.ConnectionError as e:
            self.get_logger().error(
                f"✗ HOME FAILED: Cannot connect to {PHOSPHOBOT_BASE_URL} - {e}"
            )
        except requests.exceptions.Timeout as e:
            self.get_logger().error(
                f"✗ HOME FAILED: Request timed out ({PHOSPHOBOT_TIMEOUT}s) - {e}"
            )
        except requests.exceptions.HTTPError as e:
            self.get_logger().error(
                f"✗ HOME FAILED: HTTP {e.response.status_code} - {e.response.text[:500]}"
            )
        except Exception as e:
            self.get_logger().error(f"✗ HOME FAILED: {type(e).__name__}: {e}")

    def _apply_gripper_leveling(self):
        """
        Adjust the wrist pitch joint so the gripper stays as flat (horizontal)
        as possible relative to the ground.

        Strategy
        --------
        For a serial arm the gripper's pitch angle relative to the ground is
        approximately the sum of all joint angles along the pitch kinematic
        chain.  To cancel that accumulated pitch we set:

            wrist_joint = -(sum of contributing joint angles) + WRIST_FLAT_OFFSET_RAD

        Only the single wrist pitch joint is modified; every other joint keeps
        the value the IK solver already chose.

        Tune WRIST_PITCH_CONTRIBUTING_JOINTS and WRIST_FLAT_OFFSET_RAD at the
        top of this file if the gripper is not perfectly level in practice.
        """
        if not PHOSPHOBOT_ENABLED or not GRIPPER_LEVELING_ENABLED:
            return

        try:
            # ── 1. Read current joint positions ──────────────────────────────
            read_resp = requests.post(
                f"{PHOSPHOBOT_BASE_URL}/joints/read",
                json={},
                timeout=PHOSPHOBOT_TIMEOUT,
            )
            read_resp.raise_for_status()
            joint_data = read_resp.json()
            print(f"Current joint data: {joint_data}")

            joints = joint_data.get("joints", [])
            if not joints:
                self.get_logger().warn("Gripper leveling: /joints/read returned no joint data — skipping")
                return

            if WRIST_PITCH_JOINT_INDEX >= len(joints):
                self.get_logger().warn(
                    f"Gripper leveling: WRIST_PITCH_JOINT_INDEX={WRIST_PITCH_JOINT_INDEX} "
                    f"is out of range (arm has {len(joints)} joints) — skipping"
                )
                return

            # ── 2. Compute required wrist angle ──────────────────────────────
            # Accumulated pitch from shoulder + elbow (or whatever joints are
            # listed in WRIST_PITCH_CONTRIBUTING_JOINTS).
            accumulated_pitch = sum(
                joints[i]
                for i in WRIST_PITCH_CONTRIBUTING_JOINTS
                if i < len(joints)
            )

            # Cancel out accumulated pitch; apply any fine-tune offset.
            wrist_angle = -accumulated_pitch + WRIST_FLAT_OFFSET_RAD

            self.get_logger().info(
                f"Gripper leveling: "
                f"accumulated pitch = {np.degrees(accumulated_pitch):.2f}°  →  "
                f"wrist correction = {np.degrees(wrist_angle):.2f}°"
            )

            # ── 3. Write back only the wrist joint ───────────────────────────
            joints[WRIST_PITCH_JOINT_INDEX] = wrist_angle

            write_resp = requests.post(
                f"{PHOSPHOBOT_BASE_URL}/joints/write",
                json={"joints": joints, "sync": True},
                timeout=PHOSPHOBOT_TIMEOUT,
            )
            write_resp.raise_for_status()

            self.get_logger().info(
                f"✓ Gripper leveled: joint {WRIST_PITCH_JOINT_INDEX} "
                f"set to {np.degrees(wrist_angle):.2f}°"
            )

        except requests.exceptions.ConnectionError:
            self.get_logger().warn("Gripper leveling: connection error — skipping")
        except requests.exceptions.Timeout:
            self.get_logger().warn("Gripper leveling: request timed out — skipping")
        except requests.exceptions.HTTPError as e:
            self.get_logger().warn(
                f"Gripper leveling: HTTP {e.response.status_code} — skipping"
            )
        except Exception as e:
            self.get_logger().warn(f"Gripper leveling failed: {type(e).__name__}: {e}")

    def _send_to_phosphobot(self, pose: Pose):
        """
        Send a goal pose to the physical arm running phosphobot.
        Maps input axes to physical arm axes using AXIS_MAP configuration.
        Movements are centered around the home position (7.0, 0.0, 15.0).
        
        Input axes:
          Input X (In/Out): 0.0-0.2
          Input Y (Left/Right): -0.1-0.1
          Input Z (Up/Down): 0.0-0.2
        
        Physical arm workspace (in cm):
          X: 2-20 cm
          Y: -20 to 20 cm
          Z: 2-20 cm
        """
        if not PHOSPHOBOT_ENABLED:
            return

        try:
            # Workspace limits (in cm) for each physical axis
            # Note: These are approximate limits - the actual workspace may vary
            # The phosphobot API will reject out-of-bounds commands
            limits = {
                'x': (-20.0, 20.0),  # Actual range TBD - allowing full range
                'y': (-20.0, 20.0),
                'z': (-20.0, 20.0),  # Actual range TBD - allowing full range
            }
            
            # Home position (center point for all movements)
            # This is your chosen center position
            home_position = {
                'x': -15.0,
                'y': 0.0,
                'z': 10.0,
            }
            
            # ── ROTATION COMPENSATION ──
            # If the coil has rotated, we need to un-rotate the position vector
            # to compensate and get back to canonical arm coordinates
            quaternion = {
                'x': pose.orientation.x,
                'y': pose.orientation.y,
                'z': pose.orientation.z,
                'w': pose.orientation.w,
            }
            
            position_orig = {
                'x': pose.position.x,
                'y': pose.position.y,
                'z': pose.position.z,
            }
            
            # Rotation compensation disabled - use original position as-is
            # (rotation compensation was causing unwanted Z-axis lowering)
            position_compensated = position_orig
            
            # Get input values (convert metres to centimetres)
            # Values come in as metres from magfield_transform
            input_vals = {
                'x': position_compensated['x'] * 100,      # m → cm
                'y': position_compensated['y'] * 100,      # m → cm
                'z': position_compensated['z'] * 100,      # m → cm
            }
            
            # Map input axes to physical arm axes
            arm_cmd = {}
            for physical_axis in ['x', 'y', 'z']:
                # Find which input maps to this physical axis
                input_mapping = [v for v in AXIS_MAP.values() if v[0] == physical_axis]
                if not input_mapping:
                    continue
                    
                physical_axis_name, direction = input_mapping[0]
                input_key = [k for k, v in AXIS_MAP.items() if v[0] == physical_axis][0]
                input_axis_letter = input_key.split('_')[1]  # Extract 'x', 'y', or 'z' from 'input_x'
                input_val = input_vals[input_axis_letter]
                
                min_val, max_val = limits[physical_axis]
                home_val = home_position[physical_axis]  # Use home position as center, not midpoint
                workspace_range = (max_val - min_val) / 2.0  # Half the range
                
                # Input values are in cm. Scale them to stay near home position.
                # Expected input magnitude: ~±5 cm. Keep movements close to home (±3-4 cm max).
                input_scale = 0.8  # Scales ±5 cm input to ±4 cm movement (keeps arm in usable zone)
                scaled_input = max(-workspace_range, min(workspace_range, input_val * input_scale))
                
                # Apply direction multiplier BEFORE adding to home position
                if direction == -1:
                    scaled_input = -scaled_input
                
                # Position = home position + scaled input
                arm_cmd[physical_axis] = home_val + scaled_input
                arm_cmd[physical_axis] = max(min_val, min(max_val, arm_cmd[physical_axis]))
            
            # Send move command with sync to wait for completion
            payload = {
                "x": arm_cmd['x'],
                "y": arm_cmd['y'],
                "z": arm_cmd['z'],
                "sync": True
            }

            url = f"{PHOSPHOBOT_BASE_URL}/move/absolute"
            self.get_logger().info(
                f"Sending to phosphobot arm (x={arm_cmd['x']:.2f}cm, y={arm_cmd['y']:.2f}cm, z={arm_cmd['z']:.2f}cm) "
                f"from inputs (In/Out={input_vals['x']:.4f}, Left/Right={input_vals['y']:.4f}, Up/Down={input_vals['z']:.4f})"
            )

            # Get position before move
            response_before = requests.post(
                f"{PHOSPHOBOT_BASE_URL}/end-effector/read",
                json={"sync": False, "only_gripper": False},
                timeout=5.0
            )
            pos_before = response_before.json() if response_before.status_code == 200 else None
            
            # Send actual move command
            response = requests.post(url, json=payload, timeout=PHOSPHOBOT_TIMEOUT + 10)
            response.raise_for_status()

            # ── Gripper leveling ──────────────────────────────────────────────
            # Adjust the wrist pitch joint to keep the gripper flat relative to
            # the ground, now that the IK solver has settled on a configuration.
            self._apply_gripper_leveling()
            
            # Get position after move
            response_after = requests.post(
                f"{PHOSPHOBOT_BASE_URL}/end-effector/read",
                json={"sync": False, "only_gripper": False},
                timeout=5.0
            )
            pos_after = response_after.json() if response_after.status_code == 200 else None
            
            # Verify movement
            if pos_before and pos_after:
                tolerance = 0.1
                moved = any(
                    abs(pos_after.get(k, 0) - pos_before.get(k, 0)) > tolerance
                    for k in ['x', 'y', 'z']
                )
                if moved:
                    self.get_logger().info(
                        f"✓ PHOSPHOBOT MOVED: "
                        f"({pos_before.get('x', 0):.2f}, {pos_before.get('y', 0):.2f}, {pos_before.get('z', 0):.2f}) "
                        f"→ ({pos_after.get('x', 0):.2f}, {pos_after.get('y', 0):.2f}, {pos_after.get('z', 0):.2f})"
                    )
                else:
                    self.get_logger().warn(
                        f"⚠ PHOSPHOBOT DID NOT MOVE: position unchanged after command"
                    )
            else:
                self.get_logger().info(f"✓ PHOSPHOBOT COMMAND SENT (HTTP {response.status_code})")

        except requests.exceptions.ConnectionError:
            self.get_logger().error(
                f"✗ PHOSPHOBOT FAILED: Cannot connect to {PHOSPHOBOT_BASE_URL}"
            )
        except requests.exceptions.Timeout:
            self.get_logger().error(
                f"✗ PHOSPHOBOT FAILED: Request timed out ({PHOSPHOBOT_TIMEOUT}s)"
            )
        except requests.exceptions.HTTPError as e:
            self.get_logger().error(
                f"✗ PHOSPHOBOT FAILED: HTTP {e.response.status_code} - {e.response.text[:200]}"
            )
        except Exception as e:
            self.get_logger().error(f"✗ PHOSPHOBOT FAILED: {type(e).__name__}: {e}")

    # ── Pose callback ─────────────────────────────────────────────────────────

    def _pose_callback(self, msg: Pose):
        """
        Handle incoming magfield transform poses and forward to phosphobot.
        """
        self.get_logger().info(
            f'\nIncoming pose from /magfield_transform (world frame):'
            f'\n  Position    x={msg.position.x:.4f}, y={msg.position.y:.4f}, z={msg.position.z:.4f}'
            f'\n  Orientation x={msg.orientation.x:.4f}, y={msg.orientation.y:.4f},'
            f' z={msg.orientation.z:.4f}, w={msg.orientation.w:.4f}'
        )
        print(
            f'\nIncoming pose (world frame):'
            f'\n  Position    x={msg.position.x:.4f}, y={msg.position.y:.4f}, z={msg.position.z:.4f}'
            f'\n  Orientation x={msg.orientation.x:.4f}, y={msg.orientation.y:.4f},'
            f' z={msg.orientation.z:.4f}, w={msg.orientation.w:.4f}'
        )

        # Send to physical arm
        self._send_to_phosphobot(msg)


# ── Entry point ───────────────────────────────────────────────────────────────

def main(args=None):
    rclpy.init(args=args)
    node = PhosphotbotSync()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()