# YouTube Video Ingestion Guide

Complete guide for processing YouTube videos through the MV Face Recognition system.

## Quick Start

### 1. Submit YouTube Video via Admin Dashboard

1. Navigate to: https://mv-face-recognition-api.herballemon.workers.dev/admin/youtube
2. Paste YouTube URL (supports all formats: youtube.com/watch?v=..., youtu.be/..., etc.)
3. Optionally customize the title and set priority
4. Click "Add to Processing Queue"

The video is now queued for processing!

### 2. Process the Queue

Run the queue processor to trigger Modal processing:

```bash
# Process all queued videos (one-time)
node scripts/process-youtube-queue.js

# Process a specific video
node scripts/process-youtube-queue.js --queue-id yt_abc123_1234567890

# Continuous mode (polls every 30 seconds)
node scripts/process-youtube-queue.js --continuous

# Dry run (see what would be processed)
node scripts/process-youtube-queue.js --dry-run
```

**Environment Variables Required:**
```bash
export CLOUDFLARE_API_TOKEN="your_token"
export CLOUDFLARE_ACCOUNT_ID="your_account_id"
```

### 3. Monitor Processing Status

Check the admin dashboard or use the API:

```bash
# Get all queue entries
curl "https://mv-face-recognition-api.herballemon.workers.dev/api/admin/youtube/queue"

# Filter by status
curl "https://mv-face-recognition-api.herballemon.workers.dev/api/admin/youtube/queue?status=processing"
```

## Complete Workflow

### Phase 1: Video Download & Face Detection

**What happens:**
- Modal downloads YouTube video using yt-dlp
- Samples frames every 2 seconds (max 100 frames)
- Runs InsightFace detection on each frame
- Extracts face crops and embeddings
- Stores results in Modal volume and uploads to Cloudflare KV

**Duration:** 5-10 minutes for typical video

**Status updates:**
- `queued` → `processing` → `completed` (or `failed`)

### Phase 2: Face Validation (Manual)

**What happens:**
- Admin reviews detected faces via admin UI
- Validates or corrects recognition results
- Flags incorrect identifications

**API Endpoints:**
```bash
# Get face samples
GET /api/admin/youtube/samples?queue_id=yt_abc123_1234567890

# Validate a face
POST /api/admin/youtube/validate
{
  "queue_id": "yt_abc123_1234567890",
  "sample_id": "yt_abc123_1234567890_0",
  "is_correct": false,
  "correct_contestant_id": "contestant_42",
  "notes": "Misidentified due to lighting"
}
```

### Phase 3: Embedding Bootstrap

**What happens:**
- Combines validated YouTube faces with supplied photos
- Generates improved embeddings
- Updates ChromaDB collection
- System now has better recognition accuracy

**Trigger bootstrap:**
```bash
POST /api/admin/youtube/bootstrap
{
  "queue_id": "yt_abc123_1234567890",
  "use_supplied_photos": true
}
```

Or run Modal script directly:
```bash
modal run scripts/modal_youtube_processor.py --bootstrap --queue-id yt_abc123_1234567890
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   YOUTUBE INGESTION PIPELINE                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. ADMIN UI                2. QUEUE PROCESSOR                   │
│  ┌──────────┐              ┌─────────────┐                      │
│  │ Submit   │──────────────▶│ Poll Queue  │                      │
│  │ YouTube  │              │ (Node.js)   │                      │
│  │ URL      │              └──────┬──────┘                      │
│  └──────────┘                     │                             │
│       │                           ▼                             │
│       ▼                    ┌─────────────┐                      │
│  ┌──────────┐              │   Trigger   │                      │
│  │ KV Store │◀─────────────│   Modal     │                      │
│  │  Queue   │              │  Processing │                      │
│  └──────────┘              └──────┬──────┘                      │
│                                   │                             │
│  3. MODAL PROCESSING              ▼                             │
│  ┌────────────────────────────────────────┐                     │
│  │ • Download YouTube video (yt-dlp)      │                     │
│  │ • Sample frames (every 2s, max 100)    │                     │
│  │ • Detect faces (InsightFace)           │                     │
│  │ • Extract embeddings                   │                     │
│  │ • Run recognition (ChromaDB)           │                     │
│  └────────────────┬───────────────────────┘                     │
│                   │                                             │
│                   ▼                                             │
│  ┌────────────────────────────────────────┐                     │
│  │ Upload Results to KV:                  │                     │
│  │ • youtube_detections_{queue_id}        │                     │
│  │ • Update queue status                  │                     │
│  └────────────────────────────────────────┘                     │
│                                                                  │
│  4. ADMIN VALIDATION (Manual)                                   │
│  ┌────────────────────────────────────────┐                     │
│  │ • Review face samples                  │                     │
│  │ • Validate/correct identifications     │                     │
│  │ • Store validations in KV              │                     │
│  └────────────────────────────────────────┘                     │
│                                                                  │
│  5. EMBEDDING BOOTSTRAP                                         │
│  ┌────────────────────────────────────────┐                     │
│  │ • Combine validated faces + photos     │                     │
│  │ • Generate improved embeddings         │                     │
│  │ • Update ChromaDB collection           │                     │
│  └────────────────────────────────────────┘                     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Data Storage

### Cloudflare KV Keys

**Queue Management:**
- `youtube_queue_index` - Array of queue IDs
- `youtube_queue_{queueId}` - Queue entry metadata

**Processing Results:**
- `youtube_detections_{queueId}` - Face detections array
- `youtube_validations_{queueId}` - Admin validation data
- `bootstrap_queue_index` - Bootstrap job queue
- `bootstrap_job_{jobId}` - Bootstrap job metadata

### Modal Volume Structure

```
/data/
├── youtube_downloads/{queueId}/
│   ├── {videoId}.mp4           # Downloaded video
│   └── {videoId}.info.json     # Metadata
├── youtube_samples/{queueId}/
│   ├── frame_000000_face_0.jpg # Face crops
│   └── detections.json         # Detection results
└── chroma_db/                  # ChromaDB storage
```

## API Reference

### Submit Video
```http
POST /api/admin/youtube/submit
Content-Type: application/json

