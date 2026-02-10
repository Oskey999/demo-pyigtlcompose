"""
============================
Tracked TMS nifti image data server
Receive dA/dt field from 3DSlicer, predict the E-field and send data back to 3DSlicer
============================
"""

import pyigtl  # pylint: disable=import-error
import os
import sys
import asyncio
os.environ['KMP_DUPLICATE_LIB_OK']='True'
from math import cos, sin, pi
from time import sleep
import numpy as np
import glob
import vtk
from vtk.util.numpy_support import vtk_to_numpy
import nibabel as nib
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
import torch.nn.parallel
import torch.optim as optim
from torch.optim import lr_scheduler
from collections import OrderedDict
from model import Modified3DUNet
from numpy import linalg as LA
import time
import asyncio


class ServerTMS():
    def __init__(self, f):
        self.setFile(f)
        self.stop_server = False
        self.current_example = f
        self.net = None
        self.cond_data = None
        self.xyz = None
        self.device = None

    def load_model_and_data(self, example_path):
        """Load CNN model and conductivity data for the specified example"""
        print(f'Loading model and data for example: {example_path}')
        
        script_path = os.path.dirname(os.path.abspath(__file__))
        
        # Update the file path
        self.setFile(example_path)
        
        model_path = os.path.join(script_path, str(example_path) + '/model.pth.tar')
        
        # load CNN model
        in_channels = 4
        out_channels = 3
        base_n_filter = 16

        # needs nvidia driver version 510 for cuda 11.6
        # To deactivate cuda (if no gpu available) plase uncomment to only use the cpu:
        # torch.cuda.is_available = lambda : False
        use_cuda = torch.cuda.is_available()
        print('Cuda available: ', use_cuda)

        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        print('Using device:', self.device)

        self.net = Modified3DUNet(in_channels, out_channels, base_n_filter)
        self.net = self.net.float()
        
        if torch.cuda.is_available():
            # loading all tensors onto GPU 0:
            checkpoint = torch.load(model_path, map_location='cuda:0')
        else:
            checkpoint = torch.load(model_path, map_location='cpu')

        new_state_dict = OrderedDict()
        for k, v in checkpoint['model_state_dict'].items():
            #name = k 
            name = k[7:] # remove `module.`
            new_state_dict[name] = v
        # load params
        self.net.load_state_dict(new_state_dict) 
        if torch.cuda.is_available():
            self.net = self.net.cuda() 
        else:
            pass

        # Load conductivity data
        ex_path = os.path.join(script_path, example_path)
        cond_path = os.path.join(ex_path, 'conductivity.nii.gz')
        print(f'Loading conductivity from: {cond_path}')
        cond = nib.load(cond_path)
        self.cond_data = cond.get_fdata()

        self.xyz = self.cond_data.shape
        self.cond_data = np.reshape(self.cond_data,([self.xyz[0], self.xyz[1], self.xyz[2], 1]))
        print('Image shape:', self.cond_data.shape)
        print('Model and data loaded successfully')

    async def run_server(self):
        print('Starting TMS server...')
        # servertms = pyigtl.OpenIGTLinkServer(port=18944, local_server=True)#False, iface=b"0.0.0.0")
        servertms = pyigtl.OpenIGTLinkServer(port=18944, local_server=False, iface="eth0".encode('utf-8'))
        print('TMS server started, waiting for connection...18944')
        # text_server = pyigtl.OpenIGTLinkServer(port=18945, local_server=True)#False, iface=b"0.0.0.0")
        text_server = pyigtl.OpenIGTLinkServer(port=18945, local_server=False, iface="eth0".encode('utf-8'))

        print('Text server started, waiting for connection... 18945')
        
        # Send initial ready message
        string_message = pyigtl.StringMessage("READY", device_name="TextMessage")
        print('Sending ready message to client...')
        text_server.send_message(string_message)
        print('Ready message sent to client')
        
        # Load initial model and data with default example
        self.load_model_and_data(self.current_example)
        
        timestep = 0

        while not self.stop_server:
            # Check for commands from SlicerTMS on text server
            text_messages = text_server.get_latest_messages()
            for msg in text_messages:
                if hasattr(msg, 'string'):
                    command = msg.string
                    print(f'Received command: {command}')
                    
                    # Check if it's a load example command
                    if command.startswith('LOAD_EXAMPLE:'):
                        example_name = command.split(':', 1)[1]
                        example_path = f'../data/{example_name}/'
                        print(f'Loading new example: {example_path}')
                        
                        try:
                            self.load_model_and_data(example_path)
                            self.current_example = example_path
                            
                            # Send confirmation back to SlicerTMS
                            confirm_msg = pyigtl.StringMessage(f"LOADED:{example_name}", device_name="TextMessage")
                            text_server.send_message(confirm_msg)
                            print(f'Example {example_name} loaded successfully')
                        except Exception as e:
                            error_msg = pyigtl.StringMessage(f"ERROR:{str(e)}", device_name="TextMessage")
                            text_server.send_message(error_msg)
                            print(f'Error loading example: {e}')
            
            # Process image data
            if not servertms.is_connected():
                # Wait for client to connect
                sleep(0.01)
                continue

            messages = servertms.get_latest_messages()
            if len(messages) > 0:
                print(f"got a message of length:{len(messages)}")
                
            for message in messages:
                if self.net is None or self.cond_data is None:
                    print("Model not loaded yet, skipping message")
                    continue
                    
                magvec = message.image
                magvec = np.transpose(magvec, axes=(2, 1, 0, 3))
                mask = np.concatenate((self.cond_data, self.cond_data, self.cond_data), axis=3)
                magvec = (mask>0)*magvec
                inputData = np.concatenate((self.cond_data, magvec*1000000), axis=3)


                inputData = inputData.transpose(3, 0, 1, 2)
                size = np.array([1, 4,  self.xyz[0], self.xyz[1], self.xyz[2]])
                inputData = np.reshape(inputData,size)
                inputData = np.double(inputData)

                #get start time to test CNN execution time
                st = time.time()
                inputData_gpu = torch.from_numpy(inputData).to(self.device)
                #measure end time of cnn execution
                
                outputData = self.net(inputData_gpu.float())
                outputData = outputData.cpu()
                outputData = outputData.detach().numpy()
                outputData = outputData.transpose(2, 3, 4, 1, 0)
                outputData = np.reshape(outputData,([self.xyz[0], self.xyz[1], self.xyz[2], 3]))
                outputData = np.transpose(outputData, axes=(2, 1, 0, 3))
                outputData = LA.norm(outputData, axis = 3)

                image_message = pyigtl.ImageMessage(outputData, device_name="pyigtl_data")
                servertms.send_message(image_message)

                et = time.time()

                # get the execution time
                elapsed_time = et - st
                # print('Execution time CNN:', elapsed_time, 'seconds')
                print(elapsed_time)

    async def stop(self):
        self.stop_server = True

    def setFile(self, f):
        self.file = f

    @staticmethod
    def getF(self):
        # sys.stdout = open("test.txt", "w")
        print('Selected Example:' + f + '\n' + 'Please start 3DSlicer')
        return f

# Default example if none specified
if len(sys.argv) > 1:
    f = '../data/' + str(sys.argv[1]) + '/'
else:
    f = '../data/Example1/'

async def main():
    tmsserver = ServerTMS(f)
    print(f'Starting with default example: {f}')
    print('Server will listen for example selection from SlicerTMS...')
    await tmsserver.run_server()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Server interrupted by user. Stopping...")