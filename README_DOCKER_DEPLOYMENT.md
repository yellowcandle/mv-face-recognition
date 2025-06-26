# MV Face Recognition - Docker & Cloud Deployment Guide

## 🚀 Quick Deploy Options

### Option 1: Zeabur One-Click Deploy (Recommended)
[![Deploy on Zeabur](https://zeabur.com/button.svg)](https://zeabur.com/templates/QJJSZV)

### Option 2: Docker Compose (Local/VPS)
```bash
git clone https://github.com/your-username/mv-face-recognition.git
cd mv-face-recognition
docker-compose up -d --build
```

## 📋 Prerequisites

- Docker & Docker Compose installed
- At least 4GB RAM (8GB recommended for ML models)
- 10GB+ storage for videos and models
- (For Zeabur) Free Zeabur account

## 🐳 Docker Deployment Options

### 1. Development with Hot Reloading
```bash
# Start development environment
docker-compose -f docker-compose.dev.yml up --build

# Access services:
# - Frontend: http://localhost:5173 (with hot reload)
# - Backend: http://localhost:8000 (with auto-reload)
# - API Docs: http://localhost:8000/docs
```

### 2. Production (Local/VPS)
```bash
# Build and start production containers
docker-compose up -d --build

# Access application
# - Main App: http://localhost:3000
# - API (proxied): http://localhost:3000/api
# - Direct API: http://localhost:8000

# Monitor logs
docker-compose logs -f

# Stop services
docker-compose down
```

### 3. Single Container (Zeabur/Cloud)
```bash
# Build combined container
docker build -t mv-face-recognition .

# Run locally
docker run -p 80:80 \
  -v $(pwd)/source/videos:/app/source/videos \
  -v $(pwd)/source/photo/contestants:/app/source/photo/contestants \
  mv-face-recognition
```

## ☁️ Zeabur Cloud Deployment

### Quick Deploy Steps:
1. **Fork this repository** to your GitHub account
2. **Sign up** for [Zeabur](https://zeabur.com) (free tier available)
3. **Connect GitHub** to Zeabur
4. **Click Deploy Button** or import repository manually
5. **Configure environment variables** (see below)
6. **Upload video files** to mounted volumes
7. **Start processing!**

### Environment Variables:
```env
# Required for backend
PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
PYTHONUNBUFFERED=1

# Optional optimizations
PORT=80
NODE_ENV=production
```

### Zeabur Features Used:
- ✅ **Automatic builds** from Git push
- ✅ **Zero-downtime deployments**
- ✅ **Auto-scaling** based on traffic
- ✅ **Persistent volumes** for data storage
- ✅ **Custom domains** and SSL certificates
- ✅ **Build caching** for faster deployments

## 📁 Data Persistence

### Local Docker Volumes:
```bash
# List volumes
docker volume ls

# Inspect volume
docker volume inspect mv-face-recognition_backend_data

# Backup data
docker run --rm -v mv-face-recognition_backend_data:/data -v $(pwd):/backup alpine tar czf /backup/backup.tar.gz /data
```

### Zeabur Persistent Storage:
- **Videos**: Automatically mounted to `/app/source/videos`
- **Contestant Photos**: Mounted to `/app/source/photo/contestants`
- **Database**: ChromaDB data persisted in `/app/data`
- **Models**: ML models cached between deployments

## 🔧 Configuration

### Docker Environment Variables:
```yaml
# docker-compose.yml
environment:
  - PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
  - PYTHONUNBUFFERED=1
  - RELOAD=false  # Set to true for development
```

### Frontend Configuration:
```javascript
// Frontend automatically detects API endpoint
const API_BASE = process.env.NODE_ENV === 'production' 
  ? '/api'  // Proxied through Nginx
  : 'http://localhost:8000/api';  // Direct connection
```

## 🛠️ Troubleshooting

### Common Issues:

**1. Out of Memory**
```bash
# Check container memory usage
docker stats

# Increase Docker memory limit to 8GB+
# Docker Desktop → Settings → Resources → Memory
```

**2. Model Download Failures**
```bash
# Check backend logs
docker-compose logs backend

# Models download on first startup (may take 5-10 minutes)
# Ensure stable internet connection
```

**3. Video Upload Issues**
```bash
# Check volume mounts
docker-compose exec backend ls -la /app/source/videos

# Ensure proper permissions
sudo chown -R 1000:1000 ./source/videos
```

**4. WebSocket Connection Errors**
```bash
# Check if ports are properly exposed
docker-compose ps

# Verify nginx configuration for WebSocket proxy
docker-compose exec frontend cat /etc/nginx/conf.d/default.conf
```

### Performance Optimization:

**1. For High-Traffic Deployments:**
```yaml
# docker-compose.yml
backend:
  deploy:
    replicas: 3
    resources:
      limits:
        memory: 2G
      reservations:
        memory: 1G
```

**2. For GPU Acceleration:**
```yaml
# Add to backend service
runtime: nvidia
environment:
  - NVIDIA_VISIBLE_DEVICES=all
```

## 📊 Monitoring

### Health Checks:
```bash
# Backend health
curl http://localhost:8000/health

# Frontend health
curl http://localhost:3000/health

# Combined container health
curl http://localhost/health
```

### Performance Monitoring:
```bash
# Resource usage
docker stats

# Application logs
docker-compose logs -f --tail=100

# Memory monitoring
python3 monitor_memory.py  # From project root
```

## 🚀 Deployment Strategies

### Blue-Green Deployment:
```bash
# Build new version
docker-compose -f docker-compose.yml build

# Start with different project name
docker-compose -p mv-face-recognition-blue up -d

# Switch traffic after testing
# Update load balancer or reverse proxy
```

### Rolling Updates:
```bash
# Update single service
docker-compose up -d --no-deps backend

# Zero-downtime frontend update
docker-compose up -d --no-deps --scale frontend=2 frontend
docker-compose up -d --no-deps --scale frontend=1 frontend
```

## 📚 Additional Resources

- **Docker Documentation**: [docs.docker.com](https://docs.docker.com)
- **Zeabur Documentation**: [docs.zeabur.com](https://docs.zeabur.com)
- **FastAPI Docker Guide**: [fastapi.tiangolo.com/deployment/docker](https://fastapi.tiangolo.com/deployment/docker/)
- **Svelte Production Build**: [kit.svelte.dev/docs/building-your-app](https://kit.svelte.dev/docs/building-your-app)

## 🆘 Support

If you encounter issues:
1. **Check logs** first: `docker-compose logs -f`
2. **Verify volumes** are properly mounted
3. **Ensure sufficient resources** (RAM/storage)
4. **Open an issue** on GitHub with logs and configuration

---

**Happy Deploying! 🎉**