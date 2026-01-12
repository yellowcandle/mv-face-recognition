<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import {
    triggerModalJob,
    getModalJobs,
    cancelModalJob,
    clearCompletedJobs,
    WebSocketManager,
    formatTimestamp
  } from '$lib/utils/api';
  import { processingJobs } from '$lib/stores/processingJobs';
  import Card from '$lib/components/Card.svelte';
  import Button from '$lib/components/Button.svelte';
  import Badge from '$lib/components/Badge.svelte';
  import StatusIndicator from '$lib/components/StatusIndicator.svelte';
  import IconButton from '$lib/components/IconButton.svelte';
  
  let error: string | null = null;
  let isProcessing = false;
  let ws: WebSocketManager | null = null;
  let mounted = false;
  
  // Load existing jobs on mount
  onMount(async () => {
    mounted = true;
    
    try {
      // Connect to WebSocket for real-time updates
      const wsUrl = window.location.origin.replace('http', 'ws') + '/ws/modal-jobs';
      ws = new WebSocketManager(wsUrl);
      
      ws.connect(
        (data) => {
          // Handle job updates from WebSocket
          if (data.job || data.job_id) {
            const job = data.job || { id: data.job_id, ...data };
            processingJobs.updateJob(job.id, job);
          }
        },
        (error) => {
          console.error('WebSocket error:', error);
        }
      );
      
      // Load existing jobs
      const { jobs } = await getModalJobs();
      jobs.forEach(job => processingJobs.addJob(job));
    } catch (err) {
      console.error('Failed to load jobs:', err);
      error = 'Failed to connect to processing service';
    }
    
    // Refresh job status every 5 seconds
    const interval = setInterval(async () => {
      try {
        const { jobs } = await getModalJobs();
        jobs.forEach(job => processingJobs.updateJob(job.id, job));
      } catch (err) {
        console.error('Failed to refresh jobs:', err);
      }
    }, 5000);
    
    return () => {
      clearInterval(interval);
      ws?.disconnect();
    };
  });
  
  onDestroy(() => {
    mounted = false;
    ws?.disconnect();
  });
  
  async function handleStartInitialProcessing() {
    isProcessing = true;
    error = null;
    
    try {
      const { job_id } = await triggerModalJob({
        mode: 'initial',
        similarity_threshold: 0.25,
        sync_from_hf: true,
        upload_results: true
      });
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to start processing';
    } finally {
      isProcessing = false;
    }
  }
  
  async function handleUpdateEmbeddings() {
    isProcessing = true;
    error = null;
    
    try {
      const { job_id } = await triggerModalJob({
        mode: 'embedding-update',
        sync_from_hf: true
      });
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to update embeddings';
    } finally {
      isProcessing = false;
    }
  }
  
  async function handleCancelJob(jobId: string) {
    try {
      await cancelModalJob(jobId);
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to cancel job';
    }
  }
  
  async function handleClearCompleted() {
    try {
      await clearCompletedJobs();
      processingJobs.clearCompleted();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to clear completed jobs';
    }
  }
  
  function getStatusColor(status: string): string {
    switch (status) {
      case 'completed': return '#22c55e';
      case 'running': return '#3b82f6';
      case 'failed': return '#ef4444';
      case 'cancelled': return '#6b7280';
      default: return '#f59e0b';
    }
  }
  
  function formatDuration(start?: number, end?: number): string {
    if (!start) return '--';
    const endTime = end || Date.now();
    const diff = Math.floor((endTime - start) / 1000);
    const mins = Math.floor(diff / 60);
    const secs = diff % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  }
  
  $: activeJobsCount = $processingJobs.filter(j => j.status === 'running' || j.status === 'queued').length;
  $: completedJobsCount = $processingJobs.filter(j => j.status === 'completed').length;
</script>

