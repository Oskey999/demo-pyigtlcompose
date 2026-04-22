import logging
import os
from typing import Annotated, Optional

import vtk, qt#, Qobject

import slicer
from slicer.i18n import tr as _
from slicer.i18n import translate
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin, getNode
from slicer.parameterNodeWrapper import (
    parameterNodeWrapper,
    WithinRange,
)
import math

from slicer import vtkMRMLScalarVolumeNode


#
# adjustpos
#


class adjustpos(ScriptedLoadableModule):
    """Uses ScriptedLoadableModule base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = _("adjustpos")  # TODO: make this more human readable by adding spaces
        # TODO: set categories (folders where the module shows up in the module selector)
        self.parent.categories = [translate("qSlicerAbstractCoreModule", "TMS")]
        self.parent.dependencies = []  # TODO: add here list of module names that this module requires
        self.parent.contributors = ["John Doe (AnyWare Corp.)"]  # TODO: replace with "Firstname Lastname (Organization)"
        # TODO: update with short description of the module and a link to online module documentation
        # _() function marks text as translatable to other languages
        self.parent.helpText = _("""
This is an example of scripted loadable module bundled in an extension.
See more information in <a href="https://github.com/organization/projectname#adjustpos">module documentation</a>.
""")
        # TODO: replace with organization, grant and thanks
        self.parent.acknowledgementText = _("""
