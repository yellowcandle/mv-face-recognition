# MV Face Recognition - Shell Scripts Guide

This guide explains how to use the shell scripts for video processing and application startup.

## 📋 Available Scripts

### 🎬 Video Processing Scripts

1. **`scripts/process_videos_local.sh`** - Process videos locally on your machine
2. **`scripts/process_videos_modal.sh`** - Process videos using Modal.com cloud infrastructure

### 🚀 Application Startup Scripts

3. **`scripts/start_backend.sh`** - Start the FastAPI backend server
4. **`scripts/start_frontend.sh`** - Start the SvelteKit frontend development server
5. **`scripts/start_app.sh`** - Start both backend and frontend servers together

## 🎬 Video Processing

### Local Processing

Process videos using your local machine's resources:

```bash
# Process all videos with default settings
./scripts/process_videos_local.sh

# Process with custom similarity threshold
./scripts/process_videos_local.sh -s 0.3

# Process a specific video
./scripts/process_videos_local.sh -v "video.mp4"

# Force reprocess all videos
./scripts/process_videos_local.sh -f

# Dry run to see what would be processed
./scripts/process_videos_local.sh -d

# Show help
./scripts/process_videos_local.sh -h
```

**Options:**
- `-s, --similarity-threshold`: Set similarity threshold (0.0-1.0, default: 0.25)
- `-f, --force-reprocess`: Force reprocessing of already processed videos
- `-v, --single-video`: Process only a specific video file
- `-d, --dry-run`: Show what would be processed without actually processing
- `-c, --config`: Path to config file (default: config.json)

### Modal.com Cloud Processing

Process videos using Modal's cloud infrastructure with GPU acceleration:

```bash
# First-time setup
./scripts/process_videos_modal.sh --setup

# Upload your data to Modal
./scripts/process_videos_modal.sh --sync-data

# Process all videos on Modal
./scripts/process_videos_modal.sh

# Process with custom settings
./scripts/process_videos_modal.sh -s 0.3 -f

# Download processed results
./scripts/process_videos_modal.sh --download-results

# Show help
./scripts/process_videos_modal.sh -h
```

**Typical Modal Workflow:**
1. `./scripts/process_videos_modal.sh --setup` - One-time setup
2. `./scripts/process_videos_modal.sh --sync-data` - Upload your data
3. `./scripts/process_videos_modal.sh` - Process videos
4. `./scripts/process_videos_modal.sh --download-results` - Download results

**Options:**
- `--setup`: Set up Modal.com environment (first-time setup)
- `--sync-data`: Sync local data to Modal volume
- `--download-results`: Download processed results from Modal volume
- `--volume-name`: Modal volume name (default: mv-face-recognition-data)
- Same processing options as local script

## 🚀 Application Startup

### Start Backend Only

```bash
# Start with default settings (localhost:8000)
./scripts/start_backend.sh

# Start on custom port
./scripts/start_backend.sh --port 8080

# Start in production mode
./scripts/start_backend.sh --production

# Start with custom configuration
./scripts/start_backend.sh --host 0.0.0.0 --port 8000 --workers 4
```

**Options:**
- `--host HOST`: Host to bind to (default: 0.0.0.0)
- `--port PORT`: Port to bind to (default: 8000)
- `--no-reload`: Disable auto-reload in development
- `--log-level LEVEL`: Log level (debug, info, warning, error, critical)
- `--workers N`: Number of worker processes (default: 1)
- `--production`: Run in production mode (no reload, multiple workers)

### Start Frontend Only

```bash
# Start with default settings (localhost:5173)
./scripts/start_frontend.sh

# Start on custom port
./scripts/start_frontend.sh --port 3000

# Install dependencies first
./scripts/start_frontend.sh --install

# Build for production
./scripts/start_frontend.sh --build

# Preview production build
./scripts/start_frontend.sh --preview
```

