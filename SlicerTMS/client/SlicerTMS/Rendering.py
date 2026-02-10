import numpy as np
import slicer
import vtk
import os

l2n = lambda l: np.array(l)
n2l = lambda n: list(n)


class Rendering:
    def __init__(self, config=None):
        self.config = config
        print("Rendering class initialized")

    @staticmethod
    def showVolumeRenderingCT(volumeNode):
        print(f"Starting showVolumeRenderingCT for volume: {volumeNode.GetName() if volumeNode else 'unknown'}")
        
        volRenLogic = slicer.modules.volumerendering.logic()
        print("Retrieved volume rendering logic")
        
        displayNode = volRenLogic.CreateDefaultVolumeRenderingNodes(volumeNode)
        print("Created default volume rendering nodes")
        
        displayNode.SetVisibility(True)
        print("Set volume rendering visibility to True")
        
        displayNode.GetVolumePropertyNode().Copy(volRenLogic.GetPresetByName('CT-Chest-Contrast-Enhanced'))
        print("Applied CT-Chest-Contrast-Enhanced preset to volume property")
        
        print(f"Completed showVolumeRenderingCT for volume: {volumeNode.GetName() if volumeNode else 'unknown'}")

    @staticmethod
    def showVolumeRendering(volumeNode):
        print(f"Starting showVolumeRendering for volume: {volumeNode.GetName() if volumeNode else 'unknown'}")
        
        print(f"Current directory: {os.path.dirname(__file__)}")

        volRenLogic = slicer.modules.volumerendering.logic()
        print("Retrieved volume rendering logic")
        
        displayNode = volRenLogic.CreateDefaultVolumeRenderingNodes(volumeNode)
        print("Created default volume rendering nodes")

        propertyNode = displayNode.GetVolumePropertyNode()
        VolumeProperty = propertyNode.GetVolumeProperty()
        print("Retrieved volume property")
        
        VolumeProperty.SetAmbient(1.0)
        VolumeProperty.SetDiffuse(0.0)
        VolumeProperty.SetSpecular(0.0)
        VolumeProperty.SetSpecularPower(1.0)
        print("Set volume property parameters (ambient, diffuse, specular)")

        array = slicer.util.arrayFromVolume(volumeNode)
        print(f"Retrieved volume data as numpy array, shape: {array.shape}")
        
        array_max = np.max(array)
        print(f"Maximum value in volume data: {array_max}")

        if array_max > 1.1:
            array_max = np.max(array)
            print(f"Array max > 1.1, using actual max: {array_max}")
        else:
            array_max = np.max(array)
            print(f"Array max <= 1.1, using actual max: {array_max}")

        opacityTransfer = vtk.vtkPiecewiseFunction()
        opacityTransfer.AddPoint(0, 0)
        opacityTransfer.AddPoint(array_max * 0.1, 0.)
        opacityTransfer.AddPoint(array_max * 0.3, 0.06)
        opacityTransfer.AddPoint(array_max * 0.5, 0.07)
        opacityTransfer.AddPoint(array_max * 0.6, 0.08)
        opacityTransfer.AddPoint(array_max * 0.7, 0.09)
        opacityTransfer.AddPoint(array_max * 0.85, 0.35)
        opacityTransfer.AddPoint(array_max * 0.99, 1)
        opacityTransfer.AddPoint(array_max * 1, 1.00)
        print("Created opacity transfer function with multiple control points")

        ctf = vtk.vtkColorTransferFunction()
        print("Created color transfer function")
        
        table_path = os.path.join(os.path.dirname(__file__), "jet_table.txt")
        print(f"Looking for jet table at: {table_path}")
        
        table = np.loadtxt(table_path)
        print(f"Loaded jet table, shape: {table.shape}")
        
        value_range = np.linspace(0.1 * array_max, array_max, len(table))
        print(f"Created value range for color transfer, length: {len(value_range)}")

        for i in range(len(table)):
            ctf.AddRGBPoint(value_range[i], table[i, 0], table[i, 1], table[i, 2])
        print("Added RGB points to color transfer function")

        propertyNode.SetColor(ctf)
        propertyNode.SetScalarOpacity(opacityTransfer)
        print("Set color and opacity transfer functions on property node")

        controllerWidget = slicer.app.layoutManager().threeDWidget(0).threeDController()
        print("Retrieved 3D controller widget")
        
        controllerWidget.setUseDepthPeeling(False)
        print("Disabled depth peeling")

        # Add color node
        # colorNode = slicer.mrmlScene.CreateNodeByClass("vtkMRMLProceduralColorNode")
        # colorNode.UnRegister(None)  # to prevent memory leaks
        # colorNode.SetName(slicer.mrmlScene.GenerateUniqueName("MyColormap"))
        # colorNode.SetAttribute("Category", "MyModule")
        #
        # colorNode.SetHideFromEditors(False)
        # slicer.mrmlScene.AddNode(colorNode)
        #
        # colorMap = colorNode.GetColorTransferFunction()
        # colorMap.RemoveAllPoints()
        # colorMap.DeepCopy(ctf)

        # # Add an empty displayable node (you can only show a color legend if it belongs to a displayable node)
        # displayableNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode", volumeName + "_colorbar")
        # displayableNode.CreateDefaultDisplayNodes()
        # displayNode = displayableNode.GetDisplayNode()
        # displayNode.AutoScalarRangeOff()
        # displayNode.SetScalarRange(0.1 * array_max, array_max)

        # # Display color legend
        # displayNode.SetAndObserveColorNodeID(colorNode.GetID())
        # colorLegendDisplayNode = slicer.modules.colors.logic().AddDefaultColorLegendDisplayNode(displayableNode)
        # colorLegendDisplayNode.SetLabelFormat("%2.2f")
        # colorLegendDisplayNode.SetTitleText(" ")
        # colorLegendDisplayNode.SetNumberOfLabels(5)
        # colorLegendDisplayNode.SetPosition(0.97, 0.5)
        # colorLegendDisplayNode.SetSize(0.06, 0.4)
        #
        # TextProperty = colorLegendDisplayNode.GetLabelTextProperty()
        # TextProperty.SetColor([0.0, 0.0, 0.0])
        # TextProperty.SetFontFamilyToArial()
        
        print(f"Completed showVolumeRendering for volume: {volumeNode.GetName() if volumeNode else 'unknown'}")