<script lang="ts">
  import { onMount } from 'svelte';
  import Card from '$lib/components/Card.svelte';
  import Badge from '$lib/components/Badge.svelte';
  import Button from '$lib/components/Button.svelte';
  import StatusIndicator from '$lib/components/StatusIndicator.svelte';
  
  interface ProcessingJob {
    id: string;
    filename: string;
    status: 'pending' | 'processing' | 'completed' | 'failed';
    progress: number;
    startTime?: Date;
    endTime?: Date;
    faces_detected?: number;
    faces_recognized?: number;
  }
  
  let processingJobs: ProcessingJob[] = [
    {
      id: '1',
      filename: 'video-1.mp4',
      status: 'completed',
      progress: 100,
      startTime: new Date(Date.now() - 300000),
      endTime: new Date(Date.now() - 60000),
      faces_detected: 127,
      faces_recognized: 89
    },
    {
      id: '2',
      filename: 'video-2.mp4',
      status: 'processing',
      progress: 65,
      startTime: new Date(Date.now() - 120000)
    },
    {
      id: '3',
      filename: 'video-3.mp4',
      status: 'pending',
      progress: 0
    }
  ];
  
  let isProcessingActive = true;
  let systemResources = {
    cpu: 45,
    memory: 62,
    gpu: 78
  };
  
  function getStatusColor(status: string): string {
    switch (status) {
      case 'completed': return '#22c55e';
      case 'processing': return '#3b82f6';
      case 'failed': return '#ef4444';
      default: return '#6b7280';
    }
  }
  
  function formatDuration(start?: Date, end?: Date): string {
    if (!start) return '--';
    const endTime = end || new Date();
    const diff = Math.floor((endTime.getTime() - start.getTime()) / 1000);
    const mins = Math.floor(diff / 60);
    const secs = diff % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  }
  
  function startProcessing() {
    // Simulate starting processing for pending jobs
    processingJobs = processingJobs.map(job => {
      if (job.status === 'pending') {
        return {
          ...job,
          status: 'processing',
          startTime: new Date(),
          progress: 1
        };
      }
      return job;
    });
  }
  
  function pauseProcessing() {
    isProcessingActive = false;
  }
  
  function resumeProcessing() {
    isProcessingActive = true;
  }
  
  onMount(() => {
    // Simulate processing progress
    const interval = setInterval(() => {
      if (isProcessingActive) {
        processingJobs = processingJobs.map(job => {
          if (job.status === 'processing' && job.progress < 100) {
            const newProgress = Math.min(100, job.progress + Math.random() * 5);
            if (newProgress >= 100) {
              return {
                ...job,
                status: 'completed',
                progress: 100,
                endTime: new Date(),
                faces_detected: Math.floor(Math.random() * 200 + 50),
                faces_recognized: Math.floor(Math.random() * 150 + 30)
              };
            }
            return { ...job, progress: newProgress };
          }
          return job;
        });
        
        // Update system resources
        systemResources = {
          cpu: Math.max(20, Math.min(90, systemResources.cpu + (Math.random() - 0.5) * 10)),
          memory: Math.max(30, Math.min(95, systemResources.memory + (Math.random() - 0.5) * 8)),
          gpu: Math.max(40, Math.min(100, systemResources.gpu + (Math.random() - 0.5) * 12))
        };
      }
    }, 1000);
    
    return () => clearInterval(interval);
  });
</script>

<svelte:head>
  <title>Processing - Face Recognition Dashboard</title>
</svelte:head>

