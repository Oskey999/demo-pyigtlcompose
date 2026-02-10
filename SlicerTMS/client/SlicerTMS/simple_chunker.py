"""
Simplified chunked transmission for PyIGTL - minimal implementation
Works with Slicer 5.8.1 and newer versions
"""

import numpy as np
import struct

class SimpleChunker:
    """
    Simple chunking with basic error detection
    Uses fixed 50KB chunks to stay well under network MTU limits
    """
    
    CHUNK_SIZE = 51200  # 50KB - safe for most networks
    MAGIC_NUMBER = 3735928559  # 0xDEADBEEF in little-endian - platform independent
    
    @staticmethod
    def create_chunks(data):
        """
        Split array into chunks with simple headers
        Returns: list of (is_metadata, data_array) tuples
        """
        # CRITICAL: Ensure consistent data format across platforms
        # Force little-endian float32 with C-contiguous layout
        data = np.asarray(data, dtype='<f4', order='C')  # '<f4' = little-endian float32
        
        original_shape = data.shape
        data_flat = data.flatten()
        
        # Calculate chunks
        elements_per_chunk = SimpleChunker.CHUNK_SIZE // 4  # 4 bytes per float32
        total_elements = data_flat.size
        num_chunks = int(np.ceil(total_elements / elements_per_chunk))
        
        print(f"[Chunker] Splitting {original_shape} into {num_chunks} chunks")
        
        chunks = []
        
        # First, create metadata chunk (small array with encoding info)
        # Force consistent dtype and byte order
        metadata = np.zeros(100, dtype='<f4')  # Little-endian float32
        metadata[0] = SimpleChunker.MAGIC_NUMBER
        metadata[1] = num_chunks
        metadata[2] = original_shape[0]
        metadata[3] = original_shape[1]
        metadata[4] = original_shape[2]
        metadata[5] = total_elements
        
        # Reshape to 3D for PyIGTL (minimum size)
        meta_3d = metadata.reshape(10, 10, 1)
        chunks.append((True, meta_3d))  # (is_metadata, data)
        
        # Create data chunks
        for i in range(num_chunks):
            start_idx = i * elements_per_chunk
            end_idx = min((i + 1) * elements_per_chunk, total_elements)
            
            chunk_data = data_flat[start_idx:end_idx]
            
            # Add header to chunk: [chunk_index, chunk_size, checksum]
            # Force consistent dtype
            header = np.array([i, len(chunk_data), np.sum(chunk_data)], dtype='<f4')
            chunk_with_header = np.concatenate([header, chunk_data])
            
            # Ensure C-contiguous
            chunk_with_header = np.ascontiguousarray(chunk_with_header, dtype='<f4')
            
            # Reshape to 3D for PyIGTL
            chunk_3d = chunk_with_header.reshape(-1, 1, 1)
            chunks.append((False, chunk_3d))
        
        return chunks, original_shape
    
    @staticmethod
    def parse_metadata(meta_array):
        """Parse metadata array"""
        meta_flat = meta_array.flatten()
        
        magic = int(meta_flat[0])
        if magic != SimpleChunker.MAGIC_NUMBER:
            print(f"[Chunker] WARNING: Magic number mismatch: {magic} != {SimpleChunker.MAGIC_NUMBER}")
        
        return {
            'num_chunks': int(meta_flat[1]),
            'shape': (int(meta_flat[2]), int(meta_flat[3]), int(meta_flat[4])),
            'total_elements': int(meta_flat[5])
        }
    
    @staticmethod
    def parse_chunk(chunk_array):
        """Parse a data chunk and return (index, data, checksum)"""
        chunk_flat = chunk_array.flatten()
        
        chunk_index = int(chunk_flat[0])
        chunk_size = int(chunk_flat[1])
        checksum = chunk_flat[2]
        data = chunk_flat[3:3+chunk_size]
        
        # Verify checksum
        actual_checksum = np.sum(data)
        if not np.isclose(checksum, actual_checksum, rtol=1e-5):
            print(f"[Chunker] WARNING: Checksum mismatch for chunk {chunk_index}")
        
        return chunk_index, data, checksum
    
    @staticmethod
    def reassemble(chunks_list, expected_shape):
        """
        Reassemble chunks into original array
        chunks_list: list of (chunk_index, data) tuples
        """
        # Sort by index
        chunks_list.sort(key=lambda x: x[0])
        
        # Concatenate all data - ensure consistent dtype
        all_data = np.concatenate([chunk[1] for chunk in chunks_list])
        
        # Force consistent dtype for cross-platform compatibility
        all_data = np.asarray(all_data, dtype='<f4')  # Little-endian float32
        
        # Reshape to original shape
        total_expected = np.prod(expected_shape)
        if len(all_data) != total_expected:
            print(f"[Chunker] WARNING: Size mismatch - got {len(all_data)}, expected {total_expected}")
            all_data = all_data[:total_expected]  # Trim to expected size
        
        result = all_data.reshape(expected_shape)
        
        # Convert back to native float32 for Slicer
        result = np.asarray(result, dtype=np.float32)
        
        print(f"[Chunker] Reassembled to shape {result.shape}")
        
        return result


class SimpleReceiver:
    """Simple receiver state machine"""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.metadata = None
        self.chunks = []
        self.received_indices = set()
        self.last_metadata_time = 0
    
    def add_metadata(self, meta_array):
        """Process metadata - resets state for new transmission"""
        import time
        current_time = time.time()
        
        # If we get new metadata, it means a new transmission started
        # Reset everything
        if self.metadata is not None and (current_time - self.last_metadata_time) > 0.1:
            print(f"[Receiver] New transmission detected, resetting...")
            self.reset()
        
        self.metadata = SimpleChunker.parse_metadata(meta_array)
        self.last_metadata_time = current_time
        print(f"[Receiver] Metadata: {self.metadata['num_chunks']} chunks, shape {self.metadata['shape']}")
    
    def add_chunk(self, chunk_array):
        """Process data chunk"""
        if self.metadata is None:
            print("[Receiver] ERROR: Received chunk before metadata")
            return False
        
        chunk_idx, data, checksum = SimpleChunker.parse_chunk(chunk_array)
        
        if chunk_idx in self.received_indices:
            # Silently ignore duplicates (common with network retransmission)
            return False
        
        self.chunks.append((chunk_idx, data))
        self.received_indices.add(chunk_idx)
        
        print(f"[Receiver] Chunk {chunk_idx + 1}/{self.metadata['num_chunks']} received ({len(self.chunks)} total)")
        return True
    
    def is_complete(self):
        """Check if all chunks received"""
        if self.metadata is None:
            return False
        return len(self.chunks) == self.metadata['num_chunks']
    
    def get_result(self):
        """Reassemble and return result"""
        if not self.is_complete():
            print(f"[Receiver] ERROR: Incomplete - {len(self.chunks)}/{self.metadata['num_chunks']} chunks")
            return None
        
        result = SimpleChunker.reassemble(self.chunks, self.metadata['shape'])
        self.reset()  # Reset for next transmission
        return result
