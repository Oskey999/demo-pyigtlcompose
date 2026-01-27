import os
import sys
import slicer
import time

# Ensure OpenIGTLink extension is loaded first
try:
    slicer.modules.openigtlinkif
    print("OpenIGTLink extension is available")
except AttributeError:
    print("Warning: OpenIGTLink extension not found")

# Add SlicerTMS module path to Python path
module_path = '/tmp/Slicer-root'
print(f"Adding SlicerTMS module path: {module_path}")
if module_path not in sys.path:
    print("Adding module path to Python sys.path...")
    sys.path.insert(0, module_path)
    print("Module path added.")
else:
    print("Module path already in sys.path")

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
    # First, try direct import
    import SlicerTMS
    print("SlicerTMS module imported successfully")
    
    # Give Slicer a moment to fully initialize
    time.sleep(2)
    
    # Reload the module list to discover SlicerTMS
    slicer.app.moduleManager().factoryManager().registerModules(
        '/opt/slicer/Slicer-5.8.1-linux-amd64/lib/Slicer-5.8.1/qt-scripted-modules'
    )
    print("Registered module factory paths")
    
    # Try to activate the SlicerTMS module
    try:
        slicer.util.mainWindow().moduleSelector().selectModule('SlicerTMS')
        print("SlicerTMS module activated!")
    except Exception as e:
        print(f"Could not activate SlicerTMS module via selector: {e}")
        # Try alternate activation method
        try:
            slicer.modules.slicertms
            print("SlicerTMS accessible via slicer.modules")
        except Exception as e2:
            print(f"SlicerTMS not accessible via slicer.modules: {e2}")
        
except ImportError as e:
    print(f"Warning: Could not import SlicerTMS: {e}")
    import traceback
    traceback.print_exc()

slicer.app.settings().sync()