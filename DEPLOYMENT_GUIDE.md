# 🚀 Deployment Guide - MV Face Recognition

This guide covers deploying the MV Face Recognition system to Cloudflare Workers, Modal.com, and other platforms.

## 📋 Pre-Deployment Checklist

### 1. System Testing
```bash
# Test video processing locally
python scripts/process_videos_local.sh

# Test frontend build
cd frontend-svelte && npm run build

# Verify configuration
cat config.json  # Should have frame_skip: 5 for dense processing
```

### 2. Video Processing with Modal.com
```bash
# Setup Modal environment
./scripts/process_videos_modal.sh --setup

# Sync local data to Modal
./scripts/process_videos_modal.sh --sync-data

# Process videos on Modal's GPU infrastructure
./scripts/process_videos_modal.sh

# Download processed results
./scripts/process_videos_modal.sh --download-results
```

### 3. Cloudflare Workers Preparation
```bash
# Install Wrangler CLI
npm install -g wrangler

# Authenticate with Cloudflare
wrangler login

# Verify configuration
cat wrangler.toml
```

## ☁️ Cloudflare Workers Deployment (Recommended)

### Step 1: Build Frontend

```bash
# Navigate to frontend directory
cd frontend-svelte

# Install dependencies
npm install

# Build for static deployment
npm run build

# Copy build files to worker directory
cd ..
mkdir -p worker/public
cp -r frontend-svelte/build/* worker/public/
```

### Step 2: Deploy Worker

```bash
# Deploy to Cloudflare Workers
wrangler deploy

# Your app will be available at:
# https://mv-face-recognition.your-subdomain.workers.dev
```

### Step 3: Upload Videos to R2

```bash
# Upload processed videos to Cloudflare R2
node scripts/upload-to-r2.js

# Videos will be available at:
# https://your-worker.com/videos/[filename]
```

### Step 4: Upload Metadata to KV

```bash
# Upload contestant data and metadata
node scripts/upload-metadata.js

# API endpoints will serve data from KV store
```

### Configuration

Your `wrangler.toml` should include:
```toml
name = "mv-face-recognition"
main = "worker/index.js"
compatibility_date = "2024-11-08"
compatibility_flags = ["nodejs_compat"]

[[r2_buckets]]
binding = "VIDEOS_BUCKET"
bucket_name = "mv-face-recognition-videos"

[[kv_namespaces]]
binding = "METADATA_KV"
id = "your-kv-namespace-id"
```

## 🧠 Modal.com Video Processing

### Step 1: Setup Modal Environment

```bash
# Install Modal CLI
pip install modal

# Setup authentication
modal setup

# Create volume for persistent storage
modal volume create mv-face-recognition-data
```

### Step 2: Process Videos

```bash
# Sync local data to Modal
./scripts/process_videos_modal.sh --sync-data

# Process videos with GPU acceleration
./scripts/process_videos_modal.sh

# Download processed results
./scripts/process_videos_modal.sh --download-results
```

### Configuration

Modal processing supports:
- **GPU Acceleration**: NVIDIA A100/V100 GPUs
- **Batch Processing**: Multiple videos in parallel
- **Persistent Storage**: Modal volumes for data persistence
- **Cost Optimization**: Pay only for GPU time used

### Processing Options

```bash
# Process with custom similarity threshold
./scripts/process_videos_modal.sh -s 0.3

# Force reprocess all videos
./scripts/process_videos_modal.sh -f

# Process single video
./scripts/process_videos_modal.sh -v "video.mp4"

# Refresh embeddings before processing
./scripts/process_videos_modal.sh --refresh-embeddings
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

### Cloudflare Workers Deployment
- [ ] Frontend builds successfully (`npm run build`)
- [ ] Worker deploys without errors (`wrangler deploy`)
- [ ] R2 bucket is created and videos uploaded
- [ ] KV namespace is configured with metadata
- [ ] API endpoints respond correctly
- [ ] Video streaming works with range requests
- [ ] CORS is properly configured

### Modal.com Processing
- [ ] Modal CLI is authenticated (`modal setup`)
- [ ] Video processing completes successfully
- [ ] Processed videos are downloaded
- [ ] Metadata files are generated correctly
- [ ] Frame skip is set to 5 for dense processing
- [ ] Embeddings are refreshed before processing

### Configuration
- [ ] `config.json` has `frame_skip: 5`
- [ ] `wrangler.toml` includes R2 and KV bindings
- [ ] Upload scripts are configured correctly
- [ ] Worker handles missing R2 gracefully
- [ ] Error handling is implemented
- [ ] Security measures are in place

🎉 **Ready to deploy!** Your MV Face Recognition system is now ready for serverless production deployment with Cloudflare Workers and Modal.com GPU processing.