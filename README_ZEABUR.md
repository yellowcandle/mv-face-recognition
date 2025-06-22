# 🚀 Zeabur Deployment Guide

## Overview
This guide covers deploying the MV Face Recognition System to Zeabur cloud platform.

## Prerequisites
- Zeabur account ([zeabur.com](https://zeabur.com))
- Git repository with your code
- Docker Hub account (optional, for custom images)

## Quick Deploy

### Option 1: Direct GitHub Deploy
1. **Connect Repository**: Link your GitHub repository to Zeabur
2. **Auto-Deploy**: Zeabur will automatically detect the `Dockerfile` and deploy
3. **Configure**: Set environment variables through Zeabur dashboard

### Option 2: Docker Deploy
1. **Build Image**: `docker build -t mv-face-recognition .`
2. **Push to Registry**: Push to Docker Hub or Zeabur registry
3. **Deploy**: Create service from image in Zeabur dashboard

## Configuration

### Environment Variables
Set these in your Zeabur service settings:

```bash
# Required
GRADIO_SERVER_NAME=0.0.0.0
GRADIO_SERVER_PORT=8080
GRADIO_SHARE=false
GRADIO_DEBUG=false

# Performance
NO_ALBUMENTATIONS_UPDATE=1
INSIGHTFACE_DISABLE_LOGGING=1

# Optional Authentication
GRADIO_AUTH=username:password
```

### Resources
Recommended Zeabur plan settings:
- **Memory**: 4GB+ (for AI models)
- **Storage**: 20GB+ (for video processing)
- **CPU**: 2+ cores

## Features Optimized for Zeabur

### ✅ Improvements over HuggingFace Spaces
- **No GPU quotas**: Continuous processing without interruption
- **Better storage**: 20GB+ vs 50GB limit on HF Spaces
- **1080p videos**: Full quality video assets supported
- **Faster startup**: No cold start delays
- **Custom domains**: Professional deployment URLs
- **Persistent storage**: Data survives deployments

### 🎥 Video Quality Settings
- Default quality: **1080p** (upgraded from 720p on HF Spaces)
- Available options: 480p, 720p, 1080p
- Automatic quality selection based on available bandwidth

### ⚡ Performance Optimizations
- Multi-threaded processing (20 threads vs 10 on HF Spaces)
- Better video download workers (2 vs 1 on HF Spaces)
- Standard cloud GPU/CPU detection
- No artificial quota limitations

## Deployment Steps

### 1. Prepare Repository
```bash
# Clone and update
git clone <your-repo>
cd mv-face-recognition

# Ensure all Zeabur files are present
ls Dockerfile zeabur.json .env.example
```

### 2. Deploy to Zeabur
1. **Sign up** at [zeabur.com](https://zeabur.com)
2. **Create Project**: New project in dashboard
3. **Add Service**: Choose "Git Repository" or "Docker Image"
4. **Configure**: Set environment variables and resources
5. **Deploy**: Click deploy and wait for build

### 3. Post-Deployment Setup
1. **Custom Domain**: Set up your domain (optional)
2. **SSL Certificate**: Automatically provided by Zeabur
3. **Monitoring**: Use Zeabur's built-in metrics
4. **Scaling**: Adjust resources as needed

## File Structure
```
mv-face-recognition/
├── Dockerfile              # Multi-stage optimized build
├── docker-compose.yml      # Local development
├── zeabur.json            # Zeabur platform config
├── requirements.txt       # Python dependencies (HF-free)
├── .env.example          # Environment template
├── app.py                # Main entry point (Zeabur optimized)
├── gradio_app.py         # UI interface (no HF decorators)
└── README_ZEABUR.md      # This file
```

## Troubleshooting

### Common Issues

**Build Failed**
- Check Dockerfile syntax
- Verify all requirements are installable
- Increase build timeout in Zeabur settings

**App Won't Start**
- Check port configuration (must be 8080)
- Verify environment variables
- Check logs in Zeabur dashboard

**Out of Memory**
- Increase memory allocation in Zeabur
- Consider using CPU-only mode for large videos
- Optimize video processing frame skip

**Slow Performance**
- Upgrade to higher CPU/memory plan
- Enable GPU if available
- Check video quality settings

### Performance Tips

1. **Use GPU plans** when available for faster processing
2. **Optimize video quality** based on your use case
3. **Set appropriate frame skip** for real-time processing
4. **Use persistent volumes** for caching face embeddings
5. **Monitor resource usage** in Zeabur dashboard

## Support

- **Zeabur Docs**: [docs.zeabur.com](https://docs.zeabur.com)
- **Discord**: Zeabur community server
- **GitHub Issues**: Report bugs in your repository

## Migration from HuggingFace Spaces

### What's Removed
- ❌ `spaces` decorators and ZeroGPU handling
- ❌ HF dataset integration
- ❌ GPU quota management
- ❌ HF-specific environment detection

### What's Added
- ✅ Standard cloud deployment patterns
- ✅ Docker optimization for faster builds
- ✅ Better resource configuration
- ✅ 1080p video support by default
- ✅ Professional deployment features

## Cost Comparison

| Feature | HuggingFace Spaces | Zeabur |
|---------|-------------------|---------|
| **Storage** | 50GB limit | 20GB+ configurable |
| **GPU Access** | Quota limited | Continuous (paid plans) |
| **Custom Domain** | ❌ | ✅ |
| **Persistent Data** | Limited | ✅ Full persistence |
| **Build Time** | Slow | Fast |
| **Professional Features** | Basic | Advanced |

Zeabur offers better value for production deployments with more predictable costs and features.