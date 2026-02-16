<script lang="ts">
  import { onMount } from 'svelte';
  import Card from '$lib/components/Card.svelte';
  import Button from '$lib/components/Button.svelte';
  import Badge from '$lib/components/Badge.svelte';
  
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

  let flaggedFaces: FlaggedFace[] = [];
  let loading = false;
  let error = '';
  let success = '';
  let activeTab = 'flagging';

  // Video upload state
  let uploadingVideo = false;
  let uploadProgress = 0;
  let selectedFile: File | null = null;
  let uploadedVideoUrl = '';
  let processingStatus = 'idle'; // idle, uploading, uploaded, processing, completed, failed

  // Embedding comparison state
  let selectedContestantForComparison: number | null = null;
  let comparisonData: any = null;
  let loadingComparison = false;

  // Embedding Bootstrap state
  let bootstrapActiveSubTab: 'status' | 'photos' | 'video' | 'jobs' = 'status';
  let embeddingStatuses: Array<{
    id: string; number: number; name: string; nickname: string;
    has_photos: boolean; has_embedding: boolean; photo_count: number;
    last_photo_upload: string | null; last_embedding_update: string | null;
  }> = [];
  let embeddingCoverage = { with_photos: 0, with_embeddings: 0, coverage_pct: 0, total: 0 };
  let bootstrapJobs: Array<Record<string, any>> = [];
  let selectedContestantForUpload: number | null = null;
  let photoFiles: FileList | null = null;
  let bootstrapVideoFile: File | null = null;
  let sampleInterval = 2.0;
  let maxSamples = 100;
  let loadingBootstrap = false;

  // Get unique contestant IDs from flagged faces
  $: contestantsWithFlags = [...new Set(flaggedFaces.map(f => f.contestant_id))].sort((a, b) => a - b);

  onMount(async () => {
    await loadFlaggedFaces();
  });

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

  function handleFileSelect(event: Event) {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      selectedFile = input.files[0];
      error = '';
      success = '';
    }
  }

  async function uploadVideoToHF() {
    if (!selectedFile) {
      error = 'Please select a video file first';
      return;
    }

    uploadingVideo = true;
    processingStatus = 'uploading';
    uploadProgress = 0;
    error = '';
    success = '';

    try {
      const formData = new FormData();
      formData.append('video', selectedFile);
      formData.append('filename', selectedFile.name);

      const response = await fetch('/api/admin/upload-video', {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();

      if (response.ok) {
        uploadedVideoUrl = data.video_url;
        processingStatus = 'uploaded';
        success = `Video uploaded successfully: ${data.video_name}`;
        uploadProgress = 100;
      } else {
        error = data.error || 'Upload failed';
        processingStatus = 'failed';
      }
    } catch (e) {
      error = 'Network error during upload';
      processingStatus = 'failed';
    } finally {
      uploadingVideo = false;
    }
  }

  async function triggerModalProcessing() {
    if (!uploadedVideoUrl) {
      error = 'Please upload a video first';
      return;
    }

    loading = true;
    processingStatus = 'processing';
    error = '';
    success = '';

    try {
      const response = await fetch('/api/admin/trigger-modal', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          video_url: uploadedVideoUrl,
          video_name: selectedFile?.name,
        })
      });

      const data = await response.json();

      if (response.ok) {
        success = data.message || 'Modal processing triggered successfully!';
        processingStatus = 'processing';
      } else {
        error = data.error || 'Failed to trigger Modal processing';
        processingStatus = 'failed';
      }
    } catch (e) {
      error = 'Network error triggering Modal';
      processingStatus = 'failed';
    } finally {
      loading = false;
    }
  }

  function resetUpload() {
    selectedFile = null;
    uploadedVideoUrl = '';
    uploadProgress = 0;
    processingStatus = 'idle';
    error = '';
    success = '';
  }

  // Embedding Bootstrap functions
  async function loadEmbeddingStatus() {
    loadingBootstrap = true;
    error = '';
    try {
      const response = await fetch('/api/admin/embeddings/status');
      if (response.ok) {
        const data = await response.json();
        embeddingStatuses = data.contestants || [];
        embeddingCoverage = {
          with_photos: data.with_photos || 0,
          with_embeddings: data.with_embeddings || 0,
          coverage_pct: data.coverage_pct || 0,
          total: data.total || 0
        };
      } else {
        error = 'Failed to load embedding status';
      }
    } catch (e) {
      error = 'Network error loading embedding status';
    } finally {
      loadingBootstrap = false;
    }
  }

  async function loadBootstrapJobs() {
    loadingBootstrap = true;
    error = '';
    try {
      const response = await fetch('/api/admin/bootstrap/jobs');
      if (response.ok) {
        const data = await response.json();
        bootstrapJobs = data.jobs || [];
      } else {
        error = 'Failed to load bootstrap jobs';
      }
    } catch (e) {
      error = 'Network error loading bootstrap jobs';
    } finally {
      loadingBootstrap = false;
    }
  }

  async function uploadPhotos() {
    if (!selectedContestantForUpload || !photoFiles || photoFiles.length === 0) {
      error = 'Please select a contestant and photo files';
      return;
    }

    loadingBootstrap = true;
    error = '';
    success = '';

    try {
      const formData = new FormData();
      formData.append('contestant_id', String(selectedContestantForUpload));
      for (let i = 0; i < photoFiles.length; i++) {
        formData.append('photo', photoFiles[i]);
      }

      const response = await fetch('/api/admin/photos/upload', {
        method: 'POST',
        body: formData
      });

      const data = await response.json();

      if (response.ok) {
        success = `Uploaded ${data.uploaded} photo(s) for contestant #${selectedContestantForUpload}. Total: ${data.total_photos}`;
        photoFiles = null;
        await loadEmbeddingStatus();
      } else {
        error = data.error || 'Failed to upload photos';
      }
    } catch (e) {
      error = 'Network error during photo upload';
    } finally {
      loadingBootstrap = false;
    }
  }

  async function uploadBootstrapVideo() {
    if (!bootstrapVideoFile) {
      error = 'Please select a video file';
      return;
    }

    loadingBootstrap = true;
    error = '';
    success = '';

    try {
      const formData = new FormData();
      formData.append('video', bootstrapVideoFile);
      formData.append('sample_interval', String(sampleInterval));
      formData.append('max_samples', String(maxSamples));

      const response = await fetch('/api/admin/videos/sample-faces', {
        method: 'POST',
        body: formData
      });

      const data = await response.json();

      if (response.ok) {
        success = `Video uploaded and sampling job created. Job ID: ${data.job_id}`;
        bootstrapVideoFile = null;
        await loadBootstrapJobs();
      } else {
        error = data.error || 'Failed to upload video';
      }
    } catch (e) {
      error = 'Network error during video upload';
    } finally {
      loadingBootstrap = false;
    }
  }

  async function triggerRegeneration(contestantIds?: number[]) {
    loadingBootstrap = true;
    error = '';
    success = '';

    try {
      const response = await fetch('/api/admin/embeddings/regenerate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contestant_ids: contestantIds,
          source: 'photos'
        })
      });

      const data = await response.json();

      if (response.ok) {
        success = `Regeneration job created: ${data.job_id}. Run: modal run scripts/modal_youtube_processor.py --bootstrap-job ${data.job_id}`;
        await loadBootstrapJobs();
      } else {
        error = data.error || 'Failed to create regeneration job';
      }
    } catch (e) {
      error = 'Network error triggering regeneration';
    } finally {
      loadingBootstrap = false;
    }
  }

  function handlePhotoFileSelect(event: Event) {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      photoFiles = input.files;
      error = '';
    }
  }

  function handleBootstrapVideoSelect(event: Event) {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      bootstrapVideoFile = input.files[0];
      error = '';
    }
  }
