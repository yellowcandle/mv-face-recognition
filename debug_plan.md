# ChromaDB Face Recognition Debugging Plan

## Overview
This document outlines a systematic approach to debugging issues with the face recognition system when using the ChromaDB backend.

## Common Issues and Solutions

### 1. Import and Dependency Issues

#### Symptoms:
- ImportError or ModuleNotFoundError
- "ChromaDB is not installed but is required" error message

#### Debugging Steps:
1. Verify ChromaDB installation:
   ```bash
   pip show chromadb
   ```
2. Check version compatibility (version >=0.4.18 is required)
3. Install if missing:
   ```bash
   pip install chromadb>=0.4.18
   ```

### 2. Database Connection Issues

#### Symptoms:
- "Failed to connect to ChromaDB" errors
- Hanging or timing out when accessing ChromaDB

#### Debugging Steps:
1. Try with in-memory database (add `--in-memory-db` flag)
2. Check ChromaDB cache directory permissions
3. Verify that ChromaDB files are not corrupted:
   ```bash
   ls -la cache/chromadb/
   ```
4. If corrupted, delete the cache and let it rebuild:
   ```bash
   rm -rf cache/chromadb/
   ```

### 3. Face Detection Issues

#### Symptoms:
- No faces detected in images
- Low confidence scores for detections

#### Debugging Steps:
1. Lower confidence threshold (use `--detector-confidence 0.3`)
2. Verify test images are properly loaded
3. Check detector model files existence
4. Try different detector model size

### 4. Face Recognition/Matching Issues

#### Symptoms:
- Faces detected but not recognized
- Wrong person identified

#### Debugging Steps:
1. Adjust similarity threshold (use `--distance-threshold 0.6` for more permissive matching)
2. Check if embeddings are being properly generated and stored
3. Verify that known embeddings are being loaded correctly
4. Inspect individual embedding values for anomalies

### 5. Performance Issues

#### Symptoms:
- Very slow processing
- High memory usage

#### Debugging Steps:
1. Check system resource usage during processing
2. Analyze cache efficiency - Are cached embeddings being used?
3. Try with different worker counts (use `--max-workers 2` or higher based on CPU)
4. Enable/disable optimizations systematically to isolate bottlenecks

## Debugging Workflow

1. **Isolate the problem**:
   - Run with minimal inputs (one contestant, one short video)
   - Use the debug wrapper script with debug flags enabled

2. **Enable verbose logging**:
   - Use `--debug` flag to get detailed logs
   - Check log files for patterns or recurring errors

3. **Step-by-step troubleshooting**:
   - Start with testing individual components
   - Test face detection separately
   - Test face recognition with known good images
   - Test ChromaDB functionality independently

4. **Fix and validate**:
   - Make one change at a time
   - Run tests after each change
   - Document successful fixes

## Using the Debug Wrapper

The `debug_wrapper.sh` script is designed to run the face recognition system with debug options and capture output for analysis.

```bash
chmod +x debug_wrapper.sh
./debug_wrapper.sh
```

This will:
1. Run with ChromaDB backend
2. Enable debug output
3. Optimize cache but disable performance optimizations
4. Capture all output to a timestamped log file
5. Extract and display errors from the log