import os
import vtk, qt, ctk, slicer, sitkUtils
from slicer.ScriptedLoadableModule import *
import numpy as np
from vtk.util.numpy_support import vtk_to_numpy
from vtk.util.numpy_support import numpy_to_vtk
import SimpleITK as sitk
import time
import timeit
import csv
from datetime import datetime
import json


def load_env_file(env_file=None):
    """
    Load environment variables from a .env file.
    Looks for TMSCOM.env in common locations.
    """
    if env_file is None:
        # Try to find TMSCOM.env in common locations
        possible_paths = [
            '/root/TMSCOM.env',
            '/app/TMSCOM.env',
            '/workspace/TMSCOM.env',
            os.path.expanduser('~/TMSCOM.env'),
            './TMSCOM.env',
            '../../../TMSCOM.env',
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                env_file = path
                break
    
    if env_file and os.path.exists(env_file):
        try:
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip()
            print(f"Loaded environment from {env_file}")
            return True
        except Exception as e:
            print(f"Warning: Could not load {env_file}: {e}")
    
    return False


# Load environment file at import time
load_env_file()


class Mapper:
    def __init__(self, config=None):
        self.config = config
        print("Mapper class initialized")

    @staticmethod
    def record_simulation_event(matrix_4x4, event_type, csv_path=None):
        """
        Record simulation start/end events.
        Uses file locking and atomic operations to prevent race conditions.
        """
        import fcntl  # For file locking (Unix only)
        
        try:
            if csv_path is None:
                csv_path = os.environ.get('RESULTS_CSV_PATH', '/app/evaluations/results.csv')
            
            csv_dir = os.path.dirname(csv_path)
            if csv_dir and not os.path.exists(csv_dir):
                os.makedirs(csv_dir, mode=0o777, exist_ok=True)
            
            timestamp = datetime.now().isoformat()
            matrix_values = [matrix_4x4.GetElement(i, j) for i in range(4) for j in range(4)]
            matrix_str = ";".join(f"{v:.10f}" for v in matrix_values)
            
            file_exists = os.path.exists(csv_path) and os.path.getsize(csv_path) > 0
            
            if event_type == "start":
                # Use append mode with locking
                row_data = {
                    'timestamp': timestamp,
                    'start_time': timestamp,
                    'end_time': '',
                    'start_matrix': matrix_str,
                    'end_matrix': '',
                    'execution_time_sec': ''
                }
                
                with open(csv_path, 'a', newline='', encoding='utf-8') as f:
                    # Get exclusive lock
                    try:
                        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                    except:
                        pass  # Continue without lock if not available
                    
                    # Detect fieldnames from existing file
                    if file_exists:
                        with open(csv_path, 'r', encoding='utf-8') as rf:
                            reader = csv.DictReader(rf)
                            fieldnames = reader.fieldnames or list(row_data.keys())
                    else:
                        fieldnames = list(row_data.keys())
                    
                    writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
                    if not file_exists:
                        writer.writeheader()
                    writer.writerow(row_data)
                    
                    try:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                    except:
                        pass
                
                print(f"✓ Recorded START at {timestamp}")
                
            elif event_type == "end":
                if not file_exists:
                    print("Warning: CSV doesn't exist for end event")
                    return
                
                # Use a lock file to coordinate with update.py
                lock_path = csv_path + '.mapper.lock'
                max_retries = 10
                retry_delay = 0.1
                
                for attempt in range(max_retries):
                    try:
                        # Try to acquire lock
                        with open(lock_path, 'x') as lock_f:
                            lock_f.write('mapper')
                            
                            # Read current state
                            with open(csv_path, 'r', newline='', encoding='utf-8') as f:
                                reader = csv.DictReader(f)
                                fieldnames = reader.fieldnames or []
                                rows = list(reader)
                            
                            if not rows:
                                os.remove(lock_path)
                                return
                            
                            # Find most recent incomplete row
                            target_idx = None
                            for idx, row in enumerate(reversed(rows)):
                                if not row.get('end_time'):
                                    target_idx = len(rows) - 1 - idx
                                    break
                            
                            if target_idx is None:
                                os.remove(lock_path)
                                return
                            
                            # Update the row - preserve ALL existing fields
                            rows[target_idx]['end_time'] = timestamp
                            rows[target_idx]['end_matrix'] = matrix_str
                            
                            try:
                                start_dt = datetime.fromisoformat(rows[target_idx]['start_time'])
                                end_dt = datetime.fromisoformat(timestamp)
                                rows[target_idx]['execution_time_sec'] = f"{(end_dt - start_dt).total_seconds():.3f}"
                            except:
                                rows[target_idx]['execution_time_sec'] = "0.000"
                            
                            # Ensure all fieldnames are preserved
                            for row in rows:
                                for fn in fieldnames:
                                    if fn not in row:
                                        row[fn] = ''
                            
                            # Write back with ALL fieldnames
                            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                                writer = csv.DictWriter(f, fieldnames=fieldnames)
                                writer.writeheader()
                                writer.writerows(rows)
                            
                            os.remove(lock_path)
                            print(f"✓ Recorded END at {timestamp}, duration: {rows[target_idx]['execution_time_sec']}s")
                            break  # Success!
                            
                    except FileExistsError:
                        # Lock held by update.py, wait and retry
                        time.sleep(retry_delay)
                        continue
                    except Exception as e:
                        print(f"  Attempt {attempt+1} failed: {e}")
                        time.sleep(retry_delay)
                        try:
                            os.remove(lock_path)
                        except:
                            pass
            
            try:
                os.chmod(csv_path, 0o666)
                if csv_dir:
                    os.chmod(csv_dir, 0o777)
            except:
                pass
                
        except Exception as e:
            print(f"✗ Error recording {event_type} event: {e}")
            import traceback
            traceback.print_exc()

    @classmethod
    def map(cls, loader, time=True):
        print("Starting map method")
        
        matrixFromFid = vtk.vtkMatrix4x4()
        loader.markupsPlaneNode.GetObjectToWorldMatrix(matrixFromFid)
        print("Retrieved object-to-world matrix from markups plane node")
        
        # Record simulation start event
        cls.record_simulation_event(matrixFromFid, "start")
        
        loader.transformNode.SetMatrixTransformToParent(matrixFromFid)
        print("Set matrix transform to parent")
        
        loader.transformNode.UpdateScene(slicer.mrmlScene)
        print("Updated scene with transform node")

        # Update matrix text label in Widget:
        matrixText = ""
        for i in range(3):
            for j in range(4):
                value = matrixFromFid.GetElement(i, j)
                matrixText += "{:.3f} ".format(value)
            matrixText += "\n"
        slicer.modules.SlicerTMSWidget.matrixTextLabel.setText(matrixText)
        print("Updated matrix text label in widget")

        if time:
            start = timeit.default_timer()
            print("Started timer for performance measurement")

        # the update transform based on the old transfrom
        # rotate the scalar magnetic field (magnorm)

        # if loader.showMag:  #only show scalar magnetic (magnorm) field
        #     matrix_current = vtk.vtkMatrix4x4()
        #     matrix_current_inv = vtk.vtkMatrix4x4()
        #     loader.magnormNode.GetIJKToRASMatrix(matrix_current)
        #     matrix_current_inv.Invert(matrix_current, matrix_current_inv)
        #     matrix_update1 = vtk.vtkMatrix4x4()
        #     matrix_update1.Multiply4x4(loader.coilDefaultMatrix, matrix_current_inv, matrix_update1)
        #     matrix_update2 = vtk.vtkMatrix4x4()
        #     matrix_update2.Multiply4x4(matrixFromFid, matrix_update1, matrix_update2)
        #     # loader.efieldNode.Copy(loader.magNode)
        #     loader.magnormNode.ApplyTransformMatrix(matrix_update2)
        #     Mapper.mapElectricfieldToMesh(loader.magnormNode, loader.modelNode)

        # else:  #predict the E-field and show the scalar E-field

        DataVec = loader.magfieldGTNode.GetTransformFromParent().GetDisplacementGrid()
        print("Retrieved displacement grid from magnetic field ground truth node")
        
        DataVec.SetOrigin(0, 0, 0)
        DataVec.SetSpacing(1, 1, 1)
        print("Set origin and spacing for displacement grid")


        matrix_current = vtk.vtkMatrix4x4() # current transform of the magnetic vector field
        matrix_current.Multiply4x4(matrixFromFid, loader.coilDefaultMatrix, matrix_current)
        print("Computed current transform matrix")

        matrix_current_inv = vtk.vtkMatrix4x4()
        matrix_current_inv.Invert(matrix_current,matrix_current_inv)
        print("Computed inverse of current transform matrix")
        
        combined_tfm = vtk.vtkMatrix4x4()

        matrix_ref = vtk.vtkMatrix4x4()
        loader.conductivityNode.GetIJKToRASMatrix(matrix_ref)
        print("Retrieved IJK to RAS matrix from conductivity node")
        
        img_ref = loader.conductivityNode.GetImageData()
        print("Retrieved image data from conductivity node")

        matrix_ref.Multiply4x4(matrix_current_inv, matrix_ref, combined_tfm)
        print("Computed combined transformation matrix")


        reslice = vtk.vtkImageReslice()
        reslice.SetInputData(DataVec)
        reslice.SetInformationInput(img_ref)
        reslice.SetInterpolationModeToLinear()
        reslice.SetResliceAxes(combined_tfm)
        reslice.TransformInputSamplingOff()
        reslice.Update()
        DataOut = reslice.GetOutput()
        print("Completed image reslicing operation")

        xyz = DataOut.GetDimensions()
        print(f"Resliced data dimensions: {xyz}")
        
        # # rotate DataOut vectors
        DataOut_np = vtk_to_numpy(DataOut.GetPointData().GetScalars())
        print("Converted VTK data to numpy array")
        
        # # transposed of the rotation matrix
        RotMat_transp = np.array([[matrixFromFid.GetElement(0,0), matrixFromFid.GetElement(1,0),  matrixFromFid.GetElement(2,0)],
                                   [matrixFromFid.GetElement(0,1), matrixFromFid.GetElement(1,1),  matrixFromFid.GetElement(2,1)],
                                   [matrixFromFid.GetElement(0,2), matrixFromFid.GetElement(1,2),  matrixFromFid.GetElement(2,2)]])  # FIXED: Changed [0,1] to [0,2] in last row
        
        print("Created rotation matrix transpose")
        
        # # rotate the vector field
        DataOut_np_rot = np.matmul(DataOut_np, RotMat_transp)
        print("Applied rotation to vector field data")
        
        # # reshape the numpy array
        DataOut_np_rot = np.reshape(DataOut_np_rot,(xyz[0], xyz[1], xyz[2], 3))
        print(f"Reshaped numpy array to shape: {DataOut_np_rot.shape}")

        VTK_array = numpy_to_vtk(DataOut_np_rot.ravel(), deep=True, array_type=vtk.VTK_DOUBLE)
        print("Converted numpy array back to VTK array")
        
        DataOut.GetPointData().SetScalars(VTK_array)
        DataOut.GetPointData().GetScalars().SetNumberOfComponents(3)
        print("Set scalar data on output data")

        loader.magfieldNode.SetAndObserveImageData(DataOut)
        print("Set image data on magnetic field node")
    
        ## pub here
        # Get the transform node that the magfieldNode is nested under
        loader.magfieldNode.SetAndObserveImageData(DataOut)
        print("Set image data on magnetic field node")

        ## ROS publish
        if loader.pubTransform is not None:
            try:
                transformMatrix = vtk.vtkMatrix4x4()
                loader.transformNode.GetMatrixTransformToWorld(transformMatrix)
                
                # Get the blank message from the publisher and populate it
                msg = loader.pubTransform.GetBlankMessage()
                # Copy the transform data to the message
                for i in range(4):
                    for j in range(4):
                        msg.SetElement(i, j, transformMatrix.GetElement(i, j))
                
                loader.pubTransform.Publish(msg)
                print("Published transform to ROS")
            except Exception as e:
                print(f"Error publishing transform: {e}") 

        ## IGTL push
        loader.IGTLNode.PushNode(loader.magfieldNode)
        print("Pushed magnetic field node to IGTL")
        # transformNodeID = loader.magfieldNode.GetTransformNodeID()

        # if not transformNodeID:
        #     print("No transform node associated with magfieldNode — skipping publish")
        # else:
        #     transformNode = slicer.mrmlScene.GetNodeByID(transformNodeID)
            
        #     if transformNode is None:
        #         print("Transform node ID found but node not in scene")
        #     else:
        #         loader.magfieldNode.transformMatrix = vtk.vtkMatrix4x4()
        #         transformNode.GetMatrixTransformToWorld(loader.magfieldNode.transformMatrix)
        #         loader.pubTransform.Publish(loader.magfieldNode.transformMatrix)

        #         loader.IGTLNode.PushNode(loader.magfieldNode)
        #         print("Pushed magnetic field node to IGTL node")


        # time in seconds:
        if time:
            stop = timeit.default_timer()
            execution_time = stop - start
            # print("Resampling + Mapping Executed in " + str(execution_time) + " seconds.")
            print(f"Resampling + Mapping executed in {execution_time} seconds")
        
        # # Record simulation end event
        # finalMatrix = vtk.vtkMatrix4x4()
        # loader.transformNode.GetMatrixTransformToParent(finalMatrix)
        # cls.record_simulation_event(finalMatrix, "end")
            
        print("Completed map method")

    @staticmethod
    def mapElectricfieldToMesh(scalarNode, brainNode):
        print(f"Starting mapElectricfieldToMesh for {brainNode.GetName() if brainNode else 'unknown node'}")
        print(f"Node type: {brainNode.GetClassName()}")
        
        # Check if this is a fiber bundle node
        if brainNode.GetClassName() == 'vtkMRMLFiberBundleNode':
            print("Skipping electric field mapping for fiber bundle node - not supported")
            return
            
        # get the scalar range from image scalars
        rng = scalarNode.GetImageData().GetScalarRange()
        fMin = rng[0]
        fMax = rng[1]
        print(f"Scalar range: [{fMin}, {fMax}]")

        # Transform the model into the volume's IJK space
        modelTransformerRasToIjk = vtk.vtkTransformFilter()
        transformRasToIjk = vtk.vtkTransform()
        m = vtk.vtkMatrix4x4()
        scalarNode.GetRASToIJKMatrix(m)
        transformRasToIjk.SetMatrix(m)
        modelTransformerRasToIjk.SetTransform(transformRasToIjk)
        
        # Check if node has GetMeshConnection method (for ModelNodes)
        if hasattr(brainNode, 'GetMeshConnection'):
            modelTransformerRasToIjk.SetInputConnection(brainNode.GetMeshConnection())
        else:
            print(f"Node {brainNode.GetName()} doesn't have GetMeshConnection method, skipping")
            return
            
        print("Set up RAS to IJK transformation")

        probe = vtk.vtkProbeFilter()
        probe.SetSourceData(scalarNode.GetImageData())
        probe.SetInputConnection(modelTransformerRasToIjk.GetOutputPort())
        print("Set up probe filter")
        
        # transform model back to ras
        modelTransformerIjkToRas = vtk.vtkTransformFilter()
        modelTransformerIjkToRas.SetTransform(transformRasToIjk.GetInverse())
        modelTransformerIjkToRas.SetInputConnection(probe.GetOutputPort())
        modelTransformerIjkToRas.Update()
        print("Set up IJK to RAS transformation")

        brainNode.SetAndObserveMesh(modelTransformerIjkToRas.GetOutput())
        print("Set mesh on brain node")

        probedPointScalars = probe.GetOutput().GetPointData().GetScalars()
        print("Retrieved probed point scalars")

        normals = vtk.vtkPolyDataNormals()
        normals.SetInputConnection(probe.GetOutputPort())
        print("Set up poly data normals")

        # activate scalars - only if node has a display node
        if brainNode.GetDisplayNode():
            brainNode.GetDisplayNode().SetActiveScalarName('ImageScalars')
            print("Activated scalars on brain display node")
        else:
            print("No display node found for brain node")
        
        ### if fiber bundle, then scalars need to be set different:
        fibers = slicer.util.getNode('fibers')
        if fibers:
            fibers.GetDisplayNode().SetColorMode(fibers.GetDisplayNode().colorModeScalarData)
            fibers.GetDisplayNode().SetAndObserveColorNodeID(slicer.util.getNode('ColdToHotRainbow').GetID())
            # We only want to see the lines of the fibers first, not the tubes:
            fibers.GetTubeDisplayNode().SetVisibility(False)
            print("Configured fibers node display settings")
        else:
            print("Fibers node 'fibers' not found")

        ### Same for the downsampled fibers:
        fibers1 = slicer.util.getNode('FiberBundle')
        if fibers1:
            fibers1.GetDisplayNode().SetColorMode(fibers1.GetDisplayNode().colorModeScalarData)
            fibers1.GetDisplayNode().SetAndObserveColorNodeID(slicer.util.getNode('ColdToHotRainbow').GetID())
            # We only want to see the lines of the fibers first, not the tubes:
            fibers1.GetTubeDisplayNode().SetVisibility(False)
            print("Configured FiberBundle node display settings")
        else:
            print("FiberBundle node not found")

        # select color scheme for scalars
        colorNode = slicer.util.getNode('ColdToHotRainbow')
        if colorNode and brainNode.GetDisplayNode():
            brainNode.GetDisplayNode().SetAndObserveColorNodeID(colorNode.GetID())
            print("Set color node for brain scalars")
        else:
            print("ColdToHotRainbow color node not found or no display node")
            
        if brainNode.GetDisplayNode():
            brainNode.GetDisplayNode().ScalarVisibilityOn()
            brainNode.GetDisplayNode().SetScalarRange(fMin, fMax)
            print("Enabled scalar visibility and set scalar range")
        else:
            print("No display node to set scalar properties")

        # color legend for brain scalars:
        if brainNode.GetDisplayNode():
            try:
                colorLegendDisplayNode = slicer.modules.colors.logic().AddDefaultColorLegendDisplayNode(brainNode)
                colorLegendDisplayNode.SetTitleText("EVec")
                colorLegendDisplayNode.SetLabelFormat("%7.8f")
                print("Added color legend display node")
            except Exception as e:
                print(f"Could not add color legend: {e}")
        else:
            print("No display node for color legend")

        print(f"Completed mapElectricfieldToMesh for {brainNode.GetName() if brainNode else 'unknown node'}")



    @staticmethod
    def modifyIncomingImage(loader):
        print("Starting modifyIncomingImage method")
        
        matrix_ref = vtk.vtkMatrix4x4()
        loader.conductivityNode.GetIJKToRASMatrix(matrix_ref)
        print("Retrieved IJK to RAS matrix from conductivity node")
        
        loader.pyigtlNode.ApplyTransformMatrix(matrix_ref)
        print("Applied transform matrix to pyigtl node")

        # this part will need to be done with the resampling (it only maps the incoming pyigtl image to the brain):
        Mapper.mapElectricfieldToMesh(loader.pyigtlNode, loader.modelNode)
        print("Mapped electric field to model node")
        
        # Skip mapping to fiber node or handle differently
        # Mapper.mapElectricfieldToMesh(loader.pyigtlNode, loader.fiberNode)
        print("Skipping electric field mapping to fiber node - not supported for fiber bundle nodes")

        # Jump to maximum point of E field
        try:
            pyigtl_data_image = sitkUtils.PullVolumeFromSlicer(loader.pyigtlNode)
            print("Pulled volume from Slicer to SimpleITK image")
            
            pyigtl_data_array = sitk.GetArrayFromImage(pyigtl_data_image)
            print("Converted SimpleITK image to numpy array")

            max_idx = np.squeeze(np.where(pyigtl_data_array==pyigtl_data_array.max()))
            print(f"Found maximum value at index: {max_idx}")
            
            max_point = pyigtl_data_image.TransformIndexToPhysicalPoint([int(max_idx[2]), int(max_idx[1]), int(max_idx[0])])
            print(f"Maximum point in physical coordinates: {max_point}")
            
            max_point = np.array([-max_point[0], -max_point[1], max_point[2]]) #IJK to RAS
            print(f"Maximum point converted to RAS: {max_point}")

            slicer.vtkMRMLSliceNode.JumpAllSlices(slicer.mrmlScene, *max_point[0:3])
            print("Jumped all slices to maximum point")
        except Exception as e:
            print(f"Error jumping to max point: {e}")
        
        # print("Completed modifyIncomingImage method")
        try:
            pyigtl_data_image = sitkUtils.PullVolumeFromSlicer(loader.pyigtlNode)
            # ... existing code ...
            
            slicer.vtkMRMLSliceNode.JumpAllSlices(slicer.mrmlScene, *max_point[0:3])
            print("Jumped all slices to maximum point")
        except Exception as e:
            print(f"Error jumping to max point: {e}")
        
        # Record simulation end event HERE - after full processing is complete
        finalMatrix = vtk.vtkMatrix4x4()
        loader.transformNode.GetMatrixTransformToParent(finalMatrix)
        Mapper.record_simulation_event(finalMatrix, "end")
        
        print("Completed modifyIncomingImage method")