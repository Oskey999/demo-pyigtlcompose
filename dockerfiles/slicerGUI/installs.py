import os
import slicer
import shutil
import time
from configparser import ConfigParser


# config = ConfigParser()
# config.read('/home/ubuntu/.config/slicer.org/Slicer.ini')
# # config.add_section('Developer')
# # # Modify an existing option
# config.set('Developer', 'DeveloperModet', 'true')


# # Write changes back to the file
# with open('/home/ubuntu/.config/slicer.org/Slicer.ini', 'w') as configfile:
#     config.write(configfile)
# # Download and install Slicer from GitHub
## Install the Easy Shitt extensions from the Slicer Extension Manager
extensionNames = ['SlicerOpenIGTLinkIF', 'OpenIGTLinkIF', 'SlicerDMRI', 'SlicerIGT', 'IGT', 'DMRI', 'TMS']
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