</script>

<svelte:head>
  <title>Admin - MV Face Recognition</title>
</svelte:head>

<div class="admin-container">
  <div class="admin-header">
    <h1>Admin Panel</h1>
    <p class="admin-description">Manage face flagging approvals and embedding synchronization</p>
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
    <button
      class="tab"
      class:active={activeTab === 'processing'}
      on:click={() => activeTab = 'processing'}
    >
      Video Processing
    </button>
    <button
      class="tab"
      class:active={activeTab === 'bootstrap'}
      on:click={() => { activeTab = 'bootstrap'; loadEmbeddingStatus(); loadBootstrapJobs(); }}
    >
      Embedding Bootstrap
    </button>
  </div>

  <!-- Face Flagging Approval Tab -->
  {#if activeTab === 'flagging'}
    <Card class="panel">
      <div class="panel-inner">
        <h2>Flagged Faces Review</h2>
        <p class="panel-description">Review and approve/reject user-submitted face corrections</p>

        <div class="filter-row">
          <Button variant="secondary" size="sm" on:click={loadFlaggedFaces}>Refresh</Button>
          <Badge variant="neutral">{flaggedFaces.filter(f => f.status === 'pending').length} pending</Badge>
        </div>

        {#if flaggedFaces.length === 0}
          <p class="empty-message">No flagged faces to review</p>
        {:else}
          <div class="flags-grid">
            {#each flaggedFaces as flag}
              <Card variant="bordered" class="flag-card-wrapper">
                <div class="flag-card-inner">
                  <div class="flag-header">
                    <Badge variant={flag.status === 'approved' ? 'success' : flag.status === 'pending' ? 'warning' : 'error'} class="status-badge-item">
                      {flag.status}
                    </Badge>
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
                      <Button
                        variant="success"
                        size="sm"
                        on:click={() => approveFlag(flag.id, 'approve')}
                        disabled={loading}
                      >
                        Approve
                      </Button>
                      <Button
                        variant="danger"
                        size="sm"
                        on:click={() => approveFlag(flag.id, 'reject')}
                        disabled={loading}
                      >
                        Reject
                      </Button>
                    </div>
                  {:else}
                    <div class="flag-reviewed">
                      Reviewed by {flag.reviewed_by} on {formatDate(flag.reviewed_at ?? null)}
                    </div>
                  {/if}
                </div>
              </Card>
            {/each}
          </div>
        {/if}
      </div>
    </Card>
  {/if}

  <!-- Embedding Sync Tab -->
  {#if activeTab === 'embeddings'}
    <Card class="panel">
      <div class="panel-inner">
        <h2>Embedding Synchronization</h2>
        <p class="panel-description">Update face embeddings from approved flagged faces</p>

        <div class="sync-stats">
          <Card variant="bordered">
            <div class="stat-card-content">
              <div class="stat-value">{flaggedFaces.filter(f => f.status === 'approved').length}</div>
              <div class="stat-label">Approved Flags</div>
            </div>
          </Card>
          <Card variant="bordered">
            <div class="stat-card-content">
              <div class="stat-value">{flaggedFaces.filter(f => f.status === 'pending').length}</div>
              <div class="stat-label">Pending Review</div>
            </div>
          </Card>
          <Card variant="bordered">
            <div class="stat-card-content">
              <div class="stat-value">{flaggedFaces.filter(f => f.status === 'rejected').length}</div>
              <div class="stat-label">Rejected</div>
            </div>
          </Card>
        </div>

        <Card variant="surface" padding="none">
          <div class="sync-section-inner">
            <h3>Trigger Embedding Update</h3>
            <p>This will create a sync job that processes all approved flags and updates the contestant embeddings.</p>
            <div class="warning-text">
              After triggering, run: <code>modal run scripts/modal_hf_processor.py --update-embeddings</code>
            </div>

            <Button
              variant="primary"
              on:click={triggerEmbeddingSync}
              disabled={loading || flaggedFaces.filter(f => f.status === 'approved').length === 0}
            >
              {loading ? 'Triggering...' : 'Trigger Embedding Sync'}
            </Button>
          </div>
        </Card>

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
              <Card variant="bordered" padding="none">
                <div class="comparison-results-inner">
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
              </Card>
            {/if}
          </div>
        {/if}
      </div>
    </Card>
  {/if}

  <!-- Video Processing Tab -->
  {#if activeTab === 'processing'}
    <Card class="panel">
      <div class="panel-inner">
        <h2>Video Processing with Modal</h2>
        <p class="panel-description">Upload videos to HuggingFace and trigger cloud GPU processing</p>

        <div class="processing-workflow">
          <!-- Step 1: File Selection -->
          <Card variant="bordered" padding="none">
            <div class="step-section">
              <div class="step-header">
                <div class="step-number" class:completed={selectedFile}>1</div>
                <div>
                  <h3>Select Video File</h3>
                  <p>Choose a video file to upload and process</p>
                </div>
              </div>

              <div class="file-input-wrapper">
                <input
                  type="file"
                  id="video-upload"
                  accept="video/mp4,video/avi,video/mov,video/mkv"
                  on:change={handleFileSelect}
                  disabled={uploadingVideo || loading}
                />
                <label for="video-upload" class="file-input-label">
                  {selectedFile ? selectedFile.name : 'Choose Video File'}
                </label>
                {#if selectedFile}
                  <Badge variant="success">
                    {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB
                  </Badge>
                {/if}
              </div>
            </div>
          </Card>

          <!-- Step 2: Upload to HuggingFace -->
          <Card variant="bordered" padding="none">
            <div class="step-section">
              <div class="step-header">
                <div class="step-number" class:completed={processingStatus === 'uploaded' || processingStatus === 'processing'}>2</div>
                <div>
                  <h3>Upload to HuggingFace XET</h3>
                  <p>Store video in cloud for Modal processing</p>
                </div>
              </div>

              {#if processingStatus === 'uploading'}
                <div class="progress-section">
                  <div class="progress-bar-container">
                    <div class="progress-bar" style="width: {uploadProgress}%"></div>
                  </div>
                  <p class="progress-text">Uploading... {uploadProgress}%</p>
                </div>
              {:else if processingStatus === 'uploaded'}
                <div class="success-message">
                  Video uploaded successfully!
                  <a href={uploadedVideoUrl} target="_blank" rel="noopener" class="video-link">
                    View on HuggingFace
                  </a>
                </div>
              {:else}
                <Button
                  variant="primary"
                  on:click={uploadVideoToHF}
                  disabled={!selectedFile || uploadingVideo || loading}
                >
                  {uploadingVideo ? 'Uploading...' : 'Upload to HuggingFace'}
                </Button>
              {/if}
            </div>
          </Card>

          <!-- Step 3: Trigger Modal Processing -->
          <Card variant="bordered" padding="none">
            <div class="step-section">
              <div class="step-header">
                <div class="step-number" class:completed={processingStatus === 'processing'}>3</div>
                <div>
                  <h3>Process with Modal</h3>
                  <p>Run face recognition with cloud GPUs</p>
                </div>
              </div>

              {#if processingStatus === 'processing'}
                <div class="processing-indicator">
                  <div class="spinner"></div>
                  <p>Processing video with Modal cloud GPUs...</p>
                  <p class="help-text">This may take several minutes. Check Modal dashboard for progress.</p>
                </div>
              {:else}
                <Button
                  variant="success"
                  on:click={triggerModalProcessing}
                  disabled={processingStatus !== 'uploaded' || loading}
                >
                  {loading ? 'Triggering...' : 'Trigger Modal Processing'}
                </Button>
              {/if}

              {#if processingStatus === 'uploaded' || processingStatus === 'processing'}
                <div class="modal-info">
                  <p><strong>Manual Trigger:</strong></p>
                  <code class="command-code">
                    modal run scripts/modal_hf_processor.py --sync-from-hf --include-videos --process-videos
                  </code>
                </div>
              {/if}
            </div>
          </Card>

          <!-- Reset Button -->
          {#if selectedFile}
            <div class="reset-section">
              <Button
                variant="secondary"
                size="sm"
                on:click={resetUpload}
                disabled={uploadingVideo || loading}
              >
                Reset / Upload Another Video
              </Button>
            </div>
          {/if}
        </div>

        <div class="divider"></div>

        <!-- Processing Status Guide -->
        <h3>Processing Workflow Guide</h3>
        <div class="guide-grid">
          <Card variant="surface" padding="none">
            <div class="guide-card">
              <div class="guide-icon">📹</div>
              <h4>1. Upload Video</h4>
              <p>Videos are uploaded to HuggingFace XET storage with efficient deduplication</p>
            </div>
          </Card>
          <Card variant="surface" padding="none">
            <div class="guide-card">
              <div class="guide-icon">🔄</div>
              <h4>2. Modal Sync</h4>
              <p>Modal downloads the video and contestant embeddings from HuggingFace</p>
            </div>
          </Card>
          <Card variant="surface" padding="none">
            <div class="guide-card">
              <div class="guide-icon">🎯</div>
              <h4>3. Face Recognition</h4>
              <p>Cloud GPUs process the video with face detection and matching</p>
            </div>
          </Card>
          <Card variant="surface" padding="none">
            <div class="guide-card">
              <div class="guide-icon">✨</div>
              <h4>4. Results Upload</h4>
              <p>Processed video with annotations is uploaded back to HuggingFace</p>
            </div>
          </Card>
        </div>
      </div>
    </Card>
  {/if}

  <!-- Embedding Bootstrap Tab -->
  {#if activeTab === 'bootstrap'}
    <Card class="panel">
      <div class="panel-inner">
        <h2>Embedding Bootstrap</h2>
        <p class="panel-description">Upload contestant photos, generate embeddings, and bootstrap from videos</p>

        <!-- Sub-tab navigation -->
        <div class="sub-tabs">
          <button class="sub-tab" class:active={bootstrapActiveSubTab === 'status'} on:click={() => { bootstrapActiveSubTab = 'status'; loadEmbeddingStatus(); }}>
            Status Dashboard
          </button>
          <button class="sub-tab" class:active={bootstrapActiveSubTab === 'photos'} on:click={() => { bootstrapActiveSubTab = 'photos'; loadEmbeddingStatus(); }}>
            Photo Upload
          </button>
          <button class="sub-tab" class:active={bootstrapActiveSubTab === 'video'} on:click={() => bootstrapActiveSubTab = 'video'}>
            Video Bootstrap
          </button>
          <button class="sub-tab" class:active={bootstrapActiveSubTab === 'jobs'} on:click={() => { bootstrapActiveSubTab = 'jobs'; loadBootstrapJobs(); }}>
            Jobs Monitor
          </button>
        </div>

        <!-- Sub-Tab A: Status Dashboard -->
        {#if bootstrapActiveSubTab === 'status'}
          <div class="sync-stats">
            <Card variant="bordered">
              <div class="stat-card-content">
                <div class="stat-value">{embeddingCoverage.with_photos}</div>
                <div class="stat-label">With Photos</div>
              </div>
            </Card>
            <Card variant="bordered">
              <div class="stat-card-content">
                <div class="stat-value">{embeddingCoverage.with_embeddings}</div>
                <div class="stat-label">With Embeddings</div>
              </div>
            </Card>
            <Card variant="bordered">
              <div class="stat-card-content">
                <div class="stat-value">{embeddingCoverage.coverage_pct}%</div>
                <div class="stat-label">Coverage</div>
              </div>
            </Card>
          </div>

          <div class="filter-row">
            <Button variant="secondary" size="sm" on:click={loadEmbeddingStatus}>Refresh</Button>
            <Button variant="primary" size="sm" on:click={() => triggerRegeneration()} disabled={loadingBootstrap}>
              {loadingBootstrap ? 'Processing...' : 'Regenerate All Embeddings'}
            </Button>
          </div>

          {#if embeddingStatuses.length === 0}
            <p class="empty-message">Loading contestant status...</p>
          {:else}
            <div class="contestant-status-grid">
              {#each embeddingStatuses as contestant}
                <div class="contestant-status-card">
                  <div class="contestant-status-header">
                    <span class="contestant-number">#{contestant.number}</span>
                    <span class="contestant-name">{contestant.nickname || contestant.name}</span>
                  </div>
                  <div class="contestant-status-badges">
                    <Badge variant={contestant.has_photos ? 'success' : 'neutral'}>
                      {contestant.has_photos ? `${contestant.photo_count} photos` : 'No photos'}
                    </Badge>
                    <Badge variant={contestant.has_embedding ? 'success' : 'warning'}>
                      {contestant.has_embedding ? 'Embedding' : 'No embedding'}
                    </Badge>
                  </div>
                </div>
              {/each}
            </div>
          {/if}
        {/if}

        <!-- Sub-Tab B: Photo Upload -->
        {#if bootstrapActiveSubTab === 'photos'}
          <div class="form">
            <div class="form-group">
              <label for="contestant-upload-select">Contestant</label>
              <select
                id="contestant-upload-select"
                bind:value={selectedContestantForUpload}
                class="select"
              >
                <option value={null}>-- Select Contestant --</option>
                {#each embeddingStatuses as c}
                  <option value={c.number}>#{c.number} - {c.nickname || c.name} ({c.photo_count} photos)</option>
                {/each}
              </select>
            </div>

            <div class="form-group">
              <label for="photo-upload-input">Photos (JPG/PNG, max 10MB each)</label>
              <div class="file-input-wrapper">
                <input
                  type="file"
                  id="photo-upload-input"
                  accept="image/jpeg,image/png,image/webp"
                  multiple
                  on:change={handlePhotoFileSelect}
                  disabled={loadingBootstrap}
                />
                <label for="photo-upload-input" class="file-input-label">
                  {photoFiles ? `${photoFiles.length} file(s) selected` : 'Choose Photos'}
                </label>
                {#if photoFiles}
                  <Badge variant="success">
                    {Array.from(photoFiles).reduce((sum, f) => sum + f.size, 0) / (1024 * 1024) | 0} MB total
                  </Badge>
                {/if}
              </div>
            </div>

            <Button
              variant="primary"
              on:click={uploadPhotos}
              disabled={!selectedContestantForUpload || !photoFiles || loadingBootstrap}
            >
              {loadingBootstrap ? 'Uploading...' : 'Upload Photos'}
            </Button>
          </div>

          {#if selectedContestantForUpload}
            <div class="divider"></div>
            <div class="modal-info">
              <p><strong>After uploading photos, generate embeddings:</strong></p>
              <Button
                variant="success"
                size="sm"
                on:click={() => triggerRegeneration([selectedContestantForUpload])}
                disabled={loadingBootstrap}
              >
                Generate Embedding for #{selectedContestantForUpload}
              </Button>
              <div class="warning-text" style="margin-top: 12px;">
                After triggering, run: <code>modal run scripts/modal_youtube_processor.py --bootstrap-job &lt;JOB_ID&gt;</code>
              </div>
            </div>
          {/if}
        {/if}

        <!-- Sub-Tab C: Video Bootstrap -->
        {#if bootstrapActiveSubTab === 'video'}
          <div class="processing-workflow">
            <!-- Step 1: Video file selection -->
            <Card variant="bordered" padding="none">
              <div class="step-section">
                <div class="step-header">
                  <div class="step-number" class:completed={bootstrapVideoFile}>1</div>
                  <div>
                    <h3>Select Video File</h3>
                    <p>Choose a video to sample faces from</p>
                  </div>
                </div>
                <div class="file-input-wrapper">
                  <input
                    type="file"
                    id="bootstrap-video-upload"
                    accept="video/mp4,video/avi,video/mov,video/mkv"
                    on:change={handleBootstrapVideoSelect}
                    disabled={loadingBootstrap}
                  />
                  <label for="bootstrap-video-upload" class="file-input-label">
                    {bootstrapVideoFile ? bootstrapVideoFile.name : 'Choose Video File'}
                  </label>
                  {#if bootstrapVideoFile}
                    <Badge variant="success">
                      {(bootstrapVideoFile.size / (1024 * 1024)).toFixed(2)} MB
                    </Badge>
                  {/if}
                </div>
              </div>
            </Card>

            <!-- Step 2: Sampling configuration -->
            <Card variant="bordered" padding="none">
              <div class="step-section">
                <div class="step-header">
                  <div class="step-number" class:completed={bootstrapVideoFile}>2</div>
                  <div>
                    <h3>Configure Sampling</h3>
                    <p>Set face sampling parameters</p>
                  </div>
                </div>
                <div class="form" style="max-width: 300px;">
                  <div class="form-group">
                    <label for="sample-interval">Sample Interval (seconds)</label>
                    <input id="sample-interval" type="number" class="input" bind:value={sampleInterval} min="0.5" max="30" step="0.5" />
                  </div>
                  <div class="form-group">
                    <label for="max-samples">Max Samples</label>
                    <input id="max-samples" type="number" class="input" bind:value={maxSamples} min="10" max="1000" step="10" />
                  </div>
                </div>
              </div>
            </Card>

            <!-- Step 3: Upload & start -->
            <Card variant="bordered" padding="none">
              <div class="step-section">
                <div class="step-header">
                  <div class="step-number">3</div>
                  <div>
                    <h3>Upload & Start Sampling</h3>
                    <p>Upload video and create face sampling job</p>
                  </div>
                </div>
                <Button
                  variant="success"
                  on:click={uploadBootstrapVideo}
                  disabled={!bootstrapVideoFile || loadingBootstrap}
                >
                  {loadingBootstrap ? 'Uploading...' : 'Upload & Start Face Sampling'}
                </Button>
                <div class="modal-info" style="margin-top: 16px;">
                  <p><strong>After uploading, process with Modal:</strong></p>
                  <code class="command-code">
                    modal run scripts/modal_youtube_processor.py --bootstrap-job &lt;JOB_ID&gt;
                  </code>
                </div>
              </div>
            </Card>
          </div>
        {/if}

        <!-- Sub-Tab D: Jobs Monitor -->
        {#if bootstrapActiveSubTab === 'jobs'}
          <div class="filter-row">
            <Button variant="secondary" size="sm" on:click={loadBootstrapJobs}>Refresh</Button>
            <Badge variant="neutral">{bootstrapJobs.length} jobs</Badge>
          </div>

          {#if bootstrapJobs.length === 0}
            <p class="empty-message">No bootstrap jobs found</p>
          {:else}
            <div class="table-container">
              <table class="table">
                <thead>
                  <tr>
                    <th>Job ID</th>
                    <th>Type</th>
                    <th>Status</th>
                    <th>Created</th>
                    <th>Completed</th>
                  </tr>
                </thead>
                <tbody>
                  {#each bootstrapJobs as job}
                    <tr>
                      <td><span class="video-id">{job.id}</span></td>
                      <td>{job.type || 'bootstrap'}</td>
                      <td>
                        <Badge variant={job.status === 'completed' ? 'success' : job.status === 'queued' ? 'neutral' : job.status === 'processing' ? 'warning' : 'error'}>
                          {job.status}
                        </Badge>
                      </td>
                      <td>{formatDate(job.created_at)}</td>
                      <td>{formatDate(job.completed_at)}</td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
          {/if}
        {/if}
      </div>
    </Card>
  {/if}
</div>

<style>
  .admin-container {
    padding: var(--space-5);
    max-width: 1200px;
    margin: 0 auto;
  }

  .admin-header {
    margin-bottom: var(--space-6);
  }

  .admin-header h1 {
    font-size: var(--text-h2-size);
    font-weight: var(--text-h2-weight);
    margin: 0 0 var(--space-2) 0;
    color: var(--text-primary);
  }

  .admin-description {
    color: var(--text-secondary);
    margin: 0;
  }

  .alert {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-3) var(--space-4);
    border-radius: var(--radius-md);
    margin-bottom: var(--space-4);
  }

  .alert-error {
    background-color: rgba(239, 68, 68, 0.2);
    border: var(--space-px) solid var(--color-error-500);
    color: var(--color-error-300);
  }

  .alert-success {
    background-color: rgba(34, 197, 94, 0.2);
    border: var(--space-px) solid var(--color-success-500);
    color: var(--color-success-300);
  }

  .alert-icon {
    font-weight: var(--text-h6-weight);
    padding: var(--space-0-5) var(--space-2);
    border-radius: var(--radius-sm);
    background-color: rgba(255, 255, 255, 0.2);
  }

  .alert-close {
    margin-left: auto;
    background: none;
    border: none;
    color: inherit;
    cursor: pointer;
    padding: var(--space-1) var(--space-2);
  }

  .tabs {
    display: flex;
    gap: var(--space-1);
    margin-bottom: var(--space-5);
    border-bottom: var(--space-px) solid var(--border-default);
    padding-bottom: var(--space-1);
  }

  .tab {
    padding: var(--space-3) var(--space-5);
    background: none;
    border: none;
    color: var(--text-secondary);
    cursor: pointer;
    font-size: var(--text-body-sm-size);
    font-weight: var(--text-label-weight);
    border-radius: var(--radius-md) var(--radius-md) 0 0;
    transition: all var(--duration-normal);
  }

  .tab:hover {
    color: var(--text-primary);
    background-color: var(--bg-tertiary);
  }

  .tab.active {
    color: var(--text-primary);
    background-color: var(--color-primary-600);
  }

  .panel-inner h2 {
    font-size: var(--text-h4-size);
    font-weight: var(--text-h4-weight);
    margin: 0 0 var(--space-2) 0;
    color: var(--text-primary);
  }

  .panel-header-row {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: var(--space-5);
    gap: var(--space-4);
  }

  .panel-header-row .btn {
    white-space: nowrap;
  }

  .panel-inner h3 {
    font-size: var(--text-body-size);
    font-weight: var(--text-h6-weight);
    margin: var(--space-5) 0 var(--space-3) 0;
    color: var(--text-primary);
  }

  .panel-description {
    color: var(--text-secondary);
    margin: 0 0 var(--space-5) 0;
    font-size: var(--text-body-sm-size);
  }

  .form {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
    max-width: 500px;
  }

  .form-group {
    display: flex;
    flex-direction: column;
    gap: var(--space-1-5);
  }

  .form-group label {
    font-size: var(--text-body-sm-size);
    font-weight: var(--text-label-weight);
    color: var(--text-secondary);
  }

  .select {
    padding: var(--space-2-5) var(--space-3-5);
    border: var(--space-px) solid var(--border-default);
    border-radius: var(--radius-md);
    background-color: var(--bg-tertiary);
    color: var(--text-primary);
    font-size: var(--text-body-sm-size);
  }

  .select:focus {
    outline: none;
    border-color: var(--color-primary-500);
    box-shadow: var(--focus-ring);
  }

  .select-small {
    padding: var(--space-1-5) var(--space-2-5);
    font-size: var(--text-body-xs-size);
  }

  .divider {
    height: var(--space-px);
    background-color: var(--border-subtle);
    margin: var(--space-6) 0;
  }

  .filter-row {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    margin-bottom: var(--space-4);
  }

  .filter-row label {
    font-size: var(--text-body-sm-size);
    color: var(--text-secondary);
  }

  .count-badge {
    background-color: var(--bg-tertiary);
    padding: var(--space-1) var(--space-2-5);
    border-radius: var(--radius-full);
    font-size: var(--text-body-xs-size);
    color: var(--text-secondary);
  }

  .empty-message {
    color: var(--text-disabled);
    text-align: center;
    padding: var(--space-10);
    font-style: italic;
  }

  .table-container {
    overflow-x: auto;
    border-radius: var(--radius-lg);
    border: var(--space-px) solid var(--border-subtle);
  }

  .table {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--text-body-sm-size);
  }

  .table th, .table td {
    padding: var(--space-3);
    text-align: left;
    border-bottom: var(--space-px) solid var(--border-subtle);
  }

  .table th {
    font-weight: var(--text-h6-weight);
    color: var(--text-secondary);
    background-color: var(--bg-tertiary);
  }

  .table td {
    color: var(--text-primary);
  }

  .table tr:hover {
    background-color: var(--bg-elevated);
  }

  .video-info {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  .video-info a {
    color: var(--color-primary-400);
    text-decoration: none;
  }

  .video-info a:hover {
    text-decoration: underline;
  }

  .video-id {
    font-size: var(--text-body-xs-size);
    color: var(--text-tertiary);
    font-family: var(--font-mono);
  }

  .status-badge-item {
    text-transform: capitalize;
  }

  .error-text {
    color: var(--color-error-500);
    font-size: var(--text-body-xs-size);
    margin-left: var(--space-2);
  }

  .date-info {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .submitted-by {
    font-size: var(--text-body-xs-size);
    color: var(--text-tertiary);
  }

  .flags-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: var(--space-4);
  }

  .flag-card-inner {
    padding: var(--space-4);
  }

  .flag-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--space-3);
  }

  .flag-id {
    font-size: 11px;
    color: var(--text-tertiary);
    font-family: var(--font-mono);
  }

  .flag-thumbnail {
    width: 100%;
    height: 120px;
    background-color: var(--bg-primary);
    border-radius: var(--radius-md);
    margin-bottom: var(--space-3);
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    border: var(--space-px) solid var(--border-subtle);
  }

  .flag-thumbnail img {
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
    border-radius: var(--radius-sm);
  }

  .flag-thumbnail.placeholder {
    color: var(--text-disabled);
    font-size: var(--text-body-xs-size);
  }

  .flag-details {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    margin-bottom: var(--space-4);
  }

  .detail-row {
    display: flex;
    gap: var(--space-2);
  }

  .detail-row .label {
    color: var(--text-secondary);
    font-size: var(--text-body-xs-size);
    min-width: 100px;
  }

  .detail-row .value {
    color: var(--text-primary);
    font-size: var(--text-body-xs-size);
    font-weight: var(--text-label-weight);
  }

  .flag-actions {
    display: flex;
    gap: var(--space-2);
  }

  .flag-reviewed {
    font-size: var(--text-body-xs-size);
    color: var(--text-tertiary);
    font-style: italic;
  }

  .sync-stats {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: var(--space-4);
    margin-bottom: var(--space-6);
  }

  .stat-card-content {
    text-align: center;
  }

  .stat-value {
    font-size: var(--text-h2-size);
    font-weight: var(--text-h2-weight);
    color: var(--text-primary);
    margin-bottom: var(--space-1);
  }

  .stat-label {
    font-size: var(--text-body-sm-size);
    color: var(--text-secondary);
  }

  .sync-section-inner {
    padding: var(--space-5);
  }

  .sync-section-inner h3 {
    margin-top: 0;
  }

  .sync-section-inner p {
    color: var(--text-secondary);
    font-size: var(--text-body-sm-size);
    margin: 0 0 var(--space-3) 0;
  }

  .warning-text {
    background-color: rgba(245, 158, 11, 0.1);
    border: var(--space-px) solid var(--color-warning-500);
    padding: var(--space-3);
    border-radius: var(--radius-md);
    color: var(--color-warning-300);
    margin-bottom: var(--space-4);
  }

  .warning-text code {
    background-color: rgba(0, 0, 0, 0.3);
    padding: var(--space-0-5) var(--space-1-5);
    border-radius: var(--radius-sm);
    font-family: var(--font-mono);
    font-size: var(--text-body-xs-size);
  }

  .comparison-container {
    margin-top: var(--space-4);
  }

  .contestant-selector {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    margin-bottom: var(--space-5);
  }

  .contestant-selector label {
    font-size: var(--text-body-sm-size);
    color: var(--text-secondary);
  }

  .loading-comparison {
    color: var(--text-secondary);
    text-align: center;
    padding: var(--space-10);
  }

  .comparison-results-inner {
    padding: var(--space-5);
  }

  .comparison-header h4 {
    margin: 0 0 var(--space-4) 0;
    color: var(--text-primary);
    font-size: var(--text-h5-size);
  }

  .comparison-stats {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: var(--space-3);
    margin-bottom: var(--space-5);
  }

  .comp-stat {
    background-color: var(--bg-primary);
    border: var(--space-px) solid var(--border-subtle);
    border-radius: var(--radius-md);
    padding: var(--space-4);
    text-align: center;
  }

  .comp-stat-value {
    font-size: var(--text-h4-size);
    font-weight: var(--text-h4-weight);
    color: var(--text-primary);
  }

  .comp-stat-label {
    font-size: var(--text-body-xs-size);
    color: var(--text-secondary);
    margin-top: var(--space-1);
  }

  .comp-stat.approved .comp-stat-value { color: var(--color-success-500); }
  .comp-stat.pending .comp-stat-value { color: var(--color-warning-500); }
  .comp-stat.rejected .comp-stat-value { color: var(--color-error-500); }

  .confidence-section {
    margin-bottom: var(--space-5);
  }

  .confidence-section h5 {
    margin: 0 0 var(--space-2) 0;
    font-size: var(--text-body-sm-size);
    color: var(--text-primary);
  }

  .confidence-bar-container {
    background-color: var(--bg-primary);
    border-radius: var(--radius-md);
    height: 32px;
    position: relative;
    overflow: hidden;
    border: var(--space-px) solid var(--border-subtle);
  }

  .confidence-bar {
    height: 100%;
    background: linear-gradient(90deg, var(--color-success-600), var(--color-success-400));
    border-radius: var(--radius-md);
    transition: width var(--duration-normal) var(--ease-in-out);
  }

  .confidence-value {
    position: absolute;
    right: var(--space-3);
    top: 50%;
    transform: translateY(-50%);
    font-weight: var(--text-label-weight);
    color: var(--text-primary);
    font-size: var(--text-body-sm-size);
    text-shadow: 0 1px 2px rgba(0,0,0,0.5);
  }

  .flag-timeline-section {
    margin-bottom: var(--space-5);
  }

  .flag-timeline-section h5 {
    margin: 0 0 var(--space-3) 0;
    font-size: var(--text-body-sm-size);
    color: var(--text-primary);
  }

  .flag-timeline {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .timeline-item {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-2) var(--space-3);
    background-color: var(--bg-primary);
    border-radius: var(--radius-md);
    font-size: var(--text-body-xs-size);
    border: var(--space-px) solid var(--border-subtle);
  }

  .timeline-status {
    width: 8px;
    height: 8px;
    border-radius: 50%;
  }

  .timeline-video {
    color: var(--text-primary);
    flex: 1;
  }

  .timeline-time {
    color: var(--text-secondary);
  }

  .timeline-conf {
    color: var(--color-primary-400);
    font-weight: var(--text-label-weight);
  }

  .more-flags {
    color: var(--text-disabled);
    font-size: var(--text-body-xs-size);
    text-align: center;
    margin: var(--space-2) 0 0 0;
  }

  .embedding-status-section h5 {
    margin: 0 0 var(--space-3) 0;
    font-size: var(--text-body-sm-size);
    color: var(--text-primary);
  }

  .embedding-info {
    background-color: var(--bg-primary);
    border-radius: var(--radius-md);
    padding: var(--space-4);
    border: var(--space-px) solid var(--border-subtle);
  }

  .info-row {
    display: flex;
    justify-content: space-between;
    padding: var(--space-2) 0;
    border-bottom: var(--space-px) solid var(--border-subtle);
  }

  .info-row:last-child {
    border-bottom: none;
  }

  .info-label {
    color: var(--text-secondary);
    font-size: var(--text-body-xs-size);
  }

  .info-value {
    color: var(--text-primary);
    font-size: var(--text-body-xs-size);
    font-weight: var(--text-label-weight);
  }

  .info-value.active {
    color: var(--color-success-500);
  }

  @media (max-width: 768px) {
    .admin-container {
      padding: var(--space-3);
    }

    .tabs {
      flex-wrap: wrap;
    }

    .tab {
      flex: 1;
      min-width: 100px;
      text-align: center;
      padding: var(--space-2-5) var(--space-3);
      font-size: var(--text-body-xs-size);
    }

    .sync-stats {
      grid-template-columns: 1fr;
    }

    .flags-grid {
      grid-template-columns: 1fr;
    }
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
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius-sm);
    font-size: var(--text-body-xs-size);
    font-weight: var(--text-label-weight);
    color: white;
    text-transform: capitalize;
  }

  .flag-card {
    background-color: var(--bg-tertiary);
    border: var(--space-px) solid var(--border-default);
    border-radius: var(--radius-lg);
    padding: var(--space-4);
  }

  .sync-stats {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: var(--space-4);
    margin-bottom: var(--space-6);
  }

  .sync-section {
    background-color: var(--bg-tertiary);
    border: var(--space-px) solid var(--border-default);
    border-radius: var(--radius-lg);
    padding: var(--space-5);
  }

  .sync-section p {
    color: var(--text-secondary);
    font-size: var(--text-body-sm-size);
    margin: 0 0 var(--space-3) 0;
  }

  .comparison-results {
    background-color: var(--bg-tertiary);
    border: var(--space-px) solid var(--border-default);
    border-radius: var(--radius-xl);
    padding: var(--space-5);
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

  /* Video Processing Tab Styles */
  .processing-workflow {
    display: flex;
    flex-direction: column;
    gap: var(--space-5);
  }

  .step-section {
    padding: var(--space-5);
  }

  .step-header {
    display: flex;
    align-items: flex-start;
    gap: var(--space-4);
    margin-bottom: var(--space-4);
  }

  .step-number {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    background-color: var(--bg-primary);
    border: 2px solid var(--border-default);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: var(--text-h5-size);
    font-weight: var(--text-h5-weight);
    color: var(--text-secondary);
    flex-shrink: 0;
  }

  .step-number.completed {
    background-color: var(--color-success-500);
    border-color: var(--color-success-500);
    color: white;
  }

  .step-section h3 {
    font-size: var(--text-body-size);
    font-weight: var(--text-h6-weight);
    margin: 0 0 var(--space-1) 0;
    color: var(--text-primary);
  }

  .step-section p {
    font-size: var(--text-body-sm-size);
    color: var(--text-secondary);
    margin: 0;
  }

  .file-input-wrapper {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    flex-wrap: wrap;
  }

  .file-input-wrapper input[type="file"] {
    display: none;
  }

  .file-input-label {
    padding: var(--space-3) var(--space-5);
    background-color: var(--bg-tertiary);
    border: 2px solid var(--border-default);
    border-radius: var(--radius-md);
    color: var(--text-primary);
    cursor: pointer;
    font-size: var(--text-body-sm-size);
    font-weight: var(--text-label-weight);
    transition: all var(--duration-normal);
  }

  .file-input-label:hover {
    border-color: var(--color-primary-500);
    background-color: var(--bg-elevated);
  }

  .progress-section {
    margin: var(--space-4) 0;
  }

  .progress-bar-container {
    background-color: var(--bg-primary);
    border-radius: var(--radius-md);
    height: 8px;
    overflow: hidden;
    margin-bottom: var(--space-2);
  }

  .progress-bar {
    height: 100%;
    background: linear-gradient(90deg, var(--color-primary-600), var(--color-primary-400));
    border-radius: var(--radius-md);
    transition: width var(--duration-normal);
  }

  .progress-text {
    font-size: var(--text-body-sm-size);
    color: var(--text-secondary);
    margin: 0;
  }

  .success-message {
    background-color: rgba(34, 197, 94, 0.1);
    border: 1px solid var(--color-success-500);
    padding: var(--space-3);
    border-radius: var(--radius-md);
    color: var(--color-success-300);
    font-size: var(--text-body-sm-size);
  }

  .video-link {
    color: var(--color-primary-400);
    text-decoration: underline;
    margin-left: var(--space-2);
  }

  .processing-indicator {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-5) 0;
  }

  .spinner {
    width: 40px;
    height: 40px;
    border: 4px solid var(--border-default);
    border-top-color: var(--color-primary-500);
    border-radius: 50%;
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .processing-indicator p {
    color: var(--text-primary);
    font-size: var(--text-body-size);
    margin: 0;
  }

  .help-text {
    color: var(--text-secondary);
    font-size: var(--text-body-sm-size);
  }

  .modal-info {
    margin-top: var(--space-4);
    padding: var(--space-3);
    background-color: var(--bg-primary);
    border-radius: var(--radius-md);
  }

  .modal-info p {
    margin: 0 0 var(--space-2) 0;
    font-size: var(--text-body-sm-size);
    color: var(--text-secondary);
  }

  .command-code {
    display: block;
    padding: var(--space-2-5) var(--space-3);
    background-color: rgba(0, 0, 0, 0.4);
    border-radius: var(--radius-sm);
    font-family: var(--font-mono);
    font-size: var(--text-body-xs-size);
    color: var(--color-primary-300);
    overflow-x: auto;
  }

  .reset-section {
    display: flex;
    justify-content: center;
  }

  .guide-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: var(--space-4);
    margin-top: var(--space-4);
  }

  .guide-card {
    padding: var(--space-5);
    text-align: center;
  }

  .guide-icon {
    font-size: 48px;
    margin-bottom: var(--space-3);
  }

  .guide-card h4 {
    font-size: var(--text-body-size);
    font-weight: var(--text-h6-weight);
    margin: 0 0 var(--space-2) 0;
    color: var(--text-primary);
  }

  .guide-card p {
    font-size: var(--text-body-sm-size);
    color: var(--text-secondary);
    margin: 0;
    line-height: 1.5;
  }

  /* Embedding Bootstrap Sub-tabs */
  .sub-tabs {
    display: flex;
    gap: 4px;
    margin-bottom: 20px;
    background-color: var(--bg-primary);
    border-radius: var(--radius-md);
    padding: 4px;
  }

  .sub-tab {
    flex: 1;
    padding: 8px 16px;
    background: none;
    border: none;
    color: var(--text-secondary);
    cursor: pointer;
    font-size: var(--text-body-sm-size);
    font-weight: var(--text-label-weight);
    border-radius: var(--radius-sm);
    transition: all var(--duration-normal);
    text-align: center;
  }

  .sub-tab:hover {
    color: var(--text-primary);
    background-color: var(--bg-tertiary);
  }

  .sub-tab.active {
    color: var(--text-primary);
    background-color: var(--color-primary-600);
  }

  /* Contestant Status Grid */
  .contestant-status-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 12px;
    margin-top: 16px;
  }

  .contestant-status-card {
    background-color: var(--bg-tertiary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    padding: 12px;
  }

  .contestant-status-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
  }

  .contestant-number {
    font-weight: var(--text-h6-weight);
    color: var(--color-primary-400);
    font-size: var(--text-body-sm-size);
    font-family: var(--font-mono);
  }

  .contestant-name {
    color: var(--text-primary);
    font-size: var(--text-body-sm-size);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .contestant-status-badges {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }

  .input {
    padding: 10px 14px;
    border: 1px solid var(--border-default);
    border-radius: var(--radius-md);
    background-color: var(--bg-tertiary);
    color: var(--text-primary);
    font-size: var(--text-body-sm-size);
  }

  .input:focus {
    outline: none;
    border-color: var(--color-primary-500);
    box-shadow: var(--focus-ring);
  }
</style>
