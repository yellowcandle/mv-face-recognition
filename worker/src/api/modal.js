/**
 * Modal Job Management API
 * Handles triggering and monitoring Modal cloud processing jobs
 */

import { z } from 'zod';

// Job status tracking
const JobStatus = {
  QUEUED: 'queued',
  RUNNING: 'running',
  COMPLETED: 'completed',
  FAILED: 'failed',
  CANCELLED: 'cancelled'
};

// Validation schema for job parameters
const ModalJobParamsSchema = z.object({
  video_names: z.array(z.string()).max(50).optional(),
  mode: z.enum(['full', 'initial', 'embedding-update']),
  similarity_threshold: z.number().min(0.0).max(1.0).default(0.25),
  force_reprocess: z.boolean().default(false),
  sync_from_hf: z.boolean().default(true),
  upload_results: z.boolean().default(true)
});

/**
 * Generate unique job ID
 */
function generateJobId() {
  return `modal-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * Estimate processing time based on parameters
 */
function estimateProcessingTime(params) {
  const videoCount = params.video_names?.length || 5;
  const baseTimePerVideo = 3; // minutes
  const embeddingUpdateTime = 10; // minutes
  
  if (params.mode === 'embedding-update') {
    return embeddingUpdateTime;
  }
  
  return Math.ceil(videoCount * baseTimePerVideo);
}

/**
 * Create a new Modal job
 */
export async function createModalJob(env, params) {
  try {
    // Validate parameters
    const validated = ModalJobParamsSchema.parse(params);
    
    // Generate job ID
    const jobId = generateJobId();
    
    // Create job record
    const job = {
      id: jobId,
      status: JobStatus.QUEUED,
      mode: validated.mode,
      params: validated,
      created_at: Date.now(),
      progress: 0,
      webhooks: [] // WebSocket client IDs
    };
    
    // Store in KV
    await env.MODAL_JOBS.put(jobId, JSON.stringify(job));
    
    // Trigger job asynchronously
    processModalJob(env, jobId).catch(console.error);
    
    return {
      success: true,
      job_id: jobId,
      status: JobStatus.QUEUED,
      estimated_time_minutes: estimateProcessingTime(validated)
    };
  } catch (error) {
    console.error('Error creating Modal job:', error);
    throw new Error(`Failed to create job: ${error.message}`);
  }
}

/**
 * Get job status
 */
export async function getModalJob(env, jobId) {
  try {
    const jobData = await env.MODAL_JOBS.get(jobId);
    
    if (!jobData) {
      return { error: 'Job not found', status: 404 };
    }
    
    const job = JSON.parse(jobData);
    
    return {
      job_id: job.id,
      status: job.status,
      progress: job.progress || 0,
      current_video: job.current_video,
      videos_processed: job.videos_processed || 0,
      total_videos: job.total_videos || job.params.video_names?.length || 1,
      created_at: job.created_at,
      started_at: job.started_at,
      completed_at: job.completed_at,
      results: job.results,
      error: job.error,
      mode: job.mode
    };
  } catch (error) {
    console.error(`Error fetching job ${jobId}:`, error);
    return { error: 'Failed to fetch job status', status: 500 };
  }
}

/**
 * List all jobs
 */
export async function listModalJobs(env) {
  try {
    const list = await env.MODAL_JOBS.list();
    const jobs = [];
    
    for (const key of list.keys) {
      const jobData = await env.MODAL_JOBS.get(key.name);
      if (jobData) {
        const job = JSON.parse(jobData);
        jobs.push({
          id: job.id,
          status: job.status,
          progress: job.progress || 0,
          mode: job.mode,
          created_at: job.created_at,
          current_video: job.current_video,
          error: job.error
        });
      }
    }
    
    // Sort by creation time (newest first)
    jobs.sort((a, b) => b.created_at - a.created_at);
    
    return { jobs };
  } catch (error) {
    console.error('Error listing jobs:', error);
    return { jobs: [] };
  }
}

/**
 * Cancel a job
 */
export async function cancelModalJob(env, jobId) {
  try {
    const jobData = await env.MODAL_JOBS.get(jobId);
    
    if (!jobData) {
      return { error: 'Job not found', status: 404 };
    }
    
    const job = JSON.parse(jobData);
    
    // Only allow cancelling queued or running jobs
    if (![JobStatus.QUEUED, JobStatus.RUNNING].includes(job.status)) {
      return { error: 'Job cannot be cancelled in current state', status: 400 };
    }
    
    // Update job status to cancelled
    job.status = JobStatus.CANCELLED;
    job.completed_at = Date.now();
    
    await env.MODAL_JOBS.put(jobId, JSON.stringify(job));
    
    // Broadcast cancellation to WebSocket clients
    await broadcastJobUpdate(env, jobId, job.status);
    
    return { success: true, job_id: jobId, status: JobStatus.CANCELLED };
  } catch (error) {
    console.error(`Error cancelling job ${jobId}:`, error);
    return { error: 'Failed to cancel job', status: 500 };
  }
}

/**
 * Clear completed jobs
 */
export async function clearCompletedJobs(env) {
  try {
    const list = await env.MODAL_JOBS.list();
    let cleared = 0;
    
    for (const key of list.keys) {
      const jobData = await env.MODAL_JOBS.get(key.name);
      if (jobData) {
        const job = JSON.parse(jobData);
        // Remove completed/failed/cancelled jobs
        if ([JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED].includes(job.status)) {
          await env.MODAL_JOBS.delete(key.name);
          cleared++;
        }
      }
    }
    
    return { success: true, cleared };
  } catch (error) {
    console.error('Error clearing completed jobs:', error);
    return { error: 'Failed to clear completed jobs', status: 500 };
  }
}

/**
 * Process a Modal job (actual Modal execution)
 * This runs in the background and updates job status
 */
async function processModalJob(env, jobId) {
  try {
    // Get job from KV
    const jobData = await env.MODAL_JOBS.get(jobId);
    if (!jobData) {
      console.error(`Job ${jobId} not found`);
      return;
    }
    
    let job = JSON.parse(jobData);
    
    // Update status to running
    job.status = JobStatus.RUNNING;
    job.started_at = Date.now();
    await env.MODAL_JOBS.put(jobId, JSON.stringify(job));
    
    // Broadcast status update
    await broadcastJobUpdate(env, jobId, JobStatus.RUNNING);
    
    // Build Modal command
    const cmd = buildModalCommand(job.params);
    
    // Execute Modal command
    // Note: In Cloudflare Worker, we'd use a Durable Object or Queue
    // For now, this simulates the process
    const result = await executeModalCommand(env, cmd, job, (progress) => {
      // Update progress
      job.progress = Math.min(100, progress);
      env.MODAL_JOBS.put(jobId, JSON.stringify(job)).catch(console.error);
      broadcastJobUpdate(env, jobId, JobStatus.RUNNING, job.progress).catch(console.error);
    });
    
    // Update job with results
    job.status = result.success ? JobStatus.COMPLETED : JobStatus.FAILED;
    job.completed_at = Date.now();
    job.results = result;
    if (result.error) job.error = result.error;
    
    await env.MODAL_JOBS.put(jobId, JSON.stringify(job));
    
    // Broadcast completion
    await broadcastJobUpdate(env, jobId, job.status, 100, result);
    
  } catch (error) {
    console.error(`Error processing job ${jobId}:`, error);
    
    // Update job status to failed
    try {
      const jobData = await env.MODAL_JOBS.get(jobId);
      if (jobData) {
        const job = JSON.parse(jobData);
        job.status = JobStatus.FAILED;
        job.completed_at = Date.now();
        job.error = error.message;
        
        await env.MODAL_JOBS.put(jobId, JSON.stringify(job));
        await broadcastJobUpdate(env, jobId, JobStatus.FAILED, 0, null, error.message);
      }
    } catch (updateError) {
      console.error('Failed to update failed job status:', updateError);
    }
  }
}

/**
 * Build Modal command from job parameters
 */
function buildModalCommand(params) {
  const cmd = [
    'modal', 'run', 'scripts/modal_hf_processor.py',
    '--similarity-threshold', params.similarity_threshold.toString()
  ];
  
  if (params.mode === 'embedding-update') {
    cmd.push('--update-embeddings');
    cmd.push('--sync-from-hf');
  } else {
    if (params.video_names && params.video_names.length > 0) {
      cmd.push('--single-video', params.video_names[0]);
    } else {
      cmd.push('--process-videos');
    }
    
    if (params.force_reprocess) {
      cmd.push('--force-reprocess');
    }
    
    if (params.sync_from_hf) {
      cmd.push('--sync-from-hf');
    }
    
    if (params.upload_results) {
      cmd.push('--upload-results');
    }
  }
  
  return cmd;
}

/**
 * Execute Modal command (simulated for Worker environment)
 * In production, this would use Modal's API or spawn a process
 */
async function executeModalCommand(env, cmd, job, onProgress) {
  console.log('Executing Modal command:', cmd.join(' '));
  
  // Simulate processing for demonstration
  return new Promise((resolve, reject) => {
    let progress = 0;
    const interval = setInterval(() => {
      progress += Math.random() * 15;
      if (progress >= 100) {
        progress = 100;
        clearInterval(interval);
        
        // Simulate result
        resolve({
          success: true,
          videos_processed: job.params.video_names?.length || 5,
          faces_detected: 150,
          faces_recognized: 120,
          processing_time: 892
        });
      }
      onProgress(progress);
    }, 1000);
  });
}

/**
 * Broadcast job update to WebSocket clients
 */
async function broadcastJobUpdate(env, jobId, status, progress = null, result = null, error = null) {
  // This would broadcast to WebSocket clients via Durable Object
  // For now, we'll store the update in KV for polling
  const update = {
    type: 'job_update',
    job_id: jobId,
    status,
    timestamp: Date.now()
  };
  
  if (progress !== null) update.progress = progress;
  if (result) update.result = result;
  if (error) update.error = error;
  
  // Store in KV for polling (could use a separate namespace)
  await env.MODAL_JOBS.put(`ws:${jobId}:${Date.now()}`, JSON.stringify(update), {
    expirationTtl: 3600 // 1 hour
  }).catch(console.error);
}