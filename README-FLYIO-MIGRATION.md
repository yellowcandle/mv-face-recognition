# MV Face Recognition - Fly.io Migration Guide

This guide covers the complete migration of the MV Face Recognition system to Fly.io platform. The migration maintains all existing functionality while leveraging cloud infrastructure for improved scalability and availability.

## 🚀 Quick Start

```bash
# 1. Install flyctl and authenticate
curl -L https://fly.io/install.sh | sh
fly auth login

# 2. Create volumes and deploy everything
./deploy-to-flyio.sh --create-volumes

# 3. Access your applications
# Backend: https://mv-face-recognition-backend.fly.dev
# Frontend: https://mv-face-recognition-frontend.fly.dev
```

## 📋 Prerequisites

### 1. Software Requirements
- **Fly.io CLI**: Install from https://fly.io/docs/hands-on/install-flyctl/
- **Docker**: For local testing and building
- **Git**: For version control (already available)

### 2. Fly.io Account Setup
```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

# Login to Fly.io
fly auth login

# Verify authentication
fly auth whoami
```

### 3. Critical Data Verification
The migration script automatically checks for critical files:

- ✅ `metadata/contestant_info.csv` - **CRITICAL** (96 contestants mapping)
- ✅ `source/photo/contestants/` - Face embeddings (95+ contestants)
- ✅ `config.json` - Application configuration
- ✅ Videos in `source/videos/` directory

## 🏗️ Architecture Overview

The Fly.io deployment uses a multi-app architecture:

```
┌─────────────────────────────────────────────────────────────────┐
│                          Fly.io Platform                        │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │   Frontend App  │  │   Backend API   │  │  Data Volumes   │  │
│  │  (Vue.js/Nginx) │  │   (FastAPI)     │  │  (Persistent)   │  │
│  │                 │  │                 │  │                 │  │
│  │  Port: 3000     │  │  Port: 8000     │  │  Mounted at     │  │
│  │                 │  │                 │  │  /data/*        │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Applications
- **Backend**: `mv-face-recognition-backend.fly.dev`
  - FastAPI with face recognition services
  - **NVIDIA A10 GPU acceleration** for ML workloads
  - CUDA 11.8 with PyTorch and ONNX Runtime GPU support
  - Persistent volumes for data storage

- **Frontend**: `mv-face-recognition-frontend.fly.dev`
  - Vue.js application served via Nginx
  - Optimized for static content delivery

### Persistent Volumes
- **Videos Volume**: Source and processed videos
- **Embeddings Volume**: Contestant face embeddings
- **Metadata Volume**: Critical CSV files and JSON metadata
- **ChromaDB Volume**: Vector database storage

## 🛠️ Deployment Options

### Option 1: Complete Deployment (Recommended)
```bash
# Deploy everything with volume creation
./deploy-to-flyio.sh --create-volumes
```

### Option 2: Backend Only
```bash
# Deploy only the backend API
./deploy-to-flyio.sh --backend-only --create-volumes
```

### Option 3: Frontend Only
```bash
# Deploy only the frontend (requires backend to be deployed first)
./deploy-to-flyio.sh --frontend-only
```

### Option 4: Dry Run
```bash
# See what would be deployed without making changes
./deploy-to-flyio.sh --dry-run
```

## 📦 Local Testing

Before deploying to Fly.io, test the containerized setup locally:

```bash
# Build and run with Docker Compose
docker-compose up --build

# Test endpoints
curl http://localhost:8000/health      # Backend health
curl http://localhost:3000             # Frontend

# Clean up
docker-compose down
```

## 🔧 Configuration Files

### Fly.io Configurations
- `fly.backend.toml` - Backend application configuration
- `fly.frontend.toml` - Frontend application configuration

### Docker Files
- `Dockerfile.backend` - Backend container build
- `Dockerfile.frontend` - Frontend container build
- `docker-compose.yml` - Local testing environment

### Key Features
- **CUDA GPU Acceleration**: NVIDIA A10 GPU with CUDA 11.8 support
- **Health Checks**: Comprehensive monitoring for both apps
- **Auto-scaling**: Machines start/stop based on traffic
- **Volume Mounts**: Persistent storage for critical data
- **Security**: HTTPS enforcement and security headers

## 🚀 GPU Acceleration Configuration

### CUDA Setup
The deployment is configured for high-performance face recognition using NVIDIA GPU acceleration:

- **Base Image**: `nvidia/cuda:11.8-devel-ubuntu22.04`
- **GPU Model**: NVIDIA A10 (24GB VRAM)
- **CUDA Version**: 11.8 with cuDNN support
- **ML Libraries**: PyTorch and ONNX Runtime with CUDA support

### Hardware Benefits
- **Face Detection**: ~10x faster inference with InsightFace on GPU
- **Embedding Generation**: Parallel processing of multiple faces
- **Video Processing**: GPU-accelerated frame processing
- **Batch Operations**: Efficient processing of multiple videos

### Verification
Check GPU acceleration is working:

```bash
# SSH into backend machine
fly ssh console --app mv-face-recognition-backend

