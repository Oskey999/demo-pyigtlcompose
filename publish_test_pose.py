#!/usr/bin/env python3
"""Publish a test pose to /magfield_transform via ROS2"""
import rclpy
from geometry_msgs.msg import Pose
import time

def main():
    rclpy.init()
    node = rclpy.create_node('test_pose_publisher')
    publisher = node.create_publisher(Pose, '/magfield_transform', 10)
    
    # Give time for publisher to connect
    time.sleep(2)
    
    print("=" * 60)
    print("PUBLISHING TEST POSES VIA ROS2")
    print("=" * 60)
    
    test_poses = [
        {"name": "Center", "x": 0.0, "y": 0.0, "z": 0.15},
        {"name": "Left", "x": -0.1, "y": 0.0, "z": 0.15},
        {"name": "Right", "x": 0.1, "y": 0.0, "z": 0.15},
        {"name": "Forward", "x": 0.0, "y": 0.1, "z": 0.15},
        {"name": "Back", "x": 0.0, "y": -0.1, "z": 0.15},
    ]
    
    for pose_desc in test_poses:
        pose = Pose()
        pose.position.x = pose_desc['x']
        pose.position.y = pose_desc['y']
        pose.position.z = pose_desc['z']
        pose.orientation.w = 1.0
        
        print(f"\n[PUBLISH] {pose_desc['name']}: x={pose.position.x:.2f}, y={pose.position.y:.2f}, z={pose.position.z:.2f}")
        publisher.publish(pose)
        time.sleep(5)
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE - Check adaptor logs and physical arm")
    print("=" * 60)
    rclpy.shutdown()

if __name__ == '__main__':
    main()
