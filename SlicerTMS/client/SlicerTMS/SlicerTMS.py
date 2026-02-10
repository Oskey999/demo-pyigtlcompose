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
        debug_print("SlicerTMSWidget.__init__ completed")

    def setup(self):
        debug_print("=" * 80)
        debug_print("SlicerTMSWidget.setup called")
        debug_print("=" * 80)
        
        try:
            ScriptedLoadableModuleWidget.setup(self)
            debug_print("Parent setup completed")
            
            debug_print("-" * 40)
            debug_print("Initializing Web Server...")
            self.websv = W.SlicerWebServer(logMessage=self.logMessage)
            debug_print("Web server initialized")

            debug_print("-" * 40)
            debug_print("Setting up IGTL Text Connector...")
            # IGTL connections for receiving text
            self.IGTLNode = slicer.vtkMRMLIGTLConnectorNode()
            slicer.mrmlScene.AddNode(self.IGTLNode)
            self.IGTLNode.SetName('TextConnector')
            
            # Get server host from environment variable
            tms_server_host = get_tms_value('TMS_SERVER_HOST', 'localhost')
            tms_server_port = int(get_tms_value('TMS_SERVER_PORT_2', '18945'))
            debug_print(f"Text server config: host={tms_server_host}, port={tms_server_port}")

            self.IGTLNode.SetTypeClient(tms_server_host, tms_server_port)
            print(f'Connecting TextConnector to TMS server at {tms_server_host}:{tms_server_port}')
            
            # this will activate the the status of the connection:
            self.IGTLNode.Start()
            self.IGTLNode.PushOnConnect()
            debug_print("IGTL text connector started")

            # Set up connector for sending commands to server
            debug_print("-" * 40)
            debug_print("Setting up IGTL Command Connector...")
            self.IGTLCommandNode = slicer.vtkMRMLIGTLConnectorNode()
            slicer.mrmlScene.AddNode(self.IGTLCommandNode)
            self.IGTLCommandNode.SetName('CommandConnector')
            self.IGTLCommandNode.SetTypeClient(tms_server_host, tms_server_port)
            self.IGTLCommandNode.Start()
            debug_print("IGTL command connector started")

            self.textNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLTextNode', 'TextMessage')
            self.textNode.SetForceCreateStorageNode(True)
            observer = self.textNode.AddObserver(slicer.vtkMRMLTextNode.TextModifiedEvent, self.newText)
            debug_print(f"Text node created and observer added: {observer}")
            
            # Set up command text node for sending
            self.commandTextNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLTextNode', 'CommandMessage')
            self.IGTLCommandNode.RegisterOutgoingMRMLNode(self.commandTextNode)
            debug_print("Command text node created")
            
            # Setup initial UI with example selector
            self.setupInitialUI()
            
            debug_print("=" * 80)
            debug_print("SlicerTMSWidget.setup completed successfully")
            debug_print("=" * 80)
            
        except Exception as e:
            debug_print(f"FATAL ERROR in setup: {e}")
            debug_print(traceback.format_exc())
            raise

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
            
            self.exampleFormLayout.addRow("Select Example:", self.exampleComboBox)
            
            # Store the selected example
            self.exampleComboBox.currentIndexChanged.connect(self.onExampleChanged)
            if self.exampleComboBox.count > 0:
                self.selectedExample = self.exampleComboBox.currentText
                debug_print(f"Initial selected example: {self.selectedExample}")
            
            debug_print("Example selector created successfully")
            
        except Exception as e:
            debug_print(f"ERROR in setupInitialUI: {e}")
            debug_print(traceback.format_exc())

    def onExampleChanged(self, index):
        """Called when user selects a different example"""
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
            return
        
        debug_print(f"Sending example to server: {self.selectedExample}")
        
        try:
            # Send the example path as a command
            command_text = f"LOAD_EXAMPLE:{self.selectedExample}"
            self.commandTextNode.SetText(command_text)
            self.IGTLCommandNode.PushNode(self.commandTextNode)
            debug_print(f"Command sent: {command_text}")
        except Exception as e:
            debug_print(f"ERROR sending example to server: {e}")
            debug_print(traceback.format_exc())

    def loadExampleWithSelection(self):
        """Load the selected example and notify the server"""
        debug_print(f"Loading selected example: {self.selectedExample}")
        
        # Send example selection to server first
        self.sendExampleToServer()
        
        # Load example in Slicer
        data_dir = get_tms_value('TMS_DATA_DIR', '../data')
        example_path = os.path.join(data_dir, self.selectedExample)
        L.Loader.loadExample(example_path)

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
            if len(self.log.html) > 1024 * 256:
                self.log.clear()
                self.log.insertHtml("Log cleared\n")
                debug_print("  Log cleared due to size")
                
            for i, arg in enumerate(args):
                debug_print(f"  GUI arg {i}: {str(arg)[:100]}...")
                self.log.insertHtml(arg)
                
            self.log.insertPlainText('\n')
            self.log.ensureCursorVisible()
            self.log.repaint()
            debug_print("  Log updated in GUI")