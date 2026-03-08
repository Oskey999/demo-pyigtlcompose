#!/usr/bin/env python3
"""
Magfield → MoveIt Controller
=============================
Subscribes to /magfield_transform (geometry_msgs/Pose), optionally scales the
incoming position, then plans and executes a move of the Kinova Gen3
end-effector via MoveGroup.

Usage:
  # Terminal 1 — MoveIt demo
  ros2 launch moveit2_tutorials demo.launch.py

  # Terminal 2 — this node
  python3 magfield_moveit_controller.py

  # Terminal 3 — publish a test pose
  ros2 topic pub --once /magfield_transform geometry_msgs/msg/Pose \
    "{position: {x: 0.004, y: 0.0, z: 0.004}, \
      orientation: {x: 0.0, y: 1.0, z: 0.0, w: 0.0}}"
"""

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient

import tf2_ros
from tf2_ros import LookupException, ConnectivityException, ExtrapolationException
from rclpy.time import Time

from geometry_msgs.msg import Pose, Point, Vector3
from moveit_msgs.action import MoveGroup
from moveit_msgs.msg import (
    MotionPlanRequest,
    WorkspaceParameters,
    BoundingVolume,
    PositionConstraint,
    OrientationConstraint,
    Constraints,
    MoveItErrorCodes,
    PlanningOptions,
)
from shape_msgs.msg import SolidPrimitive
from std_msgs.msg import Header


# ── Configuration ─────────────────────────────────────────────────────────────

PLANNING_GROUP = "manipulator"     # MoveIt planning group (check your SRDF)
END_EFFECTOR   = "end_effector_link"  # Confirmed from SRDF chain tip_link
BASE_FRAME     = "base_link"       # Robot base frame
PLANNING_TIME  = 10.0              # Max seconds for planner
NUM_RETRIES    = 5                 # Replan attempts on failure
VELOCITY_SCALING = 0.3             # 0.0–1.0
ACCEL_SCALING    = 0.3             # 0.0–1.0

PIPELINE_ID = "ompl"
PLANNER_ID  = "RRTConnectkConfigDefault"

POSITION_TOLERANCE    = 0.05       # metres — tighten once moves are reliable
CONSTRAIN_ORIENTATION = False      # enable once position-only moves succeed
ORIENTATION_TOLERANCE = 0.1        # radians (~5.7 deg), only if above is True

# ⚠️  SCALE AUDIT — read before changing:
#
#   Your raw incoming Z values are 0.10 – 0.65.  Those are already plausible
#   robot-workspace metres for a Kinova Gen3 (reach ≈ 0.9 m).  Multiplying by
#   100 produces targets of 10 – 65 m — impossibly far — which is why every
#   plan fails immediately with PLANNING_FAILED.
#
#   • If 3D Slicer is publishing in metres  → set POSITION_SCALE = 1.0
#   • If 3D Slicer is publishing in cm      → set POSITION_SCALE = 0.01
#   • If 3D Slicer is publishing in mm      → set POSITION_SCALE = 0.001
#
#   Compare the "Scaled pose" log line against the "Current EE pose" line
#   printed below; they should be in the same ballpark.
POSITION_SCALE = 1.0               # ← was 100.0; almost certainly wrong


# ── Node ──────────────────────────────────────────────────────────────────────

