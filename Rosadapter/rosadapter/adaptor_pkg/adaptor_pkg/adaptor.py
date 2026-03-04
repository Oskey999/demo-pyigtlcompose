#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Transform
from geometry_msgs.msg import TransformStamped  # ← changed
from geometry_msgs.msg import Pose
class TransformListener(Node):
    def __init__(self):
        super().__init__('transform_listener')
        self.subscription = self.create_subscription(
            Pose,           # ← changed
            '/magfield_transform',
            self.listener_callback,
            10
        )

    def listener_callback(self, msg):
        self.get_logger().info(
            f'\nPosition: x={msg.position.x:.4f}, y={msg.position.y:.4f}, z={msg.position.z:.4f}'
            f'\nOrientation: x={msg.orientation.x:.4f}, y={msg.orientation.y:.4f}, z={msg.orientation.z:.4f}, w={msg.orientation.w:.4f}'
        )
        print(
            f'\nPosition: x={msg.position.x:.4f}, y={msg.position.y:.4f}, z={msg.position.z:.4f}'
            f'\nOrientation: x={msg.orientation.x:.4f}, y={msg.orientation.y:.4f}, z={msg.orientation.z:.4f}, w={msg.orientation.w:.4f}'
        )


def main(args=None):
    rclpy.init(args=args)
    node = TransformListener()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()