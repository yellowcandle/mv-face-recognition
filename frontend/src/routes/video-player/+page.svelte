<script lang="ts">
  import { onMount } from 'svelte';
  
  let videos: any[] = [];
  let selectedVideo: any = null;
  let videoElement: HTMLVideoElement;
  let canvas: HTMLCanvasElement;
  let ctx: CanvasRenderingContext2D | null = null;
  let currentTime = 0;
  let duration = 0;
  let playing = false;
  let loading = true;
  let showOverlay = true;
  let showSidebar = true;
  let currentFaces: any[] = [];
  let selectedFace: any = null;
  let metadata: any = null;
  let animationId: number;
  
  onMount(async () => {
    await loadVideos();
    loading = false;
  });
  
  async function loadVideos() {
    try {
      const response = await fetch('/api/videos/processed/list');
      if (response.ok) {
        const data = await response.json();
        videos = data.videos || [];
        if (videos.length > 0) {
          await selectVideo(videos[0]);
        }
      }
    } catch (err) {
      console.error('Failed to load videos:', err);
    }
  }
  
  async function selectVideo(video: any) {
    selectedVideo = video;
    currentFaces = [];
    selectedFace = null;
    
    if (videoElement) {
      videoElement.currentTime = 0;
      currentTime = 0;
    }
    
    // Load metadata
    try {
      const metadataResponse = await fetch(`/api/videos/metadata/dense/${video.id}`);
      if (metadataResponse.ok) {
        metadata = await metadataResponse.json();
      }
    } catch (err) {
      console.error('Failed to load metadata:', err);
      // Mock metadata for demonstration
      metadata = {
        video_info: {
          filename: video.filename,
          duration: video.duration,
          fps: 30
        },
        timeline: generateMockTimeline(video.duration)
      };
    }
  }
  
  function generateMockTimeline(duration: number) {
    const timeline = [];
    const fps = 30;
    const totalFrames = Math.floor(duration * fps);
    
    for (let frame = 0; frame < totalFrames; frame += 30) { // Every second
      const timestamp = frame / fps;
      const contestants = [];
      
      // Randomly add contestants with varying confidence
      if (Math.random() > 0.7) {
        const numFaces = Math.floor(Math.random() * 3) + 1;
        for (let i = 0; i < numFaces; i++) {
          contestants.push({
            id: `face_${frame}_${i}`,
            contestant_id: Math.floor(Math.random() * 5) + 1,
            contestant_name: ['張三', '李四', '王五', '趙六', '錢七'][Math.floor(Math.random() * 5)],
            contestant_nickname: ['小張', '小李', '小王', '小趙', '小錢'][Math.floor(Math.random() * 5)],
            confidence: 0.6 + Math.random() * 0.4,
            bounding_box: {
              x: Math.random() * 300 + 50,
              y: Math.random() * 200 + 50, 
              width: 120 + Math.random() * 80,
              height: 150 + Math.random() * 100
            },
            timestamp: timestamp
          });
        }
      }
      
      timeline.push({
        frame_number: frame,
        timestamp: timestamp,
        contestants: contestants
      });
    }
    
    return timeline;
  }
  
  function initCanvas() {
    if (canvas && videoElement) {
      canvas.width = videoElement.videoWidth;
      canvas.height = videoElement.videoHeight;
      ctx = canvas.getContext('2d');
      startAnimation();
    }
  }
  
  function startAnimation() {
    function animate() {
      if (showOverlay && ctx && videoElement && metadata) {
        updateFaceOverlay();
      }
      animationId = requestAnimationFrame(animate);
    }
    animate();
  }
  
  function updateFaceOverlay() {
    if (!ctx || !canvas || !metadata) return;
    
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Find faces for current timestamp
    const currentTimestamp = videoElement.currentTime;
    const currentFrame = metadata.timeline.find((frame: any) => 
      Math.abs(frame.timestamp - currentTimestamp) < 0.5
    );
    
    if (currentFrame && currentFrame.contestants) {
      currentFaces = currentFrame.contestants;
      
      currentFrame.contestants.forEach((face: any) => {
        drawFaceBoundingBox(face);
      });
    } else {
      currentFaces = [];
    }
  }
  
  function drawFaceBoundingBox(face: any) {
    if (!ctx) return;
    
    const { x, y, width, height } = face.bounding_box;
    const confidence = face.confidence;
    
    // Scale coordinates to canvas size
    const scaleX = canvas.width / 1920; // Assuming 1080p base resolution
    const scaleY = canvas.height / 1080;
    
    const scaledX = x * scaleX;
    const scaledY = y * scaleY;
    const scaledWidth = width * scaleX;
    const scaledHeight = height * scaleY;
    
    // Set color based on confidence
    let color = '#ef4444'; // Red for low confidence
    if (confidence >= 0.8) color = '#10b981'; // Green for high confidence
    else if (confidence >= 0.6) color = '#f59e0b'; // Orange for medium confidence
    
    // Draw bounding box
    ctx.strokeStyle = color;
    ctx.lineWidth = 3;
    ctx.strokeRect(scaledX, scaledY, scaledWidth, scaledHeight);
    
    // Draw corner markers
    const cornerSize = 20;
    ctx.fillStyle = color;
    
    // Top-left corner
    ctx.fillRect(scaledX - 2, scaledY - 2, cornerSize, 4);
    ctx.fillRect(scaledX - 2, scaledY - 2, 4, cornerSize);
    
    // Top-right corner
    ctx.fillRect(scaledX + scaledWidth - cornerSize + 2, scaledY - 2, cornerSize, 4);
    ctx.fillRect(scaledX + scaledWidth - 2, scaledY - 2, 4, cornerSize);
    
    // Bottom-left corner
    ctx.fillRect(scaledX - 2, scaledY + scaledHeight - 2, cornerSize, 4);
    ctx.fillRect(scaledX - 2, scaledY + scaledHeight - cornerSize + 2, 4, cornerSize);
    
    // Bottom-right corner
    ctx.fillRect(scaledX + scaledWidth - cornerSize + 2, scaledY + scaledHeight - 2, cornerSize, 4);
    ctx.fillRect(scaledX + scaledWidth - 2, scaledY + scaledHeight - cornerSize + 2, 4, cornerSize);
    
    // Draw label
    const label = `${face.contestant_name} (${Math.round(confidence * 100)}%)`;
    ctx.fillStyle = color;
    ctx.font = '14px -apple-system, BlinkMacSystemFont, sans-serif';
    ctx.fillRect(scaledX, scaledY - 25, ctx.measureText(label).width + 10, 20);
    ctx.fillStyle = 'white';
    ctx.fillText(label, scaledX + 5, scaledY - 10);
  }
  
  function handleTimeUpdate() {
    if (videoElement) {
      currentTime = videoElement.currentTime;
      duration = videoElement.duration || 0;
    }
  }
  
  function handleCanPlay() {
    initCanvas();
  }
  
  function togglePlay() {
    if (videoElement) {
      if (playing) {
        videoElement.pause();
      } else {
        videoElement.play();
      }
      playing = !playing;
    }
  }
  
  function seek(event: Event) {
    const target = event.target as HTMLInputElement;
    const time = parseFloat(target.value);
    if (videoElement) {
      videoElement.currentTime = time;
      currentTime = time;
    }
  }
  
  function toggleOverlay() {
    showOverlay = !showOverlay;
    if (!showOverlay && ctx) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
    }
  }
  
  function toggleSidebar() {
    showSidebar = !showSidebar;
  }
  
  function selectFace(face: any) {
    selectedFace = selectedFace?.id === face.id ? null : face;
  }
  
  function formatTime(seconds: number) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  }
  
  function getConfidenceColor(confidence: number) {
    if (confidence >= 0.8) return '#10b981';
    if (confidence >= 0.6) return '#f59e0b';
    return '#ef4444';
  }
