<script lang="ts">
  import { onMount } from 'svelte';
  
  let videos = [
    { id: 'video-1', name: '全民造星IV - 前傳 MV', duration: '3:45' },
    { id: 'video-2', name: '全民造星IV - 女團駅', duration: '4:12' },
    { id: 'video-3', name: 'Training Video', duration: '2:30' }
  ];
  
  let selectedVideo = videos[0];
  let isPlaying = false;
  let currentTime = 0;
  let duration = 225; // 3:45 in seconds
  let volume = 0.8;
  
  function selectVideo(video: typeof videos[0]) {
    selectedVideo = video;
    isPlaying = false;
    currentTime = 0;
  }
  
  function togglePlay() {
    isPlaying = !isPlaying;
  }
  
  function formatTime(seconds: number): string {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  }
  
  onMount(() => {
    let interval: number;
    
    if (isPlaying) {
      interval = setInterval(() => {
        if (currentTime < duration) {
          currentTime++;
        } else {
          isPlaying = false;
        }
      }, 1000);
    }
    
    return () => {
      if (interval) clearInterval(interval);
    };
  });
</script>

<svelte:head>
  <title>Video Player - Face Recognition Dashboard</title>
</svelte:head>

<div class="video-player-container">
  <div class="player-header">
    <h1>Video Player</h1>
    <div class="video-selector">
      <label for="video-select">Select Video:</label>
      <select id="video-select" bind:value={selectedVideo} on:change={() => selectVideo(selectedVideo)}>
        {#each videos as video}
          <option value={video}>{video.name}</option>
        {/each}
      </select>
    </div>
  </div>

  <div class="player-main">
    <!-- Video Display Area -->
    <div class="video-display">
      <div class="video-frame">
        <div class="video-placeholder">
          <div class="video-info">
            <h3>{selectedVideo.name}</h3>
            <p>{selectedVideo.duration}</p>
          </div>
          
          {#if isPlaying}
            <div class="play-indicator">▶️ Playing</div>
          {:else}
            <div class="play-indicator">⏸️ Paused</div>
          {/if}
        </div>
      </div>
      
      <!-- Video Controls -->
      <div class="video-controls">
        <button class="play-button" on:click={togglePlay}>
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
            bind:value={currentTime}
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
          />
        </div>
      </div>
    </div>

    <!-- Video Information Panel -->
    <div class="info-panel">
      <h3>Video Information</h3>
      
      <div class="info-section">
        <h4>Details</h4>
        <div class="info-item">
          <span class="label">Title:</span>
          <span class="value">{selectedVideo.name}</span>
        </div>
        <div class="info-item">
          <span class="label">Duration:</span>
          <span class="value">{selectedVideo.duration}</span>
        </div>
        <div class="info-item">
          <span class="label">Resolution:</span>
          <span class="value">1920x1080</span>
        </div>
        <div class="info-item">
          <span class="label">Frame Rate:</span>
          <span class="value">30 FPS</span>
        </div>
      </div>
      
      <div class="info-section">
        <h4>Processing Status</h4>
        <div class="status-item">
          <span class="status-dot processed"></span>
          <span>Face Detection: Complete</span>
        </div>
        <div class="status-item">
          <span class="status-dot processed"></span>
          <span>Face Recognition: Complete</span>
        </div>
        <div class="status-item">
          <span class="status-dot processed"></span>
          <span>Metadata Generation: Complete</span>
        </div>
      </div>
      
      <div class="info-section">
        <h4>Statistics</h4>
        <div class="stat-item">
          <span class="stat-label">Faces Detected:</span>
          <span class="stat-value">127</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">Recognized:</span>
          <span class="stat-value">89</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">Unknown:</span>
          <span class="stat-value">38</span>
        </div>
      </div>
    </div>
  </div>
</div>

<style>
  .video-player-container {
    height: 100%;
    display: flex;
    flex-direction: column;
    padding: 20px;
    background-color: #1a1a1a;
    color: #ffffff;
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

  .video-placeholder {
    width: 100%;
    height: 100%;
    background: linear-gradient(45deg, #111, #222);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    position: relative;
  }

  .video-info h3 {
    font-size: 20px;
    margin-bottom: 8px;
  }

  .video-info p {
    color: #9ca3af;
    font-size: 16px;
  }

  .play-indicator {
    position: absolute;
    bottom: 20px;
    right: 20px;
    background: rgba(0, 0, 0, 0.7);
    padding: 8px 12px;
    border-radius: 6px;
    font-size: 14px;
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

  .play-button:hover {
    background-color: #4b5563;
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
  }

  .progress-bar::-webkit-slider-thumb {
    appearance: none;
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
  }

  .volume-slider::-webkit-slider-thumb {
    appearance: none;
    width: 12px;
    height: 12px;
    background: #3b82f6;
    border-radius: 50%;
    cursor: pointer;
  }

  .info-panel {
    flex: 1;
    background-color: #1e293b;
    border-radius: 8px;
    padding: 20px;
    overflow-y: auto;
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
    font-size: 16px;
    font-weight: 600;
    margin-bottom: 12px;
    color: #e2e8f0;
  }

  .info-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 0;
    border-bottom: 1px solid #334155;
  }

  .info-item:last-child {
    border-bottom: none;
  }

  .label {
    color: #9ca3af;
    font-weight: 500;
  }

  .value {
    color: #ffffff;
    font-weight: 600;
  }

  .status-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 6px 0;
  }

  .status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background-color: #6b7280;
  }

  .status-dot.processed {
    background-color: #22c55e;
  }

  .stat-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 6px 0;
  }

  .stat-label {
    color: #9ca3af;
  }

  .stat-value {
    color: #3b82f6;
    font-weight: 600;
    font-size: 16px;
  }

  /* Mobile Responsive */
  @media (max-width: 768px) {
    .player-header {
      flex-direction: column;
      align-items: flex-start;
      gap: 15px;
    }
    
    .player-main {
      flex-direction: column;
    }
    
    .video-controls {
      flex-wrap: wrap;
      gap: 10px;
    }
    
    .progress-container {
      order: -1;
      width: 100%;
    }
    
    .time-display {
      min-width: auto;
    }
  }
</style>