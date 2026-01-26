"""
PyIGTL Client Module
Handles direct communication with TMS server using pyigtl instead of Slicer IGTL connectors
"""

import pyigtl
import threading
import time
import logging
from typing import Optional, Callable

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class PyIGTLTextClient:
    """Manages text message communication for receiving file paths"""
    
    def __init__(self, host: str = 'localhost', port: int = 18945):
        self.host = host
        self.port = port
        self.client: Optional[pyigtl.OpenIGTLinkClient] = None
        self.connected = False
        self.last_message = None
        self.message_callback: Optional[Callable] = None
        self.listen_thread: Optional[threading.Thread] = None
        self.running = False
        
    def connect(self):
        """Connect to text server"""
        try:
            self.client = pyigtl.OpenIGTLinkClient(self.host, self.port)
            self.connected = True
            logger.info(f"Connected to text server at {self.host}:{self.port}")
            
            # Start listening thread
            self.running = True
            self.listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
            self.listen_thread.start()
            return True
        except Exception as e:
            logger.error(f"Failed to connect to text server: {e}")
            self.connected = False
            return False
    
    def _listen_loop(self):
        """Listen for incoming messages in background thread"""
        while self.running and self.connected:
            try:
                messages = self.client.get_latest_messages()
                if messages:
                    for message in messages:
                        self.last_message = message
                        logger.info(f"Received text message: {message}")
                        if self.message_callback:
                            self.message_callback(message)
                time.sleep(0.1)  # Small delay to avoid busy waiting
            except Exception as e:
                logger.error(f"Error listening for messages: {e}")
                self.connected = False
                break
    
    def disconnect(self):
        """Disconnect from text server"""
        self.running = False
        if self.listen_thread:
            self.listen_thread.join(timeout=2)
        self.connected = False
        logger.info("Disconnected from text server")
    
    def set_message_callback(self, callback: Callable):
        """Set callback function for received messages"""
        self.message_callback = callback
    
    def get_last_message(self):
        """Get the last received message"""
        return self.last_message


class PyIGTLDataClient:
    """Manages image data communication for E-field and magnetic field"""
    
    def __init__(self, host: str = 'localhost', port: int = 18944):
        self.host = host
        self.port = port
        self.client: Optional[pyigtl.OpenIGTLinkClient] = None
        self.connected = False
        self.last_image = None
        self.image_callback: Optional[Callable] = None
        self.listen_thread: Optional[threading.Thread] = None
        self.running = False
        
    def connect(self):
        """Connect to data server"""
        try:
            self.client = pyigtl.OpenIGTLinkClient(self.host, self.port)
            self.connected = True
            logger.info(f"Connected to data server at {self.host}:{self.port}")
            
            # Start listening thread
            self.running = True
            self.listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
            self.listen_thread.start()
            return True
        except Exception as e:
            logger.error(f"Failed to connect to data server: {e}")
            self.connected = False
            return False
    
    def _listen_loop(self):
        """Listen for incoming image messages in background thread"""
        while self.running and self.connected:
            try:
                messages = self.client.get_latest_messages()
                if messages:
                    for message in messages:
                        self.last_image = message
                        logger.info(f"Received image message: {message.name}")
                        if self.image_callback:
                            self.image_callback(message)
                time.sleep(0.1)  # Small delay to avoid busy waiting
            except Exception as e:
                logger.error(f"Error listening for images: {e}")
                self.connected = False
                break
    
    def disconnect(self):
        """Disconnect from data server"""
        self.running = False
        if self.listen_thread:
            self.listen_thread.join(timeout=2)
        self.connected = False
        logger.info("Disconnected from data server")
    
    def set_image_callback(self, callback: Callable):
        """Set callback function for received images"""
        self.image_callback = callback
    
    def send_image(self, image_name: str, image_data) -> bool:
        """Send image data to server"""
        try:
            if not self.connected:
                logger.error("Not connected to data server")
                return False
            
            message = pyigtl.ImageMessage()
            message.name = image_name
            message.set_image_data(image_data)
            
            self.client.send_message(message)
            logger.info(f"Sent image: {image_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to send image: {e}")
            return False
    
    def get_last_image(self):
        """Get the last received image"""
        return self.last_image


class PyIGTLServerManager:
    """Manages both text and data connections to TMS server"""
    
    def __init__(self, host: str = 'localhost', text_port: int = 18945, data_port: int = 18944):
        self.host = host
        self.text_port = text_port
        self.data_port = data_port
        
        self.text_client = PyIGTLTextClient(host, text_port)
        self.data_client = PyIGTLDataClient(host, data_port)
        
    def connect_all(self) -> bool:
        """Connect to both text and data servers"""
        text_ok = self.text_client.connect()
        if not text_ok:
            logger.warning("Failed to connect to text server, retrying...")
            time.sleep(2)
            text_ok = self.text_client.connect()
        
        data_ok = self.data_client.connect()
        if not data_ok:
            logger.warning("Failed to connect to data server, retrying...")
            time.sleep(2)
            data_ok = self.data_client.connect()
        
        return text_ok and data_ok
    
    def disconnect_all(self):
        """Disconnect from both servers"""
        self.text_client.disconnect()
        self.data_client.disconnect()
    
    def is_connected(self) -> bool:
        """Check if both connections are active"""
        return self.text_client.connected and self.data_client.connected
