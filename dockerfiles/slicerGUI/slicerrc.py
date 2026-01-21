import os
import slicer
import time

# Ensure OpenIGTLink extension is loaded first
try:
    slicer.modules.openigtlinkif
    print("OpenIGTLink extension is available")
except AttributeError:
    print("Warning: OpenIGTLink extension not found")

# Add SlicerTMS module path
module_path = '/tmp/Slicer-root'
if module_path not in slicer.util.modulePath():
    slicer.util.setModuleSearchPaths([module_path])

# Directory inside the container where images are stored
image_directory = '/images'
if os.path.exists(image_directory):
    image_files = [os.path.join(image_directory, f) for f in os.listdir(image_directory) if f.endswith('.jpeg')]
    # Load the images
    for image_file in image_files:
        slicer.util.loadVolume(image_file, {'singleFile': False})

# Set the desired directory for saving files
slicer.app.settings().setValue("IO/DefaultWriteDirectory", "/root/Documents")

# Try to load and activate SlicerTMS module
try:
    import SlicerTMS
    print("SlicerTMS module imported successfully")
    
    # Give Slicer a moment to fully initialize
    time.sleep(1)
    
    # Activate the SlicerTMS module so the UI appears
    try:
        slicer.util.mainWindow().moduleSelector().selectModule('SlicerTMS')
        print("SlicerTMS module activated!")
    except Exception as e:
        print(f"Could not activate SlicerTMS module: {e}")
        
except ImportError as e:
    print(f"Warning: Could not import SlicerTMS: {e}")

slicer.app.settings().sync()