class MagfieldMoveItController(Node):

    def __init__(self):
        super().__init__("magfield_moveit_controller")

        # TF2 buffer + listener — used to read the live end-effector pose
        self._tf_buffer   = tf2_ros.Buffer()
        self._tf_listener = tf2_ros.TransformListener(self._tf_buffer, self)

        self._action_client = ActionClient(self, MoveGroup, "/move_action")
        self.get_logger().info("Waiting for MoveGroup action server ...")
        self._action_client.wait_for_server()
        self.get_logger().info("MoveGroup action server connected")

        self._moving = False

        self.subscription = self.create_subscription(
            Pose,
            "/magfield_transform",
            self._pose_callback,
            10,
        )
        self.get_logger().info("Listening on /magfield_transform ...")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _log_current_ee_pose(self):
        """Look up BASE_FRAME → END_EFFECTOR via TF2 and print the result."""
        try:
            tf = self._tf_buffer.lookup_transform(
                BASE_FRAME,
                END_EFFECTOR,
                Time(),                 # latest available transform
            )
            t = tf.transform.translation
            r = tf.transform.rotation
            self.get_logger().info(
                f'Current EE pose ({BASE_FRAME} → {END_EFFECTOR}):'
                f'\n  Position    x={t.x:.4f}, y={t.y:.4f}, z={t.z:.4f}'
                f'\n  Orientation x={r.x:.4f}, y={r.y:.4f}, z={r.z:.4f}, w={r.w:.4f}'
            )
            print(
                f'\nCurrent EE pose ({BASE_FRAME} → {END_EFFECTOR}):'
                f'\n  Position    x={t.x:.4f}, y={t.y:.4f}, z={t.z:.4f}'
                f'\n  Orientation x={r.x:.4f}, y={r.y:.4f}, z={r.z:.4f}, w={r.w:.4f}'
            )
        except (LookupException, ConnectivityException, ExtrapolationException) as e:
            self.get_logger().warn(f'TF2 lookup failed (EE pose unavailable): {e}')

    # ── Callback ──────────────────────────────────────────────────────────────

    def _pose_callback(self, msg: Pose):
        # ── 1. Print the raw incoming pose ────────────────────────────────────
        self.get_logger().info(
            f'\nIncoming pose from /magfield_transform:'
            f'\n  Position    x={msg.position.x:.4f}, y={msg.position.y:.4f}, z={msg.position.z:.4f}'
            f'\n  Orientation x={msg.orientation.x:.4f}, y={msg.orientation.y:.4f},'
            f' z={msg.orientation.z:.4f}, w={msg.orientation.w:.4f}'
        )
        print(
            f'\nIncoming pose:'
            f'\n  Position    x={msg.position.x:.4f}, y={msg.position.y:.4f}, z={msg.position.z:.4f}'
            f'\n  Orientation x={msg.orientation.x:.4f}, y={msg.orientation.y:.4f},'
            f' z={msg.orientation.z:.4f}, w={msg.orientation.w:.4f}'
        )

        # ── 2. Print the live end-effector pose from MoveIt/TF ────────────────
        self._log_current_ee_pose()

        if self._moving:
            self.get_logger().warn("Move in progress — skipping pose.")
            return

        # ── 3. Scale and send ─────────────────────────────────────────────────
        scaled = Pose()
        scaled.position.x  = msg.position.x * POSITION_SCALE
        scaled.position.y  = msg.position.y * POSITION_SCALE
        scaled.position.z  = msg.position.z * POSITION_SCALE
        scaled.orientation = msg.orientation

        self.get_logger().info(
            f'Scaled target pose (×{POSITION_SCALE}):'
            f'\n  Position    x={scaled.position.x:.4f}, y={scaled.position.y:.4f}, z={scaled.position.z:.4f}'
        )
        print(
            f'\nScaled target (×{POSITION_SCALE}):'
            f'\n  Position    x={scaled.position.x:.4f}, y={scaled.position.y:.4f}, z={scaled.position.z:.4f}'
        )

        self._moving = True
        self._send_goal(scaled)

    # ── Goal construction ─────────────────────────────────────────────────────

    def _build_goal(self, pose: Pose) -> MoveGroup.Goal:
        goal = MoveGroup.Goal()
        req  = MotionPlanRequest()

        req.group_name                      = PLANNING_GROUP
        req.num_planning_attempts           = NUM_RETRIES
        req.allowed_planning_time           = PLANNING_TIME
        req.max_velocity_scaling_factor     = VELOCITY_SCALING
        req.max_acceleration_scaling_factor = ACCEL_SCALING

        # Do NOT set req.start_state — omitting it (leaving the default empty
        # RobotState with is_diff=False) tells MoveIt to use its internally
        # monitored current state.  Setting an empty RobotState + is_diff=True
        # causes START_STATE_INVALID after the first move because the monitor
        # state and the empty diff can't be reconciled once the robot has moved.

        req.pipeline_id = PIPELINE_ID
        req.planner_id  = PLANNER_ID

        req.workspace_parameters = WorkspaceParameters(
            header=Header(frame_id=BASE_FRAME),
            min_corner=Vector3(x=-1.0, y=-1.0, z=-1.0),
            max_corner=Vector3(x= 1.0, y= 1.0, z= 1.0),
        )

        pos                     = PositionConstraint()
        pos.header              = Header(frame_id=BASE_FRAME)
        pos.link_name           = END_EFFECTOR
        pos.weight              = 1.0
        pos.target_point_offset = Vector3(x=0.0, y=0.0, z=0.0)

        sphere            = SolidPrimitive()
        sphere.type       = SolidPrimitive.SPHERE
        sphere.dimensions = [POSITION_TOLERANCE]

        bv                 = BoundingVolume()
        bv.primitives      = [sphere]
        bv.primitive_poses = [pose]
        pos.constraint_region = bv

        constraints = Constraints(position_constraints=[pos])

        if CONSTRAIN_ORIENTATION:
            ori                           = OrientationConstraint()
            ori.header                    = Header(frame_id=BASE_FRAME)
            ori.link_name                 = END_EFFECTOR
            ori.orientation               = pose.orientation
            ori.absolute_x_axis_tolerance = ORIENTATION_TOLERANCE
            ori.absolute_y_axis_tolerance = ORIENTATION_TOLERANCE
            ori.absolute_z_axis_tolerance = ORIENTATION_TOLERANCE
            ori.weight                    = 1.0
            constraints.orientation_constraints = [ori]

        req.goal_constraints = [constraints]

        goal.request = req
        goal.planning_options = PlanningOptions(
            plan_only=False,
            replan=True,
            replan_attempts=NUM_RETRIES,
        )
        return goal

    # ── Async goal dispatch ───────────────────────────────────────────────────

    def _send_goal(self, pose: Pose):
        self.get_logger().info("Sending goal to MoveGroup ...")
        future = self._action_client.send_goal_async(self._build_goal(pose))
        future.add_done_callback(self._goal_response_callback)

    def _goal_response_callback(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().error("Goal rejected by MoveGroup server")
            self._moving = False
            return
        self.get_logger().info("Goal accepted - planning and executing ...")
        goal_handle.get_result_async().add_done_callback(self._result_callback)

    def _result_callback(self, future):
        err_code = future.result().result.error_code.val
        if err_code == MoveItErrorCodes.SUCCESS:
            self.get_logger().info("Move completed successfully")
        else:
            self.get_logger().error(
                f"Move failed - MoveItErrorCode: {err_code} ({self._error_name(err_code)})"
            )
        self._moving = False
        self.get_logger().info("Ready - waiting for next pose on /magfield_transform ...")

    @staticmethod
    def _error_name(code: int) -> str:
        names = {v: k for k, v in vars(MoveItErrorCodes).items() if isinstance(v, int)}
        return names.get(code, "UNKNOWN")


# ── Entry point ───────────────────────────────────────────────────────────────

def main(args=None):
    rclpy.init(args=args)
    node = MagfieldMoveItController()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()