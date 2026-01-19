<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import Card from '$lib/components/Card.svelte';
  import Badge from '$lib/components/Badge.svelte';
  import Button from '$lib/components/Button.svelte';
  import StatusIndicator from '$lib/components/StatusIndicator.svelte';

  interface ProcessingJob {
    id: string;
    youtubeUrl: string;
    title: string;
    status: 'pending' | 'downloading' | 'processing' | 'completed' | 'failed';
    progress: number;
    startTime?: Date;
    endTime?: Date;
    facesDetected?: number;
    facesRecognized?: number;
    duration?: number;
    error?: string;
    logs: string[];
  }

  interface ProcessedVideo {
    id: string;
    title: string;
    duration: number;
    dateAdded: Date;
    facesDetected: number;
    facesRecognized: number;
    thumbnail?: string;
  }

  let youtubeUrl = '';
  let urlError = '';
  let isSubmitting = false;

  let processingQueue: ProcessingJob[] = [];
  let videoLibrary: ProcessedVideo[] = [];
  let isLoading = true;
  let activeTab: 'queue' | 'library' = 'queue';

  let showLogModal = false;
  let selectedJobForLogs: ProcessingJob | null = null;

  let showDeleteConfirm = false;
  let videoToDelete: ProcessedVideo | null = null;

  const youtubeRegex = /^(https?:\/\/)?(www\.)?(youtube\.com\/(watch\?v=|embed\/|v\/)|youtu\.be\/)[\w-]{11}$/;

  function validateYoutubeUrl(url: string): boolean {
    if (!url.trim()) {
      urlError = 'Please enter a YouTube URL';
      return false;
    }
    if (!youtubeRegex.test(url)) {
      urlError = 'Please enter a valid YouTube URL';
      return false;
    }
    urlError = '';
    return true;
  }

  async function submitUrl() {
    if (!validateYoutubeUrl(youtubeUrl)) return;

    isSubmitting = true;
    try {
      const response = await fetch('/api/ingestion/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: youtubeUrl })
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || err.error || 'Failed to submit');
      }

      const result = await response.json();
      const newJob: ProcessingJob = {
        id: result.id,
        youtubeUrl: result.url,
        title: result.url,
        status: result.status,
        progress: result.progress || 0,
        logs: []
      };

      processingQueue = [newJob, ...processingQueue];
      youtubeUrl = '';

      startPolling();
    } catch (e) {
      console.error('Failed to submit URL:', e);
      urlError = e instanceof Error ? e.message : 'Failed to submit URL. Please try again.';
    } finally {
      isSubmitting = false;
    }
  }

  let pollingInterval: ReturnType<typeof setInterval> | null = null;

  function startPolling() {
    if (pollingInterval) return;
    pollingInterval = setInterval(refreshJobs, 3000);
  }

  function stopPolling() {
    if (pollingInterval) {
      clearInterval(pollingInterval);
      pollingInterval = null;
    }
  }

  async function refreshJobs() {
    try {
      const response = await fetch('/api/ingestion/jobs');
      if (!response.ok) return;

      const jobs = await response.json();

      processingQueue = jobs.map((job: any) => ({
        id: job.id,
        youtubeUrl: job.url,
        title: job.url,
        status: job.status,
        progress: job.progress || 0,
        startTime: job.created_at ? new Date(job.created_at) : undefined,
        endTime: job.updated_at ? new Date(job.updated_at) : undefined,
        facesDetected: job.faces_detected,
        facesRecognized: job.faces_recognized,
        error: job.error,
        logs: []
      }));

      const hasActiveJobs = processingQueue.some(j => 
        j.status === 'pending' || j.status === 'downloading' || j.status === 'processing'
      );
      if (!hasActiveJobs) {
        stopPolling();
      }
    } catch (e) {
      console.error('Failed to refresh jobs:', e);
    }
  }

  async function retryJob(job: ProcessingJob) {
    try {
      const response = await fetch('/api/ingestion/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: job.youtubeUrl })
      });

      if (response.ok) {
        const result = await response.json();
        processingQueue = processingQueue.map(j =>
          j.id === job.id ? {
            ...j,
            id: result.id,
            status: 'pending' as const,
            progress: 0,
            error: undefined,
            logs: [`[${new Date().toISOString()}] Retrying job...`]
          } : j
        );
        startPolling();
      }
    } catch (e) {
      console.error('Failed to retry job:', e);
    }
  }

  function removeFromQueue(jobId: string) {
    processingQueue = processingQueue.filter(j => j.id !== jobId);
  }

  function confirmDeleteVideo(video: ProcessedVideo) {
    videoToDelete = video;
    showDeleteConfirm = true;
  }

  function deleteVideo() {
    if (videoToDelete) {
      videoLibrary = videoLibrary.filter(v => v.id !== videoToDelete?.id);
      showDeleteConfirm = false;
      videoToDelete = null;
    }
  }

  function openLogModal(job: ProcessingJob) {
    selectedJobForLogs = job;
    showLogModal = true;
  }

  function closeLogModal() {
    showLogModal = false;
    selectedJobForLogs = null;
  }

  function formatDuration(seconds: number): string {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  }

  function formatDate(date: Date): string {
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  }

  function getStatusVariant(status: string): 'success' | 'warning' | 'error' | 'primary' | 'neutral' {
    switch (status) {
      case 'completed': return 'success';
      case 'processing':
      case 'downloading': return 'primary';
      case 'failed': return 'error';
      default: return 'neutral';
    }
  }

  onMount(async () => {
    try {
      const [jobsResponse, videosResponse] = await Promise.all([
        fetch('/api/ingestion/jobs'),
        fetch('/api/videos/processed/list')
      ]);

      if (jobsResponse.ok) {
        const jobs = await jobsResponse.json();
        processingQueue = jobs.map((job: any) => ({
          id: job.id,
          youtubeUrl: job.url,
          title: job.url,
          status: job.status,
          progress: job.progress || 0,
          startTime: job.created_at ? new Date(job.created_at) : undefined,
          endTime: job.updated_at ? new Date(job.updated_at) : undefined,
          facesDetected: job.faces_detected,
          facesRecognized: job.faces_recognized,
          error: job.error,
          logs: []
        }));

        const hasActiveJobs = processingQueue.some(j => 
          j.status === 'pending' || j.status === 'downloading' || j.status === 'processing'
        );
        if (hasActiveJobs) {
          startPolling();
        }
      }

      if (videosResponse.ok) {
        const videos = await videosResponse.json();
        videoLibrary = (Array.isArray(videos) ? videos : []).map((v: any) => ({
          id: v.id,
          title: v.name || v.title,
          duration: v.duration || 0,
          dateAdded: new Date(v.created_at || Date.now()),
          facesDetected: v.faces_detected || 0,
          facesRecognized: v.faces_recognized || 0
        }));
      }
    } catch (e) {
      console.error('Failed to load data:', e);
    } finally {
      isLoading = false;
    }
  });

  onDestroy(() => stopPolling());

  $: pendingCount = processingQueue.filter(j => j.status === 'pending').length;
  $: processingCount = processingQueue.filter(j => j.status === 'processing' || j.status === 'downloading').length;
  $: completedCount = processingQueue.filter(j => j.status === 'completed').length;
  $: failedCount = processingQueue.filter(j => j.status === 'failed').length;
