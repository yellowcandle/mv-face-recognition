<script lang="ts">
  import { onMount } from 'svelte';
  
  let videos: any[] = [];
  let selectedVideo: any = null;
  let selectedQuality = '720p';
  let videoElement: HTMLVideoElement;
  let currentTime = 0;
  let duration = 0;
  let playing = false;
  let loading = true;
  let error = '';
  
  onMount(() => {
    loadVideos().then(() => {
      loading = false;
    });
  });
  
  async function loadVideos() {
    try {
      const response = await fetch('/api/videos');
      if (response.ok) {
        const data = await response.json();
        videos = data.videos || [];
        if (videos.length > 0) {
          await selectVideo(videos[0]);
        }
      }
    } catch (err) {
      console.error('Failed to load videos:', err);
      error = 'Failed to load videos';
    }
  }
  
  async function selectVideo(video: any) {
    selectedVideo = video;
    error = '';
    
    if (videoElement) {
      videoElement.currentTime = 0;
      currentTime = 0;
    }
  }
  
  function updateVideoSource() {
    if (videoElement && selectedVideo) {
      const wasPlaying = !videoElement.paused;
      const currentTimeStamp = videoElement.currentTime;
      
      // Update source and preserve playback state
      videoElement.src = `/api/videos/${selectedVideo.id}/stream/${selectedQuality}`;
      videoElement.currentTime = currentTimeStamp;
      
      if (wasPlaying) {
        videoElement.play();
      }
    }
  }
  
  function handleTimeUpdate() {
    if (videoElement) {
      currentTime = videoElement.currentTime;
      duration = videoElement.duration || 0;
    }
  }
  
  function handlePlay() {
    playing = true;
  }
  
  function handlePause() {
    playing = false;
  }
  
  function togglePlayPause() {
    if (videoElement) {
      if (playing) {
        videoElement.pause();
      } else {
        videoElement.play();
      }
    }
  }
  
  function formatTime(seconds: number): string {
    const minutes = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
  }
  
  function handleSeek(event: any) {
    const rect = event.currentTarget.getBoundingClientRect();
    const position = (event.clientX - rect.left) / rect.width;
    if (videoElement && duration) {
      videoElement.currentTime = position * duration;
    }
  }
</script>

<svelte:head>
  <title>Video Player - MV Face Recognition</title>
</svelte:head>

<main class="video-player-container">
  <div class="header">
    <h1>Video Player</h1>
    <div class="status">
      <span class="live-indicator">●</span>
      <span>Online</span>
    </div>
  </div>

  {#if loading}
    <div class="loading">
      <div class="spinner"></div>
      <p>Loading videos...</p>
    </div>
  {:else if error}
    <div class="error">
      <p>{error}</p>
    </div>
  {:else}
    <div class="video-section">
      <div class="video-selector">
        <label for="video-select">Select Video:</label>
        <select id="video-select" bind:value={selectedVideo} on:change={() => selectedVideo && selectVideo(selectedVideo)}>
          {#each videos as video}
            <option value={video}>{video.name}</option>
          {/each}
        </select>
      </div>

      {#if selectedVideo}
        <div class="quality-selector">
          <label for="quality-select">Quality:</label>
          <select id="quality-select" bind:value={selectedQuality} on:change={() => updateVideoSource()}>
            <option value="720p">720p (Recommended)</option>
            <option value="1080p">1080p (High Quality)</option>
          </select>
        </div>
        <div class="video-container">
          <video
            bind:this={videoElement}
            src="/api/videos/{selectedVideo.id}/stream/{selectedQuality}"
            controls
            preload="metadata"
            on:timeupdate={handleTimeUpdate}
            on:play={handlePlay}
            on:pause={handlePause}
            on:loadedmetadata={handleTimeUpdate}
            class="video-element"
          >
            <track kind="captions" />
            Your browser does not support the video tag.
          </video>

          <div class="video-info">
            <h2>{selectedVideo.name}</h2>
            <div class="time-info">
              <span>{formatTime(currentTime)} / {formatTime(duration)}</span>
            </div>
          </div>

          <div class="controls">
            <button on:click={togglePlayPause} class="play-button">
              {playing ? '⏸️' : '▶️'}
            </button>
            
            <div class="progress-container" on:click={handleSeek}>
              <div class="progress-bar">
                <div 
                  class="progress-fill" 
                  style="width: {duration ? (currentTime / duration) * 100 : 0}%"
                ></div>
              </div>
            </div>
            
            <div class="time-display">
              {formatTime(currentTime)} / {formatTime(duration)}
            </div>
          </div>
        </div>
      {:else}
        <div class="no-video">
          <p>No videos available</p>
        </div>
      {/if}
    </div>
  {/if}
</main>

<style>
  .video-player-container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 2rem;
  }

  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 2rem;
    padding-bottom: 1rem;
    border-bottom: 1px solid #e5e7eb;
  }

  .header h1 {
    font-size: 2rem;
    font-weight: bold;
    margin: 0;
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

  .loading, .error, .no-video {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 4rem 2rem;
    text-align: center;
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

  .video-section {
    background: white;
    border-radius: 0.5rem;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    padding: 2rem;
  }

  .video-selector {
    margin-bottom: 1rem;
  }

  .video-selector label {
    display: block;
    font-weight: 500;
    margin-bottom: 0.5rem;
    color: #374151;
  }

  .video-selector select {
    width: 100%;
    max-width: 400px;
    padding: 0.5rem;
    border: 1px solid #d1d5db;
    border-radius: 0.375rem;
    background: white;
    font-size: 1rem;
  }

  .quality-selector {
    margin-bottom: 2rem;
    display: flex;
    align-items: center;
    gap: 1rem;
  }

  .quality-selector label {
    font-weight: 500;
    color: #374151;
    white-space: nowrap;
  }

  .quality-selector select {
    padding: 0.5rem;
    border: 1px solid #d1d5db;
    border-radius: 0.375rem;
    background: white;
    font-size: 0.9rem;
    min-width: 180px;
  }

  .video-container {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .video-element {
    width: 100%;
    max-height: 70vh;
    border-radius: 0.5rem;
    background: #000;
  }

  .video-info h2 {
    font-size: 1.25rem;
    font-weight: 600;
    margin: 0;
    color: #111827;
  }

  .time-info {
    color: #6b7280;
    font-size: 0.9rem;
    margin-top: 0.25rem;
  }

  .controls {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 1rem;
    background: #f9fafb;
    border-radius: 0.5rem;
  }

  .play-button {
    background: #3b82f6;
    border: none;
    border-radius: 0.375rem;
    padding: 0.5rem 1rem;
    color: white;
    font-size: 1.2rem;
    cursor: pointer;
    transition: background-color 0.2s;
  }

  .play-button:hover {
    background: #2563eb;
  }

  .progress-container {
    flex: 1;
    cursor: pointer;
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
    font-size: 0.9rem;
    color: #6b7280;
    white-space: nowrap;
  }

  @media (max-width: 768px) {
    .video-player-container {
      padding: 1rem;
    }
    
    .header {
      flex-direction: column;
      align-items: flex-start;
      gap: 0.5rem;
    }
    
    .controls {
      flex-wrap: wrap;
      gap: 0.5rem;
    }
    
    .time-display {
      order: -1;
      width: 100%;
      text-align: center;
    }
  }
</style>