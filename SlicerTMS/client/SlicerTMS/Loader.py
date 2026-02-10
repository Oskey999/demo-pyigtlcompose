import os
import vtk, qt, ctk, slicer, sitkUtils
import SimpleITK as sitk
# from slicer.ScriptedLoadableModule import *
import numpy as np
import Rendering as ren
import Mapper as M


class Loader:

    def __init__(self, data_directory):
        print(f"Initializing Loader with data directory: {data_directory}")
        self.data_directory = data_directory
        self._graymatter_file = 'gm'
        # the gray matter file can either be .stl or .vtk format:
        brainModelFile_stl = os.path.join(str(self.data_directory), self._graymatter_file + '.stl')
        brainModelFile_vtk = os.path.join(str(self.data_directory), self._graymatter_file + '.vtk')

        if os.path.isfile(brainModelFile_stl):
            brainModelFile = brainModelFile_stl
            print(f"Found STL brain model file: {brainModelFile_stl}")
        elif os.path.isfile(brainModelFile_vtk):
            brainModelFile = brainModelFile_vtk
            print(f"Found VTK brain model file: {brainModelFile_vtk}")
        else:
            print("No brain model file found (neither .stl nor .vtk)")
            return
        self._graymatter_file = os.path.basename(brainModelFile)
        print(f"Brain model file set to: {self._graymatter_file}")

        self._fiber_file = 'fibers.vtk'
        self._coil_file = 'coil.stl'
        self._coil_scale = 3
        self._skin_file = 'skin.stl'
        self._magnorm_file = 'magnorm.nii.gz'
        self._magfield_file = 'magfield.nii.gz'
        self._conductivity_file = 'conductivity.nii.gz'
        print("File paths initialized")

        self.modelNode = None
        self.fiberNode = None
        self.coilNode = None
        self.skinNode = None
        self.markupsPlaneNode = None

        self.conductivityNode = None
        self.magfieldGTNode = None
        self.magfieldNode = None
        self.magnormNode = None
        self.efieldNode = None
        self.enormNode = None
        self.coilDefaultMatrix = vtk.vtkMatrix4x4()

        self.IGTLNode = None

        self.showMag = False #switch between magnetic and electric field for visualization
        print("Loader initialization completed")

    def callMapper(self, param1=None, param2=None):
        print("CallMapper method called")
        M.Mapper.map(self, time=True)

    def showFibers(self):
        print(f"showFibers method called with self value: {self}")
        fiberNode1 = slicer.util.getNode('fibers')
        print(f"Retrieved fibers node: {fiberNode1}")
        brainTransparentNode = slicer.util.getNode('brainTransparent')
        print(f"Retrieved brainTransparent node: {brainTransparentNode}")
        nodes = slicer.mrmlScene.GetNodesByName('FiberBundle')
        print(f"Found {nodes.GetNumberOfItems()} nodes named 'FiberBundle'")
        if self == 2:
            print("Show Fibers")
            if nodes.GetNumberOfItems() > 0:
                slicer.util.getNode('FiberBundle').SetDisplayVisibility(1)
                fiberNode1.SetDisplayVisibility(0)
                print("Set FiberBundle visible, original fibers hidden")
            else:
                fiberNode1.SetDisplayVisibility(1)
                print("Set original fibers visible")
        elif self == 0:
            print("Hide Fibers")
            if nodes.GetNumberOfItems() > 0:
                slicer.util.getNode('FiberBundle').SetDisplayVisibility(0)
                fiberNode1.SetDisplayVisibility(0)
                print("Set FiberBundle and fibers hidden")
            else:
                fiberNode1.SetDisplayVisibility(0)
                print("Set fibers hidden")


    def updateMatrix(self):
        print("updateMatrix method called")
        # Create a 4x4 matrix with the values entered by the user
        matrix = vtk.vtkMatrix4x4()
        for i in range(3):
            for j in range(3):
                value = float(self.matrixInputs[i][j].text.replace(',', '.'))
                matrix.SetElement(i, j, value)
        print("Created matrix from user input")
        
        # Set default values for the last row and last column of matrix
        matrix.SetElement(0, 3, 0.0)
        matrix.SetElement(1, 3, 0.0)
        matrix.SetElement(2, 3, 0.0)
        matrix.SetElement(3, 3, 1.0)
        print("Set default values for matrix")

        # Get the vtkMRMLMarkupsPlaneNode and update its matrix
        planeNode = slicer.util.getNode("vtkMRMLMarkupsPlaneNode1")
        if planeNode is not None:
            planeNode.ApplyTransformMatrix(matrix)
            print("Applied transform matrix to plane node")
            # planeNode.SetNthControlPointOrientationMatrix(0, matrix)
            # transform1 = vtk.vtkTransform()
            # transform1.SetMatrix(matrix)
            # # planeNode.SetMatrixTransformToParent(matrix)
            # tfN.SetAndObserveTransformToParent(transform1)
            planeNode.UpdateScene(slicer.mrmlScene)
            print("Updated scene with modified plane node")
        else:
            print("Plane node not found")


    def showMesh(self):
        print(f"showMesh method called with self value: {self}")
        brainTransparentNode = slicer.util.getNode('brainTransparent')
        print(f"Retrieved brainTransparent node: {brainTransparentNode}")
        fiberNode1 = slicer.util.getNode('fibers')
        print(f"Retrieved fibers node: {fiberNode1}")
        modelNode = slicer.util.getNode('gm')
        print(f"Retrieved model node (gm): {modelNode}")
        if self == 2:
            print("Show Brain Surface")
            modelNode.SetDisplayVisibility(1)
            fiberNode1.SetDisplayVisibility(0)
            brainTransparentNode.SetDisplayVisibility(0)
            print("Set brain surface visible, fibers and brain transparent hidden")
        elif self == 0:
            print("Hide Brain Surface")
            modelNode.SetDisplayVisibility(0)
            print("Set brain surface hidden")


    def showVolumeRendering(self):
        print(f"showVolumeRendering method called with self value: {self}")
        modelNode = slicer.util.getNode('gm')
        print(f"Retrieved model node (gm): {modelNode}")
        brainTransparentNode = slicer.util.getNode('brainTransparent')
        print(f"Retrieved brainTransparent node: {brainTransparentNode}")
        pyigtlNode = slicer.util.getNode('pyigtl_data')
        print(f"Retrieved pyigtl_data node: {pyigtlNode}")

        if self == 2:
            print("Show volume Rendering")
            modelNode.SetDisplayVisibility(0)
            brainTransparentNode.SetDisplayVisibility(1)
            pyigtlNode.SetDisplayVisibility(1)
            print("Set volume rendering components visibility")
            ren.Rendering.showVolumeRendering(pyigtlNode)
            print("Called Rendering.showVolumeRendering")

        elif self == 0:
            print("Hide Volume")
            brainTransparentNode.SetDisplayVisibility(0)
            pyigtlNode.SetDisplayVisibility(0)
            print("Set volume rendering components hidden")


    def newImage(self, caller, event):
        print('New CNN Image received via PyIgtl')
        M.Mapper.modifyIncomingImage(self)

