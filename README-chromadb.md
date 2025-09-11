# ChromaDB Face Recognition Debugging and Optimization Guide

This guide provides detailed information on debugging and optimizing the ChromaDB-based face recognition system.

## Table of Contents
1. [Overview](#overview)
2. [Running the System](#running-the-system)
3. [Debugging Tools](#debugging-tools)
4. [Optimization Tools](#optimization-tools)
5. [Common Issues](#common-issues)
6. [Performance Recommendations](#performance-recommendations)

## Overview

The face recognition system uses ChromaDB as a vector database backend for storing and retrieving face embeddings. ChromaDB provides efficient similarity search capabilities that are essential for high-performance face recognition.

The tools in this repository help you:
- Run the system with ChromaDB enabled
- Debug issues related to ChromaDB
- Optimize ChromaDB performance
- Fix database corruption or other issues

## Running the System

To run the face recognition system with ChromaDB backend:

```bash
# Basic run with ChromaDB backend
python -m src.main --recognizer-backend chromadb

# Run with debug mode
python -m src.main --recognizer-backend chromadb --debug

# Run with performance optimizations
python -m src.main --recognizer-backend chromadb --optimize-performance

# Run with in-memory database (faster but not persistent)
python -m src.main --recognizer-backend chromadb --in-memory-db
```

Or use the debug wrapper script for a comprehensive debugging session:

```bash
./debug_wrapper.sh
```

## Debugging Tools

### Debug Wrapper (`debug_wrapper.sh`)

A shell script that runs the face recognition system with debug options and captures output for analysis.

```bash
chmod +x debug_wrapper.sh
./debug_wrapper.sh
```

Features:
- Enables debug mode
- Optimizes cache for better debugging
- Captures all output to a timestamped log file
- Extracts and displays errors from the log

### ChromaDB Debugger (`debug_chromadb.py`)

A Python script for diagnosing issues with the ChromaDB backend.

```bash
python debug_chromadb.py
```

This tool checks:
1. ChromaDB installation and version
2. Database connection
3. Embedding storage and retrieval
4. Collection integrity
5. Query functionality

### ChromaDB Fixer (`fix_chromadb.py`)

A tool for fixing common ChromaDB issues.

```bash
# Show help
python fix_chromadb.py --help

# Verify database integrity
python fix_chromadb.py verify

# Export embeddings to a backup file
python fix_chromadb.py export

# Import embeddings from a backup file
python fix_chromadb.py import

# Rebuild the database (preserving data)
python fix_chromadb.py rebuild

# Reset the database (delete and recreate)
python fix_chromadb.py reset
```

## Optimization Tools

### ChromaDB Optimizer (`optimize_chromadb.py`)

A Python script for optimizing ChromaDB performance.

```bash
python optimize_chromadb.py
```

This tool implements:
1. Batch processing for embeddings
2. Memory usage optimization
3. Query performance enhancements
4. Connection pooling and caching
5. Disk space optimization

## Common Issues

### 1. Import and Dependency Issues

**Symptoms:**
- ImportError or ModuleNotFoundError
- "ChromaDB is not installed but is required" error message

**Solution:**
```bash
pip install chromadb>=0.4.18
```

### 2. Database Connection Issues

**Symptoms:**
- "Failed to connect to ChromaDB" errors
- Hanging or timing out when accessing ChromaDB

**Solution:**
1. Try with in-memory database: `--in-memory-db`
2. Check ChromaDB cache directory permissions
3. Reset database: `python fix_chromadb.py reset`

### 3. Recognition Problems

**Symptoms:**
- Faces detected but not recognized
- Wrong person identified

**Solution:**
1. Adjust similarity threshold: `--distance-threshold 0.6`
2. Verify embeddings: `python debug_chromadb.py`
3. Rebuild database: `python fix_chromadb.py rebuild`

### 4. Performance Issues

**Symptoms:**
- Very slow processing
- High memory usage

**Solution:**
1. Use in-memory database: `--in-memory-db`
2. Optimize database: `python optimize_chromadb.py`
3. Adjust worker count: `--max-workers 4`

## Performance Recommendations

1. **Hardware Requirements**
   - CPU: 4+ cores recommended
   - RAM: 8GB+ recommended
   - SSD storage for database files

2. **Memory Optimization**
   - Use in-memory database for best performance (but data won't persist)
   - Adjust batch sizes to balance memory usage and performance

3. **Parallel Processing**
   - Set max-workers to match your CPU cores (default: 4)
   - Enable parallel processing: `--parallel`

4. **Caching**
   - Enable cache optimization: `--optimize-cache`
   - Preprocess test images for faster recognition

5. **ChromaDB Configuration**
   - Use latest ChromaDB version (0.4.18+)
   - Consider using a dedicated machine for large datasets

## Advanced Debugging

For persistent or complex issues, the debug plan provides a systematic approach:

1. **Isolate the problem**
   - Run with minimal inputs (one contestant, one short video)
   - Use the debug wrapper script with debug flags enabled

2. **Enable verbose logging**
   - Use `--debug` flag to get detailed logs
   - Check log files for patterns or recurring errors

3. **Step-by-step troubleshooting**
   - Start with testing individual components
   - Test face detection separately
   - Test face recognition with known good images
   - Test ChromaDB functionality independently

4. **Fix and validate**
   - Make one change at a time
   - Run tests after each change
   - Document successful fixes

For detailed debugging steps, see the `debug_plan.md` file.