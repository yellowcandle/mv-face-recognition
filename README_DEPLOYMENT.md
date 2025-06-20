# Deployment Setup

## Git Repository Configuration

### GitHub Repository
- **Repository**: `yellowcandle/mv-face-recognition`
- **URL**: https://github.com/yellowcandle/mv-face-recognition.git
- **Remote**: `origin`
- **Main Branch**: `main`

### Hugging Face Spaces
- **Space**: `yellowcandle/mv-face-recognition`
- **URL**: https://huggingface.co/spaces/yellowcandle/mv-face-recognition
- **Remote**: `hf`

## Git Configuration

### User Settings
- **Name**: yellowcandle
- **Email**: 4060163+yellowcandle@users.noreply.github.com

### Active Branches
- `main` (default)
- `dev-chromadb`
- `dev-gradio`
- `improve-gradio-ui`
- `feature/enhanced-bbox-visualization`
- `feature/better-ui`
- `feature/realtime-dashboard`

### Git LFS Configuration
- Enabled for GitHub repository
- Enabled for Hugging Face Spaces with `locksverify = false`

## Hugging Face Deployment Configuration

### .hfignore File
The following files/directories are excluded from HF Spaces deployment to stay under the 1GB limit:

```
# Large video files (original)
source/videos/*.mp4
source/videos_optimized/

# Cache and temporary files
cache/embeddings/
cache/chromadb/
cache/chromadb_backup*/

# Model files
models/
*.onnx

# Large data files
recognized_frames/
*.avi
*.mov
*.mkv
```

### Deployment Strategy
- **GitHub**: Full repository with all files
- **HF Spaces**: Optimized deployment excluding large files
- **Essential HF Files**: 
  - `source/photo/contestants/` (for embeddings)
  - `source/videos_hf_clean/` (small optimized videos - 194MB)
  - `source/videos_hf_optimized/` (720p videos - 194MB)
  - Dashboard code
  - Configuration files

## GitHub Actions
- **Dependabot**: Configured for devcontainers with weekly updates
- **Previous Workflow**: `push_hf.yml` was deleted (commit ed1e2b8)

## Deployment Commands

### Push to GitHub
```bash
git push origin main
```

### Push to Hugging Face
```bash
git push hf main
```

### Sync both repositories
```bash
git push origin main && git push hf main
```

## Recent Fixes (2024-06-20)

### Video Deployment Issue
- **Problem**: Videos were missing from HF Spaces deployment
- **Cause**: `.hfignore` was excluding ALL `.mp4` files globally
- **Solution**: Changed to only exclude `source/videos/*.mp4` (large originals)
- **Result**: Now allows optimized videos in `source/videos_hf_clean/` and `source/videos_hf_optimized/`

### Configuration Optimizations
- Added video directory caching to prevent redundant scanning
- Reduced startup logging noise and repeated messages
- Fixed dashboard import error handling