This file was originally developed by Jean-Christophe Fillion-Robin, Kitware Inc., Andras Lasso, PerkLab,
and Steve Pieper, Isomics, Inc. and was partially funded by NIH grant 3P41RR013218-12S1.
""")

        # Additional initialization step after application startup is complete
        slicer.app.connect("startupCompleted()", registerSampleData)


#
# Register sample data sets in Sample Data module
#


def registerSampleData():
    """Add data sets to Sample Data module."""
    # It is always recommended to provide sample data for users to make it easy to try the module,
    # but if no sample data is available then this method (and associated startupCompeted signal connection) can be removed.

    import SampleData

    iconsPath = os.path.join(os.path.dirname(__file__), "Resources/Icons")

    # To ensure that the source code repository remains small (can be downloaded and installed quickly)
    # it is recommended to store data sets that are larger than a few MB in a Github release.

    # adjustpos1
    SampleData.SampleDataLogic.registerCustomSampleDataSource(
        # Category and sample name displayed in Sample Data module
        category="adjustpos",
        sampleName="adjustpos1",
        # Thumbnail should have size of approximately 260x280 pixels and stored in Resources/Icons folder.
        # It can be created by Screen Capture module, "Capture all views" option enabled, "Number of images" set to "Single".
        thumbnailFileName=os.path.join(iconsPath, "adjustpos1.png"),
        # Download URL and target file name
        uris="https://github.com/Slicer/SlicerTestingData/releases/download/SHA256/998cb522173839c78657f4bc0ea907cea09fd04e44601f17c82ea27927937b95",
        fileNames="adjustpos1.nrrd",
        # Checksum to ensure file integrity. Can be computed by this command:
        #  import hashlib; print(hashlib.sha256(open(filename, "rb").read()).hexdigest())
        checksums="SHA256:998cb522173839c78657f4bc0ea907cea09fd04e44601f17c82ea27927937b95",
        # This node name will be used when the data set is loaded
        nodeNames="adjustpos1",
    )

    # adjustpos2
    SampleData.SampleDataLogic.registerCustomSampleDataSource(
        # Category and sample name displayed in Sample Data module
        category="adjustpos",
        sampleName="adjustpos2",
        thumbnailFileName=os.path.join(iconsPath, "adjustpos2.png"),
        # Download URL and target file name
        uris="https://github.com/Slicer/SlicerTestingData/releases/download/SHA256/1a64f3f422eb3d1c9b093d1a18da354b13bcf307907c66317e2463ee530b7a97",
        fileNames="adjustpos2.nrrd",
        checksums="SHA256:1a64f3f422eb3d1c9b093d1a18da354b13bcf307907c66317e2463ee530b7a97",
        # This node name will be used when the data set is loaded
        nodeNames="adjustpos2",
    )


#
# adjustposParameterNode
#


@parameterNodeWrapper
class adjustposParameterNode:
    """
    The parameters needed by module.

    inputVolume - The volume to threshold.
    imageThreshold - The value at which to threshold the input volume.
    invertThreshold - If true, will invert the threshold.
    thresholdedVolume - The output volume that will contain the thresholded volume.
    invertedVolume - The output volume that will contain the inverted thresholded volume.
    """

    inputVolume: vtkMRMLScalarVolumeNode
    imageThreshold: Annotated[float, WithinRange(-100, 500)] = 100
    invertThreshold: bool = False
    thresholdedVolume: vtkMRMLScalarVolumeNode
    invertedVolume: vtkMRMLScalarVolumeNode


#
# adjustposWidget
#


class adjustposWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
    """Uses ScriptedLoadableModuleWidget base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent=None) -> None:
        """Called when the user opens the module the first time and the widget is initialized."""
        ScriptedLoadableModuleWidget.__init__(self, parent)
        VTKObservationMixin.__init__(self)  # needed for parameter node observation
        self.logic = None
        self._parameterNode = None
        self._parameterNodeGuiTag = None

    def setup(self) -> None:
        """Called when the user opens the module the first time and the widget is initialized."""
        ScriptedLoadableModuleWidget.setup(self)

        # Load widget from .ui file (created by Qt Designer).
        # Additional widgets can be instantiated manually and added to self.layout.
        uiWidget = slicer.util.loadUI(self.resourcePath("UI/adjustpos.ui"))
        self.layout.addWidget(uiWidget)
        self.ui = slicer.util.childWidgetVariables(uiWidget)

        # Set scene in MRML widgets. Make sure that in Qt designer the top-level qMRMLWidget's
        # "mrmlSceneChanged(vtkMRMLScene*)" signal in is connected to each MRML widget's.
        # "setMRMLScene(vtkMRMLScene*)" slot.
        uiWidget.setMRMLScene(slicer.mrmlScene)

        # Create logic class. Logic implements all computations that should be possible to run
        # in batch mode, without a graphical user interface.
        self.logic = adjustposLogic(self.ui)

        # Connections

        # These connections ensure that we update parameter node when scene is closed
        self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.onSceneStartClose)
        self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.onSceneEndClose)

        # Buttons
        # self.ui.applyButton.connect("clicked(bool)", self.onApplyButton)
        self.ui.acc.connect("valueChanged(double)", self.logic.inc_update) 
        # self.ui.up.connect("clicked(bool)", self.logic.onUpbutton)
        self.ui.up.clicked.connect(lambda: self.logic.onbuttonPressed(-1,0,0))
        self.ui.down.clicked.connect(lambda: self.logic.onbuttonPressed(1,0,0))
        self.ui.left.clicked.connect(lambda: self.logic.onbuttonPressed(0,-1,0))
        self.ui.right.clicked.connect(lambda: self.logic.onbuttonPressed(0,1,0))
        self.ui.inb.clicked.connect(lambda: self.logic.onbuttonPressed(0,0,-1))
        self.ui.out.clicked.connect(lambda: self.logic.onbuttonPressed(0,0,1))
        self.ui.runSequence.clicked.connect(self.logic.runSequence)

        self.refreshPORT()
        self.ui.refreshPORTButton.clicked.connect(self.refreshPORT)



        # Make sure parameter node is initialized (needed for module reload)
        # self.initializeParameterNode()

    def refreshPORT(self) -> None:
        """Refresh the list of available ports (MIDI support removed)"""
        logging.info("Port refresh called (MIDI device scanning removed)")

    def cleanup(self) -> None:
        """Called when the application closes and the module widget is destroyed."""
        self.removeObservers()

    def enter(self) -> None:
        """Called each time the user opens this module."""
        # Make sure parameter node exists and observed
        # self.initializeParameterNode()

    def exit(self) -> None:
        """Called each time the user opens a different module."""
        # Do not react to parameter node changes (GUI will be updated when the user enters into the module)
        if self._parameterNode:
            self._parameterNode.disconnectGui(self._parameterNodeGuiTag)
            self._parameterNodeGuiTag = None
            # self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self._checkCanApply)

    def onSceneStartClose(self, caller, event) -> None:
        """Called just before the scene is closed."""
        # Parameter node will be reset, do not use it anymore
        self.setParameterNode(None)

    def onSceneEndClose(self, caller, event) -> None:
        """Called just after the scene is closed."""
        # If this module is shown while the scene is closed then recreate a new parameter node immediately
        if self.parent.isEntered:
            self.initializeParameterNode()

    def initializeParameterNode(self) -> None:
        """Ensure parameter node exists and observed."""
        # Parameter node stores all user choices in parameter values, node selections, etc.
        # so that when the scene is saved and reloaded, these settings are restored.

        self.setParameterNode(self.logic.getParameterNode())

        # Select default input nodes if nothing is selected yet to save a few clicks for the user
        if not self._parameterNode.inputVolume:
            firstVolumeNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLScalarVolumeNode")
            if firstVolumeNode:
                self._parameterNode.inputVolume = firstVolumeNode

    def setParameterNode(self, inputParameterNode: Optional[adjustposParameterNode]) -> None:
        """
        Set and observe parameter node.
        Observation is needed because when the parameter node is changed then the GUI must be updated immediately.
        """

        if self._parameterNode:
            self._parameterNode.disconnectGui(self._parameterNodeGuiTag)
            self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self._checkCanApply)
        self._parameterNode = inputParameterNode
        if self._parameterNode:
            # Note: in the .ui file, a Qt dynamic property called "SlicerParameterName" is set on each
            # ui element that needs connection.
            self._parameterNodeGuiTag = self._parameterNode.connectGui(self.ui)
            self.addObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self._checkCanApply)
            self._checkCanApply()

    def _checkCanApply(self, caller=None, event=None) -> None:
        if self._parameterNode and self._parameterNode.inputVolume and self._parameterNode.thresholdedVolume:
            self.ui.applyButton.toolTip = _("Compute output volume")
            self.ui.applyButton.enabled = True
        else:
            self.ui.applyButton.toolTip = _("Select input and output volume nodes")
            self.ui.applyButton.enabled = False

    def onApplyButton(self) -> None:
        """Run processing when user clicks "Apply" button."""
        with slicer.util.tryWithErrorDisplay(_("Failed to compute results."), waitCursor=True):
            # Compute output
            self.logic.process(self.ui.inputSelector.currentNode(), self.ui.outputSelector.currentNode(),
                               self.ui.imageThresholdSliderWidget.value, self.ui.invertOutputCheckBox.checked)

            # Compute inverted output (if needed)
            if self.ui.invertedOutputSelector.currentNode():
                # If additional output volume is selected then result with inverted threshold is written there
                self.logic.process(self.ui.inputSelector.currentNode(), self.ui.invertedOutputSelector.currentNode(),
                                   self.ui.imageThresholdSliderWidget.value, not self.ui.invertOutputCheckBox.checked, showResult=False)


