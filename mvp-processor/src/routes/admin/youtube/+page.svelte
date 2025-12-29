<script lang="ts">
  import { onMount } from 'svelte';

  // YouTube URL patterns
  const YOUTUBE_REGEX = /(?:youtube\.com\/(?:watch\?v=|embed\/|v\/)|youtu\.be\/)([a-zA-Z0-9_-]{11})/;

  interface YouTubeVideoInfo {
    videoId: string;
    title: string;
    thumbnail: string;
    duration: string;
    channelTitle: string;
  }

  interface QueueEntry {
    id: string;
    youtube_url: string;
    youtube_video_id: string;
    title: string;
    priority: string;
    status: string;
    submitted_at: string;
    error: string | null;
  }

  // Form state
  let youtubeUrl = '';
  let customTitle = '';
  let priority = 'normal';
  
  // UI state
  let loading = false;
  let validating = false;
  let error = '';
  let success = '';
  let videoInfo: YouTubeVideoInfo | null = null;
  let recentSubmissions: QueueEntry[] = [];
  let urlValid = false;
  let extractedVideoId = '';

  // Debounce timer
  let validateTimer: ReturnType<typeof setTimeout>;

  // Extract video ID from URL
  function extractVideoId(url: string): string | null {
    const match = url.match(YOUTUBE_REGEX);
    return match ? match[1] : null;
  }

  // Validate URL and fetch video info
  async function validateUrl(url: string) {
    clearTimeout(validateTimer);
    
    if (!url.trim()) {
      videoInfo = null;
      urlValid = false;
      extractedVideoId = '';
      return;
    }

    const videoId = extractVideoId(url);
    if (!videoId) {
      videoInfo = null;
      urlValid = false;
      extractedVideoId = '';
      error = 'Invalid YouTube URL. Please use a standard YouTube link.';
      return;
    }

    extractedVideoId = videoId;
    error = '';

    // Debounce the API call
    validateTimer = setTimeout(async () => {
      validating = true;
      try {
        // Try to fetch video info via oEmbed (no API key needed)
        const oembedUrl = `https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=${videoId}&format=json`;
        const response = await fetch(oembedUrl);
        
        if (response.ok) {
          const data = await response.json();
          videoInfo = {
            videoId,
            title: data.title,
            thumbnail: `https://img.youtube.com/vi/${videoId}/maxresdefault.jpg`,
            duration: '', // oEmbed doesn't provide duration
            channelTitle: data.author_name
          };
          urlValid = true;
          
          // Auto-fill title if empty
          if (!customTitle) {
            customTitle = data.title;
          }
        } else {
          // Video not found or private
          videoInfo = null;
          urlValid = false;
          error = 'Video not found or is private/unavailable.';
        }
      } catch (e) {
        // Fallback: assume valid if we got a video ID
        videoInfo = {
          videoId,
          title: 'Video preview unavailable',
          thumbnail: `https://img.youtube.com/vi/${videoId}/mqdefault.jpg`,
          duration: '',
          channelTitle: 'Unknown'
        };
        urlValid = true;
      } finally {
        validating = false;
      }
    }, 500);
  }

  // Handle URL input
  function handleUrlInput(event: Event) {
    const input = event.target as HTMLInputElement;
    youtubeUrl = input.value;
    validateUrl(youtubeUrl);
  }

  // Submit video to queue
  async function submitVideo() {
    if (!urlValid || !extractedVideoId) {
      error = 'Please enter a valid YouTube URL';
      return;
    }

    loading = true;
    error = '';
    success = '';

    try {
      const response = await fetch('/api/admin/youtube/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          youtube_url: youtubeUrl,
          title: customTitle || videoInfo?.title || undefined,
          priority
        })
      });

      const data = await response.json();

      if (response.ok) {
        success = `Video "${customTitle || videoInfo?.title}" added to processing queue!`;
        // Reset form
        youtubeUrl = '';
        customTitle = '';
        priority = 'normal';
        videoInfo = null;
        urlValid = false;
        extractedVideoId = '';
        // Reload recent submissions
        await loadRecentSubmissions();
      } else {
        error = data.error || 'Failed to submit video';
      }
    } catch (e) {
      error = 'Network error. Please try again.';
    } finally {
      loading = false;
    }
  }

  // Load recent submissions
  async function loadRecentSubmissions() {
    try {
      const response = await fetch('/api/admin/youtube/queue?limit=5');
      if (response.ok) {
        const data = await response.json();
        recentSubmissions = data.queue || [];
      }
    } catch (e) {
      console.error('Failed to load recent submissions:', e);
    }
  }

  // Format date
  function formatDate(dateStr: string): string {
    return new Date(dateStr).toLocaleString();
  }

  // Get status color
  function getStatusColor(status: string): string {
    switch (status) {
      case 'queued': return '#3b82f6';
      case 'processing': return '#f59e0b';
      case 'completed': return '#22c55e';
      case 'failed': return '#ef4444';
      default: return '#6b7280';
    }
  }

  onMount(() => {
    loadRecentSubmissions();
  });