**Options:**
- `--host HOST`: Host to bind to (default: localhost)
- `--port PORT`: Port to bind to (default: 5173)
- `--no-open`: Don't open browser automatically
- `--backend-url URL`: Backend API URL (default: http://localhost:8000)
- `--install`: Install dependencies before starting
- `--build`: Build for production instead of dev server
- `--preview`: Preview production build
- `--frontend-dir DIR`: Frontend directory (default: frontend-svelte)

### Start Both Backend and Frontend

```bash
# Start both servers with default settings
./scripts/start_app.sh

# Start with custom ports
./scripts/start_app.sh --backend-port 8080 --frontend-port 3000

# Install dependencies first
./scripts/start_app.sh --install

# Start only backend
./scripts/start_app.sh --backend-only

# Start only frontend
./scripts/start_app.sh --frontend-only

# Start in production mode
./scripts/start_app.sh --production
```

**Options:**
- `--backend-host HOST`: Backend host (default: 0.0.0.0)
- `--backend-port PORT`: Backend port (default: 8000)
- `--frontend-host HOST`: Frontend host (default: localhost)
- `--frontend-port PORT`: Frontend port (default: 5173)
- `--install`: Install dependencies before starting
- `--backend-only`: Start only the backend server
- `--frontend-only`: Start only the frontend server
- `--no-wait`: Don't wait for backend to be ready
- `--production`: Start in production mode

## 📦 Prerequisites

### For Local Video Processing
- Python 3.8+ with required packages (`pip install -r requirements.txt`)
- OpenCV and face recognition libraries
- FFmpeg (for video processing)
- Sufficient disk space for processed videos

### For Modal.com Processing
- Modal account and CLI (`pip install modal`)
- Modal authentication (`modal setup`)
- Internet connection for cloud processing

### For Backend
- Python 3.8+ with FastAPI dependencies
- Required Python packages from `requirements.txt`

### For Frontend
- Node.js 18+ and npm
- SvelteKit dependencies

## 🛠️ Common Usage Patterns

### Quick Start - Development

```bash
# Start the application for development
./scripts/start_app.sh --install
```

### Process Videos Locally

```bash
# Process all videos locally
./scripts/process_videos_local.sh

# Then start the application to view results
./scripts/start_app.sh
```

### Process Videos on Modal

```bash
# Setup Modal (first time only)
./scripts/process_videos_modal.sh --setup

# Upload data and process
./scripts/process_videos_modal.sh --sync-data
./scripts/process_videos_modal.sh

# Download results
./scripts/process_videos_modal.sh --download-results

# Start application to view results
./scripts/start_app.sh
```

### Production Deployment

```bash
# Build and start in production mode
./scripts/start_app.sh --production --install
```

## 🔧 Troubleshooting

### Common Issues

1. **Port already in use**: Use different ports with `--port` options
2. **Permission denied**: Make scripts executable with `chmod +x scripts/*.sh`
3. **Python packages missing**: Install with `pip install -r requirements.txt`
4. **Node.js dependencies missing**: Run with `--install` flag
5. **Backend not responding**: Check if backend is running and ports are correct

### Debug Commands

```bash
# Check if ports are available
lsof -i :8000  # Backend port
lsof -i :5173  # Frontend port

# Check Python environment
python3 --version
pip list | grep fastapi

# Check Node.js environment
node --version
npm --version
```

## 📝 Output Locations

### Video Processing Output
- **Processed videos**: `processed_videos/`
- **Metadata**: `metadata/`
- **Clips**: `clips/`
- **Processing report**: `batch_processing_report.json`

### Application URLs
- **Backend API**: `http://localhost:8000`
- **API Documentation**: `http://localhost:8000/docs`
- **Frontend**: `http://localhost:5173`

## 📊 Monitoring

### Backend Monitoring
- Health check: `http://localhost:8000/health`
- API documentation: `http://localhost:8000/docs`
- Server logs in terminal

### Frontend Monitoring
- Development server info in terminal
- Browser console for client-side issues
- Network tab for API communication

### Video Processing Monitoring
- Progress bars during processing
- Log files: `batch_processing.log`
- Processing reports with detailed statistics

## 🔐 Security Notes

- Backend runs on `0.0.0.0` by default for network access
- Frontend runs on `localhost` by default for security
- Use `--production` mode for deployment
- Configure firewall rules for production use

## 💡 Tips

1. **Use dry run first**: Test with `-d` flag before actual processing
2. **Monitor resources**: Video processing is resource-intensive
3. **Backup data**: Keep backups of original videos
4. **Check logs**: Monitor log files for issues
5. **Use Modal for heavy processing**: Offload intensive tasks to cloud

## 🆘 Getting Help

Run any script with `-h` or `--help` to see detailed usage information:

```bash
./scripts/process_videos_local.sh -h
./scripts/start_app.sh -h
```

For more information, check the project documentation and log files. 