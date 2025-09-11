# MV Face Recognition System - Project Overview

## Purpose
A comprehensive face recognition system designed for MV (Music Video) contestant identification. The system processes videos to detect and recognize faces of 95+ contestants using ChromaDB vector database and InsightFace detection technology.

## Tech Stack

### Frontend
- **SvelteKit 2.x** with TypeScript - Primary frontend framework (in mvp-processor/)
- **Vite** - Build tool and dev server
- **Playwright** - E2E testing
- **Vitest** - Unit testing with coverage
- **Dark theme UI** with video player and analytics dashboard

### Backend & Processing
- **Python 3.8-3.11** - Video processing and face recognition
- **InsightFace** - Face detection and embedding generation
- **ChromaDB** - Vector database for face similarity search
- **OpenCV** - Computer vision operations
- **FFmpeg** - Video processing pipeline
- **PyTorch** - Deep learning models

### Deployment & Infrastructure
- **Cloudflare Workers** - Edge API deployment
- **Cloudflare R2** - Video and asset storage
- **Cloudflare KV** - Metadata storage
- **GitHub Actions** - CI/CD pipeline with 5 parallel test jobs

### Development Tools
- **uv** - Python package management
- **Jest** - Node.js testing (scripts)
- **ESLint/Prettier** - Code formatting
- **pytest** - Python testing with coverage

## System Architecture
- **mvp-processor/** - Main SvelteKit frontend + Python processing
- **worker/** - Cloudflare Workers API (21 endpoints)
- **scripts/** - Deployment automation and utilities
- **metadata/** - Critical contestant database (contestant_info.csv)
- **source/videos/** - Input videos for processing
- **processed_videos/** - Output videos with face annotations

## Key Features
- Face detection with 95+ contestant recognition
- Dense frame processing with 6x performance improvement
- Hardware acceleration (Apple Silicon/CUDA auto-detection)
- Real-time video player with face overlay
- Analytics dashboard with dark theme
- Comprehensive test suite (500+ test cases, 75-90% coverage)