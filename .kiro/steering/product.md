---
inclusion: always
---

# MV Face Recognition System

Production video processing platform that identifies 95 contestants in videos and serves annotated content globally via Cloudflare's edge network.

## Core Requirements

### Face Recognition Pipeline
- Use pre-computed embeddings from `source/photo/contestants/` directory
- Process every 5th frame with linear interpolation for smooth overlays
- Display recognition confidence scores and allow filtering by confidence levels
- Always preserve original audio tracks during video processing
- Reference `source/contestant_info.csv` for authoritative contestant data (編號,姓名,暱稱,年齡)

### Performance Standards
- Target sub-100ms response times using Cloudflare's edge network
- Process videos in chunks to avoid memory issues
- Utilize GPU acceleration (Apple Silicon/NVIDIA CUDA) when available
- Maintain >85% recognition accuracy for known contestants
- Achieve 6x performance improvement over frame-by-frame processing

### User Experience
- Interactive face overlays with contestant names and confidence scores
- Timeline navigation to jump to specific contestants or segments
- Mobile-responsive video player across all device sizes
- Clear loading states and meaningful error messages
- Proper accessibility with ARIA labels and keyboard navigation

## Architecture Patterns

### Two-Phase Processing
1. **Offline Processing**: GPU-accelerated batch analysis generating dense metadata
2. **Edge Serving**: Real-time video delivery with pre-computed annotations

### Data Flow
- Input videos from `source/videos/`
- Face embeddings from `source/photo/contestants/`
- Output to `processed_videos/`, `metadata/`, and `thumbnails/`
- Deploy via Cloudflare Workers with R2 storage and KV metadata

### Error Handling Rules
- Gracefully handle missing contestants and low confidence detections
- Ensure face detection timestamps align with video playback
- Never fail silently - log errors with context
- Provide fallback UI states for processing failures

## Critical Constraints
- Never load entire videos into memory
- Always validate contestant data against CSV source
- Maintain audio quality during video processing
- Cache face embeddings and metadata at edge locations
- Use appropriate video encoding for web delivery