# Verify CUDA availability
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"
python -c "import torch; print(f'GPU count: {torch.cuda.device_count()}')"

# Check ONNX Runtime providers
python -c "import onnxruntime; print(onnxruntime.get_available_providers())"
```

## 📊 Monitoring and Management

### Application Status
```bash
# Check application status
fly status --app mv-face-recognition-backend
fly status --app mv-face-recognition-frontend

# View logs
fly logs --app mv-face-recognition-backend
fly logs --app mv-face-recognition-frontend

# Monitor metrics
fly dashboard mv-face-recognition-backend
```

### Health Endpoints
- Backend Health: `https://mv-face-recognition-backend.fly.dev/health`
- Backend Ready: `https://mv-face-recognition-backend.fly.dev/ready`
- Frontend: `https://mv-face-recognition-frontend.fly.dev`

### SSH Access
```bash
# Connect to backend machine
fly ssh console --app mv-face-recognition-backend

# Check mounted volumes
ls -la /data/

# Validate critical files
ls -la /data/metadata/contestant_info.csv
```

## 💾 Data Migration Process

### Automatic Migration
The deployment script handles basic data migration:

1. **Critical Files**: Copies `contestant_info.csv` and configuration
2. **Validation**: Runs embedding validation script
3. **Health Checks**: Ensures all services are operational

### Manual Data Upload
For large video files and embeddings:

```bash
# Connect to the backend machine
fly ssh console --app mv-face-recognition-backend

# Upload files using fly ssh (from your local machine)
# Note: Use rsync or scp for large transfers

# Or copy from local to machine
tar -czf embeddings.tar.gz source/photo/contestants/
fly ssh console --app mv-face-recognition-backend < embeddings.tar.gz
```

### Embedding Refresh
After data migration, refresh the face recognition database:

```bash
# SSH into backend
fly ssh console --app mv-face-recognition-backend

# Run embedding refresh
cd /app
python fix_embeddings.py --all --force

# Verify embeddings
python check_stored_embeddings.py
```

## 🔐 Security and Secrets

### Environment Variables
```bash
# Backend secrets
fly secrets set --app mv-face-recognition-backend \
  SECRET_KEY="your-secret-key" \
  ENVIRONMENT="production"

# Frontend configuration
fly secrets set --app mv-face-recognition-frontend \
  VITE_API_BASE_URL="https://mv-face-recognition-backend.fly.dev"
```

### Network Security
- All traffic is HTTPS-enforced
- Private internal networking between apps
- CORS configured for secure cross-origin requests
- Security headers implemented in Nginx

## 📈 Scaling and Performance

### Automatic Scaling
```bash
# Scale based on traffic
fly scale count 2 --app mv-face-recognition-backend

# Scale with specific memory
fly scale memory 2048 --app mv-face-recognition-backend

# Enable GPU for ML workloads (if needed)
fly machines create --app mv-face-recognition-backend --vm-gpu-kind a10
```

### Performance Optimization
- **GPU**: NVIDIA A10 GPU with CUDA 11.8 for ML acceleration
- **CPU**: 4 performance CPUs for supporting tasks
- **Memory**: 8GB for backend (increased for GPU workloads), 512MB for frontend
- **CUDA Libraries**: PyTorch and ONNX Runtime with GPU support
- **Caching**: Static asset caching in Nginx

## 🚨 Troubleshooting

### Common Issues

#### 1. Volume Mount Issues
```bash
# Check if volumes are attached
fly volumes list

# Attach volume to app
fly volumes attach mv_videos_vol --app mv-face-recognition-backend
```

#### 2. Health Check Failures
```bash
# Check logs for errors
fly logs --app mv-face-recognition-backend

# SSH and debug
fly ssh console --app mv-face-recognition-backend
curl localhost:8000/health
```

#### 3. Missing Critical Files
```bash
# Check critical files exist
fly ssh console --app mv-face-recognition-backend
ls -la /data/metadata/contestant_info.csv
ls -la /data/embeddings/contestants/
```