<div class="processing-container">
  <div class="processing-header">
    <h1>Video Processing</h1>
    <div class="processing-controls">
      {#if isProcessingActive}
        <Button variant="warning" size="sm" on:click={pauseProcessing}>
          ⏸️ Pause Processing
        </Button>
      {:else}
        <Button variant="primary" size="sm" on:click={resumeProcessing}>
          ▶️ Resume Processing
        </Button>
      {/if}
      <Button variant="success" size="sm" on:click={startProcessing}>
        🚀 Start New Job
      </Button>
    </div>
  </div>

  <div class="processing-main">
    <!-- System Status Panel -->
    <Card class="status-panel">
      <h3>System Status</h3>
      
      <div class="status-indicator-wrapper">
        <StatusIndicator 
          status={isProcessingActive ? 'success' : 'neutral'} 
          label={isProcessingActive ? 'Processing Active' : 'Processing Paused'}
        />
      </div>
      
      <div class="resource-metrics">
        <div class="metric">
          <div class="metric-header">
            <span class="metric-label">CPU Usage</span>
            <span class="metric-value">{Math.round(systemResources.cpu)}%</span>
          </div>
          <div class="metric-bar">
            <div 
              class="metric-fill cpu"
              style="width: {systemResources.cpu}%"
            ></div>
          </div>
        </div>
        
        <div class="metric">
          <div class="metric-header">
            <span class="metric-label">Memory Usage</span>
            <span class="metric-value">{Math.round(systemResources.memory)}%</span>
          </div>
          <div class="metric-bar">
            <div 
              class="metric-fill memory"
              style="width: {systemResources.memory}%"
            ></div>
          </div>
        </div>
        
        <div class="metric">
          <div class="metric-header">
            <span class="metric-label">GPU Usage</span>
            <span class="metric-value">{Math.round(systemResources.gpu)}%</span>
          </div>
          <div class="metric-bar">
            <div 
              class="metric-fill gpu"
              style="width: {systemResources.gpu}%"
            ></div>
          </div>
        </div>
      </div>
    </Card>

    <!-- Processing Queue -->
    <Card class="queue-panel">
      <h3>Processing Queue</h3>
      
      <div class="job-list">
        {#each processingJobs as job}
          <div class="job-item" class:active={job.status === 'processing'}>
            <div class="job-header">
              <div class="job-info">
                <h4 class="job-filename">{job.filename}</h4>
                <div class="job-meta">
                  <span class="job-status">
                    <Badge variant={job.status === 'completed' ? 'success' : job.status === 'processing' ? 'primary' : job.status === 'failed' ? 'error' : 'neutral'}>
                      {job.status.toUpperCase()}
                    </Badge>
                  </span>
                  <span class="job-duration">
                    {formatDuration(job.startTime, job.endTime)}
                  </span>
                </div>
              </div>
              
              <div class="job-progress-text">
                {Math.round(job.progress)}%
              </div>
            </div>
            
            <div class="job-progress-bar">
              <div 
                class="job-progress-fill"
                style="width: {job.progress}%; background-color: {getStatusColor(job.status)}"
              ></div>
            </div>
            
            {#if job.status === 'completed'}
              <div class="job-results">
                <div class="result-item">
                  <span class="result-label">Faces Detected:</span>
                  <span class="result-value">{job.faces_detected}</span>
                </div>
                <div class="result-item">
                  <span class="result-label">Faces Recognized:</span>
                  <span class="result-value">{job.faces_recognized}</span>
                </div>
              </div>
            {/if}
            
            {#if job.status === 'processing'}
              <div class="job-details">
                <div class="detail-item">
                  <span>Processing frames...</span>
                </div>
                <div class="detail-item">
                  <span>Detecting faces...</span>
                </div>
              </div>
            {/if}
          </div>
        {/each}
      </div>
    </Card>
  </div>

  <!-- Processing Statistics -->
  <Card class="stats-panel">
    <div class="stats-panel-inner">
      <h3>Processing Statistics</h3>
      
      <div class="stats-grid">
        <Card variant="bordered" padding="sm">
          <div class="stat-card-inner">
            <div class="stat-icon">📊</div>
            <div class="stat-content">
              <div class="stat-value">3</div>
              <div class="stat-label">Total Jobs</div>
            </div>
          </div>
        </Card>
        
        <Card variant="bordered" padding="sm">
          <div class="stat-card-inner">
            <div class="stat-icon">✅</div>
            <div class="stat-content">
              <div class="stat-value">1</div>
              <div class="stat-label">Completed</div>
            </div>
          </div>
        </Card>
        
        <Card variant="bordered" padding="sm">
          <div class="stat-card-inner">
            <div class="stat-icon">⚡</div>
            <div class="stat-content">
              <div class="stat-value">1</div>
              <div class="stat-label">Processing</div>
            </div>
          </div>
        </Card>
        
        <Card variant="bordered" padding="sm">
          <div class="stat-card-inner">
            <div class="stat-icon">⏳</div>
            <div class="stat-content">
              <div class="stat-value">1</div>
              <div class="stat-label">Pending</div>
            </div>
          </div>
        </Card>
      </div>
    </div>
  </Card>
</div>

<style>
  .processing-container {
    height: 100%;
    display: flex;
    flex-direction: column;
    padding: var(--space-5);
    background-color: var(--bg-primary);
    color: var(--text-primary);
    gap: var(--space-5);
  }

  .processing-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: var(--space-4);
    border-bottom: var(--space-px) solid var(--border-default);
  }

  .processing-header h1 {
    font-size: var(--text-h3-size);
    font-weight: var(--text-h3-weight);
    margin: 0;
  }

  .processing-controls {
    display: flex;
    gap: var(--space-2);
  }

  .control-btn {
    padding: 8px 16px;
    border: none;
    border-radius: 6px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
    font-size: 14px;
  }

  .start-btn {
    background-color: #22c55e;
    color: #000;
  }

  .pause-btn {
    background-color: #eab308;
    color: #000;
  }

  .resume-btn {
    background-color: #3b82f6;
    color: #fff;
  }

  .control-btn:hover {
    transform: translateY(-1px);
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
  }

  .processing-main {
    flex: 1;
    display: flex;
    gap: 20px;
    min-height: 0;
  }

  .status-panel {
    width: 300px;
    height: fit-content;
  }

  .status-panel h3 {
    font-size: var(--text-h5-size);
    font-weight: var(--text-h5-weight);
    margin-bottom: var(--space-5);
    color: var(--text-primary);
  }

  .status-indicator-wrapper {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin-bottom: var(--space-6);
    padding: var(--space-3);
    background-color: var(--bg-tertiary);
    border-radius: var(--radius-md);
  }

  .status-text {
    font-weight: var(--text-label-weight);
    font-size: var(--text-label-size);
  }

  .resource-metrics {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }

  .metric {
    display: flex;
    flex-direction: column;
    gap: var(--space-1-5);
  }

  .metric-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .metric-label {
    font-size: var(--text-body-sm-size);
    color: var(--text-secondary);
  }

  .metric-value {
    font-weight: var(--text-h6-weight);
    color: var(--text-primary);
  }

  .metric-bar {
    height: 8px;
    background-color: var(--color-neutral-700);
    border-radius: var(--radius-full);
    overflow: hidden;
  }

  .metric-fill {
    height: 100%;
    transition: width var(--duration-slow) var(--ease-in-out);
    border-radius: var(--radius-full);
  }

  .metric-fill.cpu {
    background-color: var(--color-primary-500);
  }

  .metric-fill.memory {
    background-color: var(--color-warning-500);
  }

  .metric-fill.gpu {
    background-color: var(--color-success-500);
  }

  .queue-panel {
    flex: 1;
    overflow-y: auto;
  }

  .queue-panel h3 {
    font-size: var(--text-h5-size);
    font-weight: var(--text-h5-weight);
    margin-bottom: var(--space-5);
    color: var(--text-primary);
  }

  .job-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }

  .job-item {
    background-color: var(--bg-tertiary);
    border-radius: var(--radius-lg);
    padding: var(--space-4);
    border: 2px solid transparent;
    transition: all var(--duration-normal);
  }

  .job-item.active {
    border-color: var(--color-primary-500);
    box-shadow: var(--shadow-dark-md);
  }

  .job-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: var(--space-2.5);
  }

  .job-info {
    flex: 1;
  }

  .job-filename {
    font-size: var(--text-body-size);
    font-weight: var(--text-h6-weight);
    margin: 0 0 var(--space-1) 0;
    color: var(--text-primary);
  }

  .job-meta {
    display: flex;
    gap: var(--space-4);
    font-size: var(--text-body-xs-size);
  }

  .job-status {
    font-weight: var(--text-h6-weight);
  }

  .job-duration {
    color: var(--text-secondary);
  }

  .job-progress-text {
    font-size: var(--text-body-sm-size);
    font-weight: var(--text-h6-weight);
    color: var(--text-primary);
  }

  .job-progress-bar {
    height: 6px;
    background-color: var(--color-neutral-700);
    border-radius: var(--radius-full);
    overflow: hidden;
    margin-bottom: var(--space-2.5);
  }

  .job-progress-fill {
    height: 100%;
    transition: width var(--duration-slow) var(--ease-in-out);
    border-radius: var(--radius-full);
  }

  .job-results {
    display: flex;
    gap: var(--space-5);
    margin-top: var(--space-2.5);
  }

  .result-item {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .result-label {
    font-size: var(--text-body-xs-size);
    color: var(--text-secondary);
  }

  .result-value {
    font-size: var(--text-body-size);
    font-weight: var(--text-h6-weight);
    color: var(--color-success-500);
  }

  .job-details {
    margin-top: var(--space-2.5);
    font-size: var(--text-body-xs-size);
    color: var(--text-secondary);
  }

  .detail-item {
    padding: 2px 0;
  }

  .stats-panel-inner h3 {
    font-size: var(--text-h5-size);
    font-weight: var(--text-h5-weight);
    margin-bottom: var(--space-5);
    color: var(--text-primary);
  }

  .stats-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: var(--space-4);
  }

  .stat-card-inner {
    display: flex;
    align-items: center;
    gap: var(--space-3);
  }

  .stat-icon {
    font-size: var(--text-h3-size);
  }

  .stat-content {
    display: flex;
    flex-direction: column;
  }

  .stat-value {
    font-size: var(--text-h4-size);
    font-weight: var(--text-h4-weight);
    color: var(--text-primary);
  }

  .stat-label {
    font-size: var(--text-body-xs-size);
    color: var(--text-secondary);
  }

  /* Mobile Responsive */
  @media (max-width: 768px) {
    .processing-header {
      flex-direction: column;
      align-items: flex-start;
      gap: 15px;
    }
    
    .processing-controls {
      width: 100%;
      justify-content: space-between;
    }
    
    .processing-main {
      flex-direction: column;
    }
    
    .status-panel {
      width: 100%;
    }
    
    .stats-grid {
      grid-template-columns: repeat(2, 1fr);
    }
  }
</style>