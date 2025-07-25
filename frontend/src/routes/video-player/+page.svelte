<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import FaceGallery from './components/FaceGallery.svelte';
  import { 
    videoElement,
    currentTime,
    duration, 
    playing,
    loading,
    error,
    videos,
    selectedVideo,
    selectedQuality,
    videoMetadata,
    isLoadingMetadata,
    contestants,
    currentFaces,
    uniqueFaces,
    showFaceGallery,
    galleryPosition,
    videoPlayerActions,
    formattedCurrentTime,
    formattedDuration,
    videoProgress
  } from '$lib/stores/videoPlayer';
  
  let videoEl: HTMLVideoElement;
  let updateTimeout: NodeJS.Timeout;
  let retryCount = 0;
  const MAX_RETRIES = 3;
  
  onMount(() => {
    videoPlayerActions.initialize();
    loadVideos().then(() => {
      loading.set(false);
    });
    videoPlayerActions.loadContestants();
    
    // Set up video element in store when component mounts
    if (videoEl) {
      videoElement.set(videoEl);
    }
  });
  
  // Update store when video element is bound
  $: if (videoEl) {
    videoElement.set(videoEl);
  }

  onDestroy(() => {
    // Clean up timers and resources
    clearTimeout(updateTimeout);
    videoPlayerActions.reset();
  });
  
  async function loadVideos() {
    try {
      const response = await fetch('/api/videos');
      if (response.ok) {
        const data = await response.json();
        videos.set(data.videos || []);
        if ($videos.length > 0) {
          await selectVideo($videos[0]);
        }
      }
    } catch (err) {
      console.error('Failed to load videos:', err);
      error.set('Failed to load videos');
    }
  }
  
  async function selectVideo(video: any) {
    try {
      loading.set(true);
      selectedVideo.set(video);
      error.set('');
      retryCount = 0;
      
      if (videoEl) {
        videoEl.currentTime = 0;
        videoPlayerActions.updateTime(0);
      }
      
      // Load video metadata for face recognition
      await videoPlayerActions.loadVideoMetadata(video.id);
    } catch (err) {
      console.error('Failed to select video:', err);
      error.set(`Failed to load video: ${err.message}`);
    } finally {
      loading.set(false);
    }
  }
  
  async function retryVideoLoad() {
    if (retryCount < MAX_RETRIES && $selectedVideo) {
      retryCount++;
      await selectVideo($selectedVideo);
    }
  }
  
  function updateVideoSource() {
    if (videoEl && $selectedVideo) {
      const wasPlaying = !videoEl.paused;
      const currentTimeStamp = videoEl.currentTime;
      
      // Update source and preserve playback state
      videoEl.src = `/api/videos/${$selectedVideo.id}/stream/${$selectedQuality}`;
      videoEl.currentTime = currentTimeStamp;
      
      if (wasPlaying) {
        videoEl.play();
      }
    }
  }
  
  function handleTimeUpdate() {
    if (videoEl) {
      const time = videoEl.currentTime;
      const dur = videoEl.duration || 0;
      
      // Update stores with throttling
      videoPlayerActions.updateTime(time);  
      duration.set(dur);
      
      // Throttled face detection update
      throttledFaceUpdate();
    }
  }
  
  function throttledFaceUpdate() {
    clearTimeout(updateTimeout);
    updateTimeout = setTimeout(() => {
      videoPlayerActions.syncFacesWithVideo();
    }, 100); // 100ms throttle to prevent excessive updates
  }
  
  // This function is now handled by the store actions
  // keeping it for backwards compatibility but delegating to store
  function updateCurrentFaces() {
    videoPlayerActions.syncFacesWithVideo();
  }
  
  function handlePlay() {
    playing.set(true);
  }
  
  function handlePause() {
    playing.set(false);
  }
  
  function togglePlayPause() {
    videoPlayerActions.togglePlayPause();
  }
  
  function formatTime(seconds: number): string {
    const minutes = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
  }
  
  function handleSeek(event: any) {
    const rect = event.currentTarget.getBoundingClientRect();
    const position = (event.clientX - rect.left) / rect.width;
    if (videoEl && $duration) {
      const seekTime = position * $duration;
      videoPlayerActions.seek(seekTime);
    }
  }
  
  function handleFaceClick(contestant: any, timestamp: number) {
    // Jump to the timestamp when face was detected
    videoPlayerActions.jumpToFace(timestamp);
  }
  
  function toggleFaceGallery() {
    videoPlayerActions.toggleFaceGallery();
  }
  
  function switchGalleryPosition() {
    videoPlayerActions.switchGalleryPosition();
  }
