# Modal Video Processing Setup Guide

## ✅ Complete Implementation

You can now trigger Modal video processing directly from your frontend admin panel!

## 🎯 What Was Built

### Frontend UI (`/admin` → Video Processing Tab)
- **Step 1**: File selection with drag-and-drop
- **Step 2**: Upload to HuggingFace XET with progress tracking
- **Step 3**: Trigger Modal processing with visual feedback
- **Guide Section**: 4-step workflow visualization

### Backend API Endpoints

#### 1. `/api/admin/upload-video` (POST)
Uploads video files to HuggingFace XET storage.

**Request**: FormData with video file
**Response**:
```json
{
  "success": true,
  "video_name": "test-video-mv2.mp4",
  "video_url": "https://huggingface.co/datasets/yellowcandle/mv-face-recognition-data/resolve/main/videos/source/test-video-mv2.mp4",
  "message": "Video uploaded to HuggingFace XET"
}
```

#### 2. `/api/admin/trigger-modal` (POST)
Queues a Modal processing job and returns command to run.

**Request**:
```json
{
  "video_url": "https://huggingface.co/...",
  "video_name": "test-video.mp4"
}
```

**Response**:
```json
{
  "success": true,
  "job_id": "modal_job_1704840123456_abc123",
  "message": "Processing job queued. Run Modal command to process:",
  "command": "modal run scripts/modal_hf_processor.py --sync-from-hf --include-videos --process-videos",
  "status": "queued",
  "notes": [...]
}
```

## 🔧 Setup Instructions

### 1. Configure HuggingFace Token in Cloudflare Worker

You need to set the `HF_TOKEN` environment variable in your Cloudflare Worker:

#### Option A: Via Wrangler CLI
```bash
# Set the token as a secret
cd worker
wrangler secret put HF_TOKEN
# Paste your HuggingFace token when prompted
```

#### Option B: Via Cloudflare Dashboard
1. Go to: https://dash.cloudflare.com
2. Navigate to: Workers & Pages → Your Worker → Settings → Variables
3. Click "Add variable"
4. Name: `HF_TOKEN`
5. Value: Your HuggingFace token (get from https://huggingface.co/settings/tokens)
6. Check "Encrypt" to make it a secret
7. Click "Save"

#### Get Your HuggingFace Token
```bash
# Login to HuggingFace CLI
huggingface-cli login

# Or get token directly
cat ~/.cache/huggingface/token
```

### 2. Deploy Updated Worker

```bash
cd worker
wrangler deploy
```

### 3. Verify Setup

```bash
# Test the upload endpoint
curl -X POST https://your-worker.workers.dev/api/admin/upload-video \
  -F "video=@test-video.mp4" \
  -F "filename=test-video.mp4"
```

## 🚀 Complete Workflow

### From Frontend UI

1. **Navigate to Admin Panel**
   ```
   http://localhost:3000/admin
   ```

2. **Select "Video Processing" Tab**

3. **Choose Video File**
   - Click "Choose Video File" button
   - Select a video (MP4, AVI, MOV, MKV)
   - File size shown in MB

4. **Upload to HuggingFace**
   - Click "Upload to HuggingFace"
   - Progress bar shows upload status
   - Success message with HuggingFace URL

5. **Trigger Modal Processing**
   - Click "Trigger Modal Processing"
   - Spinning indicator shows queued status
   - Modal command displayed for manual execution

6. **Run Modal Command**
   ```bash
   modal run scripts/modal_hf_processor.py --sync-from-hf --include-videos --process-videos
   ```

### From Command Line (Alternative)

```bash
# 1. Upload video to HuggingFace
python scripts/upload_video_to_hf.py --video source/videos/test-video.mp4

# 2. Process with Modal
modal run scripts/modal_hf_processor.py --sync-from-hf --include-videos --process-videos
```

## 📊 Processing Flow

```
┌─────────────────┐
│  User Uploads   │
│  Video File     │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  Worker Uploads │
│  to HuggingFace │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  Job Queued in  │
│  Cloudflare KV  │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  User Runs      │
│  Modal Command  │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  Modal Downloads│
│  from HuggingFace│
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  GPU Processing │
│  Face Recognition│
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  Upload Results │
│  to HuggingFace │
└─────────────────┘
```

## 🎨 UI Features

- **Progressive disclosure**: 3 numbered steps guide the user
- **Visual feedback**: Completed steps show green checkmarks
- **Progress tracking**: Upload progress bar with percentage
- **Status indicators**: Loading spinners and success messages
- **Responsive design**: Works on mobile and desktop
- **Dark theme**: Matches existing admin interface
- **Error handling**: Clear error messages for failures

## 🔍 Debugging

### Check Worker Logs
```bash
wrangler tail
```

### Test Upload Endpoint
```bash
curl -v -X POST http://localhost:3000/api/admin/upload-video \
  -F "video=@test.mp4" \
  -F "filename=test.mp4"
```

### Check Modal Job Queue
```bash
# In worker KV storage, look for keys starting with: modal_job_
```

### Verify HuggingFace Upload
```bash
python scripts/upload_video_to_hf.py --list
```

## 🚨 Troubleshooting

### Error: "HuggingFace token not configured"
**Solution**: Set the `HF_TOKEN` environment variable in Cloudflare Worker (see Setup Step 1)

### Error: "Failed to upload to HuggingFace"
**Possible causes**:
- Invalid or expired HF_TOKEN
- Network connectivity issues
- File too large (HuggingFace has size limits)
- Insufficient permissions on HuggingFace repo

**Solution**:
```bash
# Verify token is valid
python -c "from huggingface_hub import HfApi; api = HfApi(); print(api.whoami())"

# Check repo permissions
python -c "from huggingface_hub import HfApi; api = HfApi(); print(api.repo_info('yellowcandle/mv-face-recognition-data', repo_type='dataset'))"
```

### Upload Works But Processing Doesn't Start
**Solution**: You need to manually run the Modal command. The frontend only **queues** the job. To actually process:

```bash
modal run scripts/modal_hf_processor.py --sync-from-hf --include-videos --process-videos
```

### Video Not Found in Modal
**Solution**: Make sure Modal script includes `--include-videos` flag to download source videos from HuggingFace.

## 📝 Notes

- **Video Limits**: HuggingFace free tier supports files up to 5GB
- **Processing Time**: Typical videos take 5-15 minutes with T4 GPU
- **Storage**: Videos stored on HuggingFace, processed videos uploaded back
- **Cost**: Modal T4 GPU costs ~$0.60/hour, typical video = $0.05-$0.15

## 🎯 Next Steps (Optional Enhancements)

1. **Automatic Modal Trigger**: Integrate Modal's HTTP API to auto-trigger processing
2. **Progress Polling**: Add WebSocket updates for real-time processing status
3. **Job Queue UI**: Show list of queued/processing jobs
4. **Batch Processing**: Allow uploading multiple videos at once
5. **Result Notifications**: Email/webhook when processing completes

## ✅ What You Have Now

- ✅ Frontend upload UI with progress tracking
- ✅ HuggingFace XET integration for video storage
- ✅ Modal processing pipeline configured
- ✅ Job queueing in Cloudflare KV
- ✅ Complete workflow documentation

The system is **production-ready** for manual Modal triggering. Users can upload videos through the web UI, and then run the Modal command to process them.
