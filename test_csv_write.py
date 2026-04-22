#!/usr/bin/env python3
"""
Test script to verify CSV writing works through the optimized container.
This tests the Mapper.record_simulation_event functionality.
"""
import docker
import json
import time

# Create a test matrix (4x4 identity matrix)
test_matrix = [
    1.0, 0.0, 0.0, 0.0,
    0.0, 1.0, 0.0, 0.0,
    0.0, 0.0, 1.0, 0.0,
    0.0, 0.0, 0.0, 1.0
]

# Python code to execute in the container
test_code = f"""
import sys
sys.path.insert(0, '/app/SlicerTMS/client')

# Import the Mapper module
from SlicerTMS.Mapper import Mapper

# Create a mock vtkMatrix4x4 object
class MockMatrix4x4:
    def __init__(self, values):
        self.values = values
    
    def GetElement(self, i, j):
        return self.values[i * 4 + j]

# Test the record_simulation_event
matrix = MockMatrix4x4({test_matrix})
try:
    Mapper.record_simulation_event(matrix, 'start', '/app/evaluations/results.csv')
    print("TEST_RESULT: SUCCESS - Event recorded")
except Exception as e:
    print(f"TEST_RESULT: FAILED - {{e}}")
"""

client = docker.from_env()

try:
    # Execute the test in the optimized container
    container = client.containers.get('optimized')
    result = container.exec_run(
        cmd=['/usr/bin/python3', '-c', test_code],
        demux=False
    )
    
    output = result.output.decode('utf-8', errors='replace')
    print("=" * 60)
    print("Test Output:")
    print("=" * 60)
    print(output)
    print("=" * 60)
    
    if result.exit_code == 0:
        print("\n✓ Script executed successfully")
    else:
        print(f"\n✗ Script failed with exit code {result.exit_code}")
        
except Exception as e:
    print(f"✗ Error: {e}")
