# 🎬 Real-time Face Recognition Preview

## ✨ New Feature: Live Processing Preview

The MV Face Recognition system now includes **real-time preview** during video processing, allowing you to see face detection and recognition results as they happen!

## 🎯 Features

### Real-time Preview Window
- **Live video feed** with annotated faces
- **Green boxes** for recognized contestants with names
- **Red boxes** for unrecognized faces
- **Confidence scores** displayed on each detection
- **Frame counter** and timestamp display
- **Processing speed** (FPS) indicator

### Live Statistics Dashboard
- **Current frame metrics**: Faces detected and recognized
- **Running totals**: Cumulative detection counts
- **Top contestants**: Real-time leaderboard
- **Recognition rate**: Live percentage calculation

### Enhanced Annotations
- **Thicker bounding boxes** for better visibility
- **Larger labels** with contestant names
- **Frame info overlay** showing face count
- **Semi-transparent backgrounds** for better text readability

## 🚀 How to Use

### 1. Access the Feature
1. Launch the application: `streamlit run app.py`
2. Go to **Video Processing** page
3. Select your video and configure settings
4. Choose **"Real-time Preview"** processing mode
5. Click **"Process Video"**

### 2. During Processing
- **Watch the live preview** in the left column
- **Monitor statistics** in the right column  
- **See contestants appear** in real-time leaderboard
- **Track progress** with frame counter and timestamp

### 3. After Processing
- **View final summary** with charts and statistics
- **Generate outputs** (annotated video + CSV) if selected
- **Review top contestants** and recognition rates

## 📊 Real-time Interface Layout

```
┌─────────────────────────────────────────┐
│ 🎬 Live Preview (60% width)            │
│ ┌─────────────────────────────────────┐ │
│ │ [Current Video Frame]               │ │
│ │ [Green: Alice (0.85)]              │ │
│ │ [Red: Unknown (0.45)]              │ │
│ │ Faces: 3                           │ │
│ └─────────────────────────────────────┘ │
│ ████████████░░░░ 75%                   │
│ Frame 1205 | 3:24 | 12.3 FPS          │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ 📊 Live Statistics (40% width)         │
│ 👥 Faces in Frame: 3                   │
│ 🎯 Recognized: 2                       │
│ 📊 Total Detected: 125                 │
│ ✅ Total Recognized: 89                │
│                                         │
│ Current Top Contestants:                │
│ • Alice: 15 appearances                 │
│ • Bob: 12 appearances                   │
│ • Carol: 8 appearances                  │
└─────────────────────────────────────────┘
```

## ⚡ Performance

- **Processing Speed**: ~10-15 FPS on CPU
- **Memory Usage**: Efficient single-frame processing
- **Preview Quality**: Auto-resized to 800px width for smooth display
- **Real-time Updates**: Live statistics every frame

## 🆚 Real-time vs Batch Processing

| Feature | Real-time Preview | Batch Processing |
|---------|------------------|------------------|
| **Speed** | Slower (~10 FPS) | Faster (~15+ FPS) |
| **Preview** | ✅ Live video feed | ❌ Progress bar only |
| **Interaction** | ✅ Watch as it happens | ❌ Wait for completion |
| **Statistics** | ✅ Live updates | ✅ Final summary |
| **Use Case** | Demo, monitoring | Production, speed |

## 🎛️ Configuration Tips

### For Better Recognition
- **Lower similarity threshold** (0.4-0.5) for more matches
- **Higher frame skip** (10-15) for faster processing
- **Shorter time segments** (30-60 seconds) for testing

### For Better Performance  
- **Increase frame skip** to 10+ for faster processing
- **Use shorter video segments** for initial testing
- **Close other applications** to free up CPU/memory

## 🐛 Troubleshooting

### Issue: Preview is too slow
- **Solution**: Increase frame skip value (5 → 10)
- **Check**: Close other CPU-intensive applications

### Issue: No faces recognized
- **Solution**: Lower similarity threshold (0.6 → 0.4)
- **Check**: Ensure contestants are visible in the video

### Issue: Preview window blank
- **Solution**: Check video file is not corrupted
- **Try**: Different video or shorter time segment

## 🔧 Technical Details

### Real-time Processing Pipeline
1. **Frame Extraction**: Every N frames based on skip setting
2. **Face Detection**: InsightFace buffalo_l model
3. **Face Matching**: ChromaDB similarity search  
4. **Annotation**: Overlay bounding boxes and labels
5. **Display**: Streamlit image component update
6. **Statistics**: Live metrics calculation

### Preview Optimizations
- **Frame Resizing**: Max 800px width for smooth display
- **Annotation Enhancement**: Thicker lines, larger labels
- **Memory Management**: Single frame processing
- **Update Rate**: ~10 Hz for responsive preview

## 🚀 Future Enhancements

- **Pause/Resume** controls during processing
- **Frame seeking** slider for manual navigation  
- **Threshold adjustment** during live processing
- **Recording** of interesting detection moments
- **Multi-video** batch preview mode

---

**Experience face recognition like never before with real-time preview!** 🎬✨