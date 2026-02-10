# Chunked Transmission System for TMS Network Communication

This system implements chunked data transmission with error checking to resolve network corruption issues when sending large arrays over PyIGTL between separate machines.

## Problem Solved

When running the TMS server and Slicer client on separate machines (not localhost), large numpy arrays were getting corrupted during network transmission, causing:
- `ctkRangeWidget::setSingleStep( -0.01 ) is outside valid bounds` errors
- X Server errors (BadPixmap, BadShmSeg)
- Slicer crashes

## Solution

The chunked transmission system:
1. **Breaks large arrays into small chunks** (64KB each by default)
2. **Adds checksums** to each chunk for error detection
3. **Includes metadata** with shape, dtype, and chunk information
4. **Validates data** on both send and receive sides
5. **Provides detailed logging** for debugging

## Files

### 1. `chunked_transmission.py` (NEW)
Utility module containing:
- `ChunkedTransmission` class: Handles splitting and reassembling arrays
- `ChunkReceiver` class: Manages receiving and validating chunks
- Checksum computation (MD5)
- Metadata encoding/decoding

### 2. `server_chunked.py` (REPLACES `server.py`)
Updated server that:
- Splits output data into chunks before sending
- Sends metadata + chunk pairs via PyIGTL
- Sends completion signal when all chunks are sent
- Keeps `eth0` interface (as required by pyigtl)

### 3. `Loader_chunked.py` (REPLACES `Loader.py`)
Updated Slicer loader that:
- Receives and processes metadata chunks
- Collects data chunks with checksum validation
- Reassembles complete array on completion signal
- Updates the visualization with validated data

## Installation

1. **Copy the files to your TMS module directory:**
   ```bash
   # On the server machine
   cp chunked_transmission.py /path/to/tms/server/
   cp server_chunked.py /path/to/tms/server/
   
   # On the Slicer machine
   cp chunked_transmission.py /path/to/Slicer/TMS/module/
   cp Loader_chunked.py /path/to/Slicer/TMS/module/
   ```

2. **Rename the new files:**
   ```bash
   # Backup originals first!
   mv server.py server_original.py
   mv Loader.py Loader_original.py
   
   # Use the new versions
   mv server_chunked.py server.py
   mv Loader_chunked.py Loader.py
   ```

## Configuration

### Adjusting Chunk Size

If you still experience issues, you can adjust the chunk size in `chunked_transmission.py`:

```python
class ChunkedTransmission:
    # Default is 64KB - decrease if still having issues
    CHUNK_SIZE = 32768  # 32KB for more conservative chunking
    # Or increase for faster transmission on good networks
    CHUNK_SIZE = 131072  # 128KB
```

**Recommendation:** Start with the default 64KB. Only adjust if needed.

### Network Requirements

- Ports 18944 and 18945 must be open on both machines
- Ensure stable network connection between machines
- Recommended: Use wired ethernet connection for reliability

## How It Works

### Transmission Sequence

```
SERVER                          CLIENT (Slicer)
  |                                |
  |--- Metadata Chunk 0 -------->  | (stores shape, dtype, total chunks)
  |--- Data Chunk 0 ------------>  | (validates checksum)
  |                                |
  |--- Metadata Chunk 1 -------->  |
  |--- Data Chunk 1 ------------>  |
  |                                |
  |    ... (more chunks)           |
  |                                |
  |--- Completion Signal -------->  | (triggers reassembly)
  |                                | (validates all checksums)
  |                                | (updates visualization)
```

### Data Flow

1. **Server generates E-field data** from CNN
2. **Server splits data** into chunks with metadata
3. **Server sends** each chunk sequentially with small delays
4. **Client receives** and stores each chunk
5. **Client validates** checksums for each chunk
6. **Client reassembles** on completion signal
7. **Client updates** visualization with validated data

## Debugging

### Enable Detailed Logging

Both files already include detailed logging. Check the console output for:

**Server side:**
```
Splitting array: shape=(128, 128, 128), size=2097152 elements, chunks=32
Sending 32 chunks...
  Sent chunk 1/32 (checksum: 5d8e3f9a...)
  Sent chunk 2/32 (checksum: 7a2c1b4f...)
  ...
Transmission complete signal sent
Total execution time: 0.523451s
```

