# MV Face Recognition MVP - Local Processor

This is the local video processing pipeline that handles:
- Video frame extraction and preprocessing
- Face detection using OpenCV/dlib
- Face recognition against contestant database
- Metadata generation for Cloudflare delivery

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Process a video
python src/process_video.py --input ../source/videos/video-1.mp4 --output processed/

# Upload to Cloudflare
python src/upload_cloudflare.py --processed processed/ --bucket mv-face-recognition
```

## Architecture

```
Input Video → Frame Extraction → Face Detection → Recognition → Gallery Generation → Cloudflare Upload
```

This MVP demonstrates the complete local processing pipeline with automatic upload to Cloudflare R2.