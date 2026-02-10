"""
Chunked data transmission utilities for large numpy arrays over pyigtl
Includes checksums and error detection for network transmission
"""

import numpy as np
import hashlib
import struct

class ChunkedTransmission:
    """
    Handles breaking up large numpy arrays into chunks with metadata and checksums
    """
    
    # Maximum size per chunk (in bytes) - adjust based on your network MTU
    # Using 64KB as a safe default (well under typical MTU issues)
    CHUNK_SIZE = 65536  # 64KB
    
    @staticmethod
    def compute_checksum(data):
        """Compute MD5 checksum of numpy array"""
        return hashlib.md5(data.tobytes()).hexdigest()
    
    @staticmethod
    def create_metadata_array(original_shape, original_dtype, total_chunks, chunk_index, checksum):
        """
        Create a metadata array that can be sent as an image
        Stores: shape, dtype, total_chunks, chunk_index, checksum
        
        Returns a small 3D array (10x10x10) with metadata encoded
        """
        # Create a small 3D array to hold metadata
        metadata = np.zeros((10, 10, 10), dtype=np.float32)
        
        # Encode shape (first 3 values)
        for i, dim in enumerate(original_shape[:3]):
            metadata[0, 0, i] = float(dim)
        
        # Encode dtype as string -> int mapping
        dtype_map = {
            'float32': 1.0, 'float64': 2.0, 'int32': 3.0, 
            'int64': 4.0, 'uint8': 5.0, 'uint16': 6.0
        }
        metadata[0, 1, 0] = dtype_map.get(str(original_dtype), 1.0)
        
        # Encode chunk info
        metadata[0, 1, 1] = float(total_chunks)
        metadata[0, 1, 2] = float(chunk_index)
        
        # Encode checksum (convert hex to floats)
        # Store first 16 chars of checksum as floats
        for i, char in enumerate(checksum[:16]):
            if i < 10:
                metadata[0, 2, i] = float(ord(char))
        
        return metadata
    
    @staticmethod
    def parse_metadata_array(metadata_array):
        """Parse metadata from received array"""
        shape = tuple(int(metadata_array[0, 0, i]) for i in range(3))
        
        dtype_map_inv = {
            1.0: np.float32, 2.0: np.float64, 3.0: np.int32,
            4.0: np.int64, 5.0: np.uint8, 6.0: np.uint16
        }
        dtype = dtype_map_inv.get(metadata_array[0, 1, 0], np.float32)
        
        total_chunks = int(metadata_array[0, 1, 1])
        chunk_index = int(metadata_array[0, 1, 2])
        
        # Reconstruct checksum
        checksum = ''.join(chr(int(metadata_array[0, 2, i])) for i in range(10))
        
        return {
            'shape': shape,
            'dtype': dtype,
            'total_chunks': total_chunks,
            'chunk_index': chunk_index,
            'checksum': checksum
        }
    
    @staticmethod
    def split_array_for_transmission(data):
        """
        Split a large numpy array into chunks suitable for transmission
        
        Args:
            data: numpy array to transmit
            
        Returns:
            List of tuples: [(metadata_array, data_chunk), ...]
        """
        # Ensure data is contiguous and float32
        data_flat = data.flatten().astype(np.float32)
        original_shape = data.shape
        original_dtype = data.dtype
        
        # Calculate number of elements per chunk
        elements_per_chunk = ChunkedTransmission.CHUNK_SIZE // 4  # 4 bytes per float32
        
        # Calculate total chunks needed
        total_elements = data_flat.size
        total_chunks = int(np.ceil(total_elements / elements_per_chunk))
        
        print(f"Splitting array: shape={original_shape}, size={total_elements} elements, chunks={total_chunks}")
        
        chunks = []
        for chunk_idx in range(total_chunks):
            start_idx = chunk_idx * elements_per_chunk
            end_idx = min((chunk_idx + 1) * elements_per_chunk, total_elements)
            
            # Extract chunk
            chunk_data = data_flat[start_idx:end_idx]
            
            # Pad chunk to fixed size for easier transmission (optional)
            # This makes all chunks the same size except possibly the last one
            chunk_data_3d = chunk_data.reshape(-1, 1, 1)  # Make it 3D for pyigtl
            
            # Compute checksum for this chunk
            chunk_checksum = ChunkedTransmission.compute_checksum(chunk_data)
            
            # Create metadata
            metadata = ChunkedTransmission.create_metadata_array(
                original_shape, original_dtype, total_chunks, chunk_idx, chunk_checksum
            )
            
            chunks.append((metadata, chunk_data_3d, chunk_checksum))
            
        return chunks, original_shape, original_dtype
    
    @staticmethod
    def reassemble_array(chunks_data, expected_shape, expected_dtype):
        """
        Reassemble chunks back into original array
        
        Args:
            chunks_data: List of (chunk_index, chunk_data, checksum) tuples
            expected_shape: Original array shape
            expected_dtype: Original array dtype
            
        Returns:
            Reassembled numpy array or None if error
        """
        if not chunks_data:
            print("ERROR: No chunks to reassemble")
            return None
        
        # Sort chunks by index
        chunks_data.sort(key=lambda x: x[0])
        
        # Verify we have all chunks
        expected_indices = set(range(len(chunks_data)))
        received_indices = set(chunk[0] for chunk in chunks_data)
        
        if expected_indices != received_indices:
            missing = expected_indices - received_indices
            print(f"ERROR: Missing chunks: {missing}")
            return None
        
        # Concatenate all chunk data
        all_data = []
        for chunk_idx, chunk_data, expected_checksum in chunks_data:
            # Verify checksum
            actual_checksum = ChunkedTransmission.compute_checksum(chunk_data)
            if actual_checksum != expected_checksum:
                print(f"ERROR: Checksum mismatch for chunk {chunk_idx}")
                print(f"  Expected: {expected_checksum}")
                print(f"  Got: {actual_checksum}")
                return None
            
            all_data.append(chunk_data.flatten())
        
        # Concatenate and reshape
        try:
            full_data = np.concatenate(all_data)
            total_elements = np.prod(expected_shape)
            
            # Trim to exact size (remove any padding)
            full_data = full_data[:total_elements]
            
            # Reshape to original shape
            result = full_data.reshape(expected_shape).astype(expected_dtype)
            
            print(f"Successfully reassembled array: shape={result.shape}, dtype={result.dtype}")
            return result
            
        except Exception as e:
            print(f"ERROR: Failed to reassemble array: {e}")
            return None


