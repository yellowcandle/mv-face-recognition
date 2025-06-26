# 🚀 Deployment Guide - MV Face Recognition

This guide covers deploying the MV Face Recognition system to Hugging Face Spaces and other platforms.

## 📋 Pre-Deployment Checklist

### 1. System Testing
```bash
# Run the test suite
python test_system.py

# Test Gradio interface locally
python gradio_app.py

# Verify batch processing works
python batch_process_videos.py --dry-run
```

### 2. Data Preparation
```bash
# Pre-process videos for deployment
python batch_process_videos.py

# Verify outputs
ls processed_videos/  # Should contain annotated MP4s
ls metadata/         # Should contain JSON files
ls clips/           # Should contain highlight clips
```

### 3. File Size Optimization
```bash
# Check total size
du -sh processed_videos/ metadata/ clips/

# Compress videos if needed (optional)
ffmpeg -i input.mp4 -crf 28 -preset medium output.mp4
```

## 🤗 Hugging Face Spaces Deployment

### Step 1: Create New Space

1. Go to [Hugging Face Spaces](https://huggingface.co/spaces)
2. Click "Create new Space"
3. Fill in details:
   - **Space name**: `mv-face-recognition`
   - **License**: `MIT`
   - **SDK**: `Gradio`
   - **Hardware**: `CPU basic` (upgrade to GPU if needed)

### Step 2: Repository Setup

```bash
# Clone your new space
git clone https://huggingface.co/spaces/your-username/mv-face-recognition
cd mv-face-recognition

# Copy files from your development directory
cp /path/to/your/project/app.py .
cp /path/to/your/project/gradio_app.py .
cp /path/to/your/project/requirements.txt .
cp /path/to/your/project/.gitattributes .
```

### Step 3: Add Core Files

```bash
# Copy source code
cp -r /path/to/your/project/src/ .

# Copy configuration
cp /path/to/your/project/config.json .

# Copy contestant embeddings
mkdir -p source/photo/contestants
cp /path/to/your/project/source/photo/contestants/*.npy source/photo/contestants/
```

### Step 4: Add Processed Data (Using Git LFS)

```bash
# Initialize Git LFS
git lfs install

# Add processed videos (these will be large)
mkdir -p processed_videos metadata clips
cp /path/to/your/project/processed_videos/*.mp4 processed_videos/
cp /path/to/your/project/metadata/*.json metadata/
cp /path/to/your/project/clips/*.mp4 clips/

# Add and commit
git add .
git commit -m "Initial deployment with pre-processed data"
git push
```

### Step 5: Configure Space Settings

Create `README.md` in the space root:
```markdown
---
title: MV Face Recognition
emoji: 🎬
colorFrom: blue
colorTo: purple
sdk: gradio
sdk_version: 4.0.0
app_file: app.py
pinned: false
license: mit
---

# MV Face Recognition

AI-powered contestant recognition in music videos with enhanced annotations.

[Full documentation and source code](https://github.com/your-username/mv-face-recognition)
```

## 🖥️ Local Development Setup

### Quick Start
```bash
# Clone the repository
git clone https://github.com/your-username/mv-face-recognition.git
cd mv-face-recognition

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Test the system
python test_system.py

# Run Gradio interface
python gradio_app.py
```

### Development Workflow
```bash
# 1. Add new videos to source/videos/
# 2. Process videos
python batch_process_videos.py --single-video "new_video.mp4"

# 3. Test locally
python gradio_app.py

# 4. Deploy to HF Spaces
git add .
git commit -m "Add new video processing results"
git push
```

## 🐳 Docker Deployment (Alternative)

### Dockerfile
```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p processed_videos metadata clips

# Expose port
EXPOSE 7860

# Run the application
CMD ["python", "app.py"]
```

### Build and Run
```bash
# Build image
docker build -t mv-face-recognition .

# Run container
docker run -p 7860:7860 mv-face-recognition
```

## ☁️ Cloud Platform Deployment

### AWS EC2
```bash
# Launch EC2 instance (t3.large or larger)
# Install Docker
sudo yum update -y
sudo yum install -y docker
sudo service docker start

# Deploy using Docker
git clone https://github.com/your-username/mv-face-recognition.git
cd mv-face-recognition
sudo docker build -t mv-face-recognition .
sudo docker run -d -p 80:7860 mv-face-recognition
```

### Google Cloud Run
```bash
# Build and push to Container Registry
gcloud builds submit --tag gcr.io/PROJECT-ID/mv-face-recognition

# Deploy to Cloud Run
gcloud run deploy --image gcr.io/PROJECT-ID/mv-face-recognition --platform managed
```

### Azure Container Instances
```bash
# Create resource group
az group create --name mv-face-recognition --location eastus

# Deploy container
az container create --resource-group mv-face-recognition \
    --name mv-face-recognition --image your-registry/mv-face-recognition \
    --dns-name-label mv-face-recognition --ports 7860
```

## 🔧 Performance Optimization

### For HF Spaces
```python
# In app.py, optimize for HF Spaces
import os

# Enable GPU if available
if os.getenv("SPACES_ZERO_GPU"):
    device = "cuda"
else:
    device = "cpu"

# Optimize memory usage
import gc
gc.collect()
```

### For Large Datasets
```bash
# Use video compression
ffmpeg -i input.mp4 -vcodec libx264 -crf 28 output.mp4

# Optimize metadata files
python -c "
import json
with open('metadata/large_file.json') as f:
    data = json.load(f)
# Remove unnecessary fields
with open('metadata/large_file.json', 'w') as f:
    json.dump(data, f, separators=(',', ':'))
"
```

## 📊 Monitoring and Analytics

### Basic Monitoring
```python
# Add to your Gradio app
import time
import logging

def log_usage(video_name, user_ip):
    logging.info(f"Video viewed: {video_name} from {user_ip}")

# In your Gradio interface
def video_change_handler(video_name, request: gr.Request):
    log_usage(video_name, request.client.host)
    return get_video_path(video_name)
```

### Advanced Analytics (Optional)
```bash
# Install analytics tools
pip install mixpanel analytics-python

# Track user interactions
analytics.track(user_id, 'Video Viewed', {
    'video_name': video_name,
    'timestamp': datetime.now()
})
```

## 🚨 Troubleshooting

### Common Deployment Issues

**Out of Memory on HF Spaces**
```python
# Reduce memory usage
import gc
gc.collect()

# Process videos in smaller batches
batch_size = 1  # Process one video at a time
```

**Large File Upload Issues**
```bash
# Ensure Git LFS is properly configured
git lfs track "*.mp4"
git lfs track "*.npy"
git add .gitattributes
```

**Slow Loading Times**
```python
# Optimize imports
import gradio as gr
# Only import heavy libraries when needed
def lazy_import():
    global cv2, np
    import cv2
    import numpy as np
```

**CUDA/GPU Issues**
```python
# Fallback to CPU
try:
    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"
except:
    device = "cpu"
```

## 📈 Scaling Considerations

### For High Traffic
1. **Use CDN**: Serve videos from a CDN
2. **Caching**: Implement Redis caching for metadata
3. **Load Balancing**: Deploy multiple instances
4. **Database**: Move to a proper database (PostgreSQL)

### For Large Video Libraries
1. **Lazy Loading**: Load videos on demand
2. **Streaming**: Use video streaming instead of full downloads
3. **Compression**: Optimize video quality vs. file size
4. **Pagination**: Implement video pagination

## 🔒 Security Considerations

### For Production
```python
# Add basic authentication
def authenticate(username, password):
    return username == "admin" and password == "secure_password"

# In Gradio interface
demo.auth = authenticate
```

### Data Privacy
- Remove personal information from logs
- Implement user consent for analytics
- Regular security audits
- Secure API endpoints

---

## ✅ Final Deployment Checklist

- [ ] All tests pass (`python test_system.py`)
- [ ] Videos are pre-processed and optimized
- [ ] Git LFS is configured for large files
- [ ] Requirements.txt includes all dependencies
- [ ] app.py is the correct entry point
- [ ] README.md has proper HF Spaces configuration
- [ ] Performance is acceptable on target hardware
- [ ] Error handling is implemented
- [ ] Monitoring/logging is configured
- [ ] Security measures are in place

🎉 **Ready to deploy!** Your MV Face Recognition system should now be ready for production use.