**Client side:**
```
Received metadata chunk
Metadata received: {'shape': (128, 128, 128), 'dtype': dtype('float32'), ...}
Received data chunk
Chunk 1/32 received
Received data chunk
Chunk 2/32 received
...
Received completion signal
All chunks received, reassembling...
Successfully reassembled data, processing...
Updated pyigtl_data node with shape (128, 128, 128)
```

### Common Issues

**Problem:** Chunks not received in order
- **Solution:** The system handles this - chunks are sorted by index before reassembly

**Problem:** Checksum mismatch
- **Solution:** Check network stability, reduce chunk size, check for packet loss

**Problem:** Missing chunks
- **Solution:** Check network connection, firewall rules, increase delays between chunks

**Problem:** Still getting crashes
- **Solution:** Try reducing `CHUNK_SIZE` to 32KB or even 16KB

## Testing

### Test on Localhost First

Before deploying on separate machines, test on localhost:

1. Start server: `python server.py`
2. Start Slicer and load the module
3. Verify chunks are sent and received correctly
4. Check console logs for any errors

### Test on Network

1. Ensure both machines can ping each other
2. Check firewall allows ports 18944 and 18945
3. Start server on remote machine
4. Configure Slicer to connect to remote IP
5. Monitor console logs on both machines

## Performance

### Expected Behavior

- **Chunk transmission:** ~10-50ms per chunk (depending on network)
- **Total overhead:** ~0.1-0.5s for typical image (adds to CNN execution time)
- **Network bandwidth:** ~2-10 MB/s (depending on image size and chunk size)

### Comparison to Original

- **Reliability:** Much better over network (checksums detect corruption)
- **Speed:** Slightly slower due to chunking overhead
- **Localhost:** May be marginally slower than original (chunking overhead)
- **Network:** Much more reliable, worth the small overhead

## Backward Compatibility

The system includes fallback support for the original single-chunk transmission:

```python
elif node_name == 'pyigtl_data':
    # Legacy single-chunk transmission (fallback for backward compatibility)
    print('New CNN Image received via PyIgtl (legacy mode)')
    M.Mapper.modifyIncomingImage(self)
```

This means if the old server sends data, it will still work (though without error checking).

## Troubleshooting

### Server won't start
- Check that `chunked_transmission.py` is in the same directory as `server.py`
- Verify Python can import the module: `python -c "import chunked_transmission"`

### Slicer can't find module
- Ensure `chunked_transmission.py` is in the Slicer module directory
- Check Slicer Python console for import errors

### Data still corrupted
- Reduce `CHUNK_SIZE` to 16384 (16KB)
- Check network MTU settings
- Try disabling network optimizations (like TCP offload)
- Check for packet loss: `ping -c 100 <server-ip>`

### Performance issues
- Increase `CHUNK_SIZE` to 131072 (128KB) for faster networks
- Reduce delays in server.py (currently 0.01s between chunks)
- Consider using a faster checksum algorithm if MD5 is too slow

## Advanced Configuration

### Custom Delays

In `server_chunked.py`, adjust delays between chunks:

```python
# After metadata
await asyncio.sleep(0.01)  # Reduce to 0.005 for faster transmission

# After chunk
await asyncio.sleep(0.01)  # Reduce to 0.005 for faster transmission
```

**Warning:** Reducing delays too much may overwhelm slower networks.

### Custom Checksum Algorithm

If MD5 is too slow, you can use a faster algorithm in `chunked_transmission.py`:

```python
import hashlib

@staticmethod
def compute_checksum(data):
    """Compute checksum of numpy array"""
    # Option 1: CRC32 (faster, less secure)
    import zlib
    return hex(zlib.crc32(data.tobytes()))
    
    # Option 2: SHA256 (more secure, slower)
    return hashlib.sha256(data.tobytes()).hexdigest()
```

## Support

If issues persist:
1. Check both server and client console logs
2. Verify network connectivity and firewall rules
3. Try reducing chunk size progressively (64KB → 32KB → 16KB)
4. Test on localhost to isolate network issues
5. Check for system resource limitations (memory, CPU)

## Summary

This chunked transmission system solves network corruption issues by:
- ✅ Breaking large arrays into manageable chunks
- ✅ Adding error detection with checksums
- ✅ Providing detailed logging for debugging
- ✅ Maintaining compatibility with existing code
- ✅ Supporting both localhost and network operation

The small performance overhead is worth the significant improvement in reliability for network transmission.