</script>

<svelte:head>
  <title>Video Player - MV Face Recognition</title>
  <meta name="description" content="Watch videos with real-time face recognition overlays" />
</svelte:head>

<div class="video-player-page">
  <header class="page-header">
    <h1>Video Player</h1>
    <p>Watch videos with real-time face recognition overlays</p>
  </header>
  
  {#if loading}
    <div class="loading">
      <div class="spinner"></div>
      <p>Loading videos...</p>
    </div>
  {:else if videos.length === 0}
    <div class="empty-state">
      <div class="empty-icon">🎬</div>
      <h3>No Videos Available</h3>
      <p>No processed videos found. Upload and process videos to get started.</p>
    </div>
  {:else}
    <div class="player-container">
      <!-- Video Selection -->
      <div class="video-selector">
        <label for="video-select">Select Video:</label>
        <select id="video-select" on:change={(e) => selectVideo(videos.find(v => v.id === e.target.value))}>
          {#each videos as video}
            <option value={video.id} selected={selectedVideo?.id === video.id}>
              {video.name}
            </option>
          {/each}
        </select>
      </div>
      
      <!-- Main Player Area -->
      <div class="player-layout" class:with-sidebar={showSidebar}>
        <!-- Video Player -->
        <div class="video-section">
          <!-- Player Controls Top -->
          <div class="player-controls-top">
            <button class="control-btn" on:click={toggleOverlay} class:active={showOverlay}>
              🎯 Overlay
            </button>
            <button class="control-btn" on:click={toggleSidebar} class:active={showSidebar}>
              👥 Sidebar
            </button>
            <div class="detection-indicator">
              <span class="detection-count">{currentFaces.length}</span>
              <span>faces detected</span>
            </div>
          </div>
          
          <!-- Video Container -->
          <div class="video-container">
            {#if selectedVideo}
              <video
                bind:this={videoElement}
                src="/videos/{selectedVideo.filename}"
                on:timeupdate={handleTimeUpdate}
                on:canplay={handleCanPlay}
                on:play={() => playing = true}
                on:pause={() => playing = false}
                preload="metadata"
                crossorigin="anonymous"
              >
                Your browser does not support the video tag.
              </video>
              
              {#if showOverlay}
                <canvas
                  bind:this={canvas}
                  class="face-overlay"
                ></canvas>
              {/if}
            {/if}
          </div>
          
          <!-- Player Controls Bottom -->
          <div class="player-controls">
            <button class="play-button" on:click={togglePlay}>
              {playing ? '⏸️' : '▶️'}
            </button>
            
            <div class="time-display">
              {formatTime(currentTime)} / {formatTime(duration)}
            </div>
            
            <input
              type="range"
              class="seek-bar"
              min="0"
              max={duration || 0}
              value={currentTime}
              on:input={seek}
            />
            
            <div class="volume-control">
              <span>🔊</span>
            </div>
          </div>
        </div>
        
        <!-- Face Recognition Sidebar -->
        {#if showSidebar}
          <div class="face-sidebar">
            <div class="sidebar-header">
              <h3>Detected Faces</h3>
              <span class="face-count">{currentFaces.length}</span>
            </div>
            
            {#if currentFaces.length > 0}
              <div class="faces-list">
                {#each currentFaces as face}
                  <div 
                    class="face-card" 
                    class:selected={selectedFace?.id === face.id}
                    on:click={() => selectFace(face)}
                  >
                    <div class="face-info">
                      <div class="face-avatar">
                        <span>{face.contestant_name?.charAt(0) || '?'}</span>
                      </div>
                      <div class="face-details">
                        <h4>{face.contestant_name || 'Unknown'}</h4>
                        <p>{face.contestant_nickname || ''}</p>
                        <div class="confidence-bar">
                          <div 
                            class="confidence-fill" 
                            style="width: {face.confidence * 100}%; background-color: {getConfidenceColor(face.confidence)}"
                          ></div>
                          <span class="confidence-text">{Math.round(face.confidence * 100)}%</span>
                        </div>
                      </div>
                    </div>
                  </div>
                {/each}
              </div>
            {:else}
              <div class="no-faces">
                <p>No faces detected at current timestamp</p>
              </div>
            {/if}
            
            <!-- Face Details Panel -->
            {#if selectedFace}
              <div class="face-details-panel">
                <h4>Face Details</h4>
                <div class="detail-grid">
                  <div class="detail-item">
                    <label>Name:</label>
                    <span>{selectedFace.contestant_name}</span>
                  </div>
                  <div class="detail-item">
                    <label>Nickname:</label>
                    <span>{selectedFace.contestant_nickname}</span>
                  </div>
                  <div class="detail-item">
                    <label>Confidence:</label>
                    <span style="color: {getConfidenceColor(selectedFace.confidence)}">
                      {Math.round(selectedFace.confidence * 100)}%
                    </span>
                  </div>
                  <div class="detail-item">
                    <label>Timestamp:</label>
                    <span>{formatTime(selectedFace.timestamp)}</span>
                  </div>
                  <div class="detail-item">
                    <label>Bounding Box:</label>
                    <span>
                      {Math.round(selectedFace.bounding_box.width)}×{Math.round(selectedFace.bounding_box.height)}
                    </span>
                  </div>
                </div>
              </div>
            {/if}
          </div>
        {/if}
      </div>
    </div>
  {/if}
</div>

<style>
  .video-player-page {
    max-width: 100%;
  }
  
  .page-header {
    margin-bottom: 2rem;
  }
  
  .page-header h1 {
    font-size: 2.5rem;
    font-weight: 700;
    margin: 0 0 0.5rem 0;
  }
  
  .page-header p {
    font-size: 1.1rem;
    color: var(--text-secondary);
    margin: 0;
  }
  
  .loading {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 4rem 2rem;
    text-align: center;
  }
  
  .spinner {
    width: 2rem;
    height: 2rem;
    border: 3px solid var(--border-color);
    border-top: 3px solid var(--primary-color);
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin-bottom: 1rem;
  }
  
  .empty-state {
    text-align: center;
    padding: 4rem 2rem;
  }
  
  .empty-icon {
    font-size: 4rem;
    margin-bottom: 1rem;
  }
  
  .empty-state h3 {
    font-size: 1.5rem;
    margin-bottom: 0.5rem;
    color: var(--text-color);
  }
  
  .empty-state p {
    color: var(--text-secondary);
  }
  
  .player-container {
    max-width: 100%;
  }
  
  .video-selector {
    margin-bottom: 2rem;
  }
  
  .video-selector label {
    display: inline-block;
    margin-right: 1rem;
    font-weight: 600;
    color: var(--text-color);
  }
  
  .video-selector select {
    padding: 0.5rem 1rem;
    border: 1px solid var(--border-color);
    border-radius: 0.375rem;
    background-color: var(--surface-color);
    color: var(--text-color);
    font-size: 1rem;
    min-width: 300px;
  }
  
  .player-layout {
    display: grid;
    grid-template-columns: 1fr;
    gap: 2rem;
  }
  
  .player-layout.with-sidebar {
    grid-template-columns: 1fr 350px;
  }
  
  .video-section {
    background-color: var(--surface-color);
    border: 1px solid var(--border-color);
    border-radius: 0.75rem;
    overflow: hidden;
    box-shadow: var(--shadow);
  }
  
  .player-controls-top {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 1rem;
    background-color: var(--background-color);
    border-bottom: 1px solid var(--border-color);
  }
  
  .control-btn {
    padding: 0.5rem 1rem;
    border: 1px solid var(--border-color);
    border-radius: 0.375rem;
    background-color: var(--surface-color);
    color: var(--text-color);
    cursor: pointer;
    transition: all 0.2s;
    font-size: 0.9rem;
  }
  
  .control-btn:hover {
    background-color: var(--border-color);
  }
  
  .control-btn.active {
    background-color: var(--primary-color);
    color: white;
    border-color: var(--primary-color);
  }
  
  .detection-indicator {
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.9rem;
    color: var(--text-secondary);
  }
  
  .detection-count {
    background-color: var(--primary-color);
    color: white;
    padding: 0.25rem 0.5rem;
    border-radius: 0.25rem;
    font-weight: 600;
    font-size: 0.8rem;
  }
  
  .video-container {
    position: relative;
    background-color: #000;
    aspect-ratio: 16/9;
  }
  
  .video-container video {
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
    z-index: 10;
  }
  
  .player-controls {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 1rem;
    background-color: var(--background-color);
    border-top: 1px solid var(--border-color);
  }
  
  .play-button {
    width: 3rem;
    height: 3rem;
    border: none;
    border-radius: 50%;
    background-color: var(--primary-color);
    color: white;
    font-size: 1.2rem;
    cursor: pointer;
    transition: background-color 0.2s;
    flex-shrink: 0;
  }
  
  .play-button:hover {
    background-color: var(--primary-hover);
  }
  
  .time-display {
    font-size: 0.9rem;
    color: var(--text-secondary);
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
    flex-shrink: 0;
  }
  
  .seek-bar {
    flex: 1;
    height: 0.5rem;
    border-radius: 0.25rem;
    background-color: var(--border-color);
    outline: none;
    cursor: pointer;
  }
  
  .seek-bar::-webkit-slider-thumb {
    width: 1rem;
    height: 1rem;
    border-radius: 50%;
    background-color: var(--primary-color);
    cursor: pointer;
  }
  
  .volume-control {
    font-size: 1.2rem;
    flex-shrink: 0;
  }
  
  /* Sidebar */
  .face-sidebar {
    background-color: var(--surface-color);
    border: 1px solid var(--border-color);
    border-radius: 0.75rem;
    overflow: hidden;
    box-shadow: var(--shadow);
    height: fit-content;
    max-height: 800px;
    display: flex;
    flex-direction: column;
  }
  
  .sidebar-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem;
    background-color: var(--background-color);
    border-bottom: 1px solid var(--border-color);
  }
  
  .sidebar-header h3 {
    margin: 0;
    font-size: 1.1rem;
    font-weight: 600;
  }
  
  .face-count {
    background-color: var(--primary-color);
    color: white;
    padding: 0.25rem 0.5rem;
    border-radius: 0.25rem;
    font-size: 0.8rem;
    font-weight: 600;
  }
  
  .faces-list {
    flex: 1;
    overflow-y: auto;
    padding: 0.5rem;
    max-height: 400px;
  }
  
  .face-card {
    padding: 0.75rem;
    margin-bottom: 0.5rem;
    border: 1px solid var(--border-color);
    border-radius: 0.5rem;
    cursor: pointer;
    transition: all 0.2s;
  }
  
  .face-card:hover {
    background-color: var(--border-color);
    transform: translateY(-1px);
  }
  
  .face-card.selected {
    border-color: var(--primary-color);
    background-color: rgba(37, 99, 235, 0.1);
  }
  
  .face-info {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }
  
  .face-avatar {
    width: 3rem;
    height: 3rem;
    border-radius: 50%;
    background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-weight: 600;
    font-size: 1.2rem;
    flex-shrink: 0;
  }
  
  .face-details {
    flex: 1;
    min-width: 0;
  }
  
  .face-details h4 {
    margin: 0 0 0.25rem 0;
    font-size: 0.95rem;
    font-weight: 600;
    color: var(--text-color);
  }
  
  .face-details p {
    margin: 0 0 0.5rem 0;
    font-size: 0.8rem;
    color: var(--text-secondary);
  }
  
  .confidence-bar {
    position: relative;
    height: 0.5rem;
    background-color: var(--border-color);
    border-radius: 0.25rem;
    overflow: hidden;
  }
  
  .confidence-fill {
    height: 100%;
    transition: width 0.3s ease;
  }
  
  .confidence-text {
    position: absolute;
    right: 0.25rem;
    top: -1.5rem;
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--text-secondary);
  }
  
  .no-faces {
    padding: 2rem 1rem;
    text-align: center;
    color: var(--text-secondary);
  }
  
  .face-details-panel {
    padding: 1rem;
    border-top: 1px solid var(--border-color);
    background-color: var(--background-color);
  }
  
  .face-details-panel h4 {
    margin: 0 0 1rem 0;
    font-size: 1rem;
    font-weight: 600;
  }
  
  .detail-grid {
    display: grid;
    gap: 0.75rem;
  }
  
  .detail-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  
  .detail-item label {
    font-size: 0.85rem;
    color: var(--text-secondary);
    font-weight: 500;
  }
  
  .detail-item span {
    font-size: 0.85rem;
    color: var(--text-color);
    font-weight: 600;
  }
  
  /* Mobile Responsiveness */
  @media (max-width: 1024px) {
    .player-layout.with-sidebar {
      grid-template-columns: 1fr;
      gap: 1rem;
    }
    
    .face-sidebar {
      max-height: 300px;
    }
  }
  
  @media (max-width: 768px) {
    .page-header h1 {
      font-size: 2rem;
    }
    
    .video-selector {
      margin-bottom: 1rem;
    }
    
    .video-selector select {
      min-width: 100%;
    }
    
    .player-controls-top {
      flex-wrap: wrap;
      gap: 0.5rem;
    }
    
    .detection-indicator {
      margin-left: 0;
      order: -1;
      flex-basis: 100%;
    }
    
    .player-controls {
      gap: 0.5rem;
      padding: 0.75rem;
    }
    
    .time-display {
      font-size: 0.8rem;
    }
  }
  
  @media (max-width: 480px) {
    .page-header h1 {
      font-size: 1.75rem;
    }
    
    .player-controls {
      flex-wrap: wrap;
    }
    
    .seek-bar {
      order: -1;
      flex-basis: 100%;
      margin-bottom: 0.5rem;
    }
    
    .face-sidebar {
      max-height: 250px;
    }
    
    .faces-list {
      max-height: 150px;
    }
  }
  
  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }
</style>