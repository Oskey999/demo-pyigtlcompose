#!/usr/bin/env python3
"""
MoveIt Controller for UR5e Robot
=================================
Subscribes to /magfield_transform (geometry_msgs/Pose), scales the incoming
position, then plans and executes a move of the UR5e end-effector via MoveGroup.

Also subscribes to /robot_description (std_msgs/String) to patch the URDF
with BASE_OFFSET applied to the world -> base_link joint origin, then exposes
the result as a parameter on this node so a GUI (e.g. SlicerROS2) can
visualise the robot at the correct position.

GUI settings:
  Node name      : moveit_controller
  Parameter name : robot_description

Incoming /magfield_transform poses are assumed to be in the *world* frame.
BASE_OFFSET is subtracted before sending to MoveIt, which expects poses
expressed in BASE_FRAME (base_link).

Usage:
  # Terminal 1 — MoveIt demo
  ros2 launch moveit2_tutorials demo.launch.py

  # Terminal 2 — this node
  ros2 run moveit_controller_pkg moveit_controller

  # Terminal 3 — publish a test pose
  ros2 topic pub --once /magfield_transform geometry_msgs/msg/Pose \
    "{position: {x: 0.004, y: 0.0, z: 0.004}, \
      orientation: {x: 0.0, y: 1.0, z: 0.0, w: 0.0}}"
"""

import xml.etree.ElementTree as ET
import os

import rclpy
import rclpy.parameter
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy

import tf2_ros
from tf2_ros import LookupException, ConnectivityException, ExtrapolationException, StaticTransformBroadcaster
from rclpy.time import Time

from geometry_msgs.msg import Pose, Vector3, TransformStamped
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
from std_msgs.msg import Header, String


# ── Configuration ─────────────────────────────────────────────────────────────

PLANNING_GROUP   = "ur_manipulator"     # MoveIt planning group (from UR5e SRDF)
END_EFFECTOR     = "tool0"              # UR5e tip link
BASE_FRAME       = "base_link"          # Robot base frame
PLANNING_TIME    = 10.0                 # Max seconds for planner
NUM_RETRIES      = 5                    # Replan attempts on failure
VELOCITY_SCALING = 0.3                  # 0.0–1.0
ACCEL_SCALING    = 0.3                  # 0.0–1.0

PIPELINE_ID = "ompl"
PLANNER_ID  = "RRTConnect"

POSITION_TOLERANCE    = 0.05   # metres
CONSTRAIN_ORIENTATION = True   # enable once position-only moves succeed
ORIENTATION_TOLERANCE = 0.1    # radians (~5.7 deg)

# Incoming /magfield_transform poses are in world frame (metres).
# Set POSITION_SCALE = 1.0 for metres, 0.001 for mm, 0.01 for cm.
POSITION_SCALE = 1.0

# ── Base-link origin offset ────────────────────────────────────────────────────
#
# Defines where base_link sits in the world/GUI frame. Applied in three places:
#   1. The URDF's world -> base_link joint origin (parameter 'robot_description')
#      so the robot model renders at the right position in the GUI.
#   2. The static TF world -> base_link broadcast so the TF tree matches.
#   3. Subtracted from incoming /magfield_transform poses (which are in world
#      frame) to convert them into base_link coordinates before sending to
#      MoveIt.
#
BASE_OFFSET_X = 0.0   # metres — positive = move robot in +X world direction
BASE_OFFSET_Y = -0.40   # metres — positive = move robot in +Y world direction
BASE_OFFSET_Z = -0.3  # metres — positive = raise robot in +Z world direction


# ── Node ──────────────────────────────────────────────────────────────────────