<div class="processing-page">
  <div class="header">
    <h1>Video Processing</h1>
    <p>Manage Modal cloud processing jobs for face recognition</p>
  </div>
  
  {#if error}
    <div class="error-banner">
      {error}
    </div>
  {/if}
  
  {#if activeJobsCount > 0}
    <div class="status-banner active">
      🔄 {activeJobsCount} job{activeJobsCount !== 1 ? 's' : ''} running
    </div>
  {/if}
  
  <div class="processing-grid">
    <Card>
      <div class="card-header">
        <h2>Initial Processing</h2>
        <StatusIndicator status="ready" />
      </div>
      
      <p class="description">
        Process all videos using cloud GPUs for initial face detection and recognition
      </p>
      
      <div class="controls">
        <Button
          on:click={handleStartInitialProcessing}
          disabled={isProcessing}
          loading={isProcessing}
          variant="primary"
          fullWidth
        >
          🚀 Start Processing
        </Button>
      </div>
      
      <div class="features">
        <ul>
          <li>🎬 Process all unprocessed videos</li>
          <li>👥 Detect and recognize faces</li>
          <li>⚡ Cloud GPU acceleration</li>
          <li>☁️ Automatic HuggingFace sync</li>
        </ul>
      </div>
    </Card>
    
    <Card>
      <div class="card-header">
        <h2>Embedding Update</h2>
        <StatusIndicator status="ready" />
      </div>
      
      <p class="description">
        Improve recognition accuracy by incorporating user-flagged faces into embeddings
      </p>
      
      <div class="controls">
        <Button
          on:click={handleUpdateEmbeddings}
          disabled={isProcessing}
          loading={isProcessing}
          variant="secondary"
          fullWidth
        >
          🔄 Update Embeddings
        </Button>
      </div>
      
      <div class="features">
        <ul>
          <li>🎯 Improve face recognition accuracy</li>
          <li>🏷️ Incorporate user feedback</li>
          <li>⚡ Fast embedding recalculation</li>
          <li>🔄 Automatic database rebuild</li>
        </ul>
      </div>
    </Card>
  </div>
  
  <Card>
    <div class="card-header">
      <h2>Processing Jobs</h2>
      <div class="job-stats">
        <Badge color="#3b82f6">{activeJobsCount} Active</Badge>
        <Badge color="#22c55e">{completedJobsCount} Completed</Badge>
        {#if completedJobsCount > 0}
          <Button
            size="small"
            variant="text"
            on:click={handleClearCompleted}
          >
            Clear Completed
          </Button>
        {/if}
      </div>
    </div>
    
    {#if $processingJobs.length === 0}
      <div class="empty-state">
        <p>No processing jobs yet</p>
        <p class="help">Start a processing job to see it here</p>
      </div>
    {:else}
      <div class="job-list">
        {#each $processingJobs as job}
          <div class="job-item">
            <div class="job-main">
              <div class="job-header">
                <h3>{job.mode ? job.mode.replace('-', ' ').toUpperCase() : 'Processing'}</h3>
                <Badge color={getStatusColor(job.status)}>
                  {job.status}
                </Badge>
              </div>
              
              {#if job.current_video}
                <p class="current-video">📹 {job.current_video}</p>
              {/if}
              
              {#if job.videos_processed !== undefined && job.total_videos}
                <p class="video-progress">
                  {job.videos_processed} / {job.total_videos} videos
                </p>
              {/if}
              
              <div class="progress-section">
                <div class="progress-bar">
                  <div
                    class="progress-fill"
                    style="width: {job.progress || 0}%"
                  ></div>
                </div>
                <span class="progress-text">{job.progress || 0}%</span>
              </div>
            </div>
            
            <div class="job-actions">
              {#if job.status === 'queued' || job.status === 'running'}
                <IconButton
                  icon="x-circle"
                  title="Cancel job"
                  on:click={() => handleCancelJob(job.id)}
                  disabled={job.status === 'cancelled'}
                />
              {/if}
              
              <div class="job-times">
                {#if job.created_at}
                  <span class="time-label">Created: {formatTimestamp(new Date(job.created_at).toISOString())}</span>
                {/if}
                {#if job.started_at}
                  <span class="time-label">Duration: {formatDuration(job.started_at, job.completed_at)}</span>
                {/if}
              </div>
            </div>
          </div>
        {/each}
      </div>
    {/if}
  </Card>
</div>

<style>
  .processing-page {
    max-width: 1400px;
    margin: 0 auto;
    padding: 2rem;
  }
  
  .header {
    margin-bottom: 2rem;
    
    h1 {
      font-size: 2rem;
      font-weight: 600;
      margin-bottom: 0.5rem;
      color: #1f2937;
    }
    
    p {
      color: #6b7280;
      font-size: 1.125rem;
    }
  }
  
  .error-banner {
    background: #fee2e2;
    border: 1px solid #ef4444;
    color: #991b1b;
    padding: 1rem;
    border-radius: 0.75rem;
    margin-bottom: 1.5rem;
    font-weight: 500;
  }
  
  .status-banner {
    padding: 1rem 1.5rem;
    border-radius: 0.75rem;
    margin-bottom: 1.5rem;
    font-weight: 500;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    
    &.active {
      background: #dbeafe;
      border: 1px solid #3b82f6;
      color: #1d4ed8;
    }
  }
  
  .processing-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
    gap: 1.5rem;
    margin-bottom: 2rem;
  }
  
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
    
    h2 {
      font-size: 1.25rem;
      font-weight: 600;
      margin: 0;
      color: #1f2937;
    }
  }
  
  .description {
    color: #6b7280;
    margin-bottom: 1.5rem;
    line-height: 1.5;
  }
  
  .controls {
    margin-bottom: 1.5rem;
  }
  
  .features {
    ul {
      list-style: none;
      padding: 0;
      margin: 0;
      
      li {
        padding: 0.25rem 0;
        color: #6b7280;
        font-size: 0.875rem;
        
        &:before {
          content: '✓';
          color: #10b981;
          font-weight: bold;
          margin-right: 0.5rem;
        }
      }
    }
  }
  
  .job-stats {
    display: flex;
    gap: 0.5rem;
    align-items: center;
  }
  
  .empty-state {
    text-align: center;
    padding: 3rem;
    color: #9ca3af;
    
    .help {
      font-size: 0.875rem;
      margin-top: 0.5rem;
    }
  }
  
  .job-list {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }
  
  .job-item {
    border: 1px solid #e5e7eb;
    border-radius: 0.75rem;
    padding: 1.25rem;
    background: #f9fafb;
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    transition: box-shadow 0.2s ease;
    
    &:hover {
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    }
    
    .job-main {
      flex: 1;
    }
    
    .job-header {
      display: flex;
      gap: 0.75rem;
      align-items: center;
      margin-bottom: 0.75rem;
      
      h3 {
        margin: 0;
        font-size: 1rem;
        font-weight: 600;
        color: #1f2937;
      }
    }
    
    .current-video {
      margin: 0.25rem 0;
      font-size: 0.875rem;
      color: #6b7280;
      font-weight: 500;
    }
    
    .video-progress {
      margin: 0.5rem 0;
      font-size: 0.875rem;
      color: #374151;
      font-weight: 500;
    }
    
    .progress-section {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      margin: 0.75rem 0;
      
      .progress-bar {
        flex: 1;
        height: 8px;
        background: #e5e7eb;
        border-radius: 4px;
        overflow: hidden;
        
        .progress-fill {
          height: 100%;
          background: #3b82f6;
          transition: width 0.3s ease;
        }
      }
      
      .progress-text {
        font-size: 0.875rem;
        font-weight: 600;
        color: #374151;
        min-width: 40px;
      }
    }
    
    .job-actions {
      display: flex;
      flex-direction: column;
      align-items: flex-end;
      gap: 0.5rem;
      margin-left: 1rem;
      
      .job-times {
        display: flex;
        flex-direction: column;
        align-items: flex-end;
        gap: 0.25rem;
        
        .time-label {
          font-size: 0.75rem;
          color: #6b7280;
        }
      }
    }
  }
</style>
