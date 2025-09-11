<script lang="ts">
  import { onMount } from 'svelte';
  
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
        <button class="control-btn pause-btn" on:click={pauseProcessing}>
          ⏸️ Pause Processing
        </button>
      {:else}
        <button class="control-btn resume-btn" on:click={resumeProcessing}>
          ▶️ Resume Processing
        </button>
      {/if}
      <button class="control-btn start-btn" on:click={startProcessing}>
        🚀 Start New Job
      </button>
    </div>
  </div>

  <div class="processing-main">
    <!-- System Status Panel -->
    <div class="status-panel">
      <h3>System Status</h3>
      
      <div class="status-indicator">
        <span class="status-dot" class:active={isProcessingActive}></span>
        <span class="status-text">
          {isProcessingActive ? 'Processing Active' : 'Processing Paused'}
        </span>
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
    </div>

    <!-- Processing Queue -->
    <div class="queue-panel">
      <h3>Processing Queue</h3>
      
      <div class="job-list">
        {#each processingJobs as job}
          <div class="job-item" class:active={job.status === 'processing'}>
            <div class="job-header">
              <div class="job-info">
                <h4 class="job-filename">{job.filename}</h4>
                <div class="job-meta">
                  <span 
                    class="job-status" 
                    style="color: {getStatusColor(job.status)}"
                  >
                    {job.status.toUpperCase()}
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
    </div>
  </div>

  <!-- Processing Statistics -->
  <div class="stats-panel">
    <h3>Processing Statistics</h3>
    
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-icon">📊</div>
        <div class="stat-content">
          <div class="stat-value">3</div>
          <div class="stat-label">Total Jobs</div>
        </div>
      </div>
      
      <div class="stat-card">
        <div class="stat-icon">✅</div>
        <div class="stat-content">
          <div class="stat-value">1</div>
          <div class="stat-label">Completed</div>
        </div>
      </div>
      
      <div class="stat-card">
        <div class="stat-icon">⚡</div>
        <div class="stat-content">
          <div class="stat-value">1</div>
          <div class="stat-label">Processing</div>
        </div>
      </div>
      
      <div class="stat-card">
        <div class="stat-icon">⏳</div>
        <div class="stat-content">
          <div class="stat-value">1</div>
          <div class="stat-label">Pending</div>
        </div>
      </div>
    </div>
  </div>
</div>

<style>
  .processing-container {
    height: 100%;
    display: flex;
    flex-direction: column;
    padding: 20px;
    background-color: #1a1a1a;
    color: #ffffff;
    gap: 20px;
  }

  .processing-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: 15px;
    border-bottom: 1px solid #444;
  }

  .processing-header h1 {
    font-size: 24px;
    font-weight: 600;
    margin: 0;
  }

  .processing-controls {
    display: flex;
    gap: 10px;
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
    background-color: #1e293b;
    border-radius: 8px;
    padding: 20px;
    height: fit-content;
  }

  .status-panel h3 {
    font-size: 18px;
    font-weight: 600;
    margin-bottom: 20px;
    color: #ffffff;
  }

  .status-indicator {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 25px;
    padding: 12px;
    background-color: #2d3748;
    border-radius: 6px;
  }

  .status-dot {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background-color: #6b7280;
    transition: background-color 0.3s;
  }

  .status-dot.active {
    background-color: #22c55e;
  }

  .status-text {
    font-weight: 500;
  }

  .resource-metrics {
    display: flex;
    flex-direction: column;
    gap: 15px;
  }

  .metric {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .metric-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .metric-label {
    font-size: 14px;
    color: #9ca3af;
  }

  .metric-value {
    font-weight: 600;
    color: #ffffff;
  }

  .metric-bar {
    height: 8px;
    background-color: #374151;
    border-radius: 4px;
    overflow: hidden;
  }

  .metric-fill {
    height: 100%;
    transition: width 0.3s ease;
    border-radius: 4px;
  }

  .metric-fill.cpu {
    background-color: #3b82f6;
  }

  .metric-fill.memory {
    background-color: #eab308;
  }

  .metric-fill.gpu {
    background-color: #22c55e;
  }

  .queue-panel {
    flex: 1;
    background-color: #1e293b;
    border-radius: 8px;
    padding: 20px;
    overflow-y: auto;
  }

  .queue-panel h3 {
    font-size: 18px;
    font-weight: 600;
    margin-bottom: 20px;
    color: #ffffff;
  }

  .job-list {
    display: flex;
    flex-direction: column;
    gap: 15px;
  }

  .job-item {
    background-color: #2d3748;
    border-radius: 8px;
    padding: 15px;
    border: 2px solid transparent;
    transition: all 0.2s;
  }

  .job-item.active {
    border-color: #3b82f6;
    box-shadow: 0 0 10px rgba(59, 130, 246, 0.3);
  }

  .job-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 10px;
  }

  .job-info {
    flex: 1;
  }

  .job-filename {
    font-size: 16px;
    font-weight: 600;
    margin: 0 0 5px 0;
    color: #ffffff;
  }

  .job-meta {
    display: flex;
    gap: 15px;
    font-size: 12px;
  }

  .job-status {
    font-weight: 600;
  }

  .job-duration {
    color: #9ca3af;
  }

  .job-progress-text {
    font-size: 14px;
    font-weight: 600;
    color: #ffffff;
  }

  .job-progress-bar {
    height: 6px;
    background-color: #374151;
    border-radius: 3px;
    overflow: hidden;
    margin-bottom: 10px;
  }

  .job-progress-fill {
    height: 100%;
    transition: width 0.3s ease;
    border-radius: 3px;
  }

  .job-results {
    display: flex;
    gap: 20px;
    margin-top: 10px;
  }

  .result-item {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .result-label {
    font-size: 12px;
    color: #9ca3af;
  }

  .result-value {
    font-size: 16px;
    font-weight: 600;
    color: #22c55e;
  }

  .job-details {
    margin-top: 10px;
    font-size: 12px;
    color: #9ca3af;
  }

  .detail-item {
    padding: 2px 0;
  }

  .stats-panel {
    background-color: #1e293b;
    border-radius: 8px;
    padding: 20px;
  }

  .stats-panel h3 {
    font-size: 18px;
    font-weight: 600;
    margin-bottom: 20px;
    color: #ffffff;
  }

  .stats-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 15px;
  }

  .stat-card {
    background-color: #2d3748;
    border-radius: 8px;
    padding: 15px;
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .stat-icon {
    font-size: 24px;
  }

  .stat-content {
    display: flex;
    flex-direction: column;
  }

  .stat-value {
    font-size: 20px;
    font-weight: 700;
    color: #ffffff;
  }

  .stat-label {
    font-size: 12px;
    color: #9ca3af;
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