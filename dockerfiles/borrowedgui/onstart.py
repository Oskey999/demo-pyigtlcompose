import os
import sys
import slicer
import shutil
import time
from configparser import ConfigParser

# Ensure OpenIGTLink extension is properly loaded 
try:
    slicer.modules.openigtlinkif
    print("OpenIGTLink extension is available")
except AttributeError:
    print("Warning: OpenIGTLink extension not found")
try:
    slicer.modules.tractographydisplay
    print("Tractography Display extension is available")
except AttributeError:
    print("Warning: Tractography Display extension not found")


# Try to load and activate SlicerTMS module
# try:
#     # First, try direct import
#     import SlicerTMS
#     print("SlicerTMS module imported successfully")
    
#     # Give Slicer a moment to fully initialize
#     time.sleep(2)
    
#     # Reload the module list to discover SlicerTMS
#     slicer.app.moduleManager().factoryManager().registerModules(
#         '/opt/slicer/Slicer-5.8.1-linux-amd64/lib/Slicer-5.8.1/qt-scripted-modules'
#     )
#     print("Registered module factory paths")
    
#     # Try to activate the SlicerTMS module
#     try:
#         slicer.util.mainWindow().moduleSelector().selectModule('SlicerTMS')
#         print("SlicerTMS module activated!")
#     except Exception as e:
#         print(f"Could not activate SlicerTMS module via selector: {e}")
#         # Try alternate activation method
#         try:
#             slicer.modules.slicertms
#             print("SlicerTMS accessible via slicer.modules")
#         except Exception as e2:
#             print(f"SlicerTMS not accessible via slicer.modules: {e2}")
        
# except ImportError as e:
#     print(f"Warning: Could not import SlicerTMS: {e}")
#     import traceback
#     traceback.print_exc()


slicer.app.settings().sync()