#  this was @staticmethod before?
    @classmethod
    def loadExample(self, example_path):
        print(f"Starting loadExample with path: {example_path}")
        print('Your selected Example: ' + example_path)
        data_directory = os.path.join(os.path.dirname(slicer.modules.slicertms.path), '../', example_path)
        print(f"Data directory resolved to: {data_directory}")

        loader = Loader(data_directory)
        print("Loader instance created")

        # slicer.mrmlScene.Clear()

        #
        # 1. Brain:
        #
        brainModelFile = os.path.join( loader.data_directory, loader._graymatter_file )
        print(f"Loading brain model from: {brainModelFile}")
        loader.modelNode = slicer.modules.models.logic().AddModel(brainModelFile,
                                                                slicer.vtkMRMLStorageNode.CoordinateSystemRAS)
        print(f"Brain model loaded: {loader.modelNode}")

        loader.brainTransparentNode = slicer.modules.models.logic().AddModel(brainModelFile,
                                                                slicer.vtkMRMLStorageNode.CoordinateSystemRAS)
        loader.brainTransparentNode.SetName('brainTransparent')
        print("Created transparent brain model node")
        brainTransparentDisplayNode = loader.brainTransparentNode.GetDisplayNode()
        brainTransparentDisplayNode.SetOpacity(0.3)
        brainTransparentDisplayNode.SetColor(0.7, 0.7, 0.7)
        # brainTransparentDisplayNode.SetVisibility(False)
        loader.brainTransparentNode.SetDisplayVisibility(False)
        print("Configured transparent brain display settings")
        
        #
        # 2. Fibers:
        #

        fiberModelFile = os.path.join( loader.data_directory, loader._fiber_file )
        print(f"Loading fiber model from: {fiberModelFile}")
        # loader.fiberNode = slicer.modules.models.logic().AddModel(fiberModelFile,
                                                                # slicer.vtkMRMLStorageNode.CoordinateSystemRAS)
        # loader.fiberNode.SetDisplayVisibility(0)

        ############### Load fibers for ROI selection ################
        # fiberNode = slicer.util.getNode('fibers')
        # fiberBundleNode = slicer.vtkMRMLFiberBundleNode()
        # fiberBundleNode.SetAndObservePolyData(loader.fiberNode.GetPolyData())
        loader.fiberNode = slicer.util.loadFiberBundle(fiberModelFile)
        print(f"Fiber bundle loaded: {loader.fiberNode}")
        loader.fiberNode.GetTubeDisplayNode().SetVisibility(False)
        loader.fiberNode.SetDisplayVisibility(False)
        print("Configured fiber bundle display settings")



        ######### Downsampling of the tractography fibers first -- IF THE FILE IS LARGE e.g. full brain tractography #############
        loader.fibers_downsampled = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLFiberBundleNode', 'FiberBundle')
        print("Created downsampled fiber bundle node")
        # loader.fibers_downsampled.SetDisplayVisibility(False)
        loader.fibers_downsampled.GetTubeDisplayNode().SetVisibility(False)
        print("Configured downsampled fiber bundle display")
        slicer.modules.tractographydownsample.widgetRepresentation().activateWindow()
        print("Activated tractography downsampling widget")
        slicer.modules.TractographyDownsampleWidget.inputSelector.addEnabled = True
        slicer.modules.TractographyDownsampleWidget.inputSelector.setCurrentNode(slicer.util.getNode('fibers'))
        print("Set input selector to fibers node")
        slicer.modules.TractographyDownsampleWidget.outputSelector.addEnabled = True
        slicer.modules.TractographyDownsampleWidget.outputSelector.setCurrentNode(loader.fibers_downsampled)
        print("Set output selector to downsampled fibers node")
        slicer.modules.TractographyDownsampleWidget.fiberStepSizeWidget.setValue(5.00)
        slicer.modules.TractographyDownsampleWidget.fiberPercentageWidget.setValue(1.00)
        slicer.modules.TractographyDownsampleWidget.fiberMinimumPointsWidget.setValue(3)
        slicer.modules.TractographyDownsampleWidget.fiberMinimumLengthWidget.setValue(10.00)
        slicer.modules.TractographyDownsampleWidget.fiberMaximumLengthWidget.setValue(180.00)
        print("Set downsampling parameters")
        slicer.modules.TractographyDownsampleWidget.applyButton.enabled = True
        slicer.modules.TractographyDownsampleWidget.onApplyButton()
        print("Applied downsampling")

        # setting the downsampled fibers as new fibernode for further processing
        loader.fiberNode = slicer.util.getNode('FiberBundle')
        print(f"Set fiberNode to downsampled fiber bundle: {loader.fiberNode}")
        loader.fiberNode.GetDisplayNode().SetVisibility(False)
        print("Set fiber node visibility to False")

        #### Create ROI Node for Fibers ############
        loader.roi = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLAnnotationROINode', 'ROI')
        print("Created ROI node")
        # roi = vtk.vtkSlicerAnnotationsModuleMRML.vtkMRMLAnnotationROINode()
        # Set size of the ROI:
        slicer.util.getNode('ROI').SetRadiusXYZ(20.0, 20.0, 20.0)
        slicer.util.getNode('ROI').SetXYZ(0.0, 0.0, 30.0)
        print("Set ROI position and size")
        # slicer.util.getNode('ROI').GetDisplayNode().SetVisibility(False)
        slicer.util.getNode('ROI').SetDisplayVisibility(False)
        print("Set ROI visibility to False")

        ## FIBER SELECTION ########### this might need to be updated along with the slicer dmri module
        slicer.modules.tractographydisplay.widgetRepresentation().activateWindow()
        print("Activated tractography display widget")
        w = slicer.modules.tractographydisplay.widgetRepresentation()
        simpleDisplay = slicer.util.findChildren(w, text='Simple Display')[0]
        print("Found Simple Display widget")
        # w.setFiberBundleNode(slicer.util.getNode('fibers'))
        treeView = slicer.util.findChildren(simpleDisplay, name = "TractographyDisplayTreeView")[0]
        treeView.setCurrentNode(loader.fiberNode)
        print("Set current node in tractography tree view")
        # slicer.util.delayDisplay('update')
        ww = slicer.util.findChildren(w, className= "*ROI*")[0]
        ww.enabled
        combo = slicer.util.findChildren(ww, name = "ROIForFib*Selector")[0]
        combo.setCurrentNode(slicer.util.getNode('ROI'))
        print("Set ROI in ROI selector")
        wx = slicer.util.findChildren(w, name = "Positive*")[0] # This is the radiobutton for positive ROI
        if wx.checked == False:
            wx.click()
            print("Clicked positive ROI button")
        # ww.updateBundleFromSelection()

        # slicer.qSlicerTractographyDisplayModuleWidget().setFiberBundleNode(slicer.util.getNode('fibers'))
        # slicer.qSlicerTractographyDisplayModuleWidget().setPercentageOfFibersShown(0.01)
        # slicer.qSlicerTractographyEditorROIWidget().setAnnotationMRMLNodeForFiberSelection(slicer.util.getNode('ROI'))
        # slicer.qSlicerTractographyEditorROIWidget().setFiberBundleNode(slicer.util.getNode('fibers'))
        # slicer.qSlicerTractographyEditorROIWidget().positiveROISelection(1)
        # slicer.util.getNode('fibers').SetSelectWithAnnotation(1)
        ######## ALTERNATIVE FOR ACCESSING:
        # advancedDisplay = slicer.util.findChildren(text='Advanced Display')[0]
        # fiberDisplay = slicer.util.findChildren(text='Fiber Bundle Selection')[0]
        # simpleDisplay = slicer.util.findChildren(text='Simple Display')[0]
        # ss = slicer.util.findChildren(simpleDisplay, name="FiberBundleTableDisplay")[0]

        #
        # 3. Skin model:
        #
        skin = os.path.join( loader.data_directory, loader._skin_file )
        print(f"Loading skin model from: {skin}")
        loader.skinNode = slicer.modules.models.logic().AddModel(skin, slicer.vtkMRMLStorageNode.CoordinateSystemRAS)
        print(f"Skin model loaded: {loader.skinNode}")
        skinDisplayNode = loader.skinNode.GetDisplayNode()
        skinDisplayNode.SetColor(0.8, 0.8, 0.8)
        skinDisplayNode.SetOpacity(0.35)
        print("Configured skin display settings")


        #
        # 4. TMS coil:
        #
        coil = os.path.join( loader.data_directory, loader._coil_file )
        print(f"Loading coil model from: {coil}")
        
        loader.coilNode = slicer.modules.models.logic().AddModel(coil, slicer.vtkMRMLStorageNode.CoordinateSystemRAS)
        print(f"Coil model loaded: {loader.coilNode}")
        
        # Set transform on the coil and resize it:
        parentTransform = vtk.vtkTransform()
        parentTransform.Scale(loader._coil_scale, loader._coil_scale, loader._coil_scale)
        print(f"Created scaling transform with scale factor: {loader._coil_scale}")
        
        loader.coilNode.ApplyTransformMatrix(parentTransform.GetMatrix())
        print("Applied scaling transform to coil")

        # Add a plane to the scene
        markupsPlaneNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLMarkupsPlaneNode', 'Coil')
        print("Created markups plane node for coil")
        # markupsPlaneNode.SetOrigin([0, 0, 110])
        # markupsPlaneNode.SetOrigin([0, 0, 0])
        # markupsPlaneNode.SetNormalWorld([0, 0, -10])
        markupsPlaneNode.SetNormalWorld([0, 0, -1])
        markupsPlaneNode.SetAxes([.5, 0, 0], [0, .5, 0], [0, 0, .5])
        markupsPlaneNode.SetSize(10,10) # or SetPlaneBounds()
        print("Set plane properties (normal, axes, size)")
        markupsPlaneNode.GetMarkupsDisplayNode().SetHandlesInteractive(True)
        markupsPlaneNode.GetMarkupsDisplayNode().SetRotationHandleVisibility(1)
        markupsPlaneNode.GetMarkupsDisplayNode().SetTranslationHandleVisibility(1)
        markupsPlaneNode.GetMarkupsDisplayNode().SetOpacity(0.6)
        markupsPlaneNode.GetMarkupsDisplayNode().SetInteractionHandleScale(1.5)
        markupsPlaneNode.GetDisplayNode().SetSnapMode(slicer.vtkMRMLMarkupsDisplayNode.SnapModeToVisibleSurface)
        markupsPlaneNode.SetDisplayVisibility(1)
        print("Configured markups plane display settings")

        try:
            loader.transformNavigationNode = slicer.util.getNode("CoilToRefe")
            print("Found existing transform navigation node: CoilToRefe")
            markupsPlaneNode.SetOrigin([0, 0, 0])

        except:
            loader.transformNavigationNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLinearTransformNode", "NavigationTransform")
            print("Created new transform navigation node")
            markupsPlaneNode.SetOrigin([0, 0, 110])
        
        loader.markupsPlaneNode = markupsPlaneNode
        print(f"Set markupsPlaneNode: {loader.markupsPlaneNode}")

        loader.transformNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLinearTransformNode", "HandleTransform")
        print("Created handle transform node")

        # loader.transformNode = slicer.mrmlScene.AddNode(slicer.vtkMRMLLinearTransformNode())
        loader.coilNode.SetAndObserveTransformNodeID(loader.transformNode.GetID())
        print("Set transform node ID on coil node")
        loader.roi.SetAndObserveTransformNodeID(loader.transformNode.GetID())
        print("Set transform node ID on ROI node")
        
        loader.markupsPlaneNode.SetAndObserveTransformNodeID(loader.transformNavigationNode.GetID())
        print("Set transform node ID on markups plane node")

        #
        # 5. Other stuff
        #

        # load magnorm (used for tesing and visualization, not useful for predicting E-field)
        magnorm_path = os.path.join( loader.data_directory, loader._magnorm_file )
        print(f"Loading magnorm from: {magnorm_path}")
        loader.magnormNode = slicer.util.loadVolume(magnorm_path)
        loader.magnormNode.SetName('MagNorm')
        print(f"Magnorm volume loaded: {loader.magnormNode}")
        loader.magnormNode.GetIJKToRASMatrix(loader.coilDefaultMatrix)
        print("Retrieved IJK to RAS matrix for coil default")

        # load magvector as a GridTransformNode 
        # the grid transform node (GTNode) only provides the 4D vtkImageData in the original space
        magfield_path = os.path.join( loader.data_directory, loader._magfield_file )
        print(f"Loading magfield transform from: {magfield_path}")
        loader.magfieldGTNode  = slicer.util.loadTransform(magfield_path)
        print(f"Magfield grid transform loaded: {loader.magfieldGTNode}")

        # load conductivity
        conductivity_path = os.path.join( loader.data_directory, loader._conductivity_file )
        print(f"Loading conductivity from: {conductivity_path}")
        loader.conductivityNode = slicer.util.loadVolume(conductivity_path)
        print(f"Conductivity volume loaded: {loader.conductivityNode}")

        # creat magfield vector volumeNode for visualizing rotated RBG-coded magnetic vector field
        loader.magfieldNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLScalarVolumeNode')
        print("Created magnetic field scalar volume node")
        loader.magfieldNode.SetSpacing(loader.conductivityNode.GetSpacing())
        loader.magfieldNode.SetOrigin(loader.conductivityNode.GetOrigin())
        loader.magfieldNode.SetName('MagVec')
        print("Configured magnetic field node spacing, origin, and name")

        # create nodes for received E-field data from pyigtl 
        loader.efieldNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLVectorVolumeNode')
        print("Created E-field vector volume node")
        loader.efieldNode.Copy(loader.magfieldNode)
        loader.efieldNode.SetName('EVec')
        print("Copied properties from magfield to efield node")

        loader.enormNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLScalarVolumeNode')
        print("Created E-norm scalar volume node")
        loader.enormNode.Copy(loader.conductivityNode)
        loader.enormNode.SetName('ENorm')
        print("Copied properties from conductivity to enorm node")

       # IGTL connections
        # Get server host from environment variable
        tms_server_host = os.environ.get('TMS_SERVER_HOST', 'localhost')
        tms_server_port = int(os.environ.get('TMS_SERVER_PORT_1', '18944'))
        print(f"Server host from environment: {tms_server_host}:{tms_server_port}")

        # FIX: Create IGTL node if it's None
        if loader.IGTLNode is None:
            print("Creating IGTL connector node since it's None")
            loader.IGTLNode = slicer.vtkMRMLIGTLConnectorNode()
            slicer.mrmlScene.AddNode(loader.IGTLNode)
            loader.IGTLNode.SetName('DataConnector')
            print(f"Created IGTL node: {loader.IGTLNode}")
        else:
            print(f"IGTL node already exists: {loader.IGTLNode}")

        loader.IGTLNode.SetTypeClient(tms_server_host, tms_server_port)
        print(f'Connecting to TMS server at {tms_server_host}:{tms_server_port}')
        slicer.mrmlScene.AddNode(loader.IGTLNode)
        # node should be visible in OpenIGTLinkIF module under connectors
        loader.IGTLNode.SetName('Connector1')
        print(f"Set IGTL node name to: {loader.IGTLNode.GetName()}")

        # add command line stuff here
        # loader.IGTLNode.SetTypeClient('localhost', 18944)  # COMMENTED OUT - uses Docker env vars instead
        print("Set IGTL node type to client using environment variables")
        
        # this will activate the the status of the connection:
        loader.IGTLNode.Start()
        print("Started IGTL node")
        loader.IGTLNode.RegisterIncomingMRMLNode(loader.efieldNode)
        print("Registered E-field node as incoming MRML node")
        loader.IGTLNode.RegisterOutgoingMRMLNode(loader.magfieldNode)
        print("Registered magnetic field node as outgoing MRML node")
        loader.IGTLNode.PushOnConnect()
        print("Set IGTL node to push on connect")
        print('OpenIGTLink Connector created! \n Check IGT > OpenIGTLinkIF and start external pyigtl server.')

        # observer for the icoming IGTL image data
        loader.pyigtlNode = slicer.util.loadVolume( os.path.join( loader.data_directory, loader._conductivity_file ) )
        # loader.pyigtlNode.Copy(loader.enormNode)
        loader.pyigtlNode.SetName('pyigtl_data')
        print(f"Created pyigtl data node: {loader.pyigtlNode}")

        # Display setting
        # conductivityDisplayNode = loader.conductivityNode.GetDisplayNode()
        # conductivityDisplayNode.SetAndObserveColorNodeID('vtkMRMLColorTableNodeGrey')
        # conductivityDisplayNode.SetVisibility2D(True)

        pyigtlDisplayNode = loader.pyigtlNode.GetDisplayNode()
        pyigtlDisplayNode.AutoWindowLevelOff()
        pyigtlDisplayNode.SetWindowLevelMinMax(0.0, 1.0)
        pyigtlDisplayNode.SetLowerThreshold(0)
        pyigtlDisplayNode.SetUpperThreshold(1)
        pyigtlDisplayNode.SetAndObserveColorNodeID('vtkMRMLColorTableNodeFileColdToHotRainbow.txt')
        print("Configured pyigtl display settings")

        slicer.util.setSliceViewerLayers(background=loader.conductivityNode)
        slicer.util.setSliceViewerLayers(foreground=loader.pyigtlNode)
        slicer.util.setSliceViewerLayers(foregroundOpacity=0.6)
        print("Configured slice viewer layers")
        slicer.app.processEvents()  # Dynamic updating scene
        print("Processed application events")

        observationTag = loader.pyigtlNode.AddObserver(slicer.vtkMRMLScalarVolumeNode.ImageDataModifiedEvent, loader.newImage)
        print(f"Added observer for pyigtl node image data modification: tag {observationTag}")

        # # call one time
        loader.callMapper()
        print("Called mapper for initial setup")

        # # interaction hookup
        loader.markupsPlaneNode.AddObserver(slicer.vtkMRMLMarkupsNode.PointModifiedEvent, loader.callMapper)
        print("Added observer for markups plane node point modification")
        loader.transformNavigationNode.AddObserver(slicer.vtkMRMLTransformableNode.TransformModifiedEvent, loader.callMapper)
        print("Added observer for transform navigation node modification")
        #slicer.mrmlScene.AddObserver(slicer.vtkMRMLScene.NodeAddedEvent, loader.onNodeRcvd)

        print("loadExample method completed successfully")
        return loader