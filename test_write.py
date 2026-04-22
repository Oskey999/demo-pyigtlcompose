#!/usr/bin/env python3
import os
import csv
from datetime import datetime
import json

csv_path = "/app/evaluations/results.csv"
timestamp = datetime.now().isoformat()

# Create mock matrix (identity 4x4)
matrix_values = [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1]
matrix_json = json.dumps(matrix_values)

row = {
    "timestamp": timestamp,
    "event_type": "start",
    "transform_matrix": matrix_json,
    "docker_stats": ""
}

print(f"Testing CSV write to: {csv_path}")
print(f"File exists: {os.path.exists(csv_path)}")

if os.path.exists(csv_path):
    print(f"File size before: {os.path.getsize(csv_path)} bytes")

try:
    with open(csv_path, "a", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=["timestamp", "event_type", "transform_matrix", "docker_stats"])
        writer.writerow(row)
    
    print(f"✓ Successfully wrote event at {timestamp}")
    print(f"File size after: {os.path.getsize(csv_path)} bytes")
except PermissionError as e:
    print(f"✗ Permission denied: {e}")
except Exception as e:
    print(f"✗ Error: {e}")
