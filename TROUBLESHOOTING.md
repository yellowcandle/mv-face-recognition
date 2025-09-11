# Troubleshooting Guide

## Model Loading Issues

### Problem: Cannot find model files

**Error message:**
```
Error initializing face recognition model: [ONNXRuntimeError] : 7 : INVALID_PROTOBUF : Load model failed
```

**Solutions:**

1. **Use the model finder utility:**
   ```bash
   # Find and download missing models
   python run_model_finder.py --force
   ```

2. **Manually download the models:**
   ```bash
   # Force re-download all models
   python download_models.py --force
   ```

3. **Check model directories:**
   Make sure the following files exist in the `models/` directory:
   - `arcface_r50.onnx` (face recognition model)
   - `face_detection_yunet.onnx` (face detection model)
   - `face_recognition_sface.onnx` (alternate face recognition model)

### Problem: Model corruption or incompatibility

**Error message:**
```
[ONNXRuntimeError] : 1 : FAIL : Load model failed: Invalid GraphProto
```

**Solutions:**

1. **Force re-download the models:**
   ```bash
   python download_models.py --force
   ```

2. **Try alternative models:**
   ```bash
   # Use alternative models
   python -m src.main --use-tracking
   ```

## ChromaDB Issues

### Problem: ChromaDB initialization failure

**Error message:**
```
Error: Failed to initialize ChromaDB collection
```

**Solutions:**

1. **Clear ChromaDB cache:**
   ```bash
   rm -rf cache/chromadb/*
   ```

2. **Run with in-memory ChromaDB:**
   ```bash
   python -m src.main --in-memory-db
   ```

### Problem: Embedding dimension mismatch

**Error message:**
```
Error adding batch embeddings: Embedding dimension 512 does not match collection dimensionality 128
```

**Solutions:**

1. **Clear ChromaDB collection:**
   ```bash
   # Remove the ChromaDB database and start fresh
   rm -rf cache/chromadb/*
   ```

2. **Use the standard backend instead:**
   ```bash
   # Use the standard embedding-matching backend
   python -m src.main --recognizer-backend standard
   ```

3. **Update and run with fixed code:**
   The latest version has been updated to handle dimension mismatches by automatically resizing embeddings to match the collection dimensionality. Make sure you're using the latest version of the code.

## Performance Issues

### Problem: Slow processing speed

**Solutions:**

1. **Enable face tracking:**
   ```bash
   python -m src.main --use-tracking
   ```

2. **Skip more frames:**
   ```bash
   python -m src.main --frame-skip 10
   ```

3. **Use in-memory database:**
   ```bash
   python -m src.main --in-memory-db
   ```

4. **Optimize cache:**
   ```bash
   python -m src.main --optimize-cache
   ```

## Installation Issues

### Problem: ImportError for packages

**Error message:**
```
ImportError: No module named 'xxx'
```

**Solutions:**

1. **Make sure all requirements are installed:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Specific packages:**
   - InsightFace: `pip install insightface>=0.7.3`
   - ChromaDB: `pip install chromadb>=0.4.18`
   - ONNX Runtime: `pip install onnxruntime>=1.19.2`

### Problem: CUDA/GPU issues

**Error message:**
```
Failed to initialize CUDA execution provider
```

**Solution:**

Force CPU-only operation:
```bash
export CUDA_VISIBLE_DEVICES=""
python -m src.main
```

## Docker Issues

See [README-docker.md](README-docker.md) for Docker-specific troubleshooting.
