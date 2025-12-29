<script lang="ts">
  import { onMount } from 'svelte';

  // YouTube Queue
  interface YouTubeQueueEntry {
    id: string;
    youtube_url: string;
    youtube_video_id: string;
    title: string;
    priority: string;
    status: string;
    submitted_by: string;
    submitted_at: string;
    processing_started_at: string | null;
    completed_at: string | null;
    error: string | null;
    output_video_id?: string;
  }

  // Flagged Faces
  interface FlaggedFace {
    id: string;
    contestant_id: number;
    video_id: string;
    timestamp: number;
    bbox: number[] | null;
    confidence: number | null;
    user_label: string | null;
    has_thumbnail: boolean;
    flagged_at: string;
    status: string;
    reviewed_by?: string;
    reviewed_at?: string;
    thumbnail?: string; // Loaded on demand
  }

  // Thumbnail cache
  let thumbnailCache: Map<string, string> = new Map();

  let youtubeUrl = '';
  let videoTitle = '';
  let priority = 'normal';
  let youtubeQueue: YouTubeQueueEntry[] = [];
  let flaggedFaces: FlaggedFace[] = [];
  let loading = false;
  let error = '';
  let success = '';
  let activeTab = 'youtube';
  let statusFilter = '';

  // Embedding comparison state
  let selectedContestantForComparison: number | null = null;
  let comparisonData: any = null;
  let loadingComparison = false;

  // Get unique contestant IDs from flagged faces
  $: contestantsWithFlags = [...new Set(flaggedFaces.map(f => f.contestant_id))].sort((a, b) => a - b);

  onMount(async () => {
    await Promise.all([
      loadYouTubeQueue(),
      loadFlaggedFaces()
    ]);
  });

  async function loadYouTubeQueue() {
    try {
      const url = statusFilter
        ? `/api/admin/youtube/queue?status=${statusFilter}`
        : '/api/admin/youtube/queue';
      const response = await fetch(url);
      if (response.ok) {
        const data = await response.json();
        youtubeQueue = data.queue || [];
      } else if (response.status === 401) {
        error = 'Unauthorized. Please configure Cloudflare Access.';
      }
    } catch (e) {
      console.error('Failed to load YouTube queue:', e);
    }
  }

  async function loadFlaggedFaces() {
    try {
      const response = await fetch('/api/faces/flagged?details=true');
      if (response.ok) {
        const data = await response.json();
        flaggedFaces = data.flags || [];
        // Load thumbnails for faces that have them
        for (const face of flaggedFaces) {
          if (face.has_thumbnail && !thumbnailCache.has(face.id)) {
            loadThumbnail(face.id);
          }
        }
      }
    } catch (e) {
      console.error('Failed to load flagged faces:', e);
    }
  }

  async function loadThumbnail(flagId: string) {
    if (thumbnailCache.has(flagId)) return;
    try {
      const response = await fetch(`/api/faces/thumbnail?flag_id=${flagId}`);
      if (response.ok) {
        const data = await response.json();
        thumbnailCache.set(flagId, data.thumbnail);
        thumbnailCache = thumbnailCache; // Trigger reactivity
      }
    } catch (e) {
      console.error('Failed to load thumbnail:', e);
    }
  }

  async function submitYouTubeUrl() {
    if (!youtubeUrl.trim()) {
      error = 'Please enter a YouTube URL';
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
          title: videoTitle || undefined,
          priority
        })
      });

      const data = await response.json();

      if (response.ok) {
        success = `Video queued successfully! Queue ID: ${data.queue_id}`;
        youtubeUrl = '';
        videoTitle = '';
        priority = 'normal';
        await loadYouTubeQueue();
      } else {
        error = data.error || 'Failed to queue video';
      }
    } catch (e) {
      error = 'Network error. Please try again.';
    } finally {
      loading = false;
    }
  }

  async function approveFlag(flagId: string, action: 'approve' | 'reject') {
    loading = true;
    error = '';
    success = '';

    try {
      const response = await fetch('/api/admin/flagged/approve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ flag_id: flagId, action })
      });

      const data = await response.json();

      if (response.ok) {
        success = `Flag ${action}d successfully`;
        await loadFlaggedFaces();
      } else {
        error = data.error || `Failed to ${action} flag`;
      }
    } catch (e) {
      error = 'Network error. Please try again.';
    } finally {
      loading = false;
    }
  }

  async function triggerEmbeddingSync() {
    loading = true;
    error = '';
    success = '';

    try {
      const response = await fetch('/api/admin/embeddings/trigger-sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });

      const data = await response.json();

      if (response.ok) {
        success = `Sync triggered! ${data.approved_flags_count} approved flags ready. Run: modal run scripts/modal_hf_processor.py --update-embeddings`;
      } else {
        error = data.error || 'Failed to trigger sync';
      }
    } catch (e) {
      error = 'Network error. Please try again.';
    } finally {
      loading = false;
    }
  }

  async function loadEmbeddingComparison(contestantId: number) {
    selectedContestantForComparison = contestantId;
    loadingComparison = true;
    comparisonData = null;

    try {
      const response = await fetch(`/api/admin/embeddings/compare?contestant_id=${contestantId}`);
      if (response.ok) {
        comparisonData = await response.json();
      } else {
        error = 'Failed to load comparison data';
      }
    } catch (e) {
      error = 'Network error loading comparison';
    } finally {
      loadingComparison = false;
    }
  }

  function formatDate(dateStr: string | null): string {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleString();
  }

  function getStatusColor(status: string): string {
    switch (status) {
      case 'queued': return '#3b82f6';
      case 'processing': return '#f59e0b';
      case 'completed': return '#22c55e';
      case 'failed': return '#ef4444';
      case 'pending': return '#6b7280';
      case 'approved': return '#22c55e';
      case 'rejected': return '#ef4444';
      default: return '#6b7280';
    }
  }
</script>

<svelte:head>
  <title>Admin - MV Face Recognition</title>
</svelte:head>

<div class="admin-container">
  <div class="admin-header">
    <h1>Admin Panel</h1>
    <p class="admin-description">Manage YouTube video processing and face flagging approvals</p>
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

  <!-- Tab Navigation -->
  <div class="tabs">
    <button
      class="tab"
      class:active={activeTab === 'youtube'}
      on:click={() => activeTab = 'youtube'}
    >
      YouTube Ingestion
    </button>
    <button
      class="tab"
      class:active={activeTab === 'flagging'}
      on:click={() => activeTab = 'flagging'}
    >
      Face Flagging Approval
    </button>
    <button
      class="tab"
      class:active={activeTab === 'embeddings'}
      on:click={() => activeTab = 'embeddings'}
    >
      Embedding Sync
    </button>
  </div>

  <!-- YouTube Ingestion Tab -->
  {#if activeTab === 'youtube'}
    <div class="panel">
      <div class="panel-header-row">
        <div>
          <h2>Submit YouTube Video</h2>
          <p class="panel-description">Add a YouTube video URL to the processing queue</p>
        </div>
        <a href="/admin/youtube" class="btn btn-primary">
          Open Enhanced Form
        </a>
      </div>

      <form on:submit|preventDefault={submitYouTubeUrl} class="form">
        <div class="form-group">
          <label for="youtube-url">YouTube URL *</label>
          <input
            id="youtube-url"
            type="text"
            bind:value={youtubeUrl}
            placeholder="https://www.youtube.com/watch?v=..."
            class="input"
          />
        </div>

        <div class="form-group">
          <label for="video-title">Title (optional)</label>
          <input
            id="video-title"
            type="text"
            bind:value={videoTitle}
            placeholder="Custom title for the video"
            class="input"
          />
        </div>

        <div class="form-group">
          <label for="priority">Priority</label>
          <select id="priority" bind:value={priority} class="select">
            <option value="low">Low</option>
            <option value="normal">Normal</option>
            <option value="high">High</option>
          </select>
        </div>

        <button type="submit" class="btn btn-primary" disabled={loading}>
          {loading ? 'Submitting...' : 'Add to Queue'}
        </button>
      </form>

      <div class="divider"></div>

      <h3>Processing Queue</h3>
      <div class="filter-row">
        <label for="status-filter">Filter by status:</label>
        <select id="status-filter" bind:value={statusFilter} on:change={loadYouTubeQueue} class="select select-small">
          <option value="">All</option>
          <option value="queued">Queued</option>
          <option value="processing">Processing</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
        </select>
        <button class="btn btn-secondary btn-small" on:click={loadYouTubeQueue}>Refresh</button>
      </div>

      {#if youtubeQueue.length === 0}
        <p class="empty-message">No videos in queue</p>
      {:else}
        <div class="table-container">
          <table class="table">
            <thead>
              <tr>
                <th>Title</th>
                <th>Status</th>
                <th>Priority</th>
                <th>Submitted</th>
                <th>Completed</th>
              </tr>
            </thead>
            <tbody>
              {#each youtubeQueue as entry}
                <tr>
                  <td>
                    <div class="video-info">
                      <a href={entry.youtube_url} target="_blank" rel="noopener noreferrer">
                        {entry.title}
                      </a>
                      <span class="video-id">{entry.youtube_video_id}</span>
                    </div>
                  </td>
                  <td>
                    <span class="status-badge" style="background-color: {getStatusColor(entry.status)}">
                      {entry.status}
                    </span>
                    {#if entry.error}
                      <span class="error-text" title={entry.error}>Error</span>
                    {/if}
                  </td>
                  <td>{entry.priority}</td>
                  <td>
                    <div class="date-info">
                      {formatDate(entry.submitted_at)}
                      <span class="submitted-by">by {entry.submitted_by}</span>
                    </div>
                  </td>
                  <td>{formatDate(entry.completed_at)}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </div>
  {/if}

  <!-- Face Flagging Approval Tab -->
  {#if activeTab === 'flagging'}
    <div class="panel">
      <h2>Flagged Faces Review</h2>
      <p class="panel-description">Review and approve/reject user-submitted face corrections</p>

      <div class="filter-row">
        <button class="btn btn-secondary btn-small" on:click={loadFlaggedFaces}>Refresh</button>
        <span class="count-badge">{flaggedFaces.filter(f => f.status === 'pending').length} pending</span>
      </div>

      {#if flaggedFaces.length === 0}
        <p class="empty-message">No flagged faces to review</p>
      {:else}
        <div class="flags-grid">
          {#each flaggedFaces as flag}
            <div class="flag-card">
              <div class="flag-header">
                <span class="status-badge" style="background-color: {getStatusColor(flag.status)}">
                  {flag.status}
                </span>
                <span class="flag-id">{flag.id.substring(0, 20)}...</span>
              </div>

              <!-- Face Thumbnail -->
              {#if flag.has_thumbnail && thumbnailCache.has(flag.id)}
                <div class="flag-thumbnail">
                  <img src={thumbnailCache.get(flag.id)} alt="Face thumbnail" />
                </div>
              {:else if flag.has_thumbnail}
                <div class="flag-thumbnail placeholder">
                  <span>Loading...</span>
                </div>
              {/if}

              <div class="flag-details">
                <div class="detail-row">
                  <span class="label">Contestant ID:</span>
                  <span class="value">{flag.contestant_id}</span>
                </div>
                <div class="detail-row">
                  <span class="label">Video:</span>
                  <span class="value">{flag.video_id}</span>
                </div>
                <div class="detail-row">
                  <span class="label">Timestamp:</span>
                  <span class="value">{flag.timestamp?.toFixed(2)}s</span>
                </div>
                {#if flag.confidence}
                  <div class="detail-row">
                    <span class="label">Confidence:</span>
                    <span class="value">{(flag.confidence * 100).toFixed(1)}%</span>
                  </div>
                {/if}
                {#if flag.user_label}
                  <div class="detail-row">
                    <span class="label">Note:</span>
                    <span class="value">{flag.user_label}</span>
                  </div>
                {/if}
                <div class="detail-row">
                  <span class="label">Flagged:</span>
                  <span class="value">{formatDate(flag.flagged_at)}</span>
                </div>
              </div>

              {#if flag.status === 'pending'}
                <div class="flag-actions">
                  <button
                    class="btn btn-success btn-small"
                    on:click={() => approveFlag(flag.id, 'approve')}
                    disabled={loading}
                  >
                    Approve
                  </button>
                  <button
                    class="btn btn-danger btn-small"
                    on:click={() => approveFlag(flag.id, 'reject')}
                    disabled={loading}
                  >
                    Reject
                  </button>
                </div>
              {:else}
                <div class="flag-reviewed">
                  Reviewed by {flag.reviewed_by} on {formatDate(flag.reviewed_at ?? null)}
                </div>
              {/if}
            </div>
          {/each}
        </div>
      {/if}
    </div>
  {/if}

  <!-- Embedding Sync Tab -->
  {#if activeTab === 'embeddings'}
    <div class="panel">
      <h2>Embedding Synchronization</h2>
      <p class="panel-description">Update face embeddings from approved flagged faces</p>

      <div class="sync-stats">
        <div class="stat-card">
          <div class="stat-value">{flaggedFaces.filter(f => f.status === 'approved').length}</div>
          <div class="stat-label">Approved Flags</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{flaggedFaces.filter(f => f.status === 'pending').length}</div>
          <div class="stat-label">Pending Review</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{flaggedFaces.filter(f => f.status === 'rejected').length}</div>
          <div class="stat-label">Rejected</div>
        </div>
      </div>

      <div class="sync-section">
        <h3>Trigger Embedding Update</h3>
        <p>This will create a sync job that processes all approved flags and updates the contestant embeddings.</p>
        <p class="warning-text">After triggering, run: <code>modal run scripts/modal_hf_processor.py --update-embeddings</code></p>

        <button
          class="btn btn-primary"
          on:click={triggerEmbeddingSync}
          disabled={loading || flaggedFaces.filter(f => f.status === 'approved').length === 0}
        >
          {loading ? 'Triggering...' : 'Trigger Embedding Sync'}
        </button>
      </div>

      <div class="divider"></div>

      <!-- Embedding Comparison Visualization -->
      <h3>Embedding Comparison</h3>
      <p class="panel-description">View flagged face statistics per contestant</p>

      {#if contestantsWithFlags.length === 0}
        <p class="empty-message">No contestants with flagged faces yet</p>
      {:else}
        <div class="comparison-container">
          <div class="contestant-selector">
            <label for="contestant-compare">Select Contestant:</label>
            <select
              id="contestant-compare"
              bind:value={selectedContestantForComparison}
              on:change={() => selectedContestantForComparison && loadEmbeddingComparison(selectedContestantForComparison)}
              class="select"
            >
              <option value={null}>-- Select --</option>
              {#each contestantsWithFlags as id}
                <option value={id}>Contestant #{id}</option>
              {/each}
            </select>
          </div>

          {#if loadingComparison}
            <div class="loading-comparison">Loading comparison data...</div>
          {:else if comparisonData}
            <div class="comparison-results">
              <div class="comparison-header">
                <h4>Contestant #{comparisonData.contestant_id} - Embedding Analysis</h4>
              </div>

              <div class="comparison-stats">
                <div class="comp-stat">
                  <div class="comp-stat-value">{comparisonData.total_flags}</div>
                  <div class="comp-stat-label">Total Flags</div>
                </div>
                <div class="comp-stat approved">
                  <div class="comp-stat-value">{comparisonData.approved_count}</div>
                  <div class="comp-stat-label">Approved</div>
                </div>
                <div class="comp-stat pending">
                  <div class="comp-stat-value">{comparisonData.pending_count}</div>
                  <div class="comp-stat-label">Pending</div>
                </div>
                <div class="comp-stat rejected">
                  <div class="comp-stat-value">{comparisonData.rejected_count}</div>
                  <div class="comp-stat-label">Rejected</div>
                </div>
              </div>

              <!-- Confidence Distribution Bar -->
              <div class="confidence-section">
                <h5>Average Confidence</h5>
                <div class="confidence-bar-container">
                  <div
                    class="confidence-bar"
                    style="width: {comparisonData.average_confidence * 100}%"
                  ></div>
                  <span class="confidence-value">{(comparisonData.average_confidence * 100).toFixed(1)}%</span>
                </div>
              </div>

              <!-- Flag Timeline -->
              {#if comparisonData.flags && comparisonData.flags.length > 0}
                <div class="flag-timeline-section">
                  <h5>Flag Timeline</h5>
                  <div class="flag-timeline">
                    {#each comparisonData.flags.slice(0, 10) as flag}
                      <div class="timeline-item">
                        <span class="timeline-status" style="background-color: {getStatusColor(flag.status)}"></span>
                        <span class="timeline-video">{flag.video_id}</span>
                        <span class="timeline-time">@ {flag.timestamp?.toFixed(1)}s</span>
                        <span class="timeline-conf">{((flag.confidence || 0) * 100).toFixed(0)}%</span>
                      </div>
                    {/each}
                    {#if comparisonData.flags.length > 10}
                      <p class="more-flags">... and {comparisonData.flags.length - 10} more</p>
                    {/if}
                  </div>
                </div>
              {/if}

              <!-- Embedding Status -->
              <div class="embedding-status-section">
                <h5>Embedding Status</h5>
                <div class="embedding-info">
                  <div class="info-row">
                    <span class="info-label">Base Embedding:</span>
                    <span class="info-value" class:active={comparisonData.embedding_status?.has_base_embedding}>
                      {comparisonData.embedding_status?.has_base_embedding ? 'Available' : 'Missing'}
                    </span>
                  </div>
                  <div class="info-row">
                    <span class="info-label">Flag Contributions:</span>
                    <span class="info-value">{comparisonData.embedding_status?.flag_contributions || 0}</span>
                  </div>
                </div>
              </div>
            </div>
          {/if}
        </div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .admin-container {
    padding: 20px;
    max-width: 1200px;
    margin: 0 auto;
  }

  .admin-header {
    margin-bottom: 24px;
  }

  .admin-header h1 {
    font-size: 28px;
    font-weight: 600;
    margin: 0 0 8px 0;
    color: #ffffff;
  }

  .admin-description {
    color: #9ca3af;
    margin: 0;
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

  .tabs {
    display: flex;
    gap: 4px;
    margin-bottom: 20px;
    border-bottom: 1px solid #374151;
    padding-bottom: 4px;
  }

  .tab {
    padding: 12px 20px;
    background: none;
    border: none;
    color: #9ca3af;
    cursor: pointer;
    font-size: 14px;
    font-weight: 500;
    border-radius: 8px 8px 0 0;
    transition: all 0.2s;
  }

  .tab:hover {
    color: #ffffff;
    background-color: rgba(255, 255, 255, 0.1);
  }

  .tab.active {
    color: #ffffff;
    background-color: #2563eb;
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
    margin: 0 0 8px 0;
    color: #ffffff;
  }

  .panel-header-row {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 20px;
    gap: 16px;
  }

  .panel-header-row .btn {
    white-space: nowrap;
  }

  .panel h3 {
    font-size: 16px;
    font-weight: 600;
    margin: 20px 0 12px 0;
    color: #ffffff;
  }

  .panel-description {
    color: #9ca3af;
    margin: 0 0 20px 0;
    font-size: 14px;
  }

  .form {
    display: flex;
    flex-direction: column;
    gap: 16px;
    max-width: 500px;
  }

  .form-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .form-group label {
    font-size: 14px;
    font-weight: 500;
    color: #d1d5db;
  }

  .input, .select {
    padding: 10px 14px;
    border: 1px solid #4b5563;
    border-radius: 8px;
    background-color: #1f2937;
    color: #ffffff;
    font-size: 14px;
  }

  .input:focus, .select:focus {
    outline: none;
    border-color: #2563eb;
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.3);
  }

  .select-small {
    padding: 6px 10px;
    font-size: 13px;
  }

  .btn {
    padding: 10px 20px;
    border: none;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
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

  .btn-success {
    background-color: #22c55e;
    color: white;
  }

  .btn-success:hover:not(:disabled) {
    background-color: #16a34a;
  }

  .btn-danger {
    background-color: #ef4444;
    color: white;
  }

  .btn-danger:hover:not(:disabled) {
    background-color: #dc2626;
  }

  .btn-small {
    padding: 6px 12px;
    font-size: 13px;
  }

  .divider {
    height: 1px;
    background-color: #374151;
    margin: 24px 0;
  }

  .filter-row {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 16px;
  }

  .filter-row label {
    font-size: 14px;
    color: #9ca3af;
  }

  .count-badge {
    background-color: #374151;
    padding: 4px 10px;
    border-radius: 12px;
    font-size: 13px;
    color: #d1d5db;
  }

  .empty-message {
    color: #6b7280;
    text-align: center;
    padding: 40px;
    font-style: italic;
  }

  .table-container {
    overflow-x: auto;
  }

  .table {
    width: 100%;
    border-collapse: collapse;
    font-size: 14px;
  }

  .table th, .table td {
    padding: 12px;
    text-align: left;
    border-bottom: 1px solid #374151;
  }

  .table th {
    font-weight: 600;
    color: #9ca3af;
    background-color: #1f2937;
  }

  .table td {
    color: #d1d5db;
  }

  .table tr:hover {
    background-color: rgba(255, 255, 255, 0.05);
  }

  .video-info {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .video-info a {
    color: #60a5fa;
    text-decoration: none;
  }

  .video-info a:hover {
    text-decoration: underline;
  }

  .video-id {
    font-size: 12px;
    color: #6b7280;
    font-family: monospace;
  }

  .status-badge {
    display: inline-block;
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 12px;
    font-weight: 500;
    color: white;
    text-transform: capitalize;
  }

  .error-text {
    color: #ef4444;
    font-size: 12px;
    margin-left: 8px;
  }

  .date-info {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .submitted-by {
    font-size: 12px;
    color: #6b7280;
  }

  .flags-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 16px;
  }

  .flag-card {
    background-color: #1f2937;
    border: 1px solid #374151;
    border-radius: 8px;
    padding: 16px;
  }

  .flag-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
  }

  .flag-id {
    font-size: 11px;
    color: #6b7280;
    font-family: monospace;
  }

  .flag-thumbnail {
    width: 100%;
    height: 120px;
    background-color: #111827;
    border-radius: 6px;
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
  }

  .flag-thumbnail img {
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
    border-radius: 4px;
  }

  .flag-thumbnail.placeholder {
    color: #6b7280;
    font-size: 12px;
  }

  .flag-details {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 16px;
  }

  .detail-row {
    display: flex;
    gap: 8px;
  }

  .detail-row .label {
    color: #9ca3af;
    font-size: 13px;
    min-width: 100px;
  }

  .detail-row .value {
    color: #d1d5db;
    font-size: 13px;
  }

  .flag-actions {
    display: flex;
    gap: 8px;
  }

  .flag-reviewed {
    font-size: 12px;
    color: #6b7280;
    font-style: italic;
  }

  .sync-stats {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
    margin-bottom: 24px;
  }

  .stat-card {
    background-color: #1f2937;
    border: 1px solid #374151;
    border-radius: 8px;
    padding: 20px;
    text-align: center;
  }

  .stat-value {
    font-size: 32px;
    font-weight: 700;
    color: #ffffff;
    margin-bottom: 4px;
  }

  .stat-label {
    font-size: 14px;
    color: #9ca3af;
  }

  .sync-section {
    background-color: #1f2937;
    border: 1px solid #374151;
    border-radius: 8px;
    padding: 20px;
  }

  .sync-section p {
    color: #9ca3af;
    font-size: 14px;
    margin: 0 0 12px 0;
  }

  .warning-text {
    background-color: rgba(245, 158, 11, 0.2);
    border: 1px solid #f59e0b;
    padding: 12px;
    border-radius: 8px;
    color: #fcd34d;
  }

  .warning-text code {
    background-color: rgba(0, 0, 0, 0.3);
    padding: 2px 6px;
    border-radius: 4px;
    font-family: monospace;
    font-size: 13px;
  }

  /* Embedding Comparison Styles */
  .comparison-container {
    margin-top: 16px;
  }

  .contestant-selector {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 20px;
  }

  .contestant-selector label {
    font-size: 14px;
    color: #9ca3af;
  }

  .loading-comparison {
    color: #9ca3af;
    text-align: center;
    padding: 40px;
  }

  .comparison-results {
    background-color: #1f2937;
    border: 1px solid #374151;
    border-radius: 12px;
    padding: 20px;
  }

  .comparison-header h4 {
    margin: 0 0 16px 0;
    color: #ffffff;
    font-size: 18px;
  }

  .comparison-stats {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-bottom: 20px;
  }

  .comp-stat {
    background-color: #111827;
    border-radius: 8px;
    padding: 16px;
    text-align: center;
  }

  .comp-stat-value {
    font-size: 24px;
    font-weight: 700;
    color: #ffffff;
  }

  .comp-stat-label {
    font-size: 12px;
    color: #9ca3af;
    margin-top: 4px;
  }

  .comp-stat.approved .comp-stat-value { color: #22c55e; }
  .comp-stat.pending .comp-stat-value { color: #f59e0b; }
  .comp-stat.rejected .comp-stat-value { color: #ef4444; }

  .confidence-section {
    margin-bottom: 20px;
  }

  .confidence-section h5 {
    margin: 0 0 8px 0;
    font-size: 14px;
    color: #d1d5db;
  }

  .confidence-bar-container {
    background-color: #111827;
    border-radius: 8px;
    height: 32px;
    position: relative;
    overflow: hidden;
  }

  .confidence-bar {
    height: 100%;
    background: linear-gradient(90deg, #22c55e, #86efac);
    border-radius: 8px;
    transition: width 0.3s ease;
  }

  .confidence-value {
    position: absolute;
    right: 12px;
    top: 50%;
    transform: translateY(-50%);
    font-weight: 600;
    color: #ffffff;
    font-size: 14px;
  }

  .flag-timeline-section {
    margin-bottom: 20px;
  }

  .flag-timeline-section h5 {
    margin: 0 0 12px 0;
    font-size: 14px;
    color: #d1d5db;
  }

  .flag-timeline {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .timeline-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 8px 12px;
    background-color: #111827;
    border-radius: 6px;
    font-size: 13px;
  }

  .timeline-status {
    width: 8px;
    height: 8px;
    border-radius: 50%;
  }

  .timeline-video {
    color: #d1d5db;
    flex: 1;
  }

  .timeline-time {
    color: #9ca3af;
  }

  .timeline-conf {
    color: #60a5fa;
    font-weight: 500;
  }

  .more-flags {
    color: #6b7280;
    font-size: 12px;
    text-align: center;
    margin: 8px 0 0 0;
  }

  .embedding-status-section h5 {
    margin: 0 0 12px 0;
    font-size: 14px;
    color: #d1d5db;
  }

  .embedding-info {
    background-color: #111827;
    border-radius: 8px;
    padding: 16px;
  }

  .info-row {
    display: flex;
    justify-content: space-between;
    padding: 8px 0;
    border-bottom: 1px solid #1f2937;
  }

  .info-row:last-child {
    border-bottom: none;
  }

  .info-label {
    color: #9ca3af;
    font-size: 13px;
  }

  .info-value {
    color: #d1d5db;
    font-size: 13px;
    font-weight: 500;
  }

  .info-value.active {
    color: #22c55e;
  }

  @media (max-width: 768px) {
    .admin-container {
      padding: 12px;
    }

    .tabs {
      flex-wrap: wrap;
    }

    .tab {
      flex: 1;
      min-width: 100px;
      text-align: center;
      padding: 10px 12px;
      font-size: 13px;
    }

    .sync-stats {
      grid-template-columns: 1fr;
    }

    .flags-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
