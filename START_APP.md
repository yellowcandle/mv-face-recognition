# How to Start the MV Face Recognition App

## 🎯 Quick Summary

For most users, just run:
```bash
./scripts/start_app.sh
```

Then open http://localhost:5173 in your browser for the video player with face gallery!

---

## 🚀 Easiest Way (Recommended)

**One-command startup using the automated script:**

```bash
# Start both backend and frontend automatically
./scripts/start_app.sh

# Or with dependency installation
./scripts/start_app.sh --install

# Backend only
./scripts/start_app.sh --backend-only

# Frontend only  
./scripts/start_app.sh --frontend-only

# View all options
./scripts/start_app.sh --help
```

**Access the app at:**
- 🎨 **Frontend**: http://localhost:5173
- 📡 **Backend API**: http://localhost:8000
- 📚 **API Docs**: http://localhost:8000/docs

## Manual Start Options

### Option 1: SvelteKit Frontend + FastAPI Backend (Recommended)
**Best for: Video player with face gallery and real-time synchronization**

```bash
# Terminal 1: Start FastAPI Backend
cd backend
python main.py
# Backend runs on http://localhost:8000

# Terminal 2: Start SvelteKit Frontend  
cd frontend-svelte
npm install
npm run dev
# Frontend runs on http://localhost:5173
```

### Option 2: Gradio Interface (Original)
**Best for: Simple video processing and batch operations**

```bash
python gradio_app.py
# Gradio interface runs on http://localhost:7860
```

### Option 3: Vue.js Frontend (Legacy)
**Note: This is the older frontend, SvelteKit is preferred**

```bash
# Terminal 1: Start Backend
cd backend
python main.py

# Terminal 2: Start Vue Frontend
cd frontend
npm install
npm run dev
# Vue frontend runs on http://localhost:5173
```

### Option 4: Hugging Face Spaces Mode
**Best for: Deployment to Hugging Face Spaces**

```bash
python app.py
# Launches Gradio interface optimized for HF Spaces at http://localhost:7860
```

### Option 5: GUI Desktop App (Experimental)
**Best for: Desktop application with tkinter GUI**

```bash
python gui_app.py
# Opens desktop GUI application
```

### Option 6: Modal Cloud Processing 🚀
**Best for: GPU-accelerated batch processing in the cloud**

```bash
# First-time setup
scripts/process_videos_modal.sh --setup

# Upload your videos and config to Modal
scripts/process_videos_modal.sh --sync-data

# Process videos on Modal's GPU infrastructure
scripts/process_videos_modal.sh

# Download processed results
scripts/process_videos_modal.sh --download-results
```

**Benefits:**
- 🚀 GPU acceleration for faster processing
- ☁️ No local hardware requirements
- 📈 Scalable cloud infrastructure
- ⚡ Batch processing optimization

**New Features:**
- ✨ **Dense Metadata Generation**: 6x more timeline data for smooth video player sync
- ⚡ **Parallel Processing**: Optimized batch processing on Modal's infrastructure
- 🎯 **Enhanced Timeline**: Frame-by-frame tracking with interpolation

**Note:** First run will take 5-10 minutes to build the cloud environment. Subsequent runs are much faster!

## Prerequisites

### System Requirements
- Python 3.8+
- Node.js 16+
- npm or bun

### Python Dependencies
```bash
# Install Python requirements
pip install -r requirements.txt

# Or with conda/mamba
mamba install --file requirements.txt
```

### Node.js Dependencies
```bash
# For SvelteKit frontend
cd frontend-svelte
npm install

# For Vue frontend (if using legacy)
cd frontend
npm install
```

## Application Features by Interface

### SvelteKit Frontend (Recommended)
- **Video Player**: Stream processed videos with range support
- **Face Gallery**: Real-time synchronized contestant gallery  
- **Timeline Visualization**: Interactive timeline with face detection markers
- **Dense Metadata**: 6x smoother face tracking with interpolation
- **Contestant Search**: Filter and search contestants
- **Keyboard Controls**: Space to play/pause, arrows to seek

**Process videos with enhanced features:**
```bash
# Local processing with dense metadata (recommended)
scripts/process_videos_local.sh

# Modal cloud processing with GPU acceleration
scripts/process_videos_modal.sh
```