class ChunkReceiver:
    """
    Helper class to manage receiving chunks and reassembling them
    """
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        """Reset receiver state"""
        self.chunks = []
        self.expected_total_chunks = None
        self.expected_shape = None
        self.expected_dtype = None
        self.metadata_complete = False
    
    def process_metadata(self, metadata_array):
        """Process received metadata"""
        try:
            metadata = ChunkedTransmission.parse_metadata_array(metadata_array)
            
            if not self.metadata_complete:
                self.expected_shape = metadata['shape']
                self.expected_dtype = metadata['dtype']
                self.expected_total_chunks = metadata['total_chunks']
                self.metadata_complete = True
                print(f"Metadata received: {metadata}")
            
            return metadata
        except Exception as e:
            print(f"ERROR: Failed to parse metadata: {e}")
            return None
    
    def add_chunk(self, chunk_index, chunk_data, checksum):
        """Add a received chunk"""
        self.chunks.append((chunk_index, chunk_data, checksum))
        print(f"Chunk {chunk_index + 1}/{self.expected_total_chunks} received")
    
    def is_complete(self):
        """Check if all chunks have been received"""
        return (self.metadata_complete and 
                self.expected_total_chunks is not None and
                len(self.chunks) == self.expected_total_chunks)
    
    def reassemble(self):
        """Reassemble received chunks"""
        if not self.is_complete():
            print(f"ERROR: Cannot reassemble - only {len(self.chunks)}/{self.expected_total_chunks} chunks received")
            return None
        
        result = ChunkedTransmission.reassemble_array(
            self.chunks, self.expected_shape, self.expected_dtype
        )
        
        if result is not None:
            self.reset()  # Reset for next transmission
        
        return result
