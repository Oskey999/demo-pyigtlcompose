import os
import sys
import slicer
import shutil
import time
from configparser import ConfigParser


# Add SlicerTMS module path to Python path so Slicer can find and load it
module_path = '/tmp/Slicer-root'
if module_path not in sys.path:
    sys.path.insert(0, module_path)
    print(f"Added {module_path} to sys.path")

# Also ensure the module directories are in the module paths
slicer_module_paths = [
    '/opt/slicer/Slicer-5.8.1-linux-amd64/lib/Slicer-5.8.1/qt-scripted-modules',
    '/opt/slicer/Slicer-5.8.1-linux-amd64/TMS',
    '/opt/slicer/Slicer-5.8.1-linux-amd64/IGT',
    '/tmp/Slicer-root'
]

import qt
factory = slicer.app.moduleManager().factoryManager()

# Find and register all .py modules in the specified directories
module_names = []
for module_dir in slicer_module_paths:
    if not os.path.isdir(module_dir):
        print(f"Directory does not exist: {module_dir}")
        continue
    
    print(f"Scanning directory: {module_dir}")
    for filename in os.listdir(module_dir):
        if filename.endswith('.py') and not filename.startswith('_'):
            module_file_path = os.path.join(module_dir, filename)
            module_name = os.path.splitext(filename)[0]
            
            try:
                # Register the module using QFileInfo
                factory.registerModule(qt.QFileInfo(module_file_path))
                module_names.append(module_name)
                print(f"Registered module: {module_name} from {module_file_path}")
            except Exception as e:
                print(f"Failed to register module {module_name}: {e}")

# Now load all the registered modules
if module_names:
    try:
        success = factory.loadModules(module_names)
        if success:
            print(f"Successfully loaded modules: {', '.join(module_names)}")
        else:
            print(f"Failed to load some modules from: {', '.join(module_names)}")
    except Exception as e:
        print(f"Error loading modules: {e}")
else:
    print("No modules found to load")


print("Attempting to select SlicerTMS module...")
try:
    factory.registerModule(qt.QFileInfo('/opt/slicer/Slicer-5.8.1-linux-amd64/TMS/SlicerTMS.py'))
    factory.loadModules(['SlicerTMS'])
    slicer.util.mainWindow().moduleSelector().selectModule('SlicerTMS')
    print("SlicerTMS module activated!")
except Exception as e:
    print(f"Could not activate SlicerTMS module: {e}")

# config = ConfigParser()
# config.read('/home/ubuntu/.config/slicer.org/Slicer.ini')
# # config.add_section('Developer')
# # # Modify an existing option
# config.set('Developer', 'DeveloperModet', 'true')


# # Write changes back to the file
# with open('/home/ubuntu/.config/slicer.org/Slicer.ini', 'w') as configfile:
#     config.write(configfile)
# # Download and install Slicer from GitHub
## Install the extensions from the Slicer Extension Manager (excluding TMS which is local)
extensionNames = ['SlicerOpenIGTLinkIF', 'OpenIGTLinkIF', 'SlicerDMRI', 'SlicerIGT', 'IGT', 'DMRI']
for extensionName in extensionNames:
    time.sleep(5)
    em = slicer.app.extensionsManagerModel()
    em.interactive = False
    restart = True  # This will cause Slicer to restart after each installation
    if not em.installExtensionFromServer(extensionName, restart):
        print(f"Failed to install {extensionName} extension")

# archiveFilePath = os.path.join(slicer.app.temporaryPath, "main.zip")
# outputDir = os.path.join(slicer.app.temporaryPath, "SlicerTMS")

# try:
#     os.remove(archiveFilePath)
# except FileNotFoundError:
#     pass

# try:
#     shutil.rmtree(outputDir)
# except FileNotFoundError:
#     pass

# os.mkdir(outputDir)

# print("Downloading and extracting SlicerTMS")
# print(f"Downloading from {archiveFilePath} to {outputDir}")
# slicer.util.downloadAndExtractArchive(
#     url = "https://github.com/lorifranke/SlicerTMS/archive/refs/heads/main.zip",
#     archiveFilePath = archiveFilePath,
#     outputDir = outputDir)

# print("Registering SlicerTMS module")
# modulePath = os.path.join(outputDir, "SlicerTMS-main",  "client", "SlicerTMS", "SlicerTMS.py")
# # modulePath = os.path.abspath("")
# print(f"Module path: {modulePath}")
# factoryManager = slicer.app.moduleManager().factoryManager()

# factoryManager.registerModule(qt.QFileInfo(modulePath))
# # slicer.modules.addModulePath(modulePath)

# factoryManager.loadModules(["SlicerTMS"])

# slicer.util.selectModule("SlicerTMS")

# archiveFilePath = os.path.join(slicer.app.temporaryPath, "master.zip")
# outputDir = os.path.join(slicer.app.temporaryPath, "SlicerImageStacks")

# try:
#     os.remove(archiveFilePath)
# except FileNotFoundError:
#     pass

# try:
#     shutil.rmtree(outputDir)
# except FileNotFoundError:
#     pass

# os.mkdir(outputDir)

# slicer.util.downloadAndExtractArchive(
#     url = "https://github.com/pieper/SlicerImageStacks/archive/master.zip",
#     archiveFilePath = archiveFilePath,
#     outputDir = outputDir)

# modulePath = os.path.join(outputDir, "SlicerImageStacks-master", "ImageStacks", "ImageStacks.py")
# factoryManager = slicer.app.moduleManager().factoryManager()

# factoryManager.registerModule(qt.QFileInfo(modulePath))

# factoryManager.loadModules(["ImageStacks",])

# slicer.util.selectModule("ImageStacks")