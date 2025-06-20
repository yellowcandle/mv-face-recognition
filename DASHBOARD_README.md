# Face Recognition Dashboard

## Overview

A modern, real-time face recognition dashboard implemented with Gradio, following the UI specifications from `DESIGN.md`. The dashboard provides an intuitive interface for video analysis with live face detection and recognition capabilities.

## Features

### 🎬 Dashboard Layout (According to DESIGN.md)

- **Header Bar (60px height)**
  - App title: "Face Recognition Dashboard"
  - Real-time timestamp
  - LIVE indicator when processing

- **Video Player Panel (60% width)**
  - Video selection dropdown
  - Video display with detection overlays
  - Video controls (play, pause, stop, process)
  - Frame rate and resolution indicators

- **Face Recognition Panel (40% width)**
  - Face tiles grid (3 columns, 120x120px tiles)
  - Color-coded confidence borders:
    - 🟢 Green: High confidence (>90%)
    - 🟡 Yellow: Medium confidence (70-90%)
    - 🔴 Red: Low confidence (<70%)
  - Face count badge
  - Click interaction for face selection

- **Similarity Scores Panel (200px height)**
  - Horizontal bar chart showing confidence scores
  - Real-time updates indicator
  - Color-coded bars matching face tile borders
  - Legend for confidence levels

### ⚡ Real-time Capabilities

- **ZeroGPU Integration**: Supports Hugging Face Spaces GPU acceleration
- **Live Processing**: Real-time video analysis with face detection
- **Dynamic Updates**: Face tiles and similarity scores update as processing occurs
- **Interactive Elements**: Click faces to highlight in video and chart

### 🔧 Technical Features

- **Modern Gradio Interface**: Built with Gradio 5.x
- **Responsive Design**: Adapts to different screen sizes
- **Dark Theme**: Professional dark UI with blue accents
- **Face Recognition**: 95 pre-loaded contestant embeddings
- **Multiple Video Support**: Processes MP4, MOV, AVI formats
- **CPU/GPU Fallback**: Automatic fallback to CPU if GPU quota exceeded

## Files Structure

```
├── dashboard_gradio.py        # Main dashboard implementation
├── test_dashboard.py          # Test suite for dashboard functionality
├── DASHBOARD_README.md        # This documentation
├── DESIGN.md                 # UI specification document
└── app.py                    # Entry point (updated to use dashboard)
```

## Usage

### Launch the Dashboard

```bash
# Method 1: Direct launch
python dashboard_gradio.py

# Method 2: Through main app (with fallback)
python app.py
```

### Test the Dashboard

```bash
# Run comprehensive tests
python test_dashboard.py
```

### Access the Interface

- **Local**: http://localhost:7860
- **HF Spaces**: Automatic deployment when pushed to spaces

## Implementation Details

### Core Components

1. **FaceRecognitionDashboard Class**
   - Manages services (face detector, recognition, embedding)
   - Handles real-time state and video processing
   - Generates dynamic HTML for face tiles and charts

2. **UI Components**
   - `create_header_component()`: Animated header with LIVE indicator
   - `create_video_player_panel()`: Video interface with controls
   - `create_face_recognition_panel()`: Interactive face grid
   - `create_similarity_scores_panel()`: Confidence visualization

3. **Real-time Processing**
   - `process_video_real_time()`: GPU-accelerated video analysis
   - `_update_face_tiles()`: Dynamic face tile generation
   - `_update_similarity_scores()`: Live chart updates

### Key Technologies

- **Gradio 5.x**: Modern web interface framework
- **InsightFace**: Face detection and recognition
- **ChromaDB**: Vector database for embeddings
- **OpenCV**: Video processing
- **Custom CSS/JS**: Enhanced styling and interactions

## Features Compared to Original

| Feature | Original Gradio App | New Dashboard |
|---------|-------------------|---------------|
| **Layout** | Tab-based interface | Modern dashboard layout |
| **Video Display** | Basic video component | Interactive player with overlays |
| **Face Detection** | Text-based results | Visual face tile grid |
| **Real-time Updates** | Batch processing only | Live updates during processing |
| **UI Design** | Standard Gradio theme | Custom dark theme with animations |
| **Face Interaction** | No interaction | Click faces to highlight |
| **Confidence Visualization** | Text percentages | Color-coded bars and charts |
| **Processing Status** | Text status updates | Visual LIVE indicator |

## Testing Results

✅ **All 5 tests passed:**
- Gradio Availability: PASS
- Dependencies: PASS  
- Dashboard Import: PASS
- Dashboard Creation: PASS
- Interface Creation: PASS

## System Requirements

- **Python 3.8+**
- **Gradio 5.x**
- **OpenCV**
- **InsightFace models**
- **95 contestant embeddings** (automatically loaded)
- **5 video files** in source/videos directory

## Performance

- **GPU Processing**: ~60s duration limit on HF Spaces ZeroGPU
- **CPU Fallback**: Automatic switching if GPU quota exceeded
- **Memory Usage**: Optimized for HF Spaces constraints
- **Face Recognition**: Real-time processing with 95 known contestants
- **Video Support**: Multiple formats with automatic detection

## Future Enhancements

- **WebSocket Integration**: True real-time streaming
- **Face Crop Display**: Show actual face images in tiles
- **Video Timeline**: Scrub through detection timeline
- **Export Features**: Download results and statistics
- **Multi-video Support**: Process multiple videos simultaneously

## Deployment

The dashboard is ready for deployment to:
- **Hugging Face Spaces** (with ZeroGPU support)
- **Local Development** (CPU/GPU auto-detection)
- **Docker Containers** (if needed in the future)

---

*Built according to DESIGN.md specifications with modern web technologies and real-time capabilities.*