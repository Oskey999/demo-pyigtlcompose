import os
import vtk, qt, ctk, slicer, sitkUtils
import SimpleITK as sitk
# from slicer.ScriptedLoadableModule import *
import numpy as np
import Rendering as ren
import Mapper as M
from tms_env import get_tms_value

# ADDED: Simple chunker for receiving network data
from simple_chunker import SimpleReceiver



class Loader:

    def __init__(self, data_directory):
        self.data_directory = data_directory
        self._graymatter_file = 'gm'
        # the gray matter file can either be .stl or .vtk format:
        brainModelFile_stl = os.path.join(str(self.data_directory), self._graymatter_file + '.stl')
        brainModelFile_vtk = os.path.join(str(self.data_directory), self._graymatter_file + '.vtk')

        if os.path.isfile(brainModelFile_stl):
            brainModelFile = brainModelFile_stl
        elif os.path.isfile(brainModelFile_vtk):
            brainModelFile = brainModelFile_vtk
        else:
            return
        self._graymatter_file = os.path.basename(brainModelFile)

        self._fiber_file = 'fibers.vtk'
        self._coil_file = 'coil.stl'
        self._coil_scale = 3
        self._skin_file = 'skin.stl'
        self._magnorm_file = 'magnorm.nii.gz'
        self._magfield_file = 'magfield.nii.gz'
        self._conductivity_file = 'conductivity.nii.gz'

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
        
        # ADDED: Initialize chunk receiver
        self.receiver = SimpleReceiver()

    def callMapper(self, param1=None, param2=None):
        M.Mapper.map(self, time=True)

    def showFibers(self):
        fiberNode1 = slicer.util.getNode('fibers')
        brainTransparentNode = slicer.util.getNode('brainTransparent')
        nodes = slicer.mrmlScene.GetNodesByName('FiberBundle')
        if self == 2:
            print("Show Fibers")
            if nodes.GetNumberOfItems() > 0:
                slicer.util.getNode('FiberBundle').SetDisplayVisibility(1)
                fiberNode1.SetDisplayVisibility(0)
            else:
                fiberNode1.SetDisplayVisibility(1)
        elif self == 0:
            print("Hide Fibers")
            if nodes.GetNumberOfItems() > 0:
                slicer.util.getNode('FiberBundle').SetDisplayVisibility(0)
                fiberNode1.SetDisplayVisibility(0)
            else:
                fiberNode1.SetDisplayVisibility(0)


    def updateMatrix(self):
        # Create a 4x4 matrix with the values entered by the user
        matrix = vtk.vtkMatrix4x4()
        for i in range(3):
            for j in range(3):
                value = float(self.matrixInputs[i][j].text.replace(',', '.'))
                matrix.SetElement(i, j, value)
            # Set default values for the last row and last column of matrix
        matrix.SetElement(0, 3, 0.0)
        matrix.SetElement(1, 3, 0.0)
        matrix.SetElement(2, 3, 0.0)
        matrix.SetElement(3, 3, 1.0)


        # Get the vtkMRMLMarkupsPlaneNode and update its matrix
        planeNode = slicer.util.getNode("vtkMRMLMarkupsPlaneNode1")
        if planeNode is not None:
            planeNode.ApplyTransformMatrix(matrix)
            # planeNode.SetNthControlPointOrientationMatrix(0, matrix)
            # transform1 = vtk.vtkTransform()
            # transform1.SetMatrix(matrix)
            # # planeNode.SetMatrixTransformToParent(matrix)
            # tfN.SetAndObserveTransformToParent(transform1)
            planeNode.UpdateScene(slicer.mrmlScene)


    def showMesh(self):
        brainTransparentNode = slicer.util.getNode('brainTransparent')
        fiberNode1 = slicer.util.getNode('fibers')
        modelNode = slicer.util.getNode('gm')
        if self == 2:
            print("Show Brain Surface")
            modelNode.SetDisplayVisibility(1)
            fiberNode1.SetDisplayVisibility(0)
            brainTransparentNode.SetDisplayVisibility(0)
        elif self == 0:
            print("Hide Brain Surface")
            modelNode.SetDisplayVisibility(0)


    def showVolumeRendering(self):
        modelNode = slicer.util.getNode('gm')
        brainTransparentNode = slicer.util.getNode('brainTransparent')
        pyigtlNode = slicer.util.getNode('pyigtl_data')

        if self == 2:
            print("Show volume Rendering")
            modelNode.SetDisplayVisibility(0)
            brainTransparentNode.SetDisplayVisibility(1)
            pyigtlNode.SetDisplayVisibility(1)
            ren.Rendering.showVolumeRendering(pyigtlNode)

        elif self == 0:
            print("Hide Volume")
            brainTransparentNode.SetDisplayVisibility(0)
            pyigtlNode.SetDisplayVisibility(0)


    # MODIFIED: Handle chunked data reception
    def newImage(self, caller, event):
        node_name = caller.GetName()
        
        if node_name == 'pyigtl_meta':
            # Metadata chunk received
            print('[Loader] Received metadata')
            imageData = caller.GetImageData()
            if imageData:
                from vtk.util.numpy_support import vtk_to_numpy
                vtk_array = imageData.GetPointData().GetScalars()
                if vtk_array:
                    dims = imageData.GetDimensions()
                    meta_array = vtk_to_numpy(vtk_array).reshape(dims)
                    self.receiver.add_metadata(meta_array)
        
        elif node_name == 'pyigtl_chunk':
            # Data chunk received
            imageData = caller.GetImageData()
            if imageData:
                from vtk.util.numpy_support import vtk_to_numpy
                vtk_array = imageData.GetPointData().GetScalars()
                if vtk_array:
                    dims = imageData.GetDimensions()
                    chunk_array = vtk_to_numpy(vtk_array).reshape(dims)
                    self.receiver.add_chunk(chunk_array)
                    
                    # Check if complete
                    if self.receiver.is_complete():
                        print('[Loader] All chunks received, reassembling...')
                        result = self.receiver.get_result()
                        
                        if result is not None:
                            print('[Loader] Successfully reassembled, updating display...')
                            
                            # ADDED: Validate and clean the data before display
                            result = np.nan_to_num(result, nan=0.0, posinf=0.0, neginf=0.0)
                            result = np.abs(result)  # Ensure non-negative
                            
                            # Check data range
                            data_min = np.min(result)
                            data_max = np.max(result)
                            print(f'[Loader] Data range: [{data_min:.6e}, {data_max:.6e}]')
                            
                            # Normalize if needed (avoid division by zero)
                            if data_max > 0:
                                result = result / data_max
                            else:
                                print('[Loader] WARNING: All data is zero')
                            
                            # Update the pyigtl_data node
                            pyigtl_node = slicer.util.getNode('pyigtl_data')
                            
                            # Convert numpy to VTK
                            from vtk.util.numpy_support import numpy_to_vtk
                            vtk_data = vtk.vtkImageData()
                            vtk_data.SetDimensions(result.shape[2], result.shape[1], result.shape[0])
                            vtk_array_out = numpy_to_vtk(result.flatten(order='F'), deep=True)
                            vtk_data.GetPointData().SetScalars(vtk_array_out)
                            
                            # Update node
                            pyigtl_node.SetAndObserveImageData(vtk_data)
                            pyigtl_node.Modified()
                            
                            print('[Loader] pyigtl_data node updated successfully')
                            
                            # Process with mapper
                            try:
                                M.Mapper.modifyIncomingImage(self)
                            except Exception as e:
                                print(f'[Loader] Mapper error (this is OK if FiberBundle not created): {e}')
        
        elif node_name == 'pyigtl_data':
            # Legacy single-message mode (backward compatible)
            print('New CNN Image received via PyIgtl (legacy mode)')
            try:
                M.Mapper.modifyIncomingImage(self)
            except Exception as e:
                print(f'[Loader] Mapper error: {e}')