</script>

<svelte:head>
  <title>YouTube Submission - Admin - MV Face Recognition</title>
</svelte:head>

<div class="youtube-container">
  <div class="page-header">
    <div class="header-row">
      <div>
        <h1>Submit YouTube Video</h1>
        <p class="page-description">Add YouTube videos for face recognition processing</p>
      </div>
      <a href="/admin" class="back-link">Back to Admin</a>
    </div>
  </div>

  {#if error}
    <div class="alert alert-error">
      <span class="alert-icon">!</span>
      {error}
      <button class="alert-close" on:click={() => error = ''}>x</button>
    </div>
  {/if}

  {#if success}
    <div class="alert alert-success">
      <span class="alert-icon">OK</span>
      {success}
      <button class="alert-close" on:click={() => success = ''}>x</button>
    </div>
  {/if}

  <div class="main-grid">
    <!-- Submission Form -->
    <div class="panel submission-panel">
      <h2>New Video</h2>
      
      <form on:submit|preventDefault={submitVideo} class="form">
        <div class="form-group">
          <label for="youtube-url">
            YouTube URL
            <span class="required">*</span>
          </label>
          <div class="input-wrapper">
            <input
              id="youtube-url"
              type="text"
              value={youtubeUrl}
              on:input={handleUrlInput}
              placeholder="https://www.youtube.com/watch?v=..."
              class="input"
              class:valid={urlValid}
              class:invalid={youtubeUrl && !urlValid && !validating}
            />
            {#if validating}
              <span class="input-status validating">Checking...</span>
            {:else if urlValid}
              <span class="input-status valid">Valid</span>
            {:else if youtubeUrl && !urlValid}
              <span class="input-status invalid">Invalid</span>
            {/if}
          </div>
          <p class="input-help">
            Supports: youtube.com/watch?v=..., youtu.be/..., youtube.com/embed/...
          </p>
        </div>

        <!-- Video Preview -->
        {#if videoInfo}
          <div class="video-preview">
            <div class="preview-thumbnail">
              <img 
                src={videoInfo.thumbnail} 
                alt={videoInfo.title}
                on:error={(e) => {
                  const img = e.target as HTMLImageElement;
                  img.src = `https://img.youtube.com/vi/${videoInfo?.videoId}/mqdefault.jpg`;
                }}
              />
            </div>
            <div class="preview-info">
              <h3 class="preview-title">{videoInfo.title}</h3>
              <p class="preview-channel">{videoInfo.channelTitle}</p>
              <p class="preview-id">Video ID: {videoInfo.videoId}</p>
            </div>
          </div>
        {/if}

        <div class="form-group">
          <label for="custom-title">Custom Title (optional)</label>
          <input
            id="custom-title"
            type="text"
            bind:value={customTitle}
            placeholder="Override the video title"
            class="input"
          />
        </div>

        <div class="form-group">
          <label for="priority">Processing Priority</label>
          <select id="priority" bind:value={priority} class="select">
            <option value="low">Low - Process when resources available</option>
            <option value="normal">Normal - Standard queue position</option>
            <option value="high">High - Process as soon as possible</option>
          </select>
        </div>

        <button 
          type="submit" 
          class="btn btn-primary btn-large"
          disabled={loading || !urlValid}
        >
          {#if loading}
            <span class="spinner"></span>
            Submitting...
          {:else}
            Add to Processing Queue
          {/if}
        </button>
      </form>
    </div>

    <!-- Recent Submissions -->
    <div class="panel recent-panel">
      <div class="panel-header">
        <h2>Recent Submissions</h2>
        <button class="btn btn-secondary btn-small" on:click={loadRecentSubmissions}>
          Refresh
        </button>
      </div>

      {#if recentSubmissions.length === 0}
        <p class="empty-message">No recent submissions</p>
      {:else}
        <div class="submissions-list">
          {#each recentSubmissions as entry}
            <div class="submission-card">
              <div class="submission-thumbnail">
                <img 
                  src={`https://img.youtube.com/vi/${entry.youtube_video_id}/mqdefault.jpg`}
                  alt={entry.title}
                />
                <span class="status-badge" style="background-color: {getStatusColor(entry.status)}">
                  {entry.status}
                </span>
              </div>
              <div class="submission-info">
                <h4 class="submission-title">{entry.title}</h4>
                <div class="submission-meta">
                  <span class="submission-priority">{entry.priority}</span>
                  <span class="submission-date">{formatDate(entry.submitted_at)}</span>
                </div>
                {#if entry.error}
                  <p class="submission-error" title={entry.error}>Error: {entry.error}</p>
                {/if}
              </div>
            </div>
          {/each}
        </div>
        
        <a href="/admin" class="view-all-link">View all in Admin Panel</a>
      {/if}
    </div>
  </div>

  <!-- Quick Tips -->
  <div class="panel tips-panel">
    <h3>Quick Tips</h3>
    <div class="tips-grid">
      <div class="tip">
        <span class="tip-icon">1</span>
        <div class="tip-content">
          <strong>Paste YouTube URL</strong>
          <p>Copy any YouTube video link and paste it above</p>
        </div>
      </div>
      <div class="tip">
        <span class="tip-icon">2</span>
        <div class="tip-content">
          <strong>Preview & Customize</strong>
          <p>Review the video info and optionally set a custom title</p>
        </div>
      </div>
      <div class="tip">
        <span class="tip-icon">3</span>
        <div class="tip-content">
          <strong>Submit for Processing</strong>
          <p>Add to queue - face detection runs automatically</p>
        </div>
      </div>
      <div class="tip">
        <span class="tip-icon">4</span>
        <div class="tip-content">
          <strong>View Results</strong>
          <p>Check the Video Player page once processing completes</p>
        </div>
      </div>
    </div>
  </div>
</div>

<style>
  .youtube-container {
    padding: 20px;
    max-width: 1400px;
    margin: 0 auto;
  }

  .page-header {
    margin-bottom: 24px;
  }

  .header-row {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 16px;
  }

  .page-header h1 {
    font-size: 28px;
    font-weight: 600;
    margin: 0 0 8px 0;
    color: #ffffff;
  }

  .page-description {
    color: #9ca3af;
    margin: 0;
  }

  .back-link {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 8px 16px;
    background-color: #374151;
    color: #d1d5db;
    text-decoration: none;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 500;
    transition: all 0.2s;
    white-space: nowrap;
  }

  .back-link:hover {
    background-color: #4b5563;
    color: #ffffff;
  }

  .alert {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    border-radius: 8px;
    margin-bottom: 16px;
  }

  .alert-error {
    background-color: rgba(239, 68, 68, 0.2);
    border: 1px solid #ef4444;
    color: #fca5a5;
  }

  .alert-success {
    background-color: rgba(34, 197, 94, 0.2);
    border: 1px solid #22c55e;
    color: #86efac;
  }

  .alert-icon {
    font-weight: bold;
    padding: 2px 8px;
    border-radius: 4px;
    background-color: rgba(255, 255, 255, 0.2);
  }

  .alert-close {
    margin-left: auto;
    background: none;
    border: none;
    color: inherit;
    cursor: pointer;
    padding: 4px 8px;
  }

  .main-grid {
    display: grid;
    grid-template-columns: 1fr 400px;
    gap: 24px;
    margin-bottom: 24px;
  }

  .panel {
    background-color: #2a2a2a;
    border-radius: 12px;
    padding: 24px;
    border: 1px solid #374151;
  }

  .panel h2 {
    font-size: 20px;
    font-weight: 600;
    margin: 0 0 20px 0;
    color: #ffffff;
  }

  .panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
  }

  .panel-header h2 {
    margin: 0;
  }

  .form {
    display: flex;
    flex-direction: column;
    gap: 20px;
  }

  .form-group {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .form-group label {
    font-size: 14px;
    font-weight: 500;
    color: #d1d5db;
  }

  .required {
    color: #ef4444;
  }

  .input-wrapper {
    position: relative;
    display: flex;
    align-items: center;
  }

  .input, .select {
    width: 100%;
    padding: 12px 16px;
    border: 2px solid #4b5563;
    border-radius: 8px;
    background-color: #1f2937;
    color: #ffffff;
    font-size: 15px;
    transition: all 0.2s;
  }

  .input:focus, .select:focus {
    outline: none;
    border-color: #2563eb;
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.3);
  }

  .input.valid {
    border-color: #22c55e;
  }

  .input.invalid {
    border-color: #ef4444;
  }

  .input-status {
    position: absolute;
    right: 12px;
    font-size: 12px;
    font-weight: 500;
    padding: 4px 8px;
    border-radius: 4px;
  }

  .input-status.validating {
    color: #60a5fa;
    background-color: rgba(96, 165, 250, 0.2);
  }

  .input-status.valid {
    color: #22c55e;
    background-color: rgba(34, 197, 94, 0.2);
  }

  .input-status.invalid {
    color: #ef4444;
    background-color: rgba(239, 68, 68, 0.2);
  }

  .input-help {
    font-size: 12px;
    color: #6b7280;
    margin: 0;
  }

  .video-preview {
    display: flex;
    gap: 16px;
    padding: 16px;
    background-color: #1f2937;
    border-radius: 8px;
    border: 1px solid #374151;
  }

  .preview-thumbnail {
    flex-shrink: 0;
    width: 180px;
    height: 100px;
    border-radius: 6px;
    overflow: hidden;
    background-color: #111827;
  }

  .preview-thumbnail img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .preview-info {
    flex: 1;
    min-width: 0;
  }

  .preview-title {
    font-size: 16px;
    font-weight: 600;
    color: #ffffff;
    margin: 0 0 8px 0;
    overflow: hidden;
    text-overflow: ellipsis;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
  }

  .preview-channel {
    font-size: 14px;
    color: #9ca3af;
    margin: 0 0 4px 0;
  }

  .preview-id {
    font-size: 12px;
    color: #6b7280;
    font-family: monospace;
    margin: 0;
  }

  .btn {
    padding: 10px 20px;
    border: none;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
  }

  .btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-primary {
    background-color: #2563eb;
    color: white;
  }

  .btn-primary:hover:not(:disabled) {
    background-color: #1d4ed8;
  }

  .btn-secondary {
    background-color: #4b5563;
    color: white;
  }

  .btn-secondary:hover:not(:disabled) {
    background-color: #6b7280;
  }

  .btn-small {
    padding: 6px 12px;
    font-size: 13px;
  }

  .btn-large {
    padding: 14px 28px;
    font-size: 16px;
  }

  .spinner {
    width: 16px;
    height: 16px;
    border: 2px solid rgba(255, 255, 255, 0.3);
    border-top-color: #ffffff;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  /* Recent Submissions */
  .submissions-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .submission-card {
    display: flex;
    gap: 12px;
    padding: 12px;
    background-color: #1f2937;
    border-radius: 8px;
    border: 1px solid #374151;
  }

  .submission-thumbnail {
    position: relative;
    flex-shrink: 0;
    width: 120px;
    height: 68px;
    border-radius: 6px;
    overflow: hidden;
    background-color: #111827;
  }

  .submission-thumbnail img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .status-badge {
    position: absolute;
    bottom: 4px;
    left: 4px;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 10px;
    font-weight: 600;
    color: white;
    text-transform: uppercase;
  }

  .submission-info {
    flex: 1;
    min-width: 0;
  }

  .submission-title {
    font-size: 14px;
    font-weight: 500;
    color: #ffffff;
    margin: 0 0 6px 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .submission-meta {
    display: flex;
    gap: 8px;
    font-size: 12px;
    color: #6b7280;
  }

  .submission-priority {
    text-transform: capitalize;
  }

  .submission-error {
    font-size: 11px;
    color: #ef4444;
    margin: 4px 0 0 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .empty-message {
    color: #6b7280;
    text-align: center;
    padding: 40px 20px;
    font-style: italic;
  }

  .view-all-link {
    display: block;
    text-align: center;
    color: #60a5fa;
    text-decoration: none;
    font-size: 14px;
    margin-top: 16px;
    padding: 8px;
    border-radius: 6px;
    transition: all 0.2s;
  }

  .view-all-link:hover {
    background-color: rgba(96, 165, 250, 0.1);
  }

  /* Tips Panel */
  .tips-panel {
    background-color: #1f2937;
  }

  .tips-panel h3 {
    font-size: 16px;
    font-weight: 600;
    margin: 0 0 16px 0;
    color: #ffffff;
  }

  .tips-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
  }

  .tip {
    display: flex;
    gap: 12px;
    align-items: flex-start;
  }

  .tip-icon {
    flex-shrink: 0;
    width: 28px;
    height: 28px;
    border-radius: 50%;
    background-color: #2563eb;
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 600;
    font-size: 14px;
  }

  .tip-content strong {
    display: block;
    color: #ffffff;
    font-size: 14px;
    margin-bottom: 4px;
  }

  .tip-content p {
    color: #9ca3af;
    font-size: 13px;
    margin: 0;
    line-height: 1.4;
  }

  /* Responsive */
  @media (max-width: 1024px) {
    .main-grid {
      grid-template-columns: 1fr;
    }

    .tips-grid {
      grid-template-columns: repeat(2, 1fr);
    }
  }

  @media (max-width: 768px) {
    .youtube-container {
      padding: 12px;
    }

    .video-preview {
      flex-direction: column;
    }

    .preview-thumbnail {
      width: 100%;
      height: 180px;
    }

    .tips-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
