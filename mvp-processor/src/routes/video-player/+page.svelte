<script lang="ts">
  import { onMount, onDestroy } from 'svelte';

  // API base URL
  const API_BASE = '';

  // State
  let videos: any[] = [];
  let contestants: any[] = [];
  let selectedVideo: any = null;
  let videoElement: HTMLVideoElement;
  let videoContainer: HTMLDivElement;

  let isPlaying = false;
  let currentTime = 0;
  let duration = 0;
  let volume = 0.8;
  let isLoading = true;
  let error: string | null = null;

  // Face detection state
  let detectedFaces: any[] = [];
  let selectedFace: any = null;
  let showFlagDialog = false;
  let flagContestantId: number | null = null;
  let flagUserLabel = '';
  let isFlagging = false;

  // Batch flagging state
  let batchMode = false;
  let selectedFaces: Set<any> = new Set();
  let showBatchFlagDialog = false;
  let batchContestantId: number | null = null;

  // Flagged faces
  let flaggedFaces: any[] = [];
  let showFlaggedPanel = false;

  // Video metadata
  let videoMetadata: any = null;

  // Polling interval for face detection
  let facePollingInterval: number | null = null;

  async function loadVideos() {
    try {
      isLoading = true;
      const response = await fetch(`${API_BASE}/api/videos/processed/list`);
      if (response.ok) {
        const data = await response.json();
        videos = Array.isArray(data) ? data : [];
        if (videos.length > 0) {
          selectVideo(videos[0]);
        }
      }
    } catch (e) {
      console.error('Failed to load videos:', e);
      error = 'Failed to load video list';
    } finally {
      isLoading = false;
    }
  }

  async function loadContestants() {
    try {
      const response = await fetch(`${API_BASE}/api/contestants`);
      if (response.ok) {
        contestants = await response.json();
      }
    } catch (e) {
      console.error('Failed to load contestants:', e);
    }
  }

  async function loadFlaggedFaces() {
    try {
      const response = await fetch(`${API_BASE}/api/faces/flagged?details=true`);
      if (response.ok) {
        const data = await response.json();
        flaggedFaces = data.flagged_faces || [];
      }
    } catch (e) {
      console.error('Failed to load flagged faces:', e);
    }
  }

  async function selectVideo(video: any) {
    selectedVideo = video;
    isPlaying = false;
    currentTime = 0;
    detectedFaces = [];
    selectedFace = null;

    // Load video metadata
    await loadVideoMetadata(video.id);
  }

  async function loadVideoMetadata(videoId: string) {
    try {
      // Extract numeric ID
      const numericId = videoId.match(/^(\d+)/)?.[1] || videoId;
      const response = await fetch(`${API_BASE}/api/videos/metadata/dense/${numericId}`);
      if (response.ok) {
        videoMetadata = await response.json();
      }
    } catch (e) {
      console.error('Failed to load video metadata:', e);
    }
  }

  async function fetchFacesAtTime(timestamp: number) {
    if (!selectedVideo) return;

    try {
      const numericId = selectedVideo.id.match(/^(\d+)/)?.[1] || selectedVideo.id;
      const response = await fetch(
        `${API_BASE}/api/faces/detect?video_id=${numericId}&timestamp=${timestamp}`
      );
      if (response.ok) {
        const data = await response.json();
        detectedFaces = data.faces || [];
      }
    } catch (e) {
      console.error('Failed to fetch faces:', e);
    }
  }

  function startFacePolling() {
    if (facePollingInterval) clearInterval(facePollingInterval);
    facePollingInterval = setInterval(() => {
      if (isPlaying && videoElement) {
        fetchFacesAtTime(videoElement.currentTime);
      }
    }, 200); // Poll every 200ms
  }

  function stopFacePolling() {
    if (facePollingInterval) {
      clearInterval(facePollingInterval);
      facePollingInterval = null;
    }
  }

  function togglePlay() {
    if (videoElement) {
      if (isPlaying) {
        videoElement.pause();
        stopFacePolling();
      } else {
        videoElement.play();
        startFacePolling();
      }
      isPlaying = !isPlaying;
    }
  }

  function handleTimeUpdate() {
    if (videoElement) {
      currentTime = videoElement.currentTime;
    }
  }

  function handleLoadedMetadata() {
    if (videoElement) {
      duration = videoElement.duration;
    }
  }

  function handleSeek(e: Event) {
    const target = e.target as HTMLInputElement;
    const time = parseFloat(target.value);
    if (videoElement) {
      videoElement.currentTime = time;
      fetchFacesAtTime(time);
    }
  }

  function formatTime(seconds: number): string {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  }

  function handleFaceClick(face: any) {
    if (batchMode) {
      // In batch mode, toggle selection
      if (selectedFaces.has(face)) {
        selectedFaces.delete(face);
      } else {
        selectedFaces.add(face);
      }
      selectedFaces = selectedFaces; // Trigger reactivity
    } else {
      // Single face flagging
      selectedFace = face;
      showFlagDialog = true;
      flagContestantId = null;
      flagUserLabel = '';
    }
  }

  function toggleBatchMode() {
    batchMode = !batchMode;
    if (!batchMode) {
      selectedFaces.clear();
      selectedFaces = selectedFaces;
    }
  }

  function selectAllFaces() {
    detectedFaces.forEach(face => selectedFaces.add(face));
    selectedFaces = selectedFaces;
  }

  function clearSelection() {
    selectedFaces.clear();
    selectedFaces = selectedFaces;
  }

  function openBatchFlagDialog() {
    if (selectedFaces.size === 0) return;
    showBatchFlagDialog = true;
    batchContestantId = null;
  }

  async function submitBatchFlag() {
    if (batchContestantId === null || batchContestantId === undefined || !selectedVideo || selectedFaces.size === 0) return;

    isFlagging = true;
    let successCount = 0;
    let failCount = 0;

    try {
      const facesArray = Array.from(selectedFaces);

      for (const face of facesArray) {
        try {
          // Extract thumbnail for each face
          const thumbnail = extractFaceThumbnail(face);

          const response = await fetch(`${API_BASE}/api/faces/flag`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              contestant_id: batchContestantId,
              video_id: selectedVideo.id,
              timestamp: currentTime,
              bbox: face.bbox,
              confidence: face.confidence,
              user_label: `Batch flagged (${facesArray.length} faces) at ${formatTime(currentTime)}`,
              thumbnail: thumbnail
            })
          });

          if (response.ok) {
            successCount++;
          } else {
            failCount++;
          }
        } catch (e) {
          failCount++;
        }
      }

      showBatchFlagDialog = false;
      selectedFaces.clear();
      selectedFaces = selectedFaces;
      batchMode = false;
      await loadFlaggedFaces();

      if (failCount === 0) {
        alert(`Successfully flagged ${successCount} faces!`);
      } else {
        alert(`Flagged ${successCount} faces. ${failCount} failed.`);
      }
    } catch (e) {
      console.error('Batch flag error:', e);
      alert('Error during batch flagging');
    } finally {
      isFlagging = false;
    }
  }

  function closeBatchFlagDialog() {
    showBatchFlagDialog = false;
    batchContestantId = null;
  }

  async function submitFlag() {
    // Use explicit null check instead of falsy check to allow contestant ID 0
    if (!selectedFace || flagContestantId === null || flagContestantId === undefined || !selectedVideo) return;

    isFlagging = true;
    try {
      // Extract thumbnail before submitting
      const thumbnail = extractFaceThumbnail(selectedFace);

      const response = await fetch(`${API_BASE}/api/faces/flag`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contestant_id: flagContestantId,
          video_id: selectedVideo.id,
          timestamp: currentTime,
          bbox: selectedFace.bbox,
          confidence: selectedFace.confidence,
          user_label: flagUserLabel || `Flagged by user at ${formatTime(currentTime)}`,
          thumbnail: thumbnail // Include extracted face thumbnail
        })
      });

      if (response.ok) {
        const result = await response.json();
        showFlagDialog = false;
        selectedFace = null;
        await loadFlaggedFaces();
        alert('Face flagged successfully!');
      } else {
        alert('Failed to flag face');
      }
    } catch (e) {
      console.error('Failed to flag face:', e);
      alert('Error flagging face');
    } finally {
      isFlagging = false;
    }
  }

  function closeFlagDialog() {
    showFlagDialog = false;
    selectedFace = null;
  }

  function getContestantName(id: number): string {
    const contestant = contestants.find(c => c.number === id || c.id === String(id));
    return contestant ? `${contestant.nickname} (${contestant.name})` : `Contestant #${id}`;
  }

  // Extract face thumbnail from video using canvas
  function extractFaceThumbnail(face: any): string | null {
    if (!videoElement || !face.bbox || face.bbox.length < 4) return null;

    try {
      const [x, y, w, h] = face.bbox;

      // Add padding around the face (20% on each side)
      const padding = 0.2;
      const padX = w * padding;
      const padY = h * padding;

      const cropX = Math.max(0, x - padX);
      const cropY = Math.max(0, y - padY);
      const cropW = Math.min(videoElement.videoWidth - cropX, w + 2 * padX);
      const cropH = Math.min(videoElement.videoHeight - cropY, h + 2 * padY);

      // Create canvas for cropping
      const canvas = document.createElement('canvas');
      const targetSize = 150; // Output thumbnail size
      const aspectRatio = cropW / cropH;

      if (aspectRatio > 1) {
        canvas.width = targetSize;
        canvas.height = Math.round(targetSize / aspectRatio);
      } else {
        canvas.height = targetSize;
        canvas.width = Math.round(targetSize * aspectRatio);
      }

      const ctx = canvas.getContext('2d');
      if (!ctx) return null;

      // Draw the cropped face region
      ctx.drawImage(
        videoElement,
        cropX, cropY, cropW, cropH,
        0, 0, canvas.width, canvas.height
      );

      // Return as base64 JPEG
      return canvas.toDataURL('image/jpeg', 0.8);
    } catch (e) {
      console.error('Failed to extract thumbnail:', e);
      return null;
    }
  }

  // Calculate bounding box position relative to video
  function getBboxStyle(bbox: number[]): string {
    if (!bbox || bbox.length < 4 || !videoElement) return '';

    const [x, y, w, h] = bbox;
    const videoRect = videoElement.getBoundingClientRect();
    const scaleX = videoRect.width / (videoElement.videoWidth || 1920);
    const scaleY = videoRect.height / (videoElement.videoHeight || 1080);

    return `
      left: ${x * scaleX}px;
      top: ${y * scaleY}px;
      width: ${w * scaleX}px;
      height: ${h * scaleY}px;
    `;
  }

  onMount(() => {
    loadVideos();
    loadContestants();
    loadFlaggedFaces();
  });

  onDestroy(() => {
    stopFacePolling();
  });