#### 4. Face Recognition Not Working
```bash
# Refresh embeddings
fly ssh console --app mv-face-recognition-backend
cd /app && python fix_embeddings.py --all --force

# Check ChromaDB
python -c "import chromadb; print(chromadb.PersistentClient(path='/data/chroma_db').list_collections())"
```

#### 5. GPU Acceleration Issues
```bash
# Check GPU availability
fly ssh console --app mv-face-recognition-backend

# Verify CUDA installation
nvidia-smi

# Check CUDA in Python
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name())"

# Verify ONNX Runtime GPU provider
python -c "import onnxruntime as ort; print('CUDAExecutionProvider' in ort.get_available_providers())"

# Check face detector is using GPU
python -c "
from src.core.face_detector import FaceDetector
detector = FaceDetector()
print(f'Face detector providers: {detector.model.providers}')
"
```

### Log Analysis
```bash
# Follow logs in real-time
fly logs --app mv-face-recognition-backend -f

# Filter logs by level
fly logs --app mv-face-recognition-backend | grep ERROR

# Check specific time range
fly logs --app mv-face-recognition-backend --since 1h
```

## 🔄 Updates and Rollbacks

### Deploying Updates
```bash
# Update backend code
./deploy-to-flyio.sh --backend-only

# Update frontend code
./deploy-to-flyio.sh --frontend-only
```

### Rollback Strategy
```bash
# View release history
fly releases --app mv-face-recognition-backend

# Rollback to previous version
fly releases rollback <version> --app mv-face-recognition-backend
```

### Volume Snapshots
```bash
# Create volume snapshot
fly volumes snapshots create mv_embeddings_vol

# List snapshots
fly volumes snapshots list mv_embeddings_vol

# Restore from snapshot (if needed)
fly volumes restore mv_embeddings_vol --snapshot <snapshot-id>
```

## 💰 Cost Management

### Resource Optimization
- **Development**: Consider CPU-only machines for cost savings during development
- **Production**: NVIDIA A10 GPU for optimal face recognition performance
- **Auto-stop**: GPU machines automatically stop when idle to minimize costs
- **Cost Alert**: GPU machines are more expensive (~$1.50/hour for A10), monitor usage

### Volume Sizing
- **Videos**: Size based on your video library
- **Embeddings**: 10GB (sufficient for 100+ contestants)
- **Metadata**: 5GB (JSON files and logs)
- **ChromaDB**: 10GB (vector database storage)

### Monitoring Costs
```bash
# View current usage
fly dashboard mv-face-recognition-backend

# Check machine sizes
fly status --app mv-face-recognition-backend
```

## 🎯 Success Criteria

### Technical Validation
- ✅ All face recognition functionality preserved
- ✅ 95+ contestant embeddings successfully migrated
- ✅ Video processing pipeline operational
- ✅ Frontend-backend connectivity established
- ✅ Critical data (`metadata/contestant_info.csv`) preserved

### Performance Validation
- ✅ API response times < 2 seconds
- ✅ Video processing within acceptable timeframes
- ✅ 99.9% uptime with proper monitoring
- ✅ Auto-scaling functional under load

### Security Validation
- ✅ Data encryption in transit and at rest
- ✅ Secure API endpoints with rate limiting
- ✅ Private network communication
- ✅ Regular backup validation

## 📞 Support and Resources

### Fly.io Documentation
- [Fly.io Docs](https://fly.io/docs/)
- [Volume Management](https://fly.io/docs/reference/volumes/)
- [Machine API](https://fly.io/docs/machines/)

### Project Resources
- **Design Document**: `DESIGN.md` (Fly.io Migration section)
- **Constraints**: `CLAUDE.md` (Critical file protections)
- **Deployment Guide**: `DEPLOYMENT_GUIDE.md` (Alternative platforms)

### Community Support
- [Fly.io Community Forum](https://community.fly.io/)
- [GitHub Issues](https://github.com/superfly/flyctl/issues)

---

## ⚠️ Important Notes

### Critical Data Protection
This migration respects all constraints from `CLAUDE.md`:
- **Never deletes** `metadata/contestant_info.csv`
- **Preserves** all contestant embeddings
- **Maintains** existing file structure
- **Validates** data integrity throughout the process

### Migration Benefits
- **Scalability**: Auto-scaling based on demand
- **Reliability**: Global edge network with redundancy
- **Performance**: GPU acceleration for ML workloads
- **Maintainability**: Containerized deployment with easy updates
- **Monitoring**: Built-in observability and alerting

The migration successfully maintains the existing architecture while enhancing it with cloud-native capabilities. 