# Modal-Frontend Integration Design

## Architecture Overview

**Goal**: Enable triggering Modal cloud processing from the web frontend for:
1. Initial video processing
2. Post face-flagging embedding updates

**Key Components**:
- Cloudflare Worker API (existing) - for job queue management
- Modal.com - for GPU-accelerated processing
- SvelteKit Frontend - for user interface
- WebSocket - for real-time job status

## API Endpoints Required

### 1. Trigger Processing Job
```typescript
POST /api/modal/trigger-processing

Request:
{
  "video_names": ["video1.mp4", "video2.mp4"],  // Optional: empty = all videos
  "mode": "full" | "initial" | "embedding-update",
  "similarity_threshold": 0.25,
  "force_reprocess": false,
  "sync_from_hf": true,        // For embedding update after flagging
  "upload_results": true
}

Response:
{
  "success": true,
  "job_id": "modal-job-uuid",
  "status": "queued",
  "estimated_time_minutes": 15
}
```

### 2. Get Job Status
```typescript
GET /api/modal/job/:job_id

Response:
{
  "job_id": "modal-job-uuid",
  "status": "queued" | "running" | "completed" | "failed",
  "progress": 65,  // 0-100
  "current_video": "video1.mp4",
  "videos_processed": 2,
  "total_videos": 5,
  "results": {...},  // Available when completed
  "error": "..."  // If failed
}
```

### 3. List Active Jobs
```typescript
GET /api/modal/jobs

Response:
{
  "jobs": [...]
}
```

### 4. Cancel Job
```typescript
POST /api/modal/job/:job_id/cancel
```

## WebSocket Events

**Connection**: `wss://api.yourdomain.com/ws/modal-jobs`

**Events from Server**:
```typescript
{
  "type": "job_started",
  "job_id": "...",
  "timestamp": "..."
}

{
  "type": "job_progress",
  "job_id": "...",
  "progress": 65,
  "current_video": "...",
  "containers_active": 3
}

{
  "type": "job_completed",
  "job_id": "...",
  "total_time": 892,
  "results": {...}
}

{
  "type": "job_failed",
  "job_id": "...",
  "error": "..."
}
```

## Backend Architecture (Worker)

### Modal Job Manager Service
```typescript
// Worker-level job queue
interface ModalJob {
  id: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
  mode: 'full' | 'initial' | 'embedding-update';
  params: ModalJobParams;
  created_at: number;
  started_at?: number;
  completed_at?: number;
  results?: any;
  error?: string;
  webhooks: string[];  // WebSocket client IDs to notify
}

class ModalJobManager {
  private jobs: Map<string, ModalJob> = new Map();
  private activeContainers: number = 0;
  private maxContainers: number = 5;
  
  async triggerJob(params: ModalJobParams): Promise<string>;
  async getJobStatus(jobId: string): Promise<ModalJob | null>;
  async cancelJob(jobId: string): Promise<boolean>;
  async processQueue(): Promise<void>;
  broadcastToWebSocket(job: ModalJob, event: string): void;
}
```

### Job Processing Flow
1. Frontend calls `POST /api/modal/trigger-processing`
2. Worker creates job in KV store (with unique ID)
3. Worker adds job to processing queue
4. Worker spawns Modal function depending on mode:
   - `full/initial`: `modal_hf_processor.py --process-videos`
   - `embedding-update`: `modal_hf_processor.py --update-embeddings`
5. Worker monitors Modal execution via logs/results
6. Worker updates job status in KV and broadcasts via WebSocket
7. Frontend receives real-time updates via WebSocket

### Modal Integration
```python
# In Worker (via child_process or modal client)
import subprocess
import json

def run_modal_job(job_params):
    cmd = [
        "modal", "run", "scripts/modal_hf_processor.py",
        "--similarity-threshold", str(job_params['similarity_threshold'])
    ]
    
    if job_params['mode'] == 'embedding-update':
        cmd.extend(["--update-embeddings", "--sync-from-hf"])
    else:
        if job_params.get('video_names'):
            cmd.extend(["--single-video", job_params['video_names'][0]])
        else:
            cmd.extend(["--process-videos"])
        
        if job_params.get('force_reprocess'):
            cmd.append("--force-reprocess")
    
    # Run Modal and capture output
    result = subprocess.run(cmd, capture_output=True, text=True, cwd="/")
    
    # Parse results from volume or stdout
    return parse_modal_output(result.stdout, result.stderr)
```

## Frontend Implementation

### 1. API Client Functions (add to api.ts)
```typescript
export interface ModalJobParams {
  video_names?: string[];
  mode: 'full' | 'initial' | 'embedding-update';
  similarity_threshold?: number;
  force_reprocess?: boolean;
  sync_from_hf?: boolean;
  upload_results?: boolean;
}

export interface ModalJob {
  id: string;
  status: string;
  progress: number;
  current_video?: string;
  videos_processed?: number;
  total_videos?: number;
  results?: any;
  error?: string;
}

export async function triggerModalJob(params: ModalJobParams): Promise<{ job_id: string }> {
  return apiRequest('/modal/trigger-processing', {
    method: 'POST',
    body: JSON.stringify(params)
  });
}

export async function getModalJobStatus(jobId: string): Promise<ModalJob> {
  return apiRequest(`/modal/job/${jobId}`);
}

export async function getModalJobs(): Promise<{ jobs: ModalJob[] }> {
  return apiRequest('/modal/jobs');
}

// WebSocket manager for real-time updates
export class ModalJobWebSocket extends WebSocketManager {
  constructor() {
    super('wss://api.yourdomain.com/ws/modal-jobs');
  }
  
  onJobProgress(callback: (job: ModalJob) => void) {
    this.connect((data) => {
      if (data.type === 'job_progress' || data.type === 'job_completed') {
        callback(data.job);
      }
    });
  }
}
```

