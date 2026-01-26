"""
============================
pyIGTL Client Test
Test communication with TMS server
============================
"""

import pyigtl
import numpy as np
import time
import os
from time import sleep

# Get server host and ports from environment variables
server_host = os.getenv('TMS_SERVER_HOST', 'localhost')
server_port_1 = int(os.getenv('TMS_SERVER_PORT_1', '18944'))
server_port_2 = int(os.getenv('TMS_SERVER_PORT_2', '18945'))

print(f"Connecting to server at {server_host}:{server_port_1} and {server_host}:{server_port_2}")

# Connect to the text message server to get the file name
try:
    text_client = pyigtl.OpenIGTLinkClient(server_host, server_port_2)
    print("Connected to text server")
    
    # Receive text message
    for i in range(10):
        messages = text_client.get_latest_messages()
        if messages:
            for message in messages:
                print(f"Received message: {message.string}")
            break
        sleep(0.1)
except Exception as e:
    print(f"Error connecting to text server: {e}")

# Connect to the main server
try:
    client = pyigtl.OpenIGTLinkClient(server_host, server_port_1)
    print("Connected to main server")
    
    # Create a dummy magnetic field image (dA/dt field)
    # Shape: (x, y, z, 3) for 3D vector field
    image_shape = (64, 64, 64, 3)
    dummy_image = np.random.randn(*image_shape).astype(np.float32) * 0.1
    
    # Send the image data
    image_message = pyigtl.ImageMessage(dummy_image, device_name="test_data")
    client.send_message(image_message)
    print(f"Sent test image with shape {image_shape}")
    
    # Wait and receive response
    print("Waiting for response from server...")
    time.sleep(1)
    
    max_attempts = 20
    for attempt in range(max_attempts):
        messages = client.get_latest_messages()
        if messages:
            print(f"Received {len(messages)} message(s)")
            for message in messages:
                if isinstance(message.image, np.ndarray):
                    print(f"Received image shape: {message.image.shape}")
                    print(f"Image data type: {message.image.dtype}")
                    print(f"Image device name: {message.device_name}")
                    print(f"Image min value: {message.image.min():.6f}")
                    print(f"Image max value: {message.image.max():.6f}")
            break
        else:
            print(f"Attempt {attempt + 1}/{max_attempts}: No messages received yet...")
            time.sleep(0.5)
    
    print("Test completed successfully")
    client.disconnect()
    
except Exception as e:
    print(f"Error during communication: {e}")
    import traceback
    traceback.print_exc()
