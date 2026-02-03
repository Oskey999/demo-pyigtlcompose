import os
import sys
import slicer
import shutil
import time
from configparser import ConfigParser

## Install the extensions from the Slicer Extension Manager (excluding TMS which is local)
extensionNames = ['SlicerDMRI', 'SlicerIGT', 'IGT', 'DMRI']
for extensionName in extensionNames:
    time.sleep(5)
    em = slicer.app.extensionsManagerModel()
    em.interactive = False
    restart = True  # This will cause Slicer to restart after each installation
    if not em.installExtensionFromServer(extensionName, restart):
        print(f"Failed to install {extensionName} extension")