</script>

<svelte:head>
  <title>Video Player - Face Recognition Dashboard</title>
</svelte:head>

<div class="video-player-container">
  <div class="player-header">
    <h1>🎬 Annotated Video Player</h1>
    <div class="header-actions">
      <button class="btn-secondary" on:click={() => showFlaggedPanel = !showFlaggedPanel}>
        📌 Flagged Faces ({flaggedFaces.length})
      </button>
      <div class="video-selector">
        <label for="video-select">Select Video:</label>
        <select id="video-select" bind:value={selectedVideo} on:change={() => selectedVideo && selectVideo(selectedVideo)}>
          {#each videos as video}
            <option value={video}>{video.name}</option>
          {/each}
        </select>
      </div>
    </div>
  </div>

  {#if isLoading}
    <div class="loading-state">
      <div class="spinner"></div>
      <p>Loading videos...</p>
    </div>
  {:else if error}
    <div class="error-state">
      <p>❌ {error}</p>
      <button on:click={loadVideos}>Retry</button>
    </div>
  {:else}
    <div class="player-main">
      <!-- Video Display Area -->
      <div class="video-display">
        <div class="video-frame" bind:this={videoContainer}>
          {#if selectedVideo}
            <video
              bind:this={videoElement}
              src="{API_BASE}{selectedVideo.stream_url}"
              on:timeupdate={handleTimeUpdate}
              on:loadedmetadata={handleLoadedMetadata}
              on:play={() => { isPlaying = true; startFacePolling(); }}
              on:pause={() => { isPlaying = false; stopFacePolling(); }}
              on:ended={() => { isPlaying = false; stopFacePolling(); }}
              crossorigin="anonymous"
            >
              <track kind="captions" />
            </video>

            <!-- Face Overlay Layer -->
            <div class="face-overlay">
              {#each detectedFaces as face, i}
                <button
                  class="face-bbox"
                  class:selected={selectedFace === face}
                  class:batch-selected={batchMode && selectedFaces.has(face)}
                  style={getBboxStyle(face.bbox)}
                  on:click={() => handleFaceClick(face)}
                  title={batchMode ? 'Click to select/deselect' : 'Click to flag this face'}
                >
                  <span class="face-label">
                    {#if batchMode && selectedFaces.has(face)}
                      <span class="check-mark">✓</span>
                    {/if}
                    {face.contestant_name || 'Unknown'}
                    <br />
                    {((face.confidence ?? 0) * 100).toFixed(1)}%
                  </span>
                </button>
              {/each}
            </div>
          {:else}
            <div class="video-placeholder">
              <p>Select a video to play</p>
            </div>
          {/if}
        </div>

        <!-- Video Controls -->
        <div class="video-controls">
          <button class="play-button" on:click={togglePlay} disabled={!selectedVideo}>
            {isPlaying ? '⏸️' : '▶️'}
          </button>

          <div class="time-display">
            {formatTime(currentTime)} / {formatTime(duration)}
          </div>

          <div class="progress-container">
            <input
              type="range"
              class="progress-bar"
              min="0"
              max={duration}
              step="0.1"
              value={currentTime}
              on:input={handleSeek}
              disabled={!selectedVideo}
            />
          </div>

          <div class="volume-container">
            <span>🔊</span>
            <input
              type="range"
              class="volume-slider"
              min="0"
              max="1"
              step="0.1"
              bind:value={volume}
              on:input={() => { if (videoElement) videoElement.volume = volume; }}
            />
          </div>
        </div>

        <!-- Detection Info Bar -->
        <div class="detection-bar">
          <span>👥 Detected Faces: {detectedFaces.length}</span>
          <span>📍 Current Frame: {Math.floor(currentTime * (videoMetadata?.video_info?.fps || 25))}</span>
          {#if detectedFaces.length > 0}
            {#if batchMode}
              <span class="batch-info">✅ Selected: {selectedFaces.size}</span>
            {:else}
              <span class="hint">Click on a face to flag it</span>
            {/if}
          {/if}
        </div>

        <!-- Batch Mode Controls -->
        <div class="batch-controls">
          <button
            class="btn-batch"
            class:active={batchMode}
            on:click={toggleBatchMode}
          >
            {batchMode ? '✓ Batch Mode ON' : '☐ Batch Mode'}
          </button>

          {#if batchMode}
            <button class="btn-secondary-small" on:click={selectAllFaces} disabled={detectedFaces.length === 0}>
              Select All
            </button>
            <button class="btn-secondary-small" on:click={clearSelection} disabled={selectedFaces.size === 0}>
              Clear
            </button>
            <button
              class="btn-primary-small"
              on:click={openBatchFlagDialog}
              disabled={selectedFaces.size === 0}
            >
              Flag Selected ({selectedFaces.size})
            </button>
          {/if}
        </div>
      </div>

      <!-- Info Panel -->
      <div class="info-panel">
        <h3>Video Information</h3>

        {#if selectedVideo}
          <div class="info-section">
            <h4>Details</h4>
            <div class="info-item">
              <span class="label">Title:</span>
              <span class="value">{selectedVideo.name}</span>
            </div>
            <div class="info-item">
              <span class="label">Resolution:</span>
              <span class="value">{videoMetadata?.video_info?.width || 1920}x{videoMetadata?.video_info?.height || 1080}</span>
            </div>
            <div class="info-item">
              <span class="label">Frame Rate:</span>
              <span class="value">{videoMetadata?.video_info?.fps || 25} FPS</span>
            </div>
          </div>

          <div class="info-section">
            <h4>Recognition Summary</h4>
            <div class="stat-item">
              <span class="stat-label">Unique Contestants:</span>
              <span class="stat-value">{videoMetadata?.recognition_summary?.unique_contestants || 0}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">Total Faces Detected:</span>
              <span class="stat-value">{videoMetadata?.recognition_summary?.total_faces_detected || 0}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">Faces Recognized:</span>
              <span class="stat-value">{videoMetadata?.recognition_summary?.total_faces_recognized || 0}</span>
            </div>
          </div>
        {/if}

        <div class="info-section">
          <h4>Current Frame Faces</h4>
          {#if detectedFaces.length === 0}
            <p class="no-faces">No faces detected at this timestamp</p>
          {:else}
            <div class="face-list">
              {#each detectedFaces as face}
                <button class="face-item" on:click={() => handleFaceClick(face)}>
                  <span class="face-name">{face.contestant_name || 'Unknown'}</span>
                  <span class="face-confidence">{((face.confidence ?? 0) * 100).toFixed(1)}%</span>
                </button>
              {/each}
            </div>
          {/if}
        </div>
      </div>
    </div>
  {/if}

  <!-- Flag Dialog -->
  {#if showFlagDialog && selectedFace}
    <div class="dialog-overlay" on:click={closeFlagDialog} role="button" tabindex="-1" on:keypress={closeFlagDialog}>
      <div class="dialog" on:click|stopPropagation role="dialog" aria-modal="true">
        <h3>🏷️ Flag Face</h3>
        <p>Assign this detected face to a contestant to improve recognition accuracy.</p>

        <div class="dialog-content">
          <div class="field">
            <label>Detected As:</label>
            <p class="detected-info">
              {selectedFace.contestant_name || 'Unknown'}
              ({((selectedFace.confidence ?? 0) * 100).toFixed(1)}% confidence)
            </p>
          </div>

          <div class="field">
            <label for="contestant-select">Correct Contestant:</label>
            <select id="contestant-select" bind:value={flagContestantId}>
              <option value={null}>-- Select Contestant --</option>
              {#each contestants as contestant}
                <option value={contestant.number}>
                  #{contestant.number} - {contestant.nickname} ({contestant.name})
                </option>
              {/each}
            </select>
          </div>

          <div class="field">
            <label for="user-label">Note (optional):</label>
            <input
              id="user-label"
              type="text"
              bind:value={flagUserLabel}
              placeholder="e.g., Clear frontal view"
            />
          </div>
        </div>

        <div class="dialog-actions">
          <button class="btn-secondary" on:click={closeFlagDialog}>Cancel</button>
          <button
            class="btn-primary"
            on:click={submitFlag}
            disabled={!flagContestantId || isFlagging}
          >
            {isFlagging ? 'Flagging...' : 'Flag Face'}
          </button>
        </div>
      </div>
    </div>
  {/if}

  <!-- Batch Flag Dialog -->
  {#if showBatchFlagDialog}
    <div class="dialog-overlay" on:click={closeBatchFlagDialog} role="button" tabindex="-1" on:keypress={closeBatchFlagDialog}>
      <div class="dialog" on:click|stopPropagation role="dialog" aria-modal="true">
        <h3>🏷️ Batch Flag Faces ({selectedFaces.size})</h3>
        <p>Assign all selected faces to a single contestant.</p>

        <div class="dialog-content">
          <div class="field">
            <label>Selected Faces:</label>
            <div class="batch-faces-preview">
              {#each Array.from(selectedFaces) as face, i}
                <span class="batch-face-chip">
                  {face.contestant_name || 'Unknown'} ({((face.confidence ?? 0) * 100).toFixed(0)}%)
                </span>
              {/each}
            </div>
          </div>

          <div class="field">
            <label for="batch-contestant-select">Assign All to Contestant:</label>
            <select id="batch-contestant-select" bind:value={batchContestantId}>
              <option value={null}>-- Select Contestant --</option>
              {#each contestants as contestant}
                <option value={contestant.number}>
                  #{contestant.number} - {contestant.nickname} ({contestant.name})
                </option>
              {/each}
            </select>
          </div>
        </div>

        <div class="dialog-actions">
          <button class="btn-secondary" on:click={closeBatchFlagDialog}>Cancel</button>
          <button
            class="btn-primary"
            on:click={submitBatchFlag}
            disabled={batchContestantId === null || batchContestantId === undefined || isFlagging}
          >
            {isFlagging ? 'Flagging...' : `Flag ${selectedFaces.size} Faces`}
          </button>
        </div>
      </div>
    </div>
  {/if}

  <!-- Flagged Faces Panel -->
  {#if showFlaggedPanel}
    <div class="flagged-panel">
      <div class="panel-header">
        <h3>📌 Flagged Faces</h3>
        <button class="close-btn" on:click={() => showFlaggedPanel = false}>✕</button>
      </div>
      <div class="panel-content">
        {#if flaggedFaces.length === 0}
          <p class="empty-state">No faces have been flagged yet.</p>
        {:else}
          <div class="flagged-list">
            {#each flaggedFaces as flag}
              <div class="flagged-item">
                <div class="flagged-info">
                  <span class="flagged-contestant">{getContestantName(flag.contestant_id)}</span>
                  <span class="flagged-video">Video: {flag.video_id}</span>
                  <span class="flagged-time">@ {formatTime(flag.timestamp)}</span>
                </div>
                <span class="flagged-status" class:pending={flag.status === 'pending'}>
                  {flag.status}
                </span>
              </div>
            {/each}
          </div>
        {/if}
      </div>
    </div>
  {/if}
</div>

<style>
  .video-player-container {
    height: 100%;
    display: flex;
    flex-direction: column;
    padding: 20px;
    background-color: #1a1a1a;
    color: #ffffff;
    position: relative;
  }

  .player-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
    padding-bottom: 15px;
    border-bottom: 1px solid #444;
  }

  .player-header h1 {
    font-size: 24px;
    font-weight: 600;
    margin: 0;
  }

  .header-actions {
    display: flex;
    align-items: center;
    gap: 15px;
  }

  .btn-secondary {
    background-color: #374151;
    color: #fff;
    border: 1px solid #4b5563;
    padding: 8px 16px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 14px;
  }

  .btn-secondary:hover {
    background-color: #4b5563;
  }

  .btn-primary {
    background-color: #3b82f6;
    color: #fff;
    border: none;
    padding: 8px 16px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 14px;
  }

  .btn-primary:hover {
    background-color: #2563eb;
  }

  .btn-primary:disabled {
    background-color: #6b7280;
    cursor: not-allowed;
  }

  .video-selector {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .video-selector label {
    font-weight: 500;
    color: #9ca3af;
  }

  .video-selector select {
    background-color: #374151;
    color: #ffffff;
    border: 1px solid #4b5563;
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 14px;
    max-width: 300px;
  }

  .loading-state, .error-state {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
  }

  .spinner {
    width: 40px;
    height: 40px;
    border: 3px solid #444;
    border-top-color: #3b82f6;
    border-radius: 50%;
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .player-main {
    flex: 1;
    display: flex;
    gap: 20px;
    min-height: 0;
  }

  .video-display {
    flex: 2;
    display: flex;
    flex-direction: column;
  }

  .video-frame {
    flex: 1;
    background-color: #000000;
    border-radius: 8px;
    overflow: hidden;
    position: relative;
    min-height: 400px;
  }

  .video-frame video {
    width: 100%;
    height: 100%;
    object-fit: contain;
  }

  .face-overlay {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
  }

  .face-bbox {
    position: absolute;
    border: 2px solid #22c55e;
    background: rgba(34, 197, 94, 0.1);
    border-radius: 4px;
    pointer-events: auto;
    cursor: pointer;
    padding: 0;
    transition: all 0.2s;
  }

  .face-bbox:hover {
    border-color: #3b82f6;
    background: rgba(59, 130, 246, 0.2);
  }

  .face-bbox.selected {
    border-color: #f59e0b;
    background: rgba(245, 158, 11, 0.2);
  }

  .face-label {
    position: absolute;
    bottom: -40px;
    left: 50%;
    transform: translateX(-50%);
    background: rgba(0, 0, 0, 0.8);
    color: #fff;
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 11px;
    white-space: nowrap;
    text-align: center;
  }

  .video-placeholder {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(45deg, #111, #222);
    color: #9ca3af;
  }

  .video-controls {
    background-color: #2a2a2a;
    padding: 15px;
    display: flex;
    align-items: center;
    gap: 15px;
    border-radius: 0 0 8px 8px;
  }

  .play-button {
    background: none;
    border: none;
    font-size: 20px;
    cursor: pointer;
    padding: 8px;
    border-radius: 4px;
    transition: background-color 0.2s;
  }

  .play-button:hover:not(:disabled) {
    background-color: #4b5563;
  }

  .play-button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .time-display {
    font-size: 14px;
    color: #9ca3af;
    min-width: 100px;
  }

  .progress-container {
    flex: 1;
  }

  .progress-bar {
    width: 100%;
    height: 6px;
    background: #4b5563;
    border-radius: 3px;
    outline: none;
    cursor: pointer;
    -webkit-appearance: none;
  }

  .progress-bar::-webkit-slider-thumb {
    -webkit-appearance: none;
    width: 16px;
    height: 16px;
    background: #3b82f6;
    border-radius: 50%;
    cursor: pointer;
  }

  .volume-container {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .volume-slider {
    width: 80px;
    height: 4px;
    background: #4b5563;
    border-radius: 2px;
    outline: none;
    -webkit-appearance: none;
  }

  .volume-slider::-webkit-slider-thumb {
    -webkit-appearance: none;
    width: 12px;
    height: 12px;
    background: #3b82f6;
    border-radius: 50%;
    cursor: pointer;
  }

  .detection-bar {
    background-color: #1e293b;
    padding: 10px 15px;
    display: flex;
    gap: 20px;
    font-size: 13px;
    color: #9ca3af;
    border-radius: 8px;
    margin-top: 10px;
  }

  .detection-bar .hint {
    color: #3b82f6;
    margin-left: auto;
  }

  .info-panel {
    flex: 1;
    background-color: #1e293b;
    border-radius: 8px;
    padding: 20px;
    overflow-y: auto;
    max-width: 350px;
  }

  .info-panel h3 {
    font-size: 18px;
    font-weight: 600;
    margin-bottom: 20px;
    color: #ffffff;
  }

  .info-section {
    margin-bottom: 25px;
  }

  .info-section h4 {
    font-size: 14px;
    font-weight: 600;
    margin-bottom: 12px;
    color: #e2e8f0;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .info-item {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    padding: 8px 0;
    border-bottom: 1px solid #334155;
  }

  .info-item:last-child {
    border-bottom: none;
  }

  .label {
    color: #9ca3af;
    font-weight: 500;
    font-size: 13px;
  }

  .value {
    color: #ffffff;
    font-weight: 600;
    font-size: 13px;
    text-align: right;
    max-width: 180px;
    word-wrap: break-word;
  }

  .stat-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 6px 0;
  }

  .stat-label {
    color: #9ca3af;
    font-size: 13px;
  }

  .stat-value {
    color: #3b82f6;
    font-weight: 600;
    font-size: 16px;
  }

  .no-faces {
    color: #6b7280;
    font-size: 13px;
    font-style: italic;
  }

  .face-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .face-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 12px;
    background-color: #374151;
    border: 1px solid #4b5563;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.2s;
  }

  .face-item:hover {
    background-color: #4b5563;
    border-color: #3b82f6;
  }

  .face-name {
    font-weight: 500;
    font-size: 13px;
  }

  .face-confidence {
    color: #22c55e;
    font-size: 12px;
    font-weight: 600;
  }

  /* Dialog Styles */
  .dialog-overlay {
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

  .dialog {
    background: #1e293b;
    border-radius: 12px;
    padding: 24px;
    max-width: 450px;
    width: 90%;
    box-shadow: 0 20px 40px rgba(0, 0, 0, 0.5);
  }

  .dialog h3 {
    margin: 0 0 10px;
    font-size: 20px;
  }

  .dialog p {
    color: #9ca3af;
    font-size: 14px;
    margin-bottom: 20px;
  }

  .dialog-content {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .field label {
    font-size: 13px;
    font-weight: 500;
    color: #e2e8f0;
  }

  .field select, .field input {
    background-color: #374151;
    border: 1px solid #4b5563;
    border-radius: 6px;
    padding: 10px 12px;
    color: #fff;
    font-size: 14px;
  }

  .detected-info {
    color: #9ca3af;
    font-size: 14px;
    margin: 0;
  }

  .dialog-actions {
    display: flex;
    justify-content: flex-end;
    gap: 12px;
    margin-top: 24px;
  }

  /* Flagged Panel */
  .flagged-panel {
    position: absolute;
    top: 80px;
    right: 20px;
    width: 350px;
    max-height: 60vh;
    background: #1e293b;
    border-radius: 12px;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
    z-index: 100;
    overflow: hidden;
  }

  .panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 20px;
    border-bottom: 1px solid #334155;
  }

  .panel-header h3 {
    margin: 0;
    font-size: 16px;
  }

  .close-btn {
    background: none;
    border: none;
    color: #9ca3af;
    font-size: 18px;
    cursor: pointer;
    padding: 4px;
  }

  .close-btn:hover {
    color: #fff;
  }

  .panel-content {
    padding: 16px 20px;
    max-height: 50vh;
    overflow-y: auto;
  }

  .empty-state {
    color: #6b7280;
    font-size: 14px;
    text-align: center;
    padding: 20px;
  }

  .flagged-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .flagged-item {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    padding: 12px;
    background: #374151;
    border-radius: 8px;
  }

  .flagged-info {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .flagged-contestant {
    font-weight: 600;
    font-size: 14px;
  }

  .flagged-video, .flagged-time {
    font-size: 12px;
    color: #9ca3af;
  }

  .flagged-status {
    font-size: 11px;
    padding: 4px 8px;
    border-radius: 12px;
    background: #22c55e;
    color: #fff;
    text-transform: uppercase;
  }

  .flagged-status.pending {
    background: #f59e0b;
  }

  /* Batch Mode Styles */
  .batch-controls {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 15px;
    background: #1f2937;
    border-radius: 8px;
    margin-top: 10px;
  }

  .btn-batch {
    padding: 8px 16px;
    border: 2px solid #4b5563;
    border-radius: 8px;
    background: transparent;
    color: #d1d5db;
    cursor: pointer;
    font-size: 13px;
    font-weight: 500;
    transition: all 0.2s;
  }

  .btn-batch:hover {
    border-color: #60a5fa;
    color: #60a5fa;
  }

  .btn-batch.active {
    border-color: #22c55e;
    background: rgba(34, 197, 94, 0.2);
    color: #22c55e;
  }

  .btn-secondary-small,
  .btn-primary-small {
    padding: 6px 12px;
    border: none;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
  }

  .btn-secondary-small {
    background: #4b5563;
    color: #fff;
  }

  .btn-secondary-small:hover:not(:disabled) {
    background: #6b7280;
  }

  .btn-primary-small {
    background: #2563eb;
    color: #fff;
  }

  .btn-primary-small:hover:not(:disabled) {
    background: #1d4ed8;
  }

  .btn-secondary-small:disabled,
  .btn-primary-small:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .batch-info {
    color: #22c55e;
    font-weight: 500;
  }

  .face-bbox.batch-selected {
    border-color: #22c55e;
    border-width: 3px;
    background: rgba(34, 197, 94, 0.3);
  }

  .check-mark {
    display: inline-block;
    background: #22c55e;
    color: #fff;
    border-radius: 50%;
    width: 16px;
    height: 16px;
    line-height: 16px;
    text-align: center;
    font-size: 10px;
    margin-right: 4px;
  }

  .batch-faces-preview {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    max-height: 150px;
    overflow-y: auto;
    padding: 10px;
    background: #1f2937;
    border-radius: 8px;
  }

  .batch-face-chip {
    display: inline-block;
    padding: 4px 10px;
    background: #374151;
    border-radius: 16px;
    font-size: 12px;
    color: #d1d5db;
  }

  /* Mobile Responsive */
  @media (max-width: 768px) {
    .player-header {
      flex-direction: column;
      align-items: flex-start;
      gap: 15px;
    }

    .header-actions {
      flex-direction: column;
      align-items: flex-start;
      width: 100%;
    }

    .player-main {
      flex-direction: column;
    }

    .info-panel {
      max-width: none;
    }

    .video-controls {
      flex-wrap: wrap;
      gap: 10px;
    }

    .progress-container {
      order: -1;
      width: 100%;
    }

    .flagged-panel {
      left: 20px;
      width: calc(100% - 40px);
    }
  }
</style>