#
# adjustposLogic
#


class adjustposLogic(ScriptedLoadableModuleLogic):
    """This class should implement all the actual
    computation done by your module.  The interface
    should be such that other python code can import
    this class and make use of the functionality without
    requiring an instance of the Widget.
    Uses ScriptedLoadableModuleLogic base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """
    increment: float = 1.0
    UI= None
    targetNode:str= None
    coilNode:str= None
    theta: float= 0.0 #Polar angle from z axis
    phi: float= 0.0 # azimuth angle in xy plane from x axis
    rad: float= 100.0 # radial distance from origin

    inv: int=-1


    def _finddata(self)->None:
        # self.increment= self.UI.acc.value
        self.targetNode= self.UI.targ.text
        self.coilNode= self.UI.coil.text

    def __init__(self, ui) -> None:
        """Called when the logic class is instantiated. Can be used for initializing member variables."""
        ScriptedLoadableModuleLogic.__init__(self)
        self.UI = ui
        
        # Create the transform nodes we'll need
        self.rotationTransformNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLinearTransformNode", "CoilRotationTransform")
        self.finalTransformNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLinearTransformNode", "CoilFinalTransform")
        
        # Sequence tracking
        self.sequenceTimer = None
        self.sequenceIndex = 0
        self.sequenceSteps = []

    def getParameterNode(self):
        return adjustposParameterNode(super().getParameterNode())
    
    def inc_update(self,d:float)->None:
        """updates the increment value used in the adjustment calculations
        Parameters""" 
        self.increment = d
        # print(f"Increment set to {self.increment}")
        self.UI.Debug.setText(f"Current Increment: {self.increment} mm")
    def onbuttonPressed(self,theta:int,phi:int,rad:int)->None:
        """moves the volume up by the increment value"""
        
        # self.increment= self.UI.acc.value
        self._finddata()
        self.UI.Debug.setText(f"Current Increment: {self.increment} mm up {self.targetNode} {self.coilNode} ")

        ## Update coords with increment
        self.theta += self.increment*theta
        self.phi += self.increment*phi
        self.rad += self.increment*rad
        print(f"Radial distance: {self.rad} mm")
        print(f"Theta: {self.theta} degrees")
        print(f"Phi: {self.phi} degrees")
        ## move to coords
        self.set_new_position()

    def runSequence(self) -> None:
        """Runs a sequence of movements with specified increments, using non-blocking delays."""
        
        # Define the sequence: (increment, button_params)
        # button_params are (theta, phi, rad) passed to onbuttonPressed
        self.sequenceSteps = [
            (20, (0, 0, 1)),   # out
            (90, (-1, 0, 0)),  # up
            (90, (1, 0, 0)),   # down
            (90, (1, 0, 0)),   # down
            (90, (0, 1, 0)),   # right
            (90, (-1, 0, 0)),  # up
            (90, (-1, 0, 0)),  # up
            (90, (1, 0, 0)),   # down
            (90, (0, -1, 0)),  # left
            (20, (0, 0, -1)),  # in
        ]
        
        self.sequenceIndex = 0
        self._executeNextSequenceStep()
    
    def _executeNextSequenceStep(self) -> None:
        """Execute the next step in the sequence using non-blocking timer."""
        if self.sequenceIndex >= len(self.sequenceSteps):
            # Sequence complete
            self.UI.Debug.setText("Sequence complete")
            return
        
        increment, (theta, phi, rad) = self.sequenceSteps[self.sequenceIndex]
        
        # Set the increment
        self.inc_update(increment)
        slicer.app.processEvents()
        
        # Execute the button press
        self.onbuttonPressed(theta, phi, rad)
        
        # Flush all pending events to ensure scene transforms are fully applied
        # This is critical for the mapper to record the position changes correctly
        slicer.app.processEvents()
        qt.QApplication.sendPostedEvents()
        slicer.app.processEvents()
        
        # Increment index for next step
        self.sequenceIndex += 1
        
        # Schedule next step after 4 seconds (non-blocking)
        # The 4 seconds gives the mapper time to record the current position
        if self.sequenceIndex < len(self.sequenceSteps):
            if self.sequenceTimer is None:
                self.sequenceTimer = qt.QTimer()
                self.sequenceTimer.setSingleShot(True)
                self.sequenceTimer.timeout.connect(self._executeNextSequenceStep)
            
            self.sequenceTimer.start(4000)  # 4000 milliseconds = 4 seconds

    def _updateFinalTransform(self, centerPoint: tuple) -> None:
        """
        Updates the final transform to rotate around a specified point.
        This is based on the translate-rotate-translate technique.
        
        Parameters:
            centerPoint: (x, y, z) coordinates of the rotation center
        """
        # Get the current rotation matrix
        rotationMatrix = vtk.vtkMatrix4x4()
        self.rotationTransformNode.GetMatrixTransformToParent(rotationMatrix)
        
        # Build the composite transform
        finalTransform = vtk.vtkTransform()
        finalTransform.Translate(centerPoint[0], centerPoint[1], centerPoint[2])  # Move center to origin
        finalTransform.Concatenate(rotationMatrix)  # Apply rotation
        finalTransform.Translate(-centerPoint[0], -centerPoint[1], -centerPoint[2])  # Move back
        
        # Apply to final transform node
        self.finalTransformNode.SetAndObserveMatrixTransformToParent(finalTransform.GetMatrix())
    
    def _polar_to_cartesian(self, origin:tuple)->tuple:
        """Converts spherical coordinates to cartesian coordinates
        Parameters:
            r: radial distance from origin
            theta: polar angle from z axis in degrees
            phi: azimuth angle in xy plane from x axis in degrees
        Returns:
            x, y, z: cartesian coordinates
        """
        
        theta_rad = math.radians(self.theta)
        phi_rad = math.radians(self.phi)
        print(f"theta rad: {theta_rad}, phi rad: {phi_rad}")
        x = self.rad * math.sin(theta_rad) * math.cos(phi_rad)+origin[0]
        y = self.rad * math.sin(theta_rad) * math.sin(phi_rad)+origin[1]
        z = self.rad * math.cos(theta_rad)+origin[2]
        return x, y, z
    
    # def _get_origin(self, nodeName:str)->tuple:
    #     """Gets the center of the model node
    #     Parameters:
    #         nodeName: name of the model node
    #     Returns:
    #         x, y, z: center coordinates
    #     """
    #     # bounds = [0]*6
    #     # slicer.util.getNode(nodeName).GetBounds(bounds)
    #     print(f"global coords : {slicer.util.getNode(nodeName).GetOriginWorld()}")
    #     center= slicer.util.getNode(nodeName).GetOriginWorld()
    #     # center = (
    #     #     0.5 * (bounds[0] + bounds[1]),
    #     #     0.5 * (bounds[2] + bounds[3]),
    #     #     0.5 * (bounds[4] + bounds[5])
    #     # )
        # return center
    def _get_origin(self, nodeName: str) -> tuple:
        """Gets the center of the model node
        Parameters:
            nodeName: name of the model node
        Returns:
            x, y, z: center coordinates
        """
        node = slicer.util.getNode(nodeName)
        
        # Check if it's a model node (mesh)
        if node.IsA('vtkMRMLModelNode'):
            # Get the bounds of the model
            bounds = [0] * 6
            node.GetBounds(bounds)
            
            # Calculate center from bounds
            center = (
                0.5 * (bounds[0] + bounds[1]),  # x: (xmin + xmax) / 2
                0.5 * (bounds[2] + bounds[3]),  # y: (ymin + ymax) / 2
                0.5 * (bounds[4] + bounds[5])   # z: (zmin + zmax) / 2
            )
            print(f"Model '{nodeName}' center: {center}")
            return center
        
        # If it's a markup/fiducial node
        elif node.IsA('vtkMRMLMarkupsNode'):
            point = [0.0, 0.0, 0.0]
            node.GetNthControlPointPositionWorld(0, point)
            print(f"Markup '{nodeName}' position: {tuple(point)}")
            return tuple(point)
        
        # If it's a transform node or other type
        else:
            print(f"Warning: Node '{nodeName}' type not fully supported: {node.GetClassName()}")
            # Try to get position from transform
            if hasattr(node, 'GetOriginWorld'):
                origin = node.GetOriginWorld()
                return origin
            else:
                # Return origin as fallback
                return (0.0, 0.0, 0.0)
    
    def _translate_node(self, nodeName:str, newPos:tuple)->None:
        """Translates the model node to new position
        Parameters:
            nodeName: name of the model node
            newPos: new position as (x, y, z)
        """
        node = slicer.util.getNode(nodeName)
        # print(f"Current position of {nodeName}: {node}")
        node.SetOriginWorld(newPos)
        print(f"Moved plane '{node.GetName()}' to position ({newPos[0]:.2f}, {newPos[1]:.2f}, {newPos[2]:.2f})")
    
    def _set_new_position(self)->None:
        """Sets the model node to new position based on updated polar coordinates
        Parameters:
            nodeName: name of the model node
            newPos: new position as (x, y, z)
        """
        ##get center
        center= self._get_origin(self.coilNode)
        print(center)
        
        ## Convert spherical to cartesian
        print(self._polar_to_cartesian(center))
        ## Apply translation to target node
        self._translate_node(self.coilNode, self._polar_to_cartesian(center))

        ## Modify to distance from head mesh surface

    def set_new_position(self) -> None:
        """
        Sets the coil node to new position based on updated polar coordinates.
        Uses rotation around the skin node's center point.
        """
        # Get the center of rotation (skin node origin)
        print(f"Setting new coil position... of {self.coilNode} relative to {self.targetNode}")
        centerPoint = self._get_origin(self.targetNode)
        print(f"Rotation center (skin): {centerPoint}")

        # stupid bull to get slicerTMS to notice the changes
        self.rad+=0.01*self.inv
        self.inv*=-1
        
        # Convert spherical coordinates to cartesian (relative to center)
        theta_rad = math.radians(self.theta)
        phi_rad = math.radians(self.phi)
        
        # Calculate position relative to origin (0,0,0)
        x = self.rad * math.sin(theta_rad) * math.cos(phi_rad)
        y = self.rad * math.sin(theta_rad) * math.sin(phi_rad)
        z = self.rad * math.cos(theta_rad)
        
        print(f"Spherical coords - r: {self.rad}, theta: {self.theta}°, phi: {self.phi}°")
        print(f"Cartesian offset - x: {x:.2f}, y: {y:.2f}, z: {z:.2f}")
        
        # Create a rotation matrix for the current spherical position
        # This orients the coil to point toward the center
        rotationTransform = vtk.vtkTransform()
        
        # Calculate the direction vector from coil position to center
        dirX = -x  # Negative because we want to point inward
        dirY = -y
        dirZ = -z
        length = math.sqrt(dirX**2 + dirY**2 + dirZ**2)
        
        if length > 0:
            dirX /= length
            dirY /= length
            dirZ /= length
            
            # Create rotation to align with direction vector
            # You may need to adjust this based on your coil's default orientation
            azimuth = math.degrees(math.atan2(dirY, dirX))
            elevation = math.degrees(math.asin(dirZ))+90
            
            rotationTransform.RotateZ(azimuth)
            rotationTransform.RotateY(-elevation)
        
        # Set the rotation transform
        self.rotationTransformNode.SetAndObserveMatrixTransformToParent(rotationTransform.GetMatrix())
        
        # Update the final transform (handles rotation around center point)
        self._updateFinalTransform(centerPoint)
        
        # Apply the final transform to the coil node
        coilNode = slicer.util.getNode(self.coilNode)
        coilNode.SetAndObserveTransformNodeID(self.finalTransformNode.GetID())
        
        # Set the coil's base position (this will be transformed by the final transform)
        newPos = (
            centerPoint[0] + x,
            centerPoint[1] + y,
            centerPoint[2] + z
        )
        coilNode.SetOriginWorld(newPos)
        
        print(f"Coil moved to world position: ({newPos[0]:.2f}, {newPos[1]:.2f}, {newPos[2]:.2f})")
        

    # def process(self,
    #             inputVolume: vtkMRMLScalarVolumeNode,
    #             outputVolume: vtkMRMLScalarVolumeNode,
    #             imageThreshold: float,
    #             invert: bool = False,
    #             showResult: bool = True) -> None:
    #     """
    #     Run the processing algorithm.
    #     Can be used without GUI widget.
    #     :param inputVolume: volume to be thresholded
    #     :param outputVolume: thresholding result
    #     :param imageThreshold: values above/below this threshold will be set to 0
    #     :param invert: if True then values above the threshold will be set to 0, otherwise values below are set to 0
    #     :param showResult: show output volume in slice viewers
    #     """

    #     if not inputVolume or not outputVolume:
    #         raise ValueError("Input or output volume is invalid")

    #     import time

    #     startTime = time.time()
    #     logging.info("Processing started")

    #     # Compute the thresholded output volume using the "Threshold Scalar Volume" CLI module
    #     cliParams = {
    #         "InputVolume": inputVolume.GetID(),
    #         "OutputVolume": outputVolume.GetID(),
    #         "ThresholdValue": imageThreshold,
    #         "ThresholdType": "Above" if invert else "Below",
    #     }
    #     cliNode = slicer.cli.run(slicer.modules.thresholdscalarvolume, None, cliParams, wait_for_completion=True, update_display=showResult)
    #     # We don't need the CLI module node anymore, remove it to not clutter the scene with it
    #     slicer.mrmlScene.RemoveNode(cliNode)

    #     stopTime = time.time()
    #     logging.info(f"Processing completed in {stopTime-startTime:.2f} seconds")