</script>

<svelte:head>
  <title>Video Ingestion - Face Recognition Dashboard</title>
</svelte:head>

<div class="ingestion-page">
  <div class="page-header">
    <div class="header-content">
      <h1>📥 Video Ingestion</h1>
      <p class="page-description">Submit YouTube videos for face recognition processing</p>
    </div>
  </div>

  <Card variant="surface" padding="lg" class="url-form-card">
    <h2>Add New Video</h2>
    <form class="url-form" on:submit|preventDefault={submitUrl}>
      <div class="input-group">
        <div class="input-wrapper">
          <span class="input-icon">🔗</span>
          <input
            type="text"
            bind:value={youtubeUrl}
            placeholder="Paste YouTube URL (e.g., https://youtube.com/watch?v=...)"
            class:error={!!urlError}
            on:input={() => urlError && validateYoutubeUrl(youtubeUrl)}
          />
        </div>
        {#if urlError}
          <span class="error-message">{urlError}</span>
        {/if}
      </div>
      <Button type="submit" variant="primary" size="lg" disabled={isSubmitting}>
        {isSubmitting ? 'Submitting...' : '🚀 Start Processing'}
      </Button>
    </form>
    <p class="form-hint">Videos will be downloaded and processed for face detection and recognition.</p>
  </Card>

  <div class="stats-row">
    <div class="stat-card">
      <span class="stat-icon">⏳</span>
      <span class="stat-value">{pendingCount}</span>
      <span class="stat-label">Pending</span>
    </div>
    <div class="stat-card processing">
      <span class="stat-icon">⚡</span>
      <span class="stat-value">{processingCount}</span>
      <span class="stat-label">Processing</span>
    </div>
    <div class="stat-card success">
      <span class="stat-icon">✅</span>
      <span class="stat-value">{completedCount}</span>
      <span class="stat-label">Completed</span>
    </div>
    <div class="stat-card error">
      <span class="stat-icon">❌</span>
      <span class="stat-value">{failedCount}</span>
      <span class="stat-label">Failed</span>
    </div>
  </div>

  <div class="tabs">
    <button class="tab" class:active={activeTab === 'queue'} on:click={() => activeTab = 'queue'}>
      Processing Queue ({processingQueue.length})
    </button>
    <button class="tab" class:active={activeTab === 'library'} on:click={() => activeTab = 'library'}>
      Video Library ({videoLibrary.length})
    </button>
  </div>

  {#if activeTab === 'queue'}
    <Card variant="surface" padding="lg">
      {#if processingQueue.length === 0}
        <div class="empty-state">
          <span class="empty-icon">📭</span>
          <h3>No videos in queue</h3>
          <p>Submit a YouTube URL above to start processing.</p>
        </div>
      {:else}
        <div class="queue-list">
          {#each processingQueue as job}
            <div class="queue-item" class:active={job.status === 'processing' || job.status === 'downloading'}>
              <div class="job-main">
                <div class="job-info">
                  <h4 class="job-title">{job.title}</h4>
                  <p class="job-url">{job.youtubeUrl}</p>
                </div>
                <Badge variant={getStatusVariant(job.status)} size="md">
                  {job.status.toUpperCase()}
                </Badge>
              </div>

              {#if job.status === 'processing' || job.status === 'downloading'}
                <div class="progress-section">
                  <div class="progress-bar">
                    <div class="progress-fill" style="width: {job.progress}%"></div>
                  </div>
                  <span class="progress-text">{Math.round(job.progress)}%</span>
                </div>
              {/if}

              {#if job.status === 'completed'}
                <div class="job-results">
                  <span class="result">👥 {job.facesDetected} detected</span>
                  <span class="result">✅ {job.facesRecognized} recognized</span>
                  <span class="result">⏱️ {formatDuration(job.duration || 0)}</span>
                </div>
              {/if}

              {#if job.error}
                <p class="job-error">❌ {job.error}</p>
              {/if}

              <div class="job-actions">
                <Button variant="secondary" size="sm" on:click={() => openLogModal(job)}>
                  📋 Logs
                </Button>
                {#if job.status === 'failed'}
                  <Button variant="primary" size="sm" on:click={() => retryJob(job)}>
                    🔄 Retry
                  </Button>
                {/if}
                {#if job.status === 'completed' || job.status === 'failed'}
                  <Button variant="secondary" size="sm" on:click={() => removeFromQueue(job.id)}>
                    ✕ Remove
                  </Button>
                {/if}
              </div>
            </div>
          {/each}
        </div>
      {/if}
    </Card>
  {:else}
    <Card variant="surface" padding="lg">
      {#if isLoading}
        <div class="loading-state">
          <div class="spinner"></div>
          <p>Loading video library...</p>
        </div>
      {:else if videoLibrary.length === 0}
        <div class="empty-state">
          <span class="empty-icon">🎬</span>
          <h3>No videos in library</h3>
          <p>Processed videos will appear here.</p>
        </div>
      {:else}
        <div class="library-table">
          <div class="table-header">
            <span class="col-title">Title</span>
            <span class="col-duration">Duration</span>
            <span class="col-faces">Faces</span>
            <span class="col-date">Added</span>
            <span class="col-actions">Actions</span>
          </div>
          {#each videoLibrary as video}
            <div class="table-row">
              <span class="col-title">
                <span class="video-icon">📹</span>
                {video.title}
              </span>
              <span class="col-duration">{formatDuration(video.duration)}</span>
              <span class="col-faces">
                {video.facesDetected} / {video.facesRecognized}
              </span>
              <span class="col-date">{formatDate(video.dateAdded)}</span>
              <span class="col-actions">
                <Button variant="secondary" size="sm" on:click={() => window.location.href = `/player?video=${video.id}`}>
                  ▶️ Play
                </Button>
                <Button variant="secondary" size="sm" on:click={() => confirmDeleteVideo(video)}>
                  🗑️
                </Button>
              </span>
            </div>
          {/each}
        </div>
      {/if}
    </Card>
  {/if}
</div>

{#if showLogModal && selectedJobForLogs}
  <div class="modal-overlay" on:click={closeLogModal} on:keypress={(e) => e.key === 'Escape' && closeLogModal()} role="button" tabindex="-1">
    <div class="modal log-modal" on:click|stopPropagation role="dialog" aria-modal="true">
      <div class="modal-header">
        <h3>📋 Processing Logs</h3>
        <button class="modal-close" on:click={closeLogModal}>✕</button>
      </div>
      <div class="modal-body">
        <div class="log-info">
          <Badge variant={getStatusVariant(selectedJobForLogs.status)} size="md">
            {selectedJobForLogs.status.toUpperCase()}
          </Badge>
          <span class="log-title">{selectedJobForLogs.title}</span>
        </div>
        <div class="log-content">
          {#each selectedJobForLogs.logs as log}
            <div class="log-line">{log}</div>
          {/each}
        </div>
      </div>
      <div class="modal-footer">
        <Button variant="secondary" size="md" on:click={closeLogModal}>Close</Button>
      </div>
    </div>
  </div>
{/if}

{#if showDeleteConfirm && videoToDelete}
  <div class="modal-overlay" on:click={() => showDeleteConfirm = false} on:keypress={(e) => e.key === 'Escape' && (showDeleteConfirm = false)} role="button" tabindex="-1">
    <div class="modal confirm-modal" on:click|stopPropagation role="dialog" aria-modal="true">
      <h3>🗑️ Delete Video</h3>
      <p>Are you sure you want to delete "{videoToDelete.title}"? This action cannot be undone.</p>
      <div class="modal-actions">
        <Button variant="secondary" size="md" on:click={() => showDeleteConfirm = false}>Cancel</Button>
        <Button variant="primary" size="md" on:click={deleteVideo}>Delete</Button>
      </div>
    </div>
  </div>
{/if}

<style>
  .ingestion-page {
    padding: var(--space-6);
    max-width: 1200px;
    margin: 0 auto;
  }

  .page-header {
    margin-bottom: var(--space-6);
  }

  .header-content h1 {
    font-size: var(--text-h2-size);
    font-weight: 600;
    margin: 0 0 var(--space-2);
  }

  .page-description {
    color: var(--text-secondary);
    margin: 0;
  }

  :global(.url-form-card) {
    margin-bottom: var(--space-6);
  }

  h2 {
    font-size: var(--text-h4-size);
    font-weight: 600;
    margin: 0 0 var(--space-4);
  }

  .url-form {
    display: flex;
    gap: var(--space-3);
    align-items: flex-start;
  }

  .input-group {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  .input-wrapper {
    display: flex;
    align-items: center;
    background: var(--bg-tertiary);
    border: 2px solid var(--border-default);
    border-radius: var(--radius-lg);
    padding: 0 var(--space-4);
    transition: border-color 0.2s;
  }

  .input-wrapper:focus-within {
    border-color: var(--color-primary-500);
  }

  .input-wrapper.error {
    border-color: var(--color-error-500);
  }

  .input-icon {
    font-size: 1.2rem;
    margin-right: var(--space-3);
  }

  .input-wrapper input {
    flex: 1;
    background: none;
    border: none;
    padding: var(--space-4) 0;
    color: var(--text-primary);
    font-size: var(--text-body-size);
    outline: none;
  }

  .input-wrapper input::placeholder {
    color: var(--text-tertiary);
  }

  .error-message {
    color: var(--color-error-500);
    font-size: var(--text-body-sm-size);
  }

  .form-hint {
    margin: var(--space-3) 0 0;
    font-size: var(--text-body-sm-size);
    color: var(--text-tertiary);
  }

  .stats-row {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: var(--space-4);
    margin-bottom: var(--space-6);
  }

  .stat-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: var(--space-4);
    background: var(--bg-secondary);
    border-radius: var(--radius-lg);
    border: 1px solid var(--border-default);
  }

  .stat-card.processing {
    border-color: var(--color-primary-500/30);
    background: var(--color-primary-500/5);
  }

  .stat-card.success {
    border-color: var(--color-success-500/30);
    background: var(--color-success-500/5);
  }

  .stat-card.error {
    border-color: var(--color-error-500/30);
    background: var(--color-error-500/5);
  }

  .stat-icon {
    font-size: 1.5rem;
    margin-bottom: var(--space-2);
  }

  .stat-value {
    font-size: var(--text-h3-size);
    font-weight: 700;
    color: var(--text-primary);
  }

  .stat-label {
    font-size: var(--text-body-sm-size);
    color: var(--text-secondary);
  }

  .tabs {
    display: flex;
    gap: var(--space-2);
    margin-bottom: var(--space-4);
  }

  .tab {
    padding: var(--space-3) var(--space-5);
    background: none;
    border: none;
    border-bottom: 2px solid transparent;
    color: var(--text-secondary);
    font-size: var(--text-body-size);
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
  }

  .tab:hover {
    color: var(--text-primary);
  }

  .tab.active {
    color: var(--color-primary-500);
    border-color: var(--color-primary-500);
  }

  .empty-state,
  .loading-state {
    text-align: center;
    padding: var(--space-10);
    color: var(--text-secondary);
  }

  .empty-icon {
    font-size: 3rem;
    display: block;
    margin-bottom: var(--space-4);
  }

  .empty-state h3 {
    margin: 0 0 var(--space-2);
    color: var(--text-primary);
  }

  .empty-state p {
    margin: 0;
  }

  .spinner {
    width: 40px;
    height: 40px;
    border: 3px solid var(--border-default);
    border-top-color: var(--color-primary-500);
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin: 0 auto var(--space-4);
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .queue-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }

  .queue-item {
    padding: var(--space-4);
    background: var(--bg-tertiary);
    border-radius: var(--radius-lg);
    border: 2px solid transparent;
    transition: border-color 0.2s;
  }

  .queue-item.active {
    border-color: var(--color-primary-500);
  }

  .job-main {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: var(--space-3);
  }

  .job-title {
    margin: 0 0 var(--space-1);
    font-size: var(--text-body-size);
    font-weight: 600;
  }

  .job-url {
    margin: 0;
    font-size: var(--text-body-sm-size);
    color: var(--text-tertiary);
    word-break: break-all;
  }

  .progress-section {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    margin-bottom: var(--space-3);
  }

  .progress-bar {
    flex: 1;
    height: 8px;
    background: var(--bg-secondary);
    border-radius: 4px;
    overflow: hidden;
  }

  .progress-fill {
    height: 100%;
    background: var(--color-primary-500);
    border-radius: 4px;
    transition: width 0.3s;
  }

  .progress-text {
    font-size: var(--text-body-sm-size);
    font-weight: 600;
    color: var(--text-primary);
    min-width: 40px;
  }

  .job-results {
    display: flex;
    gap: var(--space-4);
    margin-bottom: var(--space-3);
    flex-wrap: wrap;
  }

  .result {
    font-size: var(--text-body-sm-size);
    color: var(--text-secondary);
  }

  .job-error {
    color: var(--color-error-500);
    font-size: var(--text-body-sm-size);
    margin: 0 0 var(--space-3);
  }

  .job-actions {
    display: flex;
    gap: var(--space-2);
  }

  .library-table {
    display: flex;
    flex-direction: column;
  }

  .table-header {
    display: grid;
    grid-template-columns: 2fr 100px 120px 150px 150px;
    gap: var(--space-4);
    padding: var(--space-3) var(--space-4);
    background: var(--bg-tertiary);
    border-radius: var(--radius-md);
    font-size: var(--text-body-sm-size);
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .table-row {
    display: grid;
    grid-template-columns: 2fr 100px 120px 150px 150px;
    gap: var(--space-4);
    padding: var(--space-3) var(--space-4);
    align-items: center;
    border-bottom: 1px solid var(--border-subtle);
    transition: background-color 0.15s;
  }

  .table-row:hover {
    background: var(--bg-tertiary);
  }

  .col-title {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  .video-icon {
    font-size: 1.2rem;
  }

  .col-actions {
    display: flex;
    gap: var(--space-2);
  }

  .modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.7);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }

  .modal {
    background: var(--bg-secondary);
    border-radius: var(--radius-lg);
    max-width: 90%;
    max-height: 80vh;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }

  .log-modal {
    width: 700px;
  }

  .confirm-modal {
    width: 400px;
    padding: var(--space-6);
  }

  .confirm-modal h3 {
    margin: 0 0 var(--space-4);
  }

  .confirm-modal p {
    color: var(--text-secondary);
    margin: 0 0 var(--space-5);
  }

  .modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--space-4) var(--space-5);
    border-bottom: 1px solid var(--border-default);
  }

  .modal-header h3 {
    margin: 0;
    font-size: var(--text-h4-size);
  }

  .modal-close {
    background: none;
    border: none;
    color: var(--text-tertiary);
    font-size: 1.2rem;
    cursor: pointer;
  }

  .modal-close:hover {
    color: var(--text-primary);
  }

  .modal-body {
    padding: var(--space-5);
    overflow-y: auto;
    flex: 1;
  }

  .log-info {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    margin-bottom: var(--space-4);
  }

  .log-title {
    font-weight: 500;
  }

  .log-content {
    background: var(--bg-primary);
    border-radius: var(--radius-md);
    padding: var(--space-4);
    font-family: monospace;
    font-size: var(--text-body-sm-size);
    max-height: 400px;
    overflow-y: auto;
  }

  .log-line {
    padding: var(--space-1) 0;
    color: var(--text-secondary);
    word-break: break-all;
  }

  .modal-footer {
    padding: var(--space-4) var(--space-5);
    border-top: 1px solid var(--border-default);
    display: flex;
    justify-content: flex-end;
  }

  .modal-actions {
    display: flex;
    gap: var(--space-3);
    justify-content: flex-end;
  }

  @media (max-width: 768px) {
    .url-form {
      flex-direction: column;
    }

    .stats-row {
      grid-template-columns: repeat(2, 1fr);
    }

    .table-header,
    .table-row {
      grid-template-columns: 1fr;
      gap: var(--space-2);
    }

    .table-header {
      display: none;
    }

    .table-row {
      padding: var(--space-4);
    }

    .col-actions {
      margin-top: var(--space-2);
    }
  }
</style>
