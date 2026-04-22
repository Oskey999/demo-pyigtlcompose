#!/usr/bin/env python3
"""Test script to verify +5cm Y offset is applied to phosphobot commands"""
import rclpy
from geometry_msgs.msg import Pose
import time

rclpy.init()
node = rclpy.create_node('test_y_offset')
pub = node.create_publisher(Pose, '/magfield_transform', 10)
time.sleep(1)

pose = Pose()
pose.position.x = 0.0
pose.position.y = 0.05
pose.position.z = 0.12
pose.orientation.w = 1.0

print(f'[TEST] Publishing pose: x={pose.position.x}, y={pose.position.y}, z={pose.position.z}')
print(f'Expected phosphobot Y: {(0.05 + 0.5) * 100 * 0.1}cm (base y 0.05 + 0.5 offset)')
pub.publish(pose)
time.sleep(4)
rclpy.shutdown()
