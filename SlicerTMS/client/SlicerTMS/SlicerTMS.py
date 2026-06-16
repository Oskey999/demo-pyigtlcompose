import os
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import sys
import Loader as L
import SlicerWebServer as W
from tms_env import get_tms_value
import traceback

DEBUG = True

def debug_print(*args, **kwargs):
    if DEBUG:
        print(f"[TMS-DEBUG] ", *args, **kwargs)
        sys.stdout.flush()

class SlicerTMS(ScriptedLoadableModule):
    def __init__(self, parent):
        debug_print("SlicerTMS.__init__ called")
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = "Slicer TMS Module"
        self.parent.categories = ["TMS"]
        self.parent.dependencies = []
        self.parent.contributors = [""]
        self.parent.helpText = ""
        self.parent.acknowledgementText = ""
        self.parent = parent
        debug_print("SlicerTMS.__init__ completed")

class SlicerTMSWidget(ScriptedLoadableModuleWidget):
    def __init__(self, parent=None):
        debug_print("SlicerTMSWidget.__init__ called")
        ScriptedLoadableModuleWidget.__init__(self, parent)
        self.guiMessages = True
        self.consoleMessages = True
        self.showGMButton = None
        self.selectedExample = None
        self.textConnector = None
        self.commandConnector = None
        self.loader = None
        debug_print("SlicerTMSWidget.__init__ completed")

    def setup(self):
        debug_print("=" * 80)
        debug_print("SlicerTMSWidget.setup called")
        debug_print("=" * 80)
        
        try:
            ScriptedLoadableModuleWidget.setup(self)
            debug_print("Parent setup completed")
            
            # Setup connection settings UI first
            self.setupConnectionSettings()
            
            # Initialize web server
            debug_print("-" * 40)
            debug_print("Initializing Web Server...")
            self.websv = W.SlicerWebServer(logMessage=self.logMessage)
            debug_print("Web server initialized")
            
            # Initialize with default connection
            self.initializeConnections()
            
            # Setup initial UI with example selector
            self.setupInitialUI()
            
            debug_print("=" * 80)
            debug_print("SlicerTMSWidget.setup completed successfully")
            debug_print("=" * 80)
            
        except Exception as e:
            debug_print(f"FATAL ERROR in setup: {e}")
            debug_print(traceback.format_exc())
            raise

    def setupConnectionSettings(self):
        """Setup the connection settings UI widget"""
        debug_print("-" * 40)
        debug_print("Setting up connection settings...")
        
        try:
            # Connection settings collapsible button
            self.connectionButton = ctk.ctkCollapsibleButton()
            self.connectionButton.text = "IGTL Connection Settings"
            self.layout.addWidget(self.connectionButton)
            self.connectionFormLayout = qt.QFormLayout(self.connectionButton)
            
            # Get current values from environment or use defaults
            default_host = get_tms_value('TMS_SERVER_HOST', 'localhost')
            default_port_text = get_tms_value('TMS_SERVER_PORT_2', '18945')
            default_port_data = get_tms_value('TMS_SERVER_PORT_1', '18944')
            
            # Host input
            self.hostLineEdit = qt.QLineEdit(default_host)
            self.hostLineEdit.toolTip = "Server IP address or hostname"
            self.connectionFormLayout.addRow("Server Host:", self.hostLineEdit)
            
            # Port for text/commands
            self.textPortLineEdit = qt.QLineEdit(str(default_port_text))
            self.textPortLineEdit.toolTip = "Port for text and command messages (default: 18945)"
            self.connectionFormLayout.addRow("Text/Command Port:", self.textPortLineEdit)
            
            # Port for data (images, transforms)
            self.dataPortLineEdit = qt.QLineEdit(str(default_port_data))
            self.dataPortLineEdit.toolTip = "Port for data transfer (default: 18944)"
            self.connectionFormLayout.addRow("Data Port:", self.dataPortLineEdit)
            
            # Connection status label
            self.connectionStatusLabel = qt.QLabel("Not connected")
            self.connectionStatusLabel.styleSheet = "QLabel { color: red; }"
            self.connectionFormLayout.addRow("Status:", self.connectionStatusLabel)
            
            # Buttons layout
            buttonsLayout = qt.QHBoxLayout()
            
            # Connect button
            self.connectButton = qt.QPushButton("Connect")
            self.connectButton.toolTip = "Establish connection with specified settings"
            self.connectButton.clicked.connect(self.reconnectWithNewSettings)
            buttonsLayout.addWidget(self.connectButton)
            
            # Disconnect button
            self.disconnectButton = qt.QPushButton("Disconnect")
            self.disconnectButton.toolTip = "Disconnect all connections"
            self.disconnectButton.clicked.connect(self.disconnectAll)
            buttonsLayout.addWidget(self.disconnectButton)
            
            # Refresh status button
            self.refreshStatusButton = qt.QPushButton("Refresh Status")
            self.refreshStatusButton.toolTip = "Check connection status"
            self.refreshStatusButton.clicked.connect(self.updateConnectionStatus)
            buttonsLayout.addWidget(self.refreshStatusButton)
            
            self.connectionFormLayout.addRow(buttonsLayout)
            
            debug_print("Connection settings UI created successfully")
            
        except Exception as e:
            debug_print(f"ERROR in setupConnectionSettings: {e}")
            debug_print(traceback.format_exc())

    def initializeConnections(self):
        """Initialize default connections"""
        debug_print("Initializing default connections...")
        
        try:
            # Get settings from UI or environment
            tms_server_host = self.hostLineEdit.text if hasattr(self, 'hostLineEdit') else get_tms_value('TMS_SERVER_HOST', 'localhost')
            text_port = int(self.textPortLineEdit.text if hasattr(self, 'textPortLineEdit') else get_tms_value('TMS_SERVER_PORT_2', '18945'))
            data_port = int(self.dataPortLineEdit.text if hasattr(self, 'dataPortLineEdit') else get_tms_value('TMS_SERVER_PORT_1', '18944'))
            
            # Setup text/command connector (port 18945)
            self.setupTextConnector(tms_server_host, text_port)
            
            # Setup data connector (port 18944) - this will be used by Loader
            self.setupDataConnector(tms_server_host, data_port)
            
            self.updateConnectionStatus()
            
        except Exception as e:
            debug_print(f"ERROR in initializeConnections: {e}")
            debug_print(traceback.format_exc())

    def setupTextConnector(self, host, port):
        """Setup the text and command connector"""
        debug_print(f"Setting up text connector on {host}:{port}")
        
        try:
            # Remove existing connectors if they exist
            if hasattr(self, 'IGTLNode') and self.IGTLNode:
                try:
                    self.IGTLNode.Stop()
                    slicer.mrmlScene.RemoveNode(self.IGTLNode)
                except:
                    pass
            
            if hasattr(self, 'IGTLCommandNode') and self.IGTLCommandNode:
                try:
                    self.IGTLCommandNode.Stop()
                    slicer.mrmlScene.RemoveNode(self.IGTLCommandNode)
                except:
                    pass
            
            # Create new text connector
            self.IGTLNode = slicer.vtkMRMLIGTLConnectorNode()
            slicer.mrmlScene.AddNode(self.IGTLNode)
            self.IGTLNode.SetName('TextConnector')
            self.IGTLNode.SetTypeClient(host, port)
            self.IGTLNode.Start()
            self.IGTLNode.PushOnConnect()
            debug_print(f"Text connector created and started")
            
            # Create command connector
            self.IGTLCommandNode = slicer.vtkMRMLIGTLConnectorNode()
            slicer.mrmlScene.AddNode(self.IGTLCommandNode)
            self.IGTLCommandNode.SetName('CommandConnector')
            self.IGTLCommandNode.SetTypeClient(host, port)
            self.IGTLCommandNode.Start()
            debug_print(f"Command connector created and started")
            
            # Setup text node
            self.textNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLTextNode', 'TextMessage')
            self.textNode.SetForceCreateStorageNode(True)
            observer = self.textNode.AddObserver(slicer.vtkMRMLTextNode.TextModifiedEvent, self.newText)
            debug_print(f"Text node created and observer added: {observer}")
            
            # Setup command text node
            self.commandTextNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLTextNode', 'CommandMessage')
            self.IGTLCommandNode.RegisterOutgoingMRMLNode(self.commandTextNode)
            debug_print(f"Command text node created")
            
            debug_print(f"Text connector established on {host}:{port}")
            
        except Exception as e:
            debug_print(f"ERROR in setupTextConnector: {e}")
            debug_print(traceback.format_exc())

    def setupDataConnector(self, host, port):
        """Setup the data connector for images and transforms"""
        debug_print(f"Setting up data connector on {host}:{port}")
        
        try:
            # Store data connection info for Loader to use
            self.dataConnectionInfo = {'host': host, 'port': port}
            
            # If Loader is already initialized, update its connection
            if hasattr(self, 'loader') and self.loader:
                self.updateLoaderConnection(host, port)
            
            debug_print(f"Data connector configured for {host}:{port}")
            
        except Exception as e:
            debug_print(f"ERROR in setupDataConnector: {e}")
            debug_print(traceback.format_exc())

    def updateLoaderConnection(self, host, port):
        """Update the connection in the Loader instance"""
        debug_print(f"Updating loader connection to {host}:{port}")
        
        try:
            if hasattr(self.loader, 'updateIGTLConnection'):
                self.loader.updateIGTLConnection(host, port)
                debug_print("Loader connection updated successfully")
            else:
                debug_print("Loader doesn't have updateIGTLConnection method")
        except Exception as e:
            debug_print(f"ERROR updating loader connection: {e}")
            debug_print(traceback.format_exc())

    def reconnectWithNewSettings(self):
        """Reconnect with new IP and port settings"""
        debug_print("Reconnecting with new settings...")
        
        try:
            # Get new settings
            host = self.hostLineEdit.text
            text_port = int(self.textPortLineEdit.text)
            data_port = int(self.dataPortLineEdit.text)
            
            debug_print(f"New settings - Host: {host}, Text Port: {text_port}, Data Port: {data_port}")
            
            # Validate ports
            if text_port < 1 or text_port > 65535:
                raise ValueError(f"Invalid text port number: {text_port}")
            if data_port < 1 or data_port > 65535:
                raise ValueError(f"Invalid data port number: {data_port}")
            
            # Reconnect text/command connector
            self.setupTextConnector(host, text_port)
            
            # Reconnect data connector
            self.setupDataConnector(host, data_port)
            
            # Update connection status
            self.updateConnectionStatus()
            
            # Log success
            self.logMessage(f"<font color='green'>✓ Connected to server at {host}:{text_port} (text) and {host}:{data_port} (data)</font>")
            
        except ValueError as ve:
            error_msg = f"Invalid port number: {str(ve)}"
            debug_print(f"ERROR: {error_msg}")
            self.logMessage(f"<font color='red'>✗ {error_msg}</font>")
            self.connectionStatusLabel.text = "Invalid port number"
            self.connectionStatusLabel.styleSheet = "QLabel { color: red; }"
            
        except Exception as e:
            error_msg = f"Failed to connect: {str(e)}"
            debug_print(f"ERROR in reconnectWithNewSettings: {e}")
            debug_print(traceback.format_exc())
            self.logMessage(f"<font color='red'>✗ {error_msg}</font>")
            self.connectionStatusLabel.text = "Connection failed"
            self.connectionStatusLabel.styleSheet = "QLabel { color: red; }"

    def disconnectAll(self):
        """Disconnect all connections"""
        debug_print("Disconnecting all connections...")
        
        try:
            # Disconnect text connector
            if hasattr(self, 'IGTLNode') and self.IGTLNode:
                self.IGTLNode.Stop()
                debug_print("Text connector stopped")
            
            # Disconnect command connector
            if hasattr(self, 'IGTLCommandNode') and self.IGTLCommandNode:
                self.IGTLCommandNode.Stop()
                debug_print("Command connector stopped")
            
            # Disconnect loader's data connector
            if hasattr(self, 'loader') and self.loader:
                if hasattr(self.loader, 'disconnectIGTL'):
                    self.loader.disconnectIGTL()
                    debug_print("Loader data connector disconnected")
            
            self.connectionStatusLabel.text = "Disconnected"
            self.connectionStatusLabel.styleSheet = "QLabel { color: red; }"
            self.logMessage("<font color='orange'>⚠ Disconnected from server</font>")
            
        except Exception as e:
            debug_print(f"ERROR in disconnectAll: {e}")
            debug_print(traceback.format_exc())

    def updateConnectionStatus(self):
        """Update the connection status display"""
        try:
            status_text = ""
            all_connected = True
            
            # Check text connector
            text_connected = False
            if hasattr(self, 'IGTLNode') and self.IGTLNode:
                if self.IGTLNode.GetState() == self.IGTLNode.StateConnected:
                    text_connected = True
                    status_text += "✓ Text: Connected "
                else:
                    all_connected = False
                    status_text += "✗ Text: Disconnected "
            else:
                all_connected = False
                status_text += "✗ Text: Not initialized "
            
            # Check command connector
            cmd_connected = False
            if hasattr(self, 'IGTLCommandNode') and self.IGTLCommandNode:
                if self.IGTLCommandNode.GetState() == self.IGTLCommandNode.StateConnected:
                    cmd_connected = True
                    status_text += "✓ Command: Connected "
                else:
                    all_connected = False
                    status_text += "✗ Command: Disconnected "
            else:
                all_connected = False
                status_text += "✗ Command: Not initialized "
            
            # Check data connector via loader
            data_connected = False
            if hasattr(self, 'loader') and self.loader:
                if hasattr(self.loader, 'isIGTLConnected') and self.loader.isIGTLConnected():
                    data_connected = True
                    status_text += "✓ Data: Connected"
                else:
                    all_connected = False
                    status_text += "✗ Data: Disconnected"
            elif hasattr(self, 'dataConnectionInfo'):
                status_text += "⏳ Data: Waiting for loader"
                all_connected = False
            else:
                status_text += "✗ Data: Not initialized"
                all_connected = False
            
            if all_connected and text_connected and cmd_connected:
                self.connectionStatusLabel.text = "✓ Fully Connected"
                self.connectionStatusLabel.styleSheet = "QLabel { color: green; font-weight: bold; }"
            elif text_connected or cmd_connected:
                self.connectionStatusLabel.text = "⚠ Partially Connected"
                self.connectionStatusLabel.styleSheet = "QLabel { color: orange; font-weight: bold; }"
            else:
                self.connectionStatusLabel.text = status_text if status_text else "Not connected"
                self.connectionStatusLabel.styleSheet = "QLabel { color: red; }"
                
        except Exception as e:
            debug_print(f"ERROR in updateConnectionStatus: {e}")
            self.connectionStatusLabel.text = "Status unknown"
            self.connectionStatusLabel.styleSheet = "QLabel { color: orange; }"

    def setupInitialUI(self):
        """Setup the initial UI with example selection before server connection"""
        debug_print("-" * 40)
        debug_print("Setting up initial UI with example selector...")
        
        try:
            # Example selection section
            self.exampleSelectionButton = ctk.ctkCollapsibleButton()
            self.exampleSelectionButton.text = "Example Selection"
            self.layout.addWidget(self.exampleSelectionButton)
            self.exampleFormLayout = qt.QFormLayout(self.exampleSelectionButton)
            
            # Get data directory path
            data_dir = get_tms_value('TMS_DATA_DIR', '../data')
            debug_print(f"Data directory: {data_dir}")
            
            # Create horizontal layout for example selection and load button
            exampleLayout = qt.QHBoxLayout()
            
            # Scan for example folders
            self.exampleComboBox = qt.QComboBox()
            if os.path.exists(data_dir):
                example_folders = [d for d in os.listdir(data_dir) 
                                 if os.path.isdir(os.path.join(data_dir, d))]
                example_folders.sort()
                debug_print(f"Found {len(example_folders)} example folders: {example_folders}")
                self.exampleComboBox.addItems(example_folders)
            else:
                debug_print(f"WARNING: Data directory not found: {data_dir}")
                self.exampleComboBox.addItem("No examples found")
            
            exampleLayout.addWidget(self.exampleComboBox)
            
            # Add a refresh button to rescan examples
            self.refreshExamplesButton = qt.QPushButton("Refresh")
            self.refreshExamplesButton.toolTip = "Rescan for examples"
            self.refreshExamplesButton.clicked.connect(self.refreshExamples)
            exampleLayout.addWidget(self.refreshExamplesButton)
            
            self.exampleFormLayout.addRow("Select Example:", exampleLayout)
            
            # Store the selected example
            self.exampleComboBox.currentIndexChanged.connect(self.onExampleChanged)
            if self.exampleComboBox.count > 0:
                self.selectedExample = self.exampleComboBox.currentText
                debug_print(f"Initial selected example: {self.selectedExample}")
            
            debug_print("Example selector created successfully")
            
        except Exception as e:
            debug_print(f"ERROR in setupInitialUI: {e}")
            debug_print(traceback.format_exc())

    def refreshExamples(self):
        """Refresh the list of available examples"""
        debug_print("Refreshing examples list...")
        
        try:
            data_dir = get_tms_value('TMS_DATA_DIR', '../data')
            current_selection = self.exampleComboBox.currentText
            
            # Clear and repopulate
            self.exampleComboBox.clear()
            
            if os.path.exists(data_dir):
                example_folders = [d for d in os.listdir(data_dir) 
                                 if os.path.isdir(os.path.join(data_dir, d))]
                example_folders.sort()
                self.exampleComboBox.addItems(example_folders)
                
                # Try to restore previous selection
                index = self.exampleComboBox.findText(current_selection)
                if index >= 0:
                    self.exampleComboBox.setCurrentIndex(index)
                elif self.exampleComboBox.count > 0:
                    self.exampleComboBox.setCurrentIndex(0)
                    
                debug_print(f"Refreshed {len(example_folders)} examples")
                self.logMessage(f"<font color='green'>✓ Refreshed examples: found {len(example_folders)} examples</font>")
            else:
                self.exampleComboBox.addItem("No examples found")
                debug_print(f"Data directory still not found: {data_dir}")
                self.logMessage(f"<font color='red'>✗ Data directory not found: {data_dir}</font>")
                
        except Exception as e:
            debug_print(f"ERROR in refreshExamples: {e}")
            debug_print(traceback.format_exc())

    def onExampleChanged(self, index):
        """Called when user selects a different example"""
        if index >= 0:
            self.selectedExample = self.exampleComboBox.currentText
            debug_print(f"Example changed to: {self.selectedExample}")

    def newText(self, caller, event):
        debug_print("-" * 40)
        debug_print("newText callback triggered")
        debug_print(f"  Caller: {caller.GetName() if caller else 'unknown'}")
        debug_print(f"  Event: {event}")
        
        try:
            self.t = slicer.mrmlScene.GetNodeByID('vtkMRMLTextNode1')
            if self.t:
                received_text = self.t.GetText()
                debug_print(f"  Received text from server: {received_text}")
                
                # Only setup buttons once (if not already done)
                if not hasattr(self, 'buttonsSetup'):
                    debug_print(f"  Setting up buttons for first time")
                    self.setupButtons()
                    self.buttonsSetup = True
            else:
                debug_print("  ERROR: Could not find text node with ID 'vtkMRMLTextNode1'")
        except Exception as e:
            debug_print(f"  ERROR in newText: {e}")
            debug_print(traceback.format_exc())

    def sendExampleToServer(self):
        """Send the selected example path to the server"""
        if not self.selectedExample:
            debug_print("ERROR: No example selected")
            self.logMessage("<font color='red'>✗ No example selected</font>")
            return
        
        debug_print(f"Sending example to server: {self.selectedExample}")
        
        try:
            # Check if command connector is connected
            if hasattr(self, 'IGTLCommandNode') and self.IGTLCommandNode:
                if self.IGTLCommandNode.GetState() != self.IGTLCommandNode.StateConnected:
                    self.logMessage("<font color='orange'>⚠ Command connector not connected. Attempting to reconnect...</font>")
                    self.reconnectWithNewSettings()
                
                # Send the example path as a command
                command_text = f"LOAD_EXAMPLE:{self.selectedExample}"
                self.commandTextNode.SetText(command_text)
                self.IGTLCommandNode.PushNode(self.commandTextNode)
                debug_print(f"Command sent: {command_text}")
                self.logMessage(f"<font color='green'>✓ Sent example '{self.selectedExample}' to server</font>")
            else:
                self.logMessage("<font color='red'>✗ Command connector not initialized</font>")
                
        except Exception as e:
            debug_print(f"ERROR sending example to server: {e}")
            debug_print(traceback.format_exc())
            self.logMessage(f"<font color='red'>✗ Failed to send example: {str(e)}</font>")

    def loadExampleWithSelection(self):
        """Load the selected example and notify the server"""
        debug_print(f"Loading selected example: {self.selectedExample}")
        
        if not self.selectedExample or self.selectedExample == "No examples found":
            debug_print("ERROR: No valid example selected")
            self.logMessage("<font color='red'>✗ No valid example selected</font>")
            return
        
        try:
            # Send example selection to server first
            self.sendExampleToServer()
            
            # Load example in Slicer
            data_dir = get_tms_value('TMS_DATA_DIR', '../data')
            example_path = os.path.join(data_dir, self.selectedExample)
            
            debug_print(f"Debug: L module type: {type(L)}")
            debug_print(f"Debug: L module dir: {dir(L)}")
            debug_print(f"Debug: Checking for Loader class in L...")
            
            if hasattr(L, 'Loader'):
                debug_print(f"✓ Loader class found in module")
                debug_print(f"  Loader class type: {type(L.Loader)}")
                
                # Pass connection info to Loader
                if hasattr(self, 'dataConnectionInfo'):
                    debug_print(f"Passing connection info to loader: {self.dataConnectionInfo}")
                    self.loader = L.Loader.loadExample(example_path, self.dataConnectionInfo)
                else:
                    debug_print("No connection info available, using defaults")
                    self.loader = L.Loader.loadExample(example_path)
                
                # Store reference to loader for connection updates
                # self.loader is already set above
                
                # Update connection status now that loader exists
                self.updateConnectionStatus()
                
                self.logMessage(f"<font color='green'>✓ Successfully loaded example: {self.selectedExample}</font>")
            else:
                debug_print(f"✗ ERROR: Loader class NOT found in module!")
                debug_print(f"  Available attributes: {[x for x in dir(L) if not x.startswith('_')]}")
                raise AttributeError(f"Loader class not found in L module. Available: {dir(L)}")
                
        except Exception as e:
            debug_print(f"✗ ERROR in loadExampleWithSelection: {e}")
            debug_print(traceback.format_exc())
            self.logMessage(f"<font color='red'>✗ Failed to load example: {str(e)}</font>")
            raise

    def setupButtons(self):
        debug_print("-" * 40)
        debug_print(f"setupButtons called")
        
        try:
            self.collapsibleButton = ctk.ctkCollapsibleButton()
            self.collapsibleButton.text = "TMS Visualization"
            self.layout.addWidget(self.collapsibleButton)
            self.formLayout = qt.QFormLayout(self.collapsibleButton)
            debug_print("  Created collapsible button for visualization")
            
            slicer.modules.tractographydisplay.widgetRepresentation().activateWindow()
            debug_print("  Activated tractography display window")
            
            self.loadExampleButton = qt.QPushButton("Load Example", self.collapsibleButton)
            self.formLayout.addRow(self.loadExampleButton)
            debug_print("  Created Load Example button")
            
            # Connect to the new function that uses selected example
            self.loadExampleButton.clicked.connect(self.loadExampleWithSelection)
            debug_print("  Connected Load Example button click")
            
            debug_print("-" * 20)
            debug_print("  Creating mesh visibility toggle...")
            self.meshButton = qt.QCheckBox("Show Mesh", self.collapsibleButton)
            self.meshButton.checked = True
            self.formLayout.addRow(self.meshButton)
            try:
                self.meshButton.stateChanged.connect(L.Loader.showMesh)
                debug_print("  Connected mesh button state change")
            except Exception as e:
                debug_print(f"  ERROR connecting mesh button: {e}")
                debug_print(traceback.format_exc())

            debug_print("  Creating volume rendering toggle...")
            self.vouleRenderingButton = qt.QCheckBox("Show Volume Rendering", self.collapsibleButton)
            self.vouleRenderingButton.checked = False
            self.formLayout.addRow(self.vouleRenderingButton)
            try:
                self.vouleRenderingButton.stateChanged.connect(L.Loader.showVolumeRendering)
                debug_print("  Connected volume rendering button state change")
            except Exception as e:
                debug_print(f"  ERROR connecting volume rendering button: {e}")
                debug_print(traceback.format_exc())

            debug_print("  Creating fibers toggle...")
            self.fiberButton = qt.QCheckBox("Show Fibers", self.collapsibleButton)
            self.fiberButton.checked = False
            self.formLayout.addRow(self.fiberButton)
            try:
                self.fiberButton.stateChanged.connect(L.Loader.showFibers)
                debug_print("  Connected fibers button state change")
            except Exception as e:
                debug_print(f"  ERROR connecting fibers button: {e}")
                debug_print(traceback.format_exc())

            self.layout.addStretch(1)
            debug_print("  Added stretch to layout")

            debug_print("-" * 20)
            debug_print("  Creating manual coil positioning section...")
            # Create grid layout for matrix input field
            self.collapsibleButton3 = ctk.ctkCollapsibleButton()
            self.collapsibleButton3.text = "Manual Coil Positioning"
            self.layout.addWidget(self.collapsibleButton3)
            self.gridLayout = qt.QGridLayout(self.collapsibleButton3)

            # Create labels for each matrix element
            labels = ["X", "Y", "Z"]
            for i in range(3):
                label = qt.QLabel(labels[i])
                self.gridLayout.addWidget(label, 0, i+1)
                label = qt.QLabel(labels[i])
                self.gridLayout.addWidget(label, i+1, 0)

            # Create line edits for each matrix element
            self.matrixInputs = []
            for i in range(3):
                row = []
                for j in range(4):
                    matrixInput = qt.QLineEdit()
                    matrixInput.setFixedSize(50, 30)  # Set fixed size for QLineEdit widget
                    row.append(matrixInput)
                    self.gridLayout.addWidget(matrixInput, i+1, j+1)
                     # Connect the editingFinished signal of each QLineEdit to updateMatrix function
                    try:
                        matrixInput.editingFinished.connect(lambda: L.Loader.updateMatrix(self))
                        debug_print(f"    Connected matrix input [{i},{j}]")
                    except Exception as e:
                        debug_print(f"    ERROR connecting matrix input [{i},{j}]: {e}")
                self.matrixInputs.append(row)

            debug_print("  Creating matrix display labels...")
            # Create label to display current matrix position
            self.currentMatrixLabel = qt.QLabel("Current Matrix Position: ", self.collapsibleButton3)
            self.layout.addWidget(self.currentMatrixLabel)
            # Create label to display matrix elements as text
            self.matrixTextLabel = qt.QLabel("", self.collapsibleButton3)
            self.layout.addWidget(self.matrixTextLabel)
            debug_print("  Matrix display labels created")

            self.initialScalarArray = None
            self.layout.addStretch(1)

            debug_print("-" * 20)
            debug_print("  Creating web server section...")
            ### WEBSERVER ####
            self.collapsibleButton2 = ctk.ctkCollapsibleButton()
            self.collapsibleButton2.text = "WebServer"
            self.layout.addWidget(self.collapsibleButton2)
            self.formLayout2 = qt.QFormLayout(self.collapsibleButton2)

            # start button
            self.startServerButton = qt.QPushButton("Start Server")
            self.startServerButton.toolTip = "Start web server with the selected options."
            self.formLayout2.addRow(self.startServerButton)
            self.startServerButton.clicked.connect(self.websv.start)
            debug_print("    Start server button created")

            # # stop button
            self.stopServerButton = qt.QPushButton("Stop Server")
            self.stopServerButton.toolTip = "Stop web server"
            self.formLayout2.addRow(self.stopServerButton)
            self.stopServerButton.connect('clicked()', self.websv.stop)
            debug_print("    Stop server button created")

            # open browser page
            self.localConnectionButton = qt.QPushButton("Open static page in external browser")
            self.localConnectionButton.toolTip = "Open a connection to the server on the local machine with your system browser."
            self.formLayout2.addRow(self.localConnectionButton)
            self.localConnectionButton.connect('clicked()', self.websv.openLocalConnection)
            debug_print("    Local connection button created")

            self.log = qt.QTextEdit()
            self.log.readOnly = True
            self.formLayout2.addRow(self.log)
            debug_print("    Log text edit created")
            
            debug_print("=" * 80)
            debug_print("setupButtons completed successfully")
            debug_print("=" * 80)

        except Exception as e:
            debug_print(f"FATAL ERROR in setupButtons: {e}")
            debug_print(traceback.format_exc())
            raise

    def logMessage(self, *args):
        debug_print("-" * 20)
        debug_print(f"logMessage called with {len(args)} arguments")
        
        if self.consoleMessages:
            for i, arg in enumerate(args):
                debug_print(f"  Console arg {i}: {str(arg)[:100]}...")
                print(arg)
                
        if self.guiMessages:
            if hasattr(self, 'log') and self.log:
                if len(self.log.toHtml()) > 1024 * 256:
                    self.log.clear()
                    self.log.insertHtml("Log cleared<br>")
                    debug_print("  Log cleared due to size")
                    
                for i, arg in enumerate(args):
                    debug_print(f"  GUI arg {i}: {str(arg)[:100]}...")
                    self.log.insertHtml(str(arg))
                    
                self.log.insertPlainText('\n')
                self.log.ensureCursorVisible()
                self.log.repaint()
                debug_print("  Log updated in GUI")