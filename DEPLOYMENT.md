# MV Face Recognition - Deployment Guide

This guide explains how to deploy the MV Face Recognition application to Cloudflare with all components properly configured.

## Overview

The deployment includes:
- **Frontend**: Svelte application on Cloudflare Pages
- **Backend**: Python FastAPI on Cloudflare Workers (Python Workers)
- **Metadata**: JSON files in Cloudflare KV storage
- **Videos**: Processed MP4 files in Cloudflare R2 storage

## Issues Fixed

### 1. Python Workers Compatibility
- ✅ Added `python_workers` compatibility flag
- ✅ Created separate `backend/wrangler.toml` for Python deployment
- ✅ Fixed main wrangler.toml for Pages deployment

### 2. Metadata Upload
- ✅ Created automated script to upload all metadata to KV
- ✅ Organized video metadata into collections
- ✅ Converted CSV contestant data to structured JSON

### 3. Video Upload
- ✅ Created script to upload processed videos to R2
- ✅ Added safety confirmation for large file uploads
- ✅ Generated manifest and access information

## Quick Deployment

### Option 1: All-in-One Script
```bash
./scripts/deploy_all.sh
```

### Option 2: Step-by-Step

#### Step 1: Deploy Frontend
```bash
npx wrangler pages deploy frontend/build --project-name=mv-face-recognition
```

#### Step 2: Deploy Backend
```bash
cd backend
npx wrangler deploy
cd ..
```

#### Step 3: Upload Metadata
```bash
node scripts/upload_metadata_to_kv.js
```

#### Step 4: Upload Videos (Optional)
```bash
# Warning: This uploads ~3GB of video files
node scripts/upload_videos_to_r2.js --confirm
```

## Configuration Files

### Main wrangler.toml
```toml
name = "mv-face-recognition"
main = "worker/index.js"
compatibility_date = "2024-11-08"
compatibility_flags = ["nodejs_compat"]

# Pages configuration
pages_build_output_dir = "frontend/build"

[[r2_buckets]]
binding = "VIDEOS_BUCKET"
bucket_name = "mv-face-recognition-videos"

[[kv_namespaces]]
binding = "METADATA_KV"
id = "890d77e11bfc4623ac4ef56db6b9a4ab"
```

### Backend wrangler.toml
```toml
name = "mv-face-recognition-api"
main = "main.py"
compatibility_date = "2024-11-08"
compatibility_flags = ["python_workers"]

[[kv_namespaces]]
binding = "METADATA_KV"
id = "890d77e11bfc4623ac4ef56db6b9a4ab"

[[r2_buckets]]
binding = "VIDEOS_BUCKET"
bucket_name = "mv-face-recognition-videos"
```

## Data Structure

### KV Storage Keys
- `batch_processing_summary` - Processing summary
- `contestant_info` - Raw CSV data
- `contestants_structured` - Parsed contestant data as JSON
- `video_metadata_collection` - All video metadata organized
- `annotated_metadata_collection` - Dense annotation data
- `processed_videos_manifest` - Video inventory and access info
- Individual video metadata: `1-《全民造星IV》...`, `2-《全民造星IV》...`, etc.

### R2 Storage Structure
```
mv-face-recognition-videos/
├── processed_videos/
│   ├── 1-《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅_annotated.mp4
│   ├── 2-《全民造星IV》主題曲 《前傳》MV 2021夏の次部曲：始発の駅_annotated.mp4
│   ├── 3-《全民造星IV》主題曲 《前傳》MV 2021夏の三部曲：女團の駅_annotated.mp4
│   ├── 4-《全民造星IV》極限拍MV_annotated.mp4
│   └── 5-《全民造星IV》播前熱身！率先表演《前傳》_annotated.mp4
└── manifest/
    └── processed_videos_manifest.json
```

## Deployment URLs

After successful deployment:
- **Frontend**: https://29374aab.mv-face-recognition.pages.dev
- **Backend API**: https://mv-face-recognition-api.{your-subdomain}.workers.dev

## Useful Commands

### View KV Data
```bash
# List all KV keys
npx wrangler kv:key list --binding=METADATA_KV

# Get specific key
npx wrangler kv:key get "contestants_structured" --binding=METADATA_KV
```

### View R2 Objects
```bash
# List all R2 objects
npx wrangler r2 object list --bucket=mv-face-recognition-videos

# Get object info
npx wrangler r2 object head "processed_videos/1-《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅_annotated.mp4" --bucket=mv-face-recognition-videos
```

### Monitor Deployments
```bash
# View worker logs
npx wrangler tail

# View deployment status
npx wrangler deployments list
```

## Troubleshooting

### Python Workers Error
If you see: `The python_workers compatibility flag is required to use Python`
- Ensure `backend/wrangler.toml` has `compatibility_flags = ["python_workers"]`
- Deploy from the backend directory: `cd backend && npx wrangler deploy`

### Large File Upload Timeout
For video uploads that timeout:
- Videos are large (500MB-700MB each)
- Ensure stable internet connection
- Upload can be resumed by re-running the script

### KV Namespace Not Found
If KV operations fail:
- Verify the KV namespace ID in wrangler.toml
- Create namespace if needed: `npx wrangler kv:namespace create "METADATA_KV"`

## Next Steps

1. **Custom Domain**: Configure custom domains for your deployed applications
2. **Environment Variables**: Set up production environment variables
3. **Monitoring**: Set up alerts and monitoring for your applications
4. **Security**: Configure access controls and security headers
5. **CDN**: Set up custom R2 domain for direct video access

## Security Considerations

- R2 bucket access is currently through Cloudflare APIs
- For public video access, configure custom domain with appropriate CORS settings
- Consider implementing authentication for sensitive metadata
- Use environment variables for sensitive configuration 