{
  "youtube_url": "https://www.youtube.com/watch?v=abc123",
  "title": "Custom Title (optional)",
  "priority": "normal"  // low, normal, high
}
```

### Get Queue
```http
GET /api/admin/youtube/queue?status=queued&limit=10
```

### Update Status
```http
POST /api/admin/youtube/status
Content-Type: application/json

{
  "queue_id": "yt_abc123_1234567890",
  "status": "processing",  // queued, processing, completed, failed
  "error": "Error message (for failed status)"
}
```

### Get Face Samples
```http
GET /api/admin/youtube/samples?queue_id=yt_abc123_1234567890
```

### Validate Face
```http
POST /api/admin/youtube/validate
Content-Type: application/json

{
  "queue_id": "yt_abc123_1234567890",
  "sample_id": "yt_abc123_1234567890_0",
  "is_correct": false,
  "correct_contestant_id": "contestant_42",
  "notes": "Optional notes"
}
```

### Trigger Bootstrap
```http
POST /api/admin/youtube/bootstrap
Content-Type: application/json

{
  "queue_id": "yt_abc123_1234567890",
  "use_supplied_photos": true
}
```

## Troubleshooting

### Video Download Fails

**Issue:** Modal can't download YouTube video

**Solutions:**
- Check if video is private/unavailable
- Update yt-dlp: `pip install --upgrade yt-dlp`
- Check Modal logs for detailed error

### No Faces Detected

**Issue:** Processing completes but no faces found

**Possible causes:**
- Video quality too low
- Faces too small (< 20px)
- Lighting conditions poor

**Solutions:**
- Try different video
- Adjust `det_size` parameter in Modal script
- Reduce sample interval for more frames

### Queue Processor Not Finding Entries

**Issue:** `process-youtube-queue.js` shows no entries

**Solutions:**
1. Check environment variables:
   ```bash
   echo $CLOUDFLARE_API_TOKEN
   echo $CLOUDFLARE_ACCOUNT_ID
   ```

2. Verify KV namespace ID in script matches deployment

3. Check API endpoint is accessible:
   ```bash
   curl "https://mv-face-recognition-api.herballemon.workers.dev/api/system/status"
   ```

### Modal Processing Hangs

**Issue:** Modal script doesn't complete

**Solutions:**
- Check Modal dashboard for GPU availability
- Increase timeout in Modal decorator
- Monitor Modal logs: `modal logs mv-youtube-processor`

## Performance Metrics

**Typical processing times:**
- 5-minute video: ~8-12 minutes total
  - Download: 1-2 minutes
  - Frame sampling & detection: 5-8 minutes
  - Recognition: 1-2 minutes

**Resource requirements:**
- Modal: T4 GPU (default)
- Storage: ~500MB per video (temporary)
- KV: ~100KB per video metadata

## Best Practices

1. **Priority Management:**
   - Use `high` priority for urgent videos
   - Use `low` priority for batch processing

2. **Validation Quality:**
   - Review at least 50% of detected faces
   - Focus on ambiguous or low-confidence detections
   - Add notes for future reference

3. **Bootstrap Timing:**
   - Wait until you have 10+ validated samples per contestant
   - Include supplied photos for better coverage
   - Re-run after significant validation updates

4. **Queue Management:**
   - Use continuous mode for active processing periods
   - Monitor failed entries and retry with fixes
   - Clean up old completed entries periodically

## Future Enhancements

- [ ] Automatic queue processing via Cloudflare Workers Cron
- [ ] Web UI for face validation (currently API-only)
- [ ] Webhook notifications for processing completion
- [ ] Batch video submission
- [ ] Real-time processing status updates via WebSocket

---

**Last Updated:** January 2025
**Status:** Production Ready