class MoveItController(Node):

    def __init__(self):
        super().__init__("moveit_controller")

        # TF2 buffer + listener — used to read the live end-effector pose
        self._tf_buffer   = tf2_ros.Buffer()
        self._tf_listener = tf2_ros.TransformListener(self._tf_buffer, self)

        # Static TF broadcaster — publishes world -> base_link with BASE_OFFSET.
        # Slicer's vtkMRMLROS2RobotNode positions links from /tf_static, NOT
        # from URDF joint origins, so this broadcast is what actually moves the
        # rendered robot.  robot_state_publisher also publishes world->base_link
        # with zero offset; we re-broadcast on a 1 s timer to continuously win.
        self._static_tf_broadcaster = StaticTransformBroadcaster(self)
        self._broadcast_base_offset()
        self.create_timer(1.0, self._broadcast_base_offset)

        # Declare "robot_description" as a parameter on this node so the GUI
        # can monitor it directly.  Starts empty; filled once the URDF arrives.
        # GUI settings:
        #   Node name      : moveit_controller
        #   Parameter name : robot_description
        self.declare_parameter("robot_description", "")

        # Also publish the patched URDF as a latched topic for other consumers
        latched_qos = QoSProfile(
            depth=1,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            reliability=ReliabilityPolicy.RELIABLE,
        )
        self._desc_pub = self.create_publisher(
            String, "/robot_description_offset", latched_qos
        )

        # Subscribe to the original robot description (transient_local so we
        # receive the latched value even if we start after robot_state_publisher)
        self._desc_patched = False
        self.create_subscription(
            String,
            "/robot_description",
            self._robot_description_callback,
            latched_qos,
        )
        self.get_logger().info(
            "Subscribed to /robot_description — will patch offset "
            f"({BASE_OFFSET_X}, {BASE_OFFSET_Y}, {BASE_OFFSET_Z}) "
            "into world->base_link joint and expose as parameter 'robot_description'"
        )

        # MoveIt action client
        self._action_client = ActionClient(self, MoveGroup, "/move_action")
        self.get_logger().info("Waiting for MoveGroup action server ...")
        self._action_client.wait_for_server()
        self.get_logger().info("MoveGroup action server connected")

        self._moving = False

        self.create_subscription(
            Pose,
            "/magfield_transform",
            self._pose_callback,
            10,
        )
        self.get_logger().info("Listening on /magfield_transform ...")

    # ── Robot description: parse, patch, set parameter ────────────────────────

    def _robot_description_callback(self, msg: String):
        """
        Receive the original URDF, apply BASE_OFFSET to the world->base_link
        joint origin, then:
          - publish the patched URDF on /robot_description_offset (topic)
          - set it as the "robot_description" parameter on this node (for GUI)
        Only runs once — the robot description never changes at runtime.
        """
        if self._desc_patched:
            return
        self._desc_patched = True

        try:
            root = ET.fromstring(msg.data)
        except ET.ParseError as e:
            self.get_logger().error(f"Failed to parse robot_description XML: {e}")
            return

        # Log all joints so we can confirm the right one is found
        all_joints = [
            (j.get("name"), j.find("child").get("link") if j.find("child") is not None else "?")
            for j in root.findall("joint")
        ]
        self.get_logger().info(f"URDF joints found: {all_joints}")

        # Find the joint whose child is BASE_FRAME (base_link)
        target_joint = None
        for joint in root.findall("joint"):
            child_el = joint.find("child")
            if child_el is not None and child_el.get("link") == BASE_FRAME:
                target_joint = joint
                break

        if target_joint is None:
            self.get_logger().warn(
                f"No joint with child '{BASE_FRAME}' found — "
                "URDF parameter will be set unchanged. Check BASE_FRAME matches "
                "the child link name shown in the joints log above."
            )
        else:
            origin = target_joint.find("origin")
            if origin is None:
                origin = ET.SubElement(target_joint, "origin")

            existing = origin.get("xyz", "0 0 0").split()
            ox, oy, oz = float(existing[0]), float(existing[1]), float(existing[2])
            new_x, new_y, new_z = ox + BASE_OFFSET_X, oy + BASE_OFFSET_Y, oz + BASE_OFFSET_Z
            origin.set("xyz", f"{new_x} {new_y} {new_z}")

            self.get_logger().info(
                f"Patched joint '{target_joint.get('name')}': "
                f"xyz ({ox}, {oy}, {oz}) -> ({new_x}, {new_y}, {new_z})"
            )

        patched_urdf = ET.tostring(root, encoding="unicode")

        # ── Publish as latched topic ───────────────────────────────────────────
        out      = String()
        out.data = patched_urdf
        self._desc_pub.publish(out)

        # ── Set as parameter on this node (what the GUI reads) ─────────────────
        self.set_parameters([
            rclpy.parameter.Parameter(
                "robot_description",
                rclpy.parameter.Parameter.Type.STRING,
                patched_urdf,
            )
        ])

        self.get_logger().info(
            "Patched URDF set as parameter 'robot_description' on node "
            "'moveit_controller' and published on /robot_description_offset"
        )

    # ── TF broadcast ─────────────────────────────────────────────────────────

    def _broadcast_base_offset(self):
        """
        Publish a static TF world -> base_link carrying BASE_OFFSET.
        Called once at startup and then every second via a timer so our
        offset continuously overwrites the zero-offset transform that
        robot_state_publisher re-publishes from the original URDF.
        """
        t                         = TransformStamped()
        t.header.stamp            = self.get_clock().now().to_msg()
        t.header.frame_id         = "world"
        t.child_frame_id          = BASE_FRAME
        t.transform.translation.x = BASE_OFFSET_X
        t.transform.translation.y = BASE_OFFSET_Y
        t.transform.translation.z = BASE_OFFSET_Z
        t.transform.rotation.x    = 0.0
        t.transform.rotation.y    = 0.0
        t.transform.rotation.z    = 0.0
        t.transform.rotation.w    = 1.0
        self._static_tf_broadcaster.sendTransform(t)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _log_current_ee_pose(self):
        """Look up BASE_FRAME -> END_EFFECTOR via TF2 and print the result."""
        try:
            tf = self._tf_buffer.lookup_transform(
                BASE_FRAME, END_EFFECTOR, Time()
            )
            t = tf.transform.translation
            r = tf.transform.rotation
            self.get_logger().info(
                f'Current EE pose ({BASE_FRAME} -> {END_EFFECTOR}):'
                f'\n  Position    x={t.x:.4f}, y={t.y:.4f}, z={t.z:.4f}'
                f'\n  Orientation x={r.x:.4f}, y={r.y:.4f}, z={r.z:.4f}, w={r.w:.4f}'
            )
            print(
                f'\nCurrent EE pose ({BASE_FRAME} -> {END_EFFECTOR}):'
                f'\n  Position    x={t.x:.4f}, y={t.y:.4f}, z={t.z:.4f}'
                f'\n  Orientation x={r.x:.4f}, y={r.y:.4f}, z={r.z:.4f}, w={r.w:.4f}'
            )
        except (LookupException, ConnectivityException, ExtrapolationException) as e:
            self.get_logger().warn(f"TF2 lookup failed (EE pose unavailable): {e}")

    # ── Pose callback ─────────────────────────────────────────────────────────

    def _pose_callback(self, msg: Pose):
        # ── 1. Print the raw incoming pose ────────────────────────────────────
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

        # ── 2. Print the live end-effector pose from TF ───────────────────────
        self._log_current_ee_pose()

        # ── 3. Skip MoveIt planning if a move is already in progress
        if self._moving:
            self.get_logger().warn("Move in progress — skipping MoveIt planning.")
            return

        # ── 4. Scale from sensor units to metres ──────────────────────────────
        scaled_x = msg.position.x * POSITION_SCALE
        scaled_y = msg.position.y * POSITION_SCALE
        scaled_z = msg.position.z * POSITION_SCALE

        # ── 5. Convert world frame -> base_link frame ─────────────────────────
        #
        # /magfield_transform is in the same world frame as the GUI.
        # BASE_OFFSET defines where base_link sits in that world frame, so
        # subtracting it converts the target into base_link coordinates that
        # MoveIt expects.
        #
        goal_pose = Pose()
        goal_pose.position.x  = scaled_x - BASE_OFFSET_X
        goal_pose.position.y  = scaled_y - BASE_OFFSET_Y
        goal_pose.position.z  = scaled_z - BASE_OFFSET_Z
        goal_pose.orientation = msg.orientation

        self.get_logger().info(
            f'Goal pose in {BASE_FRAME} '
            f'(world ({scaled_x:.4f}, {scaled_y:.4f}, {scaled_z:.4f}) '
            f'minus offset ({BASE_OFFSET_X}, {BASE_OFFSET_Y}, {BASE_OFFSET_Z})):'
            f'\n  Position    x={goal_pose.position.x:.4f},'
            f' y={goal_pose.position.y:.4f}, z={goal_pose.position.z:.4f}'
        )
        print(
            f'\nGoal pose in {BASE_FRAME}:'
            f'\n  Position    x={goal_pose.position.x:.4f},'
            f' y={goal_pose.position.y:.4f}, z={goal_pose.position.z:.4f}'
        )

        self._moving = True
        self._send_goal(goal_pose)

    # ── Goal construction ─────────────────────────────────────────────────────

    def _build_goal(self, pose: Pose) -> MoveGroup.Goal:
        goal = MoveGroup.Goal()
        req  = MotionPlanRequest()

        req.group_name                      = PLANNING_GROUP
        req.num_planning_attempts           = NUM_RETRIES
        req.allowed_planning_time           = PLANNING_TIME
        req.max_velocity_scaling_factor     = VELOCITY_SCALING
        req.max_acceleration_scaling_factor = ACCEL_SCALING

        # Do NOT set req.start_state — leaving the default empty RobotState
        # (is_diff=False) tells MoveIt to use its internally monitored current
        # state.  Setting an empty RobotState + is_diff=True causes
        # START_STATE_INVALID after the first successful move.

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
    node = MoveItController()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
