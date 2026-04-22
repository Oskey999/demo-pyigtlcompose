#!/usr/bin/env python3
"""Test script to verify arm moves to different positions with calibration"""
import requests
import json
import time

# Test pose positions (we'll send these via phosphobot directly for a quick test)
test_positions = [
    {"name": "Home", "x": 0.0, "y": 0.0, "z": 0.0},
    {"name": "Forward-Up", "x": 10.0, "y": 5.0, "z": 10.0},
    {"name": "Left-High", "x": -10.0, "y": 15.0, "z": 15.0},
    {"name": "Right-Down", "x": 10.0, "y": 20.0, "z": 5.0},
    {"name": "Center-Mid", "x": 0.0, "y": 10.0, "z": 8.0},
]

phosphobot_url = "http://localhost:80"

print("=" * 60)
print("PHOSPHOBOT ARM MOVEMENT TEST")
print("=" * 60)

for pos in test_positions:
    print(f"\n[TEST] Moving arm to: {pos['name']}")
    print(f"  Position: x={pos['x']:.1f}cm, y={pos['y']:.1f}cm, z={pos['z']:.1f}cm")
    
    payload = {
        "x": pos['x'],
        "y": pos['y'],
        "z": pos['z']
    }
    
    try:
        # Send command directly to phosphobot
        response = requests.post(
            f"{phosphobot_url}/move/absolute",
            json=payload,
            timeout=5.0
        )
        
        print(f"  Response Status: {response.status_code}")
        try:
            resp_json = response.json()
            print(f"  Response Body: {resp_json}")
        except:
            print(f"  Response Body: {response.text}")
        
        if response.status_code == 200:
            print(f"  ✓ Command sent successfully")
        else:
            print(f"  ✗ Command failed with status {response.status_code}")
            
    except Exception as e:
        print(f"  ✗ Error: {e}")
    
    time.sleep(2)

print("\n" + "=" * 60)
print("TEST COMPLETE - Check if arm moved to all positions")
print("=" * 60)