**Access at**: http://localhost:5173/video-player

### Gradio Interface
- **Video Upload**: Upload new MV videos for processing
- **Batch Processing**: Process multiple videos at once
- **Contestant Management**: Manage contestant photos and embeddings
- **Settings Configuration**: Adjust face detection and matching parameters

**Access at**: http://localhost:7860

## API Endpoints

### FastAPI Backend (http://localhost:8000)

**Video Streaming:**
- `GET /api/videos/processed/list` - List processed videos
- `GET /api/videos/processed/stream/{filename}` - Stream video with range support

**Metadata:**
- `GET /api/videos/metadata/{video_id}` - Get face detection metadata
- `GET /api/videos/metadata/dense/{video_id}` - Get dense metadata (6x more data)
- `POST /api/videos/metadata/dense/{video_id}/generate` - Generate dense metadata

**Contestants:**
- `GET /api/videos/contestants` - Get contestant information
- `GET /api/contestants/{contestant_id}/photo` - Get contestant photo

## File Structure Requirements

Ensure these directories exist with data:

```
mv-face-recognition/
├── source/
│   ├── videos/           # Original MV videos
│   └── photo/
│       └── contestants/  # Contestant photos (organized by number)
├── processed_videos/     # Annotated videos (_annotated.mp4)
├── metadata/            # Face detection metadata
│   ├── contestant_info.csv  # Contestant database (CRITICAL FILE)
│   ├── *_metadata.json      # Sparse metadata
│   └── *_dense_metadata.json # Dense metadata (6x more data)
└── data/
    └── chroma_db/       # Face embedding database
```

## First Time Setup

### 1. Setup Contestant Database
```bash
# Ensure contestant_info.csv exists in metadata/
# File should have columns: 編號,姓名,暱稱,年齡
head metadata/contestant_info.csv
```

### 2. Process Videos (Optional)
```bash
# Process a single video
python src/services/enhanced_video_processor.py path/to/video.mp4

# Generate dense metadata for better video player experience
python src/services/realtime_video_processor.py path/to/video.mp4

# Batch process all videos
python batch_process_videos.py
```

### 3. Setup Face Database
```bash
# Initialize ChromaDB with contestant photos
python src/database/chroma_setup.py
```

## Troubleshooting

### Backend Won't Start
```bash
# Check Python path and dependencies
python -c "import fastapi, uvicorn; print('Backend dependencies OK')"

# Check file paths
ls -la backend/app/
```

### Frontend Won't Start
```bash
# Clear node modules and reinstall
cd frontend-svelte
rm -rf node_modules package-lock.json
npm install
npm run dev
```

### No Videos Showing
- Check that `processed_videos/` directory exists and contains `*_annotated.mp4` files
- Verify backend is running and accessible at http://localhost:8000
- Check browser console for API errors

### Face Recognition Not Working
- Ensure `metadata/contestant_info.csv` exists and is properly formatted
- Check that `data/chroma_db/` contains face embeddings
- Run: `python src/database/chroma_setup.py` to rebuild embeddings

### Dense Metadata Missing
```bash
# Generate dense metadata for better video player performance
python src/services/realtime_video_processor.py processed_videos/your_video.mp4

# Or use the API endpoint
curl -X POST http://localhost:8000/api/videos/metadata/dense/VIDEO_ID/generate
```

### Modal Cloud Processing Issues
```bash
# Re-authenticate if needed
modal setup

# Check if volume exists
modal volume list

# Force sync if files already exist
scripts/process_videos_modal.sh --sync-data

# View script help for more options
scripts/process_videos_modal.sh --help
```

## Performance Tips

1. **Use Dense Metadata**: Generate dense metadata for smoother video player experience
2. **Hardware Acceleration**: The system automatically uses MPS (Apple Silicon) or CUDA when available  
3. **Video Format**: MP4 format works best for streaming
4. **File Size**: Large videos may take time to process initially

## Development

### Hot Reload Development
```bash
# Backend with auto-reload
cd backend
uvicorn app.main:app --reload --port 8000

# Frontend with hot reload
cd frontend-svelte  
npm run dev
```

### Testing
```bash
# Test face detection
python test_system.py

# Demo dense metadata improvements
python demo_dense_metadata.py
```

Choose the interface that best fits your needs and follow the corresponding startup instructions!