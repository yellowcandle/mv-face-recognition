# Product Overview

## MV Face Recognition System

A production-ready video processing and annotation platform that transforms raw videos into annotated content with comprehensive face recognition overlays. The system identifies contestants from a database of 95 individuals and provides real-time video playback with face detection capabilities served globally via Cloudflare's edge network.

## Key Features

- **Face Recognition**: Identifies 95 contestants from a pre-trained database using InsightFace buffalo_l model
- **Dense Video Processing**: Processes every 5th frame (6x improvement over sparse processing) with linear interpolation for smooth playback
- **Real-time Video Player**: SvelteKit-based frontend with interactive face overlays, confidence indicators, and timeline visualization
- **Global Distribution**: Cloudflare Workers deployment with 300+ edge locations for sub-100ms response times worldwide
- **Audio Preservation**: FFmpeg integration maintains original audio tracks during processing

## Architecture

Two-phase system:
1. **Offline Batch Processing**: GPU-accelerated video analysis with dense metadata generation
2. **Global Edge Serving**: Cloudflare Workers delivering annotated videos and real-time interfaces

## Target Use Case

Video content analysis for entertainment/competition shows where contestant identification and tracking across video content is required, with emphasis on smooth user experience and global accessibility.