#
# adjustposTest
#


class adjustposTest(ScriptedLoadableModuleTest):
    """
    This is the test case for your scripted module.
    Uses ScriptedLoadableModuleTest base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def setUp(self):
        """Do whatever is needed to reset the state - typically a scene clear will be enough."""
        slicer.mrmlScene.Clear()

    def runTest(self):
        """Run as few or as many tests as needed here."""
        self.setUp()
        self.test_adjustpos1()

    def test_adjustpos1(self):
        """Ideally you should have several levels of tests.  At the lowest level
        tests should exercise the functionality of the logic with different inputs
        (both valid and invalid).  At higher levels your tests should emulate the
        way the user would interact with your code and confirm that it still works
        the way you intended.
        One of the most important features of the tests is that it should alert other
        developers when their changes will have an impact on the behavior of your
        module.  For example, if a developer removes a feature that you depend on,
        your test should break so they know that the feature is needed.
        """

        self.delayDisplay("Starting the test")

        # Get/create input data

        import SampleData

        registerSampleData()
        inputVolume = SampleData.downloadSample("adjustpos1")
        self.delayDisplay("Loaded test data set")

        inputScalarRange = inputVolume.GetImageData().GetScalarRange()
        self.assertEqual(inputScalarRange[0], 0)
        self.assertEqual(inputScalarRange[1], 695)

        outputVolume = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode")
        threshold = 100

        # Test the module logic

        logic = adjustposLogic()

        # Test algorithm with non-inverted threshold
        logic.process(inputVolume, outputVolume, threshold, True)
        outputScalarRange = outputVolume.GetImageData().GetScalarRange()
        self.assertEqual(outputScalarRange[0], inputScalarRange[0])
        self.assertEqual(outputScalarRange[1], threshold)

        # Test algorithm with inverted threshold
        logic.process(inputVolume, outputVolume, threshold, False)
        outputScalarRange = outputVolume.GetImageData().GetScalarRange()
        self.assertEqual(outputScalarRange[0], inputScalarRange[0])
        self.assertEqual(outputScalarRange[1], inputScalarRange[1])

        self.delayDisplay("Test passed")


# class MIDIDeviceFinder:
#     def __init__(self, timeout=5):
#         self.timeout = timeout
#         self.midi_baud = 31250
        
#     def list_serial_ports(self):
#         """List all available serial ports"""
#         ports = serial.tools.list_ports.comports()
#         return ports
    
#     def parse_midi_message(self, data):
#         """Parse MIDI message bytes"""
#         if len(data) < 2:
#             return None
        
#         status = data[0]
#         msg_type = status & 0xF0
#         channel = status & 0x0F
        
#         msg_info = {
#             'status': status,
#             'channel': channel,
#             'type': msg_type
#         }
        
#         if msg_type == 0x90:  # Note On
#             msg_info['message'] = 'Note ON'
#             msg_info['note'] = data[1] if len(data) > 1 else None
#             msg_info['velocity'] = data[2] if len(data) > 2 else None
#         elif msg_type == 0x80:  # Note Off
#             msg_info['message'] = 'Note OFF'
#             msg_info['note'] = data[1] if len(data) > 1 else None
#             msg_info['velocity'] = data[2] if len(data) > 2 else None
#         elif msg_type == 0xB0:  # Control Change
#             msg_info['message'] = 'Control Change'
#             msg_info['controller'] = data[1] if len(data) > 1 else None
#             msg_info['value'] = data[2] if len(data) > 2 else None
#         elif msg_type == 0xC0:  # Program Change
#             msg_info['message'] = 'Program Change'
#             msg_info['program'] = data[1] if len(data) > 1 else None
#         else:
#             msg_info['message'] = 'Unknown'
        
#         return msg_info
    
#     def test_port(self, port_name):
#         """Test a specific port for MIDI messages"""
#         try:
#             print(f"\nTesting {port_name}...")
#             ser = serial.Serial(
#                 port=port_name,
#                 baudrate=self.midi_baud,
#                 bytesize=serial.EIGHTBITS,
#                 parity=serial.PARITY_NONE,
#                 stopbits=serial.STOPBITS_ONE,
#                 timeout=1
#             )
            
#             print(f"  Listening for MIDI messages (timeout: {self.timeout}s)...")
#             start_time = time.time()
#             midi_messages = []
            
#             while time.time() - start_time < self.timeout:
#                 if ser.in_waiting >= 3:
#                     data = ser.read(3)
#                     msg = self.parse_midi_message(data)
#                     if msg:
#                         midi_messages.append(msg)
#                         print(f"  ✓ Received {msg['message']}: {data.hex()}")
                        
#                         # Check for characteristic startup sequence (Note On at 60)
#                         if msg['type'] == 0x90 and msg['note'] == 60:
#                             print(f"  ✓ Detected startup Note ON (Middle C)!")
#                             ser.close()
#                             return True, midi_messages
                        
#                         # Check for periodic CC messages (controller 1)
#                         if msg['type'] == 0xB0 and msg['controller'] == 1:
#                             print(f"  ✓ Detected CC message (Modulation Wheel)!")
            
#             ser.close()
            
#             if midi_messages:
#                 print(f"  ✓ Found {len(midi_messages)} MIDI messages")
#                 return True, midi_messages
#             else:
#                 print(f"  ✗ No MIDI messages detected")
#                 return False, []
                
#         except serial.SerialException as e:
#             print(f"  ✗ Error: {e}")
#             return False, []
#         except Exception as e:
#             print(f"  ✗ Unexpected error: {e}")
#             return False, []
    
#     def find_device(self):
#         """Find the Arduino MIDI device"""
#         print("=" * 60)
#         print("MIDI Serial Device Finder")
#         print("=" * 60)
        
#         ports = self.list_serial_ports()
        
#         if not ports:
#             print("No serial ports found!")
#             return None
        
#         print(f"\nFound {len(ports)} serial port(s):")
#         for port in ports:
#             print(f"  - {port.device}: {port.description}")
        
#         # Test each port
#         midi_devices = []
#         for port in ports:
#             is_midi, messages = self.test_port(port.device)
#             if is_midi:
#                 midi_devices.append({
#                     'port': port.device,
#                     'description': port.description,
#                     'messages': messages
#                 })
        
#         print("\n" + "=" * 60)
#         if midi_devices:
#             print(f"✓ Found {len(midi_devices)} MIDI device(s):")
#             for i, device in enumerate(midi_devices, 1):
#                 print(f"\n  Device {i}:")
#                 print(f"    Port: {device['port']}")
#                 print(f"    Description: {device['description']}")
#                 print(f"    Messages received: {len(device['messages'])}")
            
#             return midi_devices#[0]['port']  # Return first found device
#         else:
#             print("✗ No MIDI devices found")
#             print("\nTroubleshooting:")
#             print("  1. Check Arduino is connected and powered")
#             print("  2. Verify Arduino code is uploaded and running")
#             print("  3. Check MIDI baud rate is 31250")
#             print("  4. Press the button (GPIO 4) to trigger MIDI notes")
#             return None

#     def handle_midi_messages(self, port_name):
#         """Continuously listen and handle MIDI messages from the device"""
#         try:
#             ser = serial.Serial(
#                 port=port_name,
#                 baudrate=self.midi_baud,
#                 bytesize=serial.EIGHTBITS,
#                 parity=serial.PARITY_NONE,
#                 stopbits=serial.STOPBITS_ONE,
#                 timeout=0.1
#             )
            
#             print("\n" + "=" * 60)
#             print(f"Listening for MIDI messages on {port_name}")
#             print("Press Ctrl+C to stop")
#             print("=" * 60 + "\n")
            
#             buffer = []
            
#             while True:
#                 if ser.in_waiting > 0:
#                     byte = ser.read(1)[0]
                    
#                     # Check if this is a status byte (bit 7 set)
#                     if byte & 0x80:
#                         # If we have a previous incomplete message, clear it
#                         if buffer:
#                             buffer = []
#                         buffer.append(byte)
#                     else:
#                         # Data byte
#                         buffer.append(byte)
                    
#                     # Check if we have a complete message
#                     msg_type = buffer[0] & 0xF0 if buffer else 0
                    
#                     # Program Change and Channel Pressure are 2-byte messages
#                     expected_length = 2 if msg_type in [0xC0, 0xD0] else 3
                    
#                     if len(buffer) >= expected_length:
#                         self.print_midi_message(buffer[:expected_length])
#                         buffer = []
                
#                 time.sleep(0.001)  # Small delay to prevent CPU spinning
                
#         except KeyboardInterrupt:
#             print("\n\nStopping MIDI listener...")
#             ser.close()
#         except serial.SerialException as e:
#             print(f"\nSerial error: {e}")
#             if 'ser' in locals():
#                 ser.close()
#         except Exception as e:
#             print(f"\nUnexpected error: {e}")
#             if 'ser' in locals():
#                 ser.close()
    
#     def print_midi_message(self, data):
#         """Print MIDI message in a readable format"""
#         if len(data) < 2:
#             return
        
#         timestamp = time.strftime("%H:%M:%S")
#         print(data, timestamp)
#         status = data[0]
#         msg_type = status & 0xF0
#         channel = (status & 0x0F) + 1  # Display as 1-16 instead of 0-15
        
#         # Format hex bytes
#         hex_str = ' '.join(f'{b:02X}' for b in data)
        
#         if msg_type == 0x90:  # Note On
#             note = data[1]
#             velocity = data[2]
#             note_name = self.get_note_name(note)
#             if velocity > 0:
#                 print(f"[{timestamp}] Note ON  | Ch:{channel:2d} | {note_name:4s} (#{note:3d}) | Vel:{velocity:3d} | [{hex_str}]")
#             else:
#                 print(f"[{timestamp}] Note OFF | Ch:{channel:2d} | {note_name:4s} (#{note:3d}) | Vel:{velocity:3d} | [{hex_str}]")
        
#         elif msg_type == 0x80:  # Note Off
#             note = data[1]
#             velocity = data[2]
#             note_name = self.get_note_name(note)
#             print(f"[{timestamp}] Note OFF | Ch:{channel:2d} | {note_name:4s} (#{note:3d}) | Vel:{velocity:3d} | [{hex_str}]")
        
#         elif msg_type == 0xB0:  # Control Change
#             controller = data[1]
#             value = data[2]
#             cc_name = self.get_cc_name(controller)
#             print(f"[{timestamp}] CC       | Ch:{channel:2d} | {cc_name:20s} (#{controller:3d}) | Val:{value:3d} | [{hex_str}]")
        
#         elif msg_type == 0xC0:  # Program Change
#             program = data[1]
#             print(f"[{timestamp}] Prog Chg | Ch:{channel:2d} | Program:{program:3d} | [{hex_str}]")
        
#         elif msg_type == 0xD0:  # Channel Pressure
#             pressure = data[1]
#             print(f"[{timestamp}] Pressure | Ch:{channel:2d} | Value:{pressure:3d} | [{hex_str}]")
        
#         elif msg_type == 0xE0:  # Pitch Bend
#             lsb = data[1]
#             msb = data[2]
#             value = (msb << 7) | lsb
#             print(f"[{timestamp}] PitchBnd | Ch:{channel:2d} | Value:{value:5d} | [{hex_str}]")
        
#         else:
#             print(f"[{timestamp}] Unknown  | [{hex_str}]")
    
#     def get_note_name(self, note):
#         """Convert MIDI note number to note name"""
#         note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
#         octave = (note // 12) - 1
#         name = note_names[note % 12]
#         return f"{name}{octave}"
    
#     def get_cc_name(self, cc):
#         """Get common CC controller names"""
#         cc_names = {
#             1: "Modulation Wheel",
#             7: "Volume",
#             10: "Pan",
#             11: "Expression",
#             64: "Sustain Pedal",
#             91: "Reverb",
#             93: "Chorus"
#         }
#         return cc_names.get(cc, f"CC #{cc}")