### 2. Processing Page Component (enhance existing)
```svelte
<script lang="ts">
  import { onMount } from 'svelte';
  import { triggerModalJob, getModalJobs, ModalJobWebSocket } from '$lib/utils/api';
  import { processingJobs } from '$lib/stores/processingJobs';
  
  let ws: ModalJobWebSocket;
  let isConnecting = false;
  
  async function handleStartProcessing() {
    const { job_id } = await triggerModalJob({
      mode: 'initial',
      similarity_threshold: 0.25,
      sync_from_hf: true
    });
    
    // Add to local store
    processingJobs.addJob({
      id: job_id,
      status: 'queued',
      progress: 0,
      mode: 'initial'
    });
  }
  
  async function handleUpdateEmbeddings() {
    const { job_id } = await triggerModalJob({
      mode: 'embedding-update',
      sync_from_hf: true
    });
    
    processingJobs.addJob({
      id: job_id,
      status: 'queued',
      progress: 0,
      mode: 'embedding-update'
    });
  }
  
  onMount(() => {
    // Connect to WebSocket for real-time updates
    ws = new ModalJobWebSocket();
    ws.onJobProgress((job) => {
      processingJobs.updateJob(job.id, job);
    });
    ws.connect();
    
    // Load existing jobs on mount
    getModalJobs().then(({ jobs }) => {
      jobs.forEach(job => processingJobs.addJob(job));
    });
  });
</script>

<div class="processing-dashboard">
  <div class="controls">
    <button on:click={handleStartProcessing}>
      🚀 Start Initial Processing
    </button>
    <button on:click={handleUpdateEmbeddings}>
      🔄 Update Embeddings from Flagged Faces
    </button>
  </div>
  
  <div class="active-jobs">
    {#each $processingJobs as job}
      <JobCard {job} />
    {/each}
  </div>
</div>
```

### 3. Job Status Store
```typescript
// src/lib/stores/processingJobs.ts
import { writable } from 'svelte/store';
import type { ModalJob } from '$lib/utils/api';

function createProcessingJobsStore() {
  const { subscribe, update } = writable<ModalJob[]>([]);
  
  return {
    subscribe,
    addJob: (job: ModalJob) => update(jobs => [...jobs, job]),
    updateJob: (jobId: string, updates: Partial<ModalJob>) => 
      update(jobs => jobs.map(j => j.id === jobId ? { ...j, ...updates } : j)),
    removeJob: (jobId: string) => 
      update(jobs => jobs.filter(j => j.id !== jobId))
  };
}

export const processingJobs = createProcessingJobsStore();
```

## Security Considerations

### 1. API Authentication
```typescript
// In Worker API endpoints
async function handleModalTrigger(request, env) {
  const auth = request.headers.get('Authorization');
  
  // Verify JWT or API key
  const isValid = await verifyAuth(auth, env);
  if (!isValid) {
    return new Response('Unauthorized', { status: 401 });
  }
  
  // Proceed with job trigger
}
```

### 2. Rate Limiting
```typescript
// Limit Modal job triggers per user/IP
const rateLimiter = new RateLimiter({
  tokensPerInterval: 3,
  interval: 'hour'
});

if (!(await rateLimiter.checkLimit(userId))) {
  return new Response('Rate limit exceeded', { status: 429 });
}
```

### 3. Input Validation
```typescript
// Validate job parameters
const schema = z.object({
  mode: z.enum(['full', 'initial', 'embedding-update']),
  similarity_threshold: z.number().min(0.0).max(1.0).default(0.25),
  video_names: z.array(z.string()).max(50).optional()
});

const result = schema.safeParse(params);
if (!result.success) {
  return new Response('Invalid parameters', { status: 400 });
}
```

## Deployment Checklist

- [ ] Add Modal API token to Worker secrets
- [ ] Configure HuggingFace token in Modal secrets
- [ ] Set up KV namespace for job persistence
- [ ] Configure WebSocket endpoint in Worker
- [ ] Add rate limiting to API endpoints
- [ ] Implement proper error handling and logging
- [ ] Add job timeout/cleanup mechanism
- [ ] Test Modal job cancellation
- [ ] Add frontend loading states and error messages
- [ ] Implement job history persistence (R2/KV)

## Integration Points Summary

1. **Frontend → Worker**: HTTP API calls to trigger/monitor jobs
2. **Worker → Modal**: CLI commands via `modal run`
3. **Modal → HuggingFace**: Upload/download dataset
4. **Worker → Frontend**: WebSocket for real-time updates
5. **Worker State**: KV store for job persistence across requests

This architecture provides a complete, secure, and real-time integration between the web frontend and Modal cloud processing.