#  this was @staticmethod before?
    @classmethod
    def loadExample(self, example_path):

        print('Your selected Example: ' + example_path)
        data_directory = os.path.join(os.path.dirname(slicer.modules.slicertms.path), '../', example_path)

        loader = Loader(data_directory)

        # slicer.mrmlScene.Clear()

        #
        # 1. Brain:
        #
        brainModelFile = os.path.join( loader.data_directory, loader._graymatter_file )
        loader.modelNode = slicer.modules.models.logic().AddModel(brainModelFile,
                                                                slicer.vtkMRMLStorageNode.CoordinateSystemRAS)

        loader.brainTransparentNode = slicer.modules.models.logic().AddModel(brainModelFile,
                                                                slicer.vtkMRMLStorageNode.CoordinateSystemRAS)
        loader.brainTransparentNode.SetName('brainTransparent')
        brainTransparentDisplayNode = loader.brainTransparentNode.GetDisplayNode()
        brainTransparentDisplayNode.SetOpacity(0.3)
        brainTransparentDisplayNode.SetColor(0.7, 0.7, 0.7)
        # brainTransparentDisplayNode.SetVisibility(False)
        loader.brainTransparentNode.SetDisplayVisibility(False)
        #
        # 2. Fibers:
        #

        fiberModelFile = os.path.join( loader.data_directory, loader._fiber_file )
        # loader.fiberNode = slicer.modules.models.logic().AddModel(fiberModelFile,
                                                                # slicer.vtkMRMLStorageNode.CoordinateSystemRAS)
        # loader.fiberNode.SetDisplayVisibility(0)


        loader.fiberNode = slicer.util.loadFiberBundle(fiberModelFile)
        loader.fiberNode.SetName('fibers')
        # set visibilit to hide
        loader.fiberNode.SetDisplayVisibility(0)

        # create annotation ROI for selecting fibers
        # MODIFIED: Use MarkupsROI instead of deprecated AnnotationROI for Slicer 5.8.1+
        try:
            # Try new API first (Slicer 5.8+)
            loader.roi = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLMarkupsROINode', 'ROI')
            loader.roi.SetCenter(0, 0, 0)
            loader.roi.SetSize(60, 60, 60)  # Size is diameter, so 60 = radius of 30
        except:
            # Fallback to old API
            loader.roi = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLAnnotationROINode', 'ROI')
            loader.roi.SetXYZ(0, 0, 0)
            loader.roi.SetRadiusXYZ(30, 30, 30)
        
        loader.roi.SetDisplayVisibility(0)
        
        # MODIFIED: Use display node methods instead of deprecated fiber bundle methods
        fiberDisplayNode = loader.fiberNode.GetDisplayNode()
        if fiberDisplayNode:
            try:
                # Try setting ROI using display node (newer API)
                if hasattr(fiberDisplayNode, 'SetAndObserveROINodeID'):
                    fiberDisplayNode.SetAndObserveROINodeID(loader.roi.GetID())
            except:
                pass
        
        # Try old API if available
        if hasattr(loader.fiberNode, 'SelectWithAnnotationNodeOn'):
            loader.fiberNode.SelectWithAnnotationNodeOn()
            loader.fiberNode.SetAndObserveAnnotationNodeID(loader.roi.GetID())



        # MODIFIED: Handle tractography display for Slicer 5.8.1+
        fiberBundleCreated = False
        try:
            slicer.modules.tractographydisplay.widgetRepresentation().activateWindow()
            w = slicer.modules.tractographydisplay.widgetRepresentation()
            simpleDisplay = slicer.util.findChildren(w, text='Simple Display')[0]
            # w.setFiberBundleNode(slicer.util.getNode('fibers'))
            treeView = slicer.util.findChildren(simpleDisplay, name = "TractographyDisplayTreeView")[0]
            treeView.setCurrentNode(loader.fiberNode)
            # slicer.util.delayDisplay('update')
            ww = slicer.util.findChildren(w, className= "*ROI*")[0]
            ww.enabled
            combo = slicer.util.findChildren(ww, name = "ROIForFib*Selector")[0]
            combo.setCurrentNode(slicer.util.getNode('ROI'))
            wx = slicer.util.findChildren(w, name = "Positive*")[0] # This is the radiobutton for positive ROI
            if wx.checked == False:
                wx.click()
            
            # Check if FiberBundle was created
            nodes = slicer.mrmlScene.GetNodesByName('FiberBundle')
            if nodes.GetNumberOfItems() > 0:
                fiberBundleCreated = True
                print("FiberBundle node created successfully via widget")
        except Exception as e:
            print(f"Note: Tractography display widget setup skipped: {e}")
        
        # ADDED: Create FiberBundle manually if widget setup failed
        if not fiberBundleCreated:
            print("Creating FiberBundle node manually...")
            try:
                # Create a copy of the fiber node as FiberBundle for the Mapper
                loader.fiberBundleNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLFiberBundleNode', 'FiberBundle')
                
                # Copy the polydata from the original fiber node
                originalPolyData = loader.fiberNode.GetPolyData()
                if originalPolyData:
                    loader.fiberBundleNode.SetAndObservePolyData(originalPolyData)
                    loader.fiberBundleNode.SetDisplayVisibility(0)
                    
                    # Set up display node
                    displayNode = loader.fiberBundleNode.GetDisplayNode()
                    if displayNode:
                        # Copy display properties from original
                        origDisplayNode = loader.fiberNode.GetDisplayNode()
                        if origDisplayNode:
                            displayNode.Copy(origDisplayNode)
                    
                    print("FiberBundle node created manually")
                else:
                    print("Warning: Could not get polydata from fiber node")
            except Exception as e:
                print(f"Warning: Could not create FiberBundle manually: {e}")
                # Create a placeholder so Mapper doesn't crash
                try:
                    slicer.mrmlScene.AddNewNodeByClass('vtkMRMLModelNode', 'FiberBundle')
                    print("Created placeholder FiberBundle node")
                except:
                    pass

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
        loader.skinNode = slicer.modules.models.logic().AddModel(skin, slicer.vtkMRMLStorageNode.CoordinateSystemRAS)
        skinDisplayNode = loader.skinNode.GetDisplayNode()
        skinDisplayNode.SetColor(0.8, 0.8, 0.8)
        skinDisplayNode.SetOpacity(0.35)


        #
        # 4. TMS coil:
        #
        coil = os.path.join( loader.data_directory, loader._coil_file )
        
        loader.coilNode = slicer.modules.models.logic().AddModel(coil, slicer.vtkMRMLStorageNode.CoordinateSystemRAS)
        
        # Set transform on the coil and resize it:
        parentTransform = vtk.vtkTransform()
        parentTransform.Scale(loader._coil_scale, loader._coil_scale, loader._coil_scale)
        
        loader.coilNode.ApplyTransformMatrix(parentTransform.GetMatrix())

        # Add a plane to the scene
        markupsPlaneNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLMarkupsPlaneNode', 'Coil')
        # markupsPlaneNode.SetOrigin([0, 0, 110])
        # markupsPlaneNode.SetOrigin([0, 0, 0])
        # markupsPlaneNode.SetNormalWorld([0, 0, -10])
        markupsPlaneNode.SetNormalWorld([0, 0, -1])
        markupsPlaneNode.SetAxes([.5, 0, 0], [0, .5, 0], [0, 0, .5])
        markupsPlaneNode.SetSize(10,10) # or SetPlaneBounds()
        markupsPlaneNode.GetMarkupsDisplayNode().SetHandlesInteractive(True)
        markupsPlaneNode.GetMarkupsDisplayNode().SetRotationHandleVisibility(1)
        markupsPlaneNode.GetMarkupsDisplayNode().SetTranslationHandleVisibility(1)
        markupsPlaneNode.GetMarkupsDisplayNode().SetOpacity(0.6)
        markupsPlaneNode.GetMarkupsDisplayNode().SetInteractionHandleScale(1.5)
        markupsPlaneNode.GetDisplayNode().SetSnapMode(slicer.vtkMRMLMarkupsDisplayNode.SnapModeToVisibleSurface)
        markupsPlaneNode.SetDisplayVisibility(1)


        try:
            loader.transformNavigationNode = slicer.util.getNode("CoilToRefe")
            markupsPlaneNode.SetOrigin([0, 0, 0])

        except:
            loader.transformNavigationNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLinearTransformNode", "NavigationTransform")
            markupsPlaneNode.SetOrigin([0, 0, 110])
        
        loader.markupsPlaneNode = markupsPlaneNode

        loader.transformNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLinearTransformNode", "HandleTransform")

        # loader.transformNode = slicer.mrmlScene.AddNode(slicer.vtkMRMLLinearTransformNode())
        loader.coilNode.SetAndObserveTransformNodeID(loader.transformNode.GetID())
        loader.roi.SetAndObserveTransformNodeID(loader.transformNode.GetID())
        
        loader.markupsPlaneNode.SetAndObserveTransformNodeID(loader.transformNavigationNode.GetID())

        #
        # 5. Other stuff
        #

        # load magnorm (used for tesing and visualization, not useful for predicting E-field)
        loader.magnormNode = slicer.util.loadVolume( os.path.join( loader.data_directory, loader._magnorm_file ) )
        loader.magnormNode.SetName('MagNorm')
        loader.magnormNode.GetIJKToRASMatrix(loader.coilDefaultMatrix)


        # load magvector as a GridTransformNode 
        # the grid transform node (GTNode) only provides the 4D vtkImageData in the original space
        loader.magfieldGTNode  = slicer.util.loadTransform(os.path.join( loader.data_directory, loader._magfield_file ))

        # load conductivity
        loader.conductivityNode = slicer.util.loadVolume( os.path.join( loader.data_directory, loader._conductivity_file ) )

        # creat magfield vector volumeNode for visualizing rotated RBG-coded magnetic vector field
        loader.magfieldNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLScalarVolumeNode')
        loader.magfieldNode.SetSpacing(loader.conductivityNode.GetSpacing())
        loader.magfieldNode.SetOrigin(loader.conductivityNode.GetOrigin())
        loader.magfieldNode.SetName('MagVec')

        # create nodes for received E-field data from pyigtl 
        loader.efieldNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLVectorVolumeNode')
        loader.efieldNode.Copy(loader.magfieldNode)
        loader.efieldNode.SetName('EVec')

        loader.enormNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLScalarVolumeNode')
        loader.enormNode.Copy(loader.conductivityNode)
        loader.enormNode.SetName('ENorm')


        # IGTL connections
        # Get server host from environment variable
        tms_server_host = get_tms_value('TMS_SERVER_HOST', 'localhost')
        tms_server_port = int(get_tms_value('TMS_SERVER_PORT_1', '18944'))

        loader.IGTLNode = slicer.vtkMRMLIGTLConnectorNode()
        loader.IGTLNode.SetTypeClient(tms_server_host, tms_server_port)
        print(f'Connecting to TMS server at {tms_server_host}:{tms_server_port}')
        slicer.mrmlScene.AddNode(loader.IGTLNode)
        # node should be visible in OpenIGTLinkIF module under connectors
        loader.IGTLNode.SetName('Connector1')
        # this will activate the the status of the connection:
        loader.IGTLNode.Start()
        loader.IGTLNode.RegisterIncomingMRMLNode(loader.efieldNode)
        loader.IGTLNode.RegisterOutgoingMRMLNode(loader.magfieldNode)
        loader.IGTLNode.PushOnConnect()
        print('OpenIGTLink Connector created! \n Check IGT > OpenIGTLinkIF and start external pyigtl server.')

        # observer for the icoming IGTL image data
        loader.pyigtlNode = slicer.util.loadVolume( os.path.join( loader.data_directory, loader._conductivity_file ) )
        # loader.pyigtlNode.Copy(loader.enormNode)
        loader.pyigtlNode.SetName('pyigtl_data')
        
        # ADDED: Create nodes for chunked data reception
        loader.metaNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLScalarVolumeNode', 'pyigtl_meta')
        loader.IGTLNode.RegisterIncomingMRMLNode(loader.metaNode)
        
        loader.chunkNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLScalarVolumeNode', 'pyigtl_chunk')
        loader.IGTLNode.RegisterIncomingMRMLNode(loader.chunkNode)

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

        slicer.util.setSliceViewerLayers(background=loader.conductivityNode)
        slicer.util.setSliceViewerLayers(foreground=loader.pyigtlNode)
        slicer.util.setSliceViewerLayers(foregroundOpacity=0.6)
        slicer.app.processEvents()  # Dynamic updating scene

        # MODIFIED: Add observers for all node types
        observationTag = loader.pyigtlNode.AddObserver(slicer.vtkMRMLScalarVolumeNode.ImageDataModifiedEvent, loader.newImage)
        loader.metaNode.AddObserver(slicer.vtkMRMLScalarVolumeNode.ImageDataModifiedEvent, loader.newImage)
        loader.chunkNode.AddObserver(slicer.vtkMRMLScalarVolumeNode.ImageDataModifiedEvent, loader.newImage)


        # # call one time
        loader.callMapper()

        # # interaction hookup
        loader.markupsPlaneNode.AddObserver(slicer.vtkMRMLMarkupsNode.PointModifiedEvent, loader.callMapper)
        loader.transformNavigationNode.AddObserver(slicer.vtkMRMLTransformableNode.TransformModifiedEvent, loader.callMapper)
        #slicer.mrmlScene.AddObserver(slicer.vtkMRMLScene.NodeAddedEvent, loader.onNodeRcvd)

        return loader