</script>

<svelte:head>
  <title>Video Player - MV Face Recognition</title>
</svelte:head>

<main class="video-player-container">
  <div class="header">
    <h1>視頻播放器與人臉識別</h1>
    <div class="header-controls">
      <div class="layout-controls">
        <button 
          class="control-button" 
          class:active={$showFaceGallery}
          on:click={toggleFaceGallery}
          title="切換人臉圖庫"
          aria-label="Toggle face gallery"
        >
          <svg class="control-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
            <circle cx="9" cy="7" r="4"/>
            <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
            <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
          </svg>
          <span class="control-label">人臉識別</span>
        </button>
        {#if $showFaceGallery}
          <button 
            class="control-button control-button-secondary" 
            on:click={switchGalleryPosition}
            title="切換圖庫位置"
            aria-label="Switch gallery position"
          >
            <svg class="control-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              {#if $galleryPosition === 'right'}
                <path d="M7 13l3 3 7-7"/>
                <path d="M21 12c0 4.97-4.03 9-9 9s-9-4.03-9-9 4.03-9 9-9"/>
              {:else}
                <path d="M9 18l6-6-6-6"/>
              {/if}
            </svg>
            <span class="control-label">{$galleryPosition === 'right' ? '底部' : '右側'}</span>
          </button>
        {/if}
      </div>
      <div class="status">
        <span class="live-indicator">●</span>
        <span>線上</span>
        {#if isLoadingMetadata}
          <span class="metadata-loading">載入中...</span>
        {/if}
      </div>
    </div>
  </div>

  {#if $loading}
    <div class="loading">
      <div class="spinner"></div>
      <p>載入影片中...</p>
    </div>
  {:else if $error}
    <div class="error" role="alert" aria-live="polite">
      <div class="error-content">
        <svg class="error-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"/>
          <line x1="15" y1="9" x2="9" y2="15"/>
          <line x1="9" y1="9" x2="15" y2="15"/>
        </svg>
        <div class="error-details">
          <h3>發生錯誤</h3>
          <p>{$error}</p>
          {#if retryCount < MAX_RETRIES}
            <button 
              on:click={retryVideoLoad} 
              class="retry-button"
              aria-label="重新載入視頻"
            >
              重試 ({MAX_RETRIES - retryCount} 次剩餘)
            </button>
          {/if}
        </div>
      </div>
    </div>
  {:else}
    <div class="main-content" class:split-layout={$showFaceGallery} class:bottom-layout={$galleryPosition === 'bottom'}>
      <div class="video-section">
        <div class="video-controls-bar">
          <div class="video-selector">
            <label for="video-select">選擇影片:</label>
            <select id="video-select" bind:value={$selectedVideo} on:change={() => $selectedVideo && selectVideo($selectedVideo)}>
              {#each $videos as video}
                <option value={video}>{video.name}</option>
              {/each}
            </select>
          </div>

          <div class="quality-selector">
            <label for="quality-select">品質:</label>
            <select id="quality-select" bind:value={$selectedQuality} on:change={() => updateVideoSource()}>
              <option value="720p">720p (推薦)</option>
              <option value="1080p">1080p (高品質)</option>
            </select>
          </div>
        </div>

        {#if $selectedVideo}
          <div class="video-container">
            <video
              bind:this={videoEl}
              src="/api/videos/{$selectedVideo.id}/stream/{$selectedQuality}"
              controls
              preload="metadata"
              on:timeupdate={handleTimeUpdate}
              on:play={handlePlay}
              on:pause={handlePause}
              on:loadedmetadata={handleTimeUpdate}
              on:error={() => error.set('Video failed to load')}
              on:loadstart={() => loading.set(true)}
              on:canplay={() => loading.set(false)}
              class="video-element"
              aria-label="Video player for face recognition analysis"
              aria-describedby="video-description"
            >
              <track kind="captions" />
              您的瀏覽器不支援視頻標籤。
            </video>
            
            <!-- Hidden description for screen readers -->
            <div id="video-description" class="sr-only">
              視頻播放器顯示參賽者並進行即時人臉識別分析
            </div>

            <div class="video-info">
              <div class="video-title-section">
                <h2>{$selectedVideo.name}</h2>
                {#if $isLoadingMetadata}
                  <div class="loading-badge">
                    <div class="loading-spinner"></div>
                    <span>處理中...</span>
                  </div>
                {:else if $currentFaces.length > 0}
                  <div class="faces-badge">
                    <svg class="faces-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                      <circle cx="12" cy="7" r="4"/>
                    </svg>
                    <span>{$currentFaces.length} 個參賽者</span>
                  </div>
                {/if}
              </div>
              <div class="time-info">
                <span class="timestamp">{$formattedCurrentTime} / {$formattedDuration}</span>
                {#if $videoProgress > 0}
                  <div class="progress-indicator" style="width: {$videoProgress}%"></div>
                {/if}
              </div>
            </div>

            <div class="controls">
              <button on:click={togglePlayPause} class="play-button">
                {$playing ? '⏸️' : '▶️'}
              </button>
              
              <div 
                class="progress-container" 
                role="slider"
                tabindex="0"
                aria-label="視頻進度條"
                aria-valuemin="0"
                aria-valuemax={$duration || 0}
                aria-valuenow={$currentTime || 0}
                aria-valuetext="{$formattedCurrentTime} / {$formattedDuration}"
                on:click={handleSeek}
                on:keydown={(e) => {
                  if (e.key === 'ArrowLeft') {
                    e.preventDefault();
                    videoPlayerActions.seek(Math.max(0, $currentTime - 10));
                  } else if (e.key === 'ArrowRight') {
                    e.preventDefault();
                    videoPlayerActions.seek(Math.min($duration, $currentTime + 10));
                  } else if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    togglePlayPause();
                  }
                }}
              >
                <div class="progress-bar">
                  <div 
                    class="progress-fill" 
                    style="width: {$duration ? ($currentTime / $duration) * 100 : 0}%"
                  ></div>
                </div>
              </div>
              
              <div class="time-display">
                {$formattedCurrentTime} / {$formattedDuration}
              </div>
            </div>
          </div>
        {:else}
          <div class="no-video">
            <p>沒有可用的影片</p>
          </div>
        {/if}
      </div>

      {#if $showFaceGallery}
        <div class="face-gallery-container" role="complementary" aria-label="Face recognition gallery">
          <FaceGallery 
            currentFaces={$currentFaces}
            onFaceClick={handleFaceClick}
          />
        </div>
      {/if}
    </div>
  {/if}
</main>

<style>
  .video-player-container {
    max-width: 1400px;
    margin: 0 auto;
    padding: 1rem;
    height: 100vh;
    display: flex;
    flex-direction: column;
  }

  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
    padding-bottom: 1rem;
    border-bottom: 1px solid #e5e7eb;
  }

  .header h1 {
    font-size: 1.5rem;
    font-weight: bold;
    margin: 0;
  }

  .header-controls {
    display: flex;
    align-items: center;
    gap: 1rem;
  }

  .layout-controls {
    display: flex;
    gap: 0.5rem;
  }

  .control-button {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    background: var(--surface-color);
    border: 1px solid var(--border-color);
    border-radius: 0.5rem;
    padding: 0.625rem 1rem;
    cursor: pointer;
    transition: all 0.2s ease;
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--text-secondary);
    min-height: 44px; /* Accessibility: minimum touch target */
  }

  .control-button:hover {
    background: var(--background-color);
    border-color: var(--primary-color);
    color: var(--text-color);
    transform: translateY(-1px);
    box-shadow: 0 2px 8px rgba(59, 130, 246, 0.15);
  }

  .control-button:focus {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
  }

  .control-button.active {
    background: var(--primary-color);
    border-color: var(--primary-color);
    color: white;
    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
  }

  .control-button-secondary {
    background: transparent;
    border-color: var(--border-color);
  }

  .control-icon {
    width: 1.125rem;
    height: 1.125rem;
    flex-shrink: 0;
  }

  .control-label {
    white-space: nowrap;
  }

  @media (max-width: 768px) {
    .control-label {
      display: none;
    }
    .control-button {
      padding: 0.75rem;
    }
  }

  .status {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.9rem;
    color: #6b7280;
  }

  .live-indicator {
    color: #10b981;
    font-size: 0.8rem;
  }

  .metadata-loading {
    color: #f59e0b;
    font-size: 0.8rem;
  }

  .main-content {
    flex: 1;
    display: flex;
    gap: 1rem;
    min-height: 0;
  }

  .main-content.split-layout .video-section {
    flex: 1;
  }

  .main-content.split-layout.bottom-layout {
    flex-direction: column;
  }

  .main-content.split-layout.bottom-layout .video-section {
    flex: 1;
  }

  .main-content.split-layout.bottom-layout .face-gallery-container {
    height: clamp(250px, 35vh, 400px);
    flex-shrink: 0;
  }

  .main-content:not(.split-layout) .video-section {
    width: 100%;
  }

  .video-section {
    background: white;
    border-radius: 0.75rem;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
    padding: 1.5rem;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }

  .video-controls-bar {
    display: flex;
    gap: 1rem;
    margin-bottom: 1rem;
    flex-wrap: wrap;
  }

  .video-selector, .quality-selector {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .video-selector label, .quality-selector label {
    font-weight: 500;
    color: #374151;
    white-space: nowrap;
    font-size: 0.9rem;
  }

  .video-selector select, .quality-selector select {
    padding: 0.5rem;
    border: 1px solid #d1d5db;
    border-radius: 0.375rem;
    background: white;
    font-size: 0.9rem;
    min-width: 150px;
  }

  .video-container {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    flex: 1;
    min-height: 0;
  }

  .video-element {
    width: 100%;
    height: 100%;
    max-height: none;
    border-radius: 0.5rem;
    background: #000;
    object-fit: contain;
  }

  .video-info {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    flex-wrap: wrap;
    gap: 1rem;
  }

  .video-title-section {
    display: flex;
    align-items: center;
    gap: 1rem;
    flex: 1;
    min-width: 200px;
  }

  .video-info h2 {
    font-size: 1.25rem;
    font-weight: 600;
    margin: 0;
    color: var(--text-color);
    line-height: 1.3;
  }

  .loading-badge {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    background: var(--warning-color);
    color: white;
    padding: 0.25rem 0.75rem;
    border-radius: 1rem;
    font-size: 0.8rem;
    font-weight: 500;
  }

  .loading-spinner {
    width: 0.875rem;
    height: 0.875rem;
    border: 1.5px solid rgba(255, 255, 255, 0.3);
    border-top: 1.5px solid white;
    border-radius: 50%;
    animation: spin 1s linear infinite;
  }

  .faces-badge {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    background: var(--primary-color);
    color: white;
    padding: 0.375rem 0.75rem;
    border-radius: 1rem;
    font-size: 0.8rem;
    font-weight: 500;
  }

  .faces-icon {
    width: 0.875rem;
    height: 0.875rem;
  }

  .time-info {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 0.5rem;
    min-width: 120px;
  }

  .timestamp {
    color: var(--text-secondary);
    font-size: 0.9rem;
    font-weight: 500;
    font-variant-numeric: tabular-nums;
  }

  .progress-indicator {
    height: 2px;
    background: var(--primary-color);
    border-radius: 1px;
    transition: width 0.1s ease;
    min-width: 4px;
  }

  .controls {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 0.75rem;
    background: #f9fafb;
    border-radius: 0.5rem;
    flex-shrink: 0;
  }

  .play-button {
    background: #3b82f6;
    border: none;
    border-radius: 0.375rem;
    padding: 0.5rem 0.75rem;
    color: white;
    font-size: 1rem;
    cursor: pointer;
    transition: background-color 0.2s;
  }

  .play-button:hover {
    background: #2563eb;
  }

  .progress-container {
    flex: 1;
    cursor: pointer;
    padding: 0.5rem;
    border-radius: 0.25rem;
    transition: all 0.2s ease;
  }
  
  .progress-container:hover {
    background: rgba(59, 130, 246, 0.05);
  }
  
  .progress-container:focus {
    outline: 2px solid #3b82f6;
    outline-offset: 2px;
    background: rgba(59, 130, 246, 0.1);
  }

  .progress-bar {
    height: 6px;
    background: #e5e7eb;
    border-radius: 3px;
    overflow: hidden;
  }

  .progress-fill {
    height: 100%;
    background: #3b82f6;
    transition: width 0.1s ease;
  }

  .time-display {
    font-size: 0.85rem;
    color: #6b7280;
    white-space: nowrap;
  }

  .face-gallery-container {
    width: clamp(320px, 25vw, 400px);
    flex-shrink: 0;
  }

  .loading, .error, .no-video {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 4rem 2rem;
    text-align: center;
    flex: 1;
  }

  .spinner {
    width: 2rem;
    height: 2rem;
    border: 2px solid #e5e7eb;
    border-top: 2px solid #3b82f6;
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin-bottom: 1rem;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .error {
    color: #dc2626;
  }

  /* Responsive Design */
  @media (max-width: 1200px) {
    .main-content.split-layout:not(.bottom-layout) {
      flex-direction: column-reverse;
    }
    
    .main-content.split-layout:not(.bottom-layout) .face-gallery-container {
      width: 100%;
      height: clamp(250px, 30vh, 350px);
    }
  }

  @media (max-width: 1024px) {
    .video-player-container {
      padding: 0.75rem;
    }
    
    .face-gallery-container {
      width: 100%;
      height: clamp(200px, 25vh, 300px);
    }
    
    .video-info {
      flex-direction: column;
      align-items: flex-start;
      gap: 0.75rem;
    }
    
    .video-title-section {
      width: 100%;
    }
    
    .time-info {
      align-items: flex-start;
      width: 100%;
    }
  }

  @media (max-width: 768px) {
    .video-player-container {
      padding: 0.5rem;
      height: 100dvh; /* Use dynamic viewport height on mobile */
    }
    
    .header {
      flex-direction: column;
      align-items: flex-start;
      gap: 0.75rem;
      padding-bottom: 0.75rem;
    }

    .header h1 {
      font-size: 1.25rem;
    }
    
    .header-controls {
      width: 100%;
      justify-content: space-between;
    }
    
    .video-controls-bar {
      flex-direction: column;
      gap: 0.75rem;
    }

    .video-selector, .quality-selector {
      width: 100%;
    }
    
    .video-selector select, .quality-selector select {
      width: 100%;
      min-width: unset;
      padding: 0.75rem;
      font-size: 1rem; /* Better touch experience */
    }
    
    .controls {
      padding: 1rem;
      border-radius: var(--radius-md);
    }
    
    .play-button {
      padding: 0.75rem 1rem;
      font-size: 1.125rem;
    }

    .face-gallery-container {
      height: clamp(180px, 25vh, 250px);
    }
    
    .video-info h2 {
      font-size: 1.1rem;
    }
  }

  @media (max-width: 480px) {
    .video-player-container {
      padding: 0.25rem;
    }
    
    .header {
      padding: 0.75rem 0.5rem;
    }
    
    .header-controls {
      flex-direction: column;
      align-items: stretch;
      gap: 0.5rem;
    }
    
    .layout-controls {
      justify-content: center;
    }

    .status {
      font-size: 0.8rem;
      align-self: center;
    }
    
    .video-section {
      padding: 0.75rem;
    }
    
    .video-info {
      gap: 0.5rem;
    }
    
    .video-title-section {
      flex-direction: column;
      align-items: flex-start;
      gap: 0.5rem;
    }
    
    .faces-badge, .loading-badge {
      align-self: flex-start;
    }
  }
  
  /* Accessibility styles */
  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
  }
  
  .error-content {
    display: flex;
    align-items: flex-start;
    gap: 1rem;
    max-width: 500px;
    margin: 0 auto;
  }
  
  .error-icon {
    width: 2rem;
    height: 2rem;
    color: #ef4444;
    flex-shrink: 0;
    margin-top: 0.25rem;
  }
  
  .error-details h3 {
    margin: 0 0 0.5rem;
    font-size: 1.1rem;
    font-weight: 600;
    color: #dc2626;
  }
  
  .error-details p {
    margin: 0 0 1rem;
    color: #6b7280;
    line-height: 1.5;
  }
  
  .retry-button {
    background: #3b82f6;
    color: white;
    border: none;
    padding: 0.5rem 1rem;
    border-radius: 0.375rem;
    font-size: 0.9rem;
    font-weight: 500;
    cursor: pointer;
    transition: background-color 0.2s ease;
    min-height: 44px; /* Accessibility: minimum touch target */
  }
  
  .retry-button:hover {
    background: #2563eb;
  }
  
  .retry-button:focus {
    outline: 2px solid #3b82f6;
    outline-offset: 2px;
  }

  /* Reduced motion preference */
  @media (prefers-reduced-motion: reduce) {
    .control-button,
    .progress-fill,
    .loading-spinner {
      transition: none;
      animation: none;
    }
  }
</style>