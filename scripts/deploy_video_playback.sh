#!/bin/bash

set -e  # Exit on any error

echo "🎬 MV Face Recognition - Video Playback Deployment"
echo "================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_status "This script will deploy video playback functionality:"
print_status "• Frontend (Pages) for video player interface"
print_status "• Metadata upload to KV storage"  
print_status "• Processed videos upload to R2 storage"
print_warning "Note: Python backend cannot be deployed (experimental feature)"
echo

# Step 1: Deploy Frontend
print_status "Step 1: Deploying Frontend to Cloudflare Pages..."
if [ -d "frontend/build" ]; then
    npx wrangler pages deploy frontend/build --project-name=mv-face-recognition
    print_success "Frontend deployed successfully!"
    FRONTEND_URL="https://29374aab.mv-face-recognition.pages.dev"
    echo "Frontend URL: $FRONTEND_URL"
else
    print_warning "Frontend build directory not found."
    print_warning "To build frontend: cd frontend && npm run build"
fi

# Step 2: Upload Metadata to KV
print_status "Step 2: Uploading metadata to KV storage..."
if [ -f "scripts/upload_metadata_to_kv.js" ]; then
    node scripts/upload_metadata_to_kv.js
    print_success "Metadata uploaded to KV successfully!"
else
    print_error "Metadata upload script not found!"
    exit 1
fi

# Step 3: Upload Videos to R2 (with confirmation)
print_status "Step 3: Video Upload to R2"
echo
print_warning "The processed videos are very large (~3GB total):"
echo "  • 1-《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅_annotated.mp4 (733MB)"
echo "  • 2-《全民造星IV》主題曲 《前傳》MV 2021夏の次部曲：始発の駅_annotated.mp4 (661MB)"  
echo "  • 3-《全民造星IV》主題曲 《前傳》MV 2021夏の三部曲：女團の駅_annotated.mp4 (658MB)"
echo "  • 4-《全民造星IV》極限拍MV_annotated.mp4 (497MB)"
echo "  • 5-《全民造星IV》播前熱身！率先表演《前傳》_annotated.mp4 (513MB)"
echo
print_warning "This will take significant time and bandwidth."
echo
read -p "Upload videos to R2 now? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_status "Uploading videos to R2 storage..."
    node scripts/upload_videos_to_r2.js --confirm
    print_success "Videos uploaded to R2 successfully!"
    VIDEO_UPLOADED=true
else
    print_warning "Skipping video upload. Run manually later:"
    print_warning "node scripts/upload_videos_to_r2.js --confirm"
    VIDEO_UPLOADED=false
fi

# Step 4: Create video playback configuration
print_status "Step 4: Configuring video playback..."

cat > video_config.json << EOF
{
  "deployment_date": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "frontend_url": "$FRONTEND_URL",
  "storage": {
    "kv_namespace": "METADATA_KV",
    "r2_bucket": "mv-face-recognition-videos",
    "videos_uploaded": $VIDEO_UPLOADED
  },
  "videos": [
    {
      "id": "1",
      "name": "《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅",
      "filename": "1-《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅_annotated.mp4",
      "r2_path": "processed_videos/1-《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅_annotated.mp4"
    },
    {
      "id": "2", 
      "name": "《全民造星IV》主題曲 《前傳》MV 2021夏の次部曲：始発の駅",
      "filename": "2-《全民造星IV》主題曲 《前傳》MV 2021夏の次部曲：始発の駅_annotated.mp4",
      "r2_path": "processed_videos/2-《全民造星IV》主題曲 《前傳》MV 2021夏の次部曲：始発の駅_annotated.mp4"
    },
    {
      "id": "3",
      "name": "《全民造星IV》主題曲 《前傳》MV 2021夏の三部曲：女團の駅", 
      "filename": "3-《全民造星IV》主題曲 《前傳》MV 2021夏の三部曲：女團の駅_annotated.mp4",
      "r2_path": "processed_videos/3-《全民造星IV》主題曲 《前傳》MV 2021夏の三部曲：女團の駅_annotated.mp4"
    },
    {
      "id": "4",
      "name": "《全民造星IV》極限拍MV",
      "filename": "4-《全民造星IV》極限拍MV_annotated.mp4", 
      "r2_path": "processed_videos/4-《全民造星IV》極限拍MV_annotated.mp4"
    },
    {
      "id": "5",
      "name": "《全民造星IV》播前熱身！率先表演《前傳》",
      "filename": "5-《全民造星IV》播前熱身！率先表演《前傳》_annotated.mp4",
      "r2_path": "processed_videos/5-《全民造星IV》播前熱身！率先表演《前傳》_annotated.mp4" 
    }
  ],
  "next_steps": [
    "Configure R2 custom domain for direct video access",
    "Update frontend to use R2 URLs for video playback",
    "Set up CORS headers for video streaming"
  ]
}
EOF

print_success "Video configuration created: video_config.json"

# Upload config to KV
npx wrangler kv key put "video_playback_config" --path="video_config.json" --binding=METADATA_KV --preview false

echo
print_success "🎉 Video Playback Deployment Complete!"
echo "========================================"
echo
print_status "Deployment Summary:"
echo "• Frontend: $FRONTEND_URL"
echo "• Metadata: Uploaded to KV storage"
if [ "$VIDEO_UPLOADED" = true ]; then
    echo "• Videos: Uploaded to R2 storage"
else
    echo "• Videos: Not uploaded (manual upload needed)"
fi
echo "• Configuration: Saved to KV as 'video_playback_config'"
echo
print_status "To play videos, you need to:"
echo "1. Configure R2 custom domain for public access"
echo "2. Update frontend to load video URLs from KV/R2"
echo "3. Test video playback in the deployed frontend"
echo
print_status "Useful commands:"
echo "• List videos: npx wrangler r2 object list --bucket=mv-face-recognition-videos"
echo "• View config: npx wrangler kv key get video_playback_config --binding=METADATA_KV --preview false"
echo "• View metadata: npx wrangler kv key list --binding=METADATA_KV --preview false"
echo
print_success "Video playback system ready! 🎬"

# Cleanup
rm -f video_config.json 