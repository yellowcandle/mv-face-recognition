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
  let hoveredFace: any = null;
  let mousePosition = { x: 0, y: 0 };
  let confidenceFilter = 0.5;
  let contestantSearch = '';
  let showMobileMenu = false;
  let videoError = false;
  let errorMessage = '';
  let showExportDialog = false;
  let exportStartTime = 0;
  let exportEndTime = 0;
  let exportProgress = 0;
  let isExporting = false;
  let highlightedFace: any = null;
  
  onMount(async () => {
    await loadVideos();
    loading = false;
  });
  
  async function loadVideos() {
    try {
      // Mock video data for testing
      videos = [
        {
          id: 'test-video',
          filename: 'test-video_720p.mp4',
          name: '《全民造星IV》主題曲',
          duration: 180
        },
        {
          id: 'video-1',
          filename: 'video-1_720p.mp4',
          name: '女團の駅 Performance',
          duration: 240
        }
      ];
      
      if (videos.length > 0) {
        await selectVideo(videos[0]);
      }
    } catch (err) {
      console.error('Failed to load videos:', err);
    }
  }
  
  async function selectVideo(videoOrName: any) {
    let video;
    if (typeof videoOrName === 'string') {
      video = videos.find(v => v.name === videoOrName);
    } else {
      video = videoOrName;
    }
    
    if (!video) return;
    
    selectedVideo = video;
    currentFaces = [];
    selectedFace = null;
    videoError = false;
    errorMessage = '';
    
    if (videoElement) {
      videoElement.currentTime = 0;
      currentTime = 0;
    }
    
    // Mock metadata for demonstration
    metadata = {
      video_info: {
        filename: video.filename,
        duration: video.duration,
        fps: 30,
        title: video.name
      },
      timeline: generateMockTimeline(video.duration)
    };
  }
  
  function generateMockTimeline(duration: number) {
    const timeline = [];
    const fps = 30;
    const totalFrames = Math.floor(duration * fps);
    
    for (let frame = 0; frame < totalFrames; frame += 30) {
      const timestamp = frame / fps;
      const contestants = [];
      
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
      updateCanvasSize();
      ctx = canvas.getContext('2d');
    }
  }
  
  function updateCanvasSize() {
    if (!canvas || !videoElement) return;
    
    const rect = videoElement.getBoundingClientRect();
    const displayWidth = rect.width;
    const displayHeight = rect.height;
    
    canvas.style.width = displayWidth + 'px';
    canvas.style.height = displayHeight + 'px';
    
    const devicePixelRatio = window.devicePixelRatio || 1;
    canvas.width = displayWidth * devicePixelRatio;
    canvas.height = displayHeight * devicePixelRatio;
    
    if (ctx) {
      ctx.scale(devicePixelRatio, devicePixelRatio);
    }
  }
  
  function getVideoScaleFactors() {
    if (!videoElement || !canvas) return { 
      scaleX: 1, 
      scaleY: 1, 
      offsetX: 0, 
      offsetY: 0, 
      actualVideoWidth: 0, 
      actualVideoHeight: 0 
    };
    
    const videoWidth = videoElement.videoWidth || 1920;
    const videoHeight = videoElement.videoHeight || 1080;
    
    const rect = videoElement.getBoundingClientRect();
    const displayWidth = rect.width;
    const displayHeight = rect.height;
    
    const videoAspect = videoWidth / videoHeight;
    const displayAspect = displayWidth / displayHeight;
    
    let actualVideoWidth = displayWidth;
    let actualVideoHeight = displayHeight;
    let offsetX = 0;
    let offsetY = 0;
    
    if (videoAspect > displayAspect) {
      actualVideoWidth = displayWidth;
      actualVideoHeight = displayWidth / videoAspect;
      offsetY = (displayHeight - actualVideoHeight) / 2;
    } else {
      actualVideoHeight = displayHeight;
      actualVideoWidth = displayHeight * videoAspect;
      offsetX = (displayWidth - actualVideoWidth) / 2;
    }
    
    return {
      scaleX: actualVideoWidth / videoWidth,
      scaleY: actualVideoHeight / videoHeight,
      offsetX,
      offsetY,
      actualVideoWidth,
      actualVideoHeight
    };
  }
  
  function updateFaceOverlay() {
    if (!ctx || !canvas) return;
    
    const rect = videoElement?.getBoundingClientRect();
    if (rect) {
      ctx.clearRect(0, 0, rect.width, rect.height);
    }
    
    if (metadata) {
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
  }
  
  function drawFaceBoundingBox(face: any) {
    if (!ctx) return;
    
    const { x, y, width, height } = face.bounding_box;
    const confidence = face.confidence;
    
    const scaleFactors = getVideoScaleFactors();
    
    const scaledX = x * scaleFactors.scaleX + scaleFactors.offsetX;
    const scaledY = y * scaleFactors.scaleY + scaleFactors.offsetY;
    const scaledWidth = width * scaleFactors.scaleX;
    const scaledHeight = height * scaleFactors.scaleY;
    
    const isHovered = hoveredFace?.id === face.id;
    const isSelected = selectedFace?.id === face.id;
    const isHighlighted = highlightedFace?.id === face.id;
    
    let color = '#ef4444';
    let alpha = 0.8;
    let lineWidth = 3;
    
    if (confidence >= 0.8) {
      color = '#10b981';
      alpha = 0.9;
    } else if (confidence >= 0.7) {
      color = '#10b981';
      alpha = 0.8;
    } else if (confidence >= 0.5) {
      color = '#f59e0b';
      alpha = 0.8;
    } else {
      color = '#ef4444';
      alpha = 0.7;
    }
    
    if (isSelected) {
      alpha = 1.0;
      lineWidth = 4;
      color = '#2563eb';
    } else if (isHighlighted) {
      alpha = 1.0;
      lineWidth = 4;
      color = '#f59e0b';
    } else if (isHovered) {
      alpha = 0.95;
      lineWidth = 4;
    }
    
    ctx.save();
    ctx.globalAlpha = alpha;
    
    ctx.strokeStyle = color;
    ctx.lineWidth = lineWidth;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.strokeRect(scaledX, scaledY, scaledWidth, scaledHeight);
    
    const cornerSize = Math.min(25, Math.min(scaledWidth, scaledHeight) * 0.15);
    const cornerThickness = 4;
    
    ctx.fillStyle = color;
    ctx.globalAlpha = 1.0;
    
    ctx.fillRect(scaledX - cornerThickness/2, scaledY - cornerThickness/2, cornerSize, cornerThickness);
    ctx.fillRect(scaledX - cornerThickness/2, scaledY - cornerThickness/2, cornerThickness, cornerSize);
    
    ctx.fillRect(scaledX + scaledWidth - cornerSize + cornerThickness/2, scaledY - cornerThickness/2, cornerSize, cornerThickness);
    ctx.fillRect(scaledX + scaledWidth - cornerThickness/2, scaledY - cornerThickness/2, cornerThickness, cornerSize);
    
    ctx.fillRect(scaledX - cornerThickness/2, scaledY + scaledHeight - cornerThickness/2, cornerSize, cornerThickness);
    ctx.fillRect(scaledX - cornerThickness/2, scaledY + scaledHeight - cornerSize + cornerThickness/2, cornerThickness, cornerSize);
    
    ctx.fillRect(scaledX + scaledWidth - cornerSize + cornerThickness/2, scaledY + scaledHeight - cornerThickness/2, cornerSize, cornerThickness);
    ctx.fillRect(scaledX + scaledWidth - cornerThickness/2, scaledY + scaledHeight - cornerSize + cornerThickness/2, cornerThickness, cornerSize);
    
    if (confidence >= 0.7) {
      const label = `${face.contestant_name} (${Math.round(confidence * 100)}%)`;
      ctx.font = 'bold 14px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
      
      const textMetrics = ctx.measureText(label);
      const labelWidth = textMetrics.width + 16;
      const labelHeight = 24;
      const labelX = Math.max(scaledX, Math.min(scaledX, scaleFactors.actualVideoWidth - labelWidth));
      const labelY = scaledY > labelHeight + 5 ? scaledY - 5 : scaledY + scaledHeight + labelHeight;
      
      ctx.fillStyle = color;
      ctx.globalAlpha = 0.9;
      ctx.fillRect(labelX, labelY - labelHeight, labelWidth, labelHeight);
      
      ctx.fillStyle = 'rgba(0, 0, 0, 0.3)';
      ctx.fillRect(labelX + 2, labelY - labelHeight + 2, labelWidth, labelHeight);
      
      ctx.fillStyle = color;
      ctx.fillRect(labelX, labelY - labelHeight, labelWidth, labelHeight);
      
      ctx.fillStyle = 'white';
      ctx.globalAlpha = 1.0;
      ctx.textAlign = 'left';
      ctx.textBaseline = 'middle';
      ctx.fillText(label, labelX + 8, labelY - labelHeight/2);
    }
    
    ctx.restore();
  }
  
  function handleTimeUpdate() {
    if (videoElement) {
      currentTime = videoElement.currentTime;
      duration = videoElement.duration || 0;
      updateFaceOverlay();
    }
  }
  
  function handleCanPlay() {
    initCanvas();
    updateFaceOverlay();
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
    if (!showOverlay && ctx && videoElement) {
      const rect = videoElement.getBoundingClientRect();
      ctx.clearRect(0, 0, rect.width, rect.height);
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
  
  function handleCanvasMouseMove(event: MouseEvent) {
    if (!canvas || !currentFaces.length) return;
    
    const rect = canvas.getBoundingClientRect();
    mousePosition.x = event.clientX - rect.left;
    mousePosition.y = event.clientY - rect.top;
    
    const previousHoveredFace = hoveredFace;
    hoveredFace = null;
    
    for (const face of currentFaces) {
      if (isPointInFaceBoundingBox(mousePosition, face)) {
        hoveredFace = face;
        break;
      }
    }
    
    if (hoveredFace) {
      canvas.style.cursor = 'pointer';
    } else {
      canvas.style.cursor = 'default';
    }
    
    if (hoveredFace?.id !== previousHoveredFace?.id) {
      // Force redraw
    }
  }
  
  function handleCanvasClick(event: MouseEvent) {
    if (!canvas || !currentFaces.length) return;
    
    const rect = canvas.getBoundingClientRect();
    const clickPosition = {
      x: event.clientX - rect.left,
      y: event.clientY - rect.top
    };
    
    for (const face of currentFaces) {
      if (isPointInFaceBoundingBox(clickPosition, face)) {
        selectFace(face);
        break;
      }
    }
  }
  
  function handleCanvasMouseLeave() {
    hoveredFace = null;
    if (canvas) {
      canvas.style.cursor = 'default';
    }
  }
  
  function isPointInFaceBoundingBox(point: {x: number, y: number}, face: any): boolean {
    const scaleFactors = getVideoScaleFactors();
    const { x, y, width, height } = face.bounding_box;
    
    const scaledX = x * scaleFactors.scaleX + scaleFactors.offsetX;
    const scaledY = y * scaleFactors.scaleY + scaleFactors.offsetY;
    const scaledWidth = width * scaleFactors.scaleX;
    const scaledHeight = height * scaleFactors.scaleY;
    
    return point.x >= scaledX && point.x <= scaledX + scaledWidth &&
           point.y >= scaledY && point.y <= scaledY + scaledHeight;
  }
  
  function handleVideoError() {
    videoError = true;
    errorMessage = 'Failed to load video. Please try again.';
  }
  
  function handleExport() {
    showExportDialog = true;
  }
  
  function closeExportDialog() {
    showExportDialog = false;
  }
  
  function startExport() {
    // Mock export functionality with progress
    isExporting = true;
    exportProgress = 0;
    
    const progressInterval = setInterval(() => {
      exportProgress += 10;
      if (exportProgress >= 100) {
        clearInterval(progressInterval);
        isExporting = false;
        showExportDialog = false;
        exportProgress = 0;
      }
    }, 200);
    
    console.log('Exporting video from', exportStartTime, 'to', exportEndTime);
  }

  function searchAndJumpToContestant(contestantName: string) {
    if (!metadata) return;
    
    // Find first occurrence of contestant
    for (const frame of metadata.timeline) {
      for (const contestant of frame.contestants) {
        if (contestant.contestant_name === contestantName) {
          jumpToTimestamp(frame.timestamp);
          highlightedFace = contestant;
          selectedFace = contestant;
          return;
        }
      }
    }
  }
  
  function jumpToTimestamp(timestamp: number) {
    if (videoElement) {
      videoElement.currentTime = timestamp;
      currentTime = timestamp;
    }
  }
  
  function filterFacesByConfidence(faces: any[]) {
    return faces.filter(face => face.confidence >= confidenceFilter);
  }
  
  function filterFacesBySearch(faces: any[]) {
    if (!contestantSearch.trim()) return faces;
    
    const searchTerm = contestantSearch.toLowerCase();
    return faces.filter(face => 
      face.contestant_name.toLowerCase().includes(searchTerm) ||
      face.contestant_nickname.toLowerCase().includes(searchTerm)
    );
  }
  
  function getFilteredFaces() {
    let filtered = currentFaces;
    filtered = filterFacesByConfidence(filtered);
    filtered = filterFacesBySearch(filtered);
    return filtered;
  }
  
  function getUniqueContestants() {
    const contestants = new Map();
    if (metadata) {
      metadata.timeline.forEach((frame: any) => {
        frame.contestants.forEach((face: any) => {
          if (!contestants.has(face.contestant_id)) {
            contestants.set(face.contestant_id, {
              id: face.contestant_id,
              name: face.contestant_name,
              nickname: face.contestant_nickname,
              appearances: 0
            });
          }
          contestants.get(face.contestant_id).appearances++;
        });
      });
    }
    return Array.from(contestants.values());
  }
</script>

<div class="video-player-page" data-testid="video-player">
  {#if loading}
    <div class="loading">
      <div class="spinner"></div>
      <p>Loading videos...</p>
    </div>
  {:else if videos.length === 0}
    <div class="empty-state">
      <div class="empty-icon">🎬</div>
      <h3>No videos found</h3>
      <p>Please upload some videos to get started</p>
    </div>
  {:else}
    <div class="player-container">
      <div class="page-header">
        <h1>Video Player with Face Recognition</h1>
        <p>Watch videos with real-time face detection and contestant identification</p>
      </div>

      <div class="video-selector" data-testid="video-selector">
        <label for="video-select">Select Video:</label>
        <select 
          id="video-select" 
          bind:value={selectedVideo}
          on:change={(e) => selectVideo(e.target.value)}
        >
          {#each videos as video}
            <option value={video}>{video.name}</option>
          {/each}
        </select>
      </div>

      {#if selectedVideo}
        <div class="video-info">
          <h2 data-testid="video-title">Now Playing: {selectedVideo.name}</h2>
          <div class="video-meta">
            <span data-testid="video-duration">Duration: {formatTime(selectedVideo.duration)}</span>
          </div>
        </div>
      {/if}

      <div class="player-layout" class:with-sidebar={showSidebar}>
        <div class="video-section">
          <div class="player-controls-top">
            <button 
              class="control-btn" 
              class:active={showOverlay}
              on:click={toggleOverlay}
              data-testid="toggle-overlay"
            >
              {showOverlay ? 'Hide' : 'Show'} Overlay
            </button>
            <button 
              class="control-btn" 
              on:click={toggleSidebar}
              data-testid="toggle-sidebar"
            >
              {showSidebar ? 'Hide' : 'Show'} Sidebar
            </button>
            <button 
              class="control-btn" 
              on:click={handleExport}
              data-testid="export-clip-button"
            >
              Export Clip
            </button>
            <div class="detection-indicator">
              <span>Detections:</span>
              <span class="detection-count" data-testid="detection-count">
                {currentFaces.length}
              </span>
            </div>
          </div>

          <div class="video-container">
            {#if videoError}
              <div class="error-message" data-testid="video-error">
                <p>{errorMessage}</p>
              </div>
            {:else}
              <video
                bind:this={videoElement}
                src="/videos/{selectedVideo?.filename}"
                on:timeupdate={handleTimeUpdate}
                on:canplay={handleCanPlay}
                on:error={handleVideoError}
                data-testid="video-element"
              >
                <track kind="captions" src="" label="English" default />
              </video>
              <canvas
                bind:this={canvas}
                class="face-overlay"
                style:display={showOverlay ? 'block' : 'none'}
                on:mousemove={handleCanvasMouseMove}
                on:click={handleCanvasClick}
                on:mouseleave={handleCanvasMouseLeave}
                data-testid="face-overlay-canvas"
              ></canvas>
            {/if}
          </div>

          <div class="player-controls" data-testid="video-controls">
            <button 
              class="play-button" 
              on:click={togglePlay}
              aria-label={playing ? 'Pause' : 'Play'}
              data-testid="play-button"
            >
              {playing ? '⏸' : '▶'}
            </button>
            <div class="time-display" data-testid="video-time">
              {formatTime(currentTime)} / {formatTime(duration)}
            </div>
            <input
              type="range"
              class="seek-bar"
              min="0"
              max={duration || 0}
              step="0.1"
              bind:value={currentTime}
              on:input={seek}
              data-testid="video-timeline"
            />
            <div class="volume-control">🔊</div>
          </div>

          <div class="timeline-markers" data-testid="timeline-markers">
            {#if metadata}
              {#each metadata.timeline as frame}
                {#if frame.contestants && frame.contestants.length > 0}
                  <button
                    class="timeline-marker"
                    style="left: {(frame.timestamp / duration) * 100}%"
                    title={`${frame.contestants.length} faces at ${formatTime(frame.timestamp)}`}
                    on:click={() => jumpToTimestamp(frame.timestamp)}
                    on:keydown={(e) => e.key === 'Enter' && jumpToTimestamp(frame.timestamp)}
                    data-testid="timeline-marker"
                    aria-label={`Jump to ${formatTime(frame.timestamp)} with ${frame.contestants.length} faces`}
                  ></button>
                {/if}
              {/each}
            {/if}
          </div>
        </div>

        {#if showSidebar}
          <div class="face-sidebar" class:hidden={!showSidebar} class:sm:block={showSidebar} data-testid="face-recognition-sidebar">
            <div class="sidebar-header">
              <h3>Face Recognition</h3>
              <span class="face-count">{getFilteredFaces().length}</span>
            </div>

            <div class="recognition-stats" data-testid="recognition-stats">
              <h4>Recognition Stats</h4>
              <div class="stat-item">
                <span class="stat-label">Current Faces:</span>
                <span class="stat-value">{currentFaces.length}</span>
              </div>
              <div class="stat-item">
                <span class="stat-label">High Confidence:</span>
                <span class="stat-value">{currentFaces.filter(f => f.confidence >= 0.8).length}</span>
              </div>
              <div class="stat-item">
                <span class="stat-label">Total Contestants:</span>
                <span class="stat-value">{getUniqueContestants().length}</span>
              </div>
            </div>

            <div class="sidebar-controls">
              <div class="control-group">
                <label for="confidence-filter">Min Confidence:</label>
                <input
                  id="confidence-filter"
                  type="range"
                  min="0"
                  max="1"
                  step="0.1"
                  bind:value={confidenceFilter}
                  data-testid="confidence-filter"
                />
                <span>{Math.round(confidenceFilter * 100)}%</span>
              </div>

              <div class="control-group">
                <label for="contestant-search">Search:</label>
                <input
                  id="contestant-search"
                  type="text"
                  placeholder="Search contestants..."
                  bind:value={contestantSearch}
                  data-testid="contestant-search"
                />
              </div>
            </div>

            <div class="faces-list" data-testid="contestants-list">
              {#each getUniqueContestants() as contestant}
                <div class="contestant-item">
                  <div class="contestant-avatar">
                    {contestant.name.charAt(0)}
                  </div>
                  <div class="contestant-info">
                    <h4>{contestant.name}</h4>
                    <p>{contestant.nickname}</p>
                    <small>{contestant.appearances} appearances</small>
                  </div>
                </div>
              {/each}
            </div>

            <div class="faces-list" data-testid="face-gallery">
              {#each getFilteredFaces() as face}
                <button
                  class="face-card"
                  class:selected={selectedFace?.id === face.id}
                  class:highlighted={highlightedFace?.id === face.id}
                  on:click={() => selectFace(face)}
                  on:keydown={(e) => e.key === 'Enter' && selectFace(face)}
                  data-testid={highlightedFace?.id === face.id ? "highlighted-face" : "face-item"}
                >
                  <div class="face-info">
                    <div class="face-avatar">
                      {face.contestant_name.charAt(0)}
                    </div>
                    <div class="face-details">
                      <h4>{face.contestant_name}</h4>
                      <p>{face.contestant_nickname}</p>
                      <div class="confidence-bar">
                        <div
                          class="confidence-fill"
                          style="width: {face.confidence * 100}%; background-color: {getConfidenceColor(face.confidence)}"
                        ></div>
                        <span class="confidence-text">{Math.round(face.confidence * 100)}%</span>
                      </div>
                      <small>at {formatTime(face.timestamp)}</small>
                    </div>
                  </div>
                </button>
              {/each}
            </div>

            <div class="contestant-search-section">
              <h4>Search Contestants</h4>
              <div class="search-results" data-testid="search-results">
                {#each getUniqueContestants() as contestant}
                  <button
                    class="contestant-search-item"
                    on:click={() => searchAndJumpToContestant(contestant.name)}
                    data-testid="contestant-search-item"
                  >
                    <div class="contestant-avatar">
                      {contestant.name.charAt(0)}
                    </div>
                    <div class="contestant-info">
                      <span class="contestant-name">{contestant.name}</span>
                      <small>{contestant.appearances} appearances</small>
                    </div>
                  </button>
                {/each}
              </div>
            </div>

            {#if selectedFace}
              <div class="face-details-panel" data-testid="face-details">
                <h4>Face Details</h4>
                <div class="detail-grid">
                  <div class="detail-item">
                    <span class="detail-label">Name:</span>
                    <span>{selectedFace.contestant_name}</span>
                  </div>
                  <div class="detail-item">
                    <span class="detail-label">Nickname:</span>
                    <span>{selectedFace.contestant_nickname}</span>
                  </div>
                  <div class="detail-item">
                    <span class="detail-label">Confidence:</span>
                    <span style="color: {getConfidenceColor(selectedFace.confidence)}">
                      {Math.round(selectedFace.confidence * 100)}%
                    </span>
                  </div>
                  <div class="detail-item">
                    <span class="detail-label">Timestamp:</span>
                    <span>{formatTime(selectedFace.timestamp)}</span>
                  </div>
                  <div class="detail-item">
                    <span class="detail-label">Bounding Box:</span>
                    <span>
                      {Math.round(selectedFace.bounding_box.width)}×{Math.round(selectedFace.bounding_box.height)}
                    </span>
                  </div>
                </div>
                <button
                  class="jump-button"
                  on:click={() => jumpToTimestamp(selectedFace.timestamp)}
                >
                  Jump to Timestamp
                </button>
              </div>
            {/if}
          </div>
        {/if}
      </div>
    </div>

    {#if showExportDialog}
      <div class="export-dialog-overlay" data-testid="export-dialog">
        <div class="export-dialog">
          <h3>Export Video Clip</h3>
          <div class="export-form">
            <div class="form-group">
              <label for="start-time">Start Time (seconds):</label>
              <input
                id="start-time"
                type="number"
                min="0"
                max={duration}
                bind:value={exportStartTime}
                data-testid="start-time-input"
              />
            </div>
            <div class="form-group">
              <label for="end-time">End Time (seconds):</label>
              <input
                id="end-time"
                type="number"
                min="0"
                max={duration}
                bind:value={exportEndTime}
                data-testid="end-time-input"
              />
            </div>
            {#if isExporting}
              <div class="export-progress" data-testid="export-progress">
                <div class="progress-bar">
                  <div class="progress-fill" style="width: {exportProgress}%"></div>
                </div>
                <p>Exporting... {exportProgress}%</p>
              </div>
            {/if}
            <div class="export-actions">
              <button
                class="btn btn-primary"
                on:click={startExport}
                disabled={isExporting}
                data-testid="confirm-export-button"
              >
                {isExporting ? 'Exporting...' : 'Export'}
              </button>
              <button
                class="btn btn-secondary"
                on:click={closeExportDialog}
                disabled={isExporting}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      </div>
    {/if}

    <!-- Mobile Menu Button -->
    <button
      class="mobile-menu-button"
      class:visible={!showSidebar}
      on:click={toggleSidebar}
      data-testid="mobile-menu-button"
    >
      ☰
    </button>
  {/if}
</div>

<style>
  .video-player-page {
    max-width: 100%;
    padding: 1rem;
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

  .error-message {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: #ef4444;
    font-size: 1.2rem;
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
    flex-wrap: wrap;
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
    pointer-events: auto;
    z-index: 10;
  }

  .timeline-markers {
    position: relative;
    height: 20px;
    background-color: var(--background-color);
    border-top: 1px solid var(--border-color);
    overflow: hidden;
  }

  .timeline-marker {
    position: absolute;
    top: 50%;
    transform: translateY(-50%);
    width: 2px;
    height: 12px;
    background-color: var(--primary-color);
    cursor: pointer;
    transition: height 0.2s;
    border: none;
    padding: 0;
  }

  .timeline-marker:hover {
    height: 16px;
  }

  .timeline-marker:focus {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
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

  .sidebar-controls {
    padding: 1rem;
    background-color: var(--background-color);
    border-bottom: 1px solid var(--border-color);
  }

  .control-group {
    margin-bottom: 1rem;
  }

  .control-group label {
    display: block;
    margin-bottom: 0.5rem;
    font-size: 0.9rem;
    font-weight: 500;
    color: var(--text-color);
  }

  .control-group input[type="range"] {
    width: 100%;
    margin-bottom: 0.25rem;
  }

  .control-group input[type="text"] {
    width: 100%;
    padding: 0.5rem;
    border: 1px solid var(--border-color);
    border-radius: 0.375rem;
    background-color: var(--surface-color);
    color: var(--text-color);
  }

  .faces-list {
    flex: 1;
    overflow-y: auto;
    padding: 0.5rem;
    max-height: 400px;
  }

  .contestant-item {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.75rem;
    margin-bottom: 0.5rem;
    border: 1px solid var(--border-color);
    border-radius: 0.5rem;
  }

  .contestant-avatar {
    width: 2.5rem;
    height: 2.5rem;
    border-radius: 50%;
    background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-weight: 600;
    font-size: 1rem;
    flex-shrink: 0;
  }

  .contestant-info h4 {
    margin: 0;
    font-size: 0.9rem;
    font-weight: 600;
  }

  .contestant-info p {
    margin: 0;
    font-size: 0.8rem;
    color: var(--text-secondary);
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

  .face-card.highlighted {
    border-color: #f59e0b;
    background-color: rgba(245, 158, 11, 0.1);
    box-shadow: 0 0 0 2px #f59e0b;
  }

  .face-card:focus {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
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



  .detail-item span {
    font-size: 0.85rem;
    color: var(--text-color);
    font-weight: 600;
  }

  .jump-button {
    width: 100%;
    margin-top: 1rem;
    padding: 0.5rem;
    background-color: var(--primary-color);
    color: white;
    border: none;
    border-radius: 0.375rem;
    cursor: pointer;
    font-size: 0.9rem;
  }

  .jump-button:hover {
    background-color: var(--primary-hover);
  }

  /* Export Dialog */
  .export-dialog-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }

  .export-dialog {
    background-color: var(--surface-color);
    border-radius: 0.75rem;
    padding: 2rem;
    max-width: 400px;
    width: 90%;
    box-shadow: var(--shadow);
  }

  .export-dialog h3 {
    margin: 0 0 1.5rem 0;
    font-size: 1.5rem;
    font-weight: 600;
  }

  .export-form {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .form-group {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .form-group label {
    font-weight: 500;
    color: var(--text-color);
  }

  .form-group input {
    padding: 0.5rem;
    border: 1px solid var(--border-color);
    border-radius: 0.375rem;
    background-color: var(--surface-color);
    color: var(--text-color);
  }

  .export-actions {
    display: flex;
    gap: 1rem;
    margin-top: 1rem;
  }

  .btn {
    padding: 0.75rem 1.5rem;
    border: none;
    border-radius: 0.375rem;
    cursor: pointer;
    font-size: 1rem;
    transition: background-color 0.2s;
  }

  .btn-primary {
    background-color: var(--primary-color);
    color: white;
  }

  .btn-primary:hover {
    background-color: var(--primary-hover);
  }

  .btn-secondary {
    background-color: var(--border-color);
    color: var(--text-color);
  }

  .btn-secondary:hover {
    background-color: var(--text-secondary);
  }

  /* Export Progress */
  .export-progress {
    margin: 1rem 0;
  }

  .progress-bar {
    width: 100%;
    height: 8px;
    background-color: var(--border-color);
    border-radius: 4px;
    overflow: hidden;
    margin-bottom: 0.5rem;
  }

  .progress-fill {
    height: 100%;
    background-color: var(--primary-color);
    transition: width 0.3s ease;
  }

  /* Contestant Search */
  .contestant-search-section {
    margin-top: 1rem;
    padding-top: 1rem;
    border-top: 1px solid var(--border-color);
  }

  .contestant-search-item {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    width: 100%;
    padding: 0.75rem;
    border: 1px solid var(--border-color);
    border-radius: 0.5rem;
    background-color: var(--surface-color);
    cursor: pointer;
    transition: all 0.2s;
    margin-bottom: 0.5rem;
  }

  .contestant-search-item:hover {
    background-color: var(--border-color);
    border-color: var(--primary-color);
  }

  .contestant-search-item:focus {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
  }

  .contestant-name {
    font-weight: 600;
    color: var(--text-color);
  }

  /* Video Info */
  .video-info {
    margin-bottom: 1.5rem;
    padding: 1rem;
    background-color: var(--surface-color);
    border: 1px solid var(--border-color);
    border-radius: 0.5rem;
  }

  .video-info h2 {
    margin: 0 0 0.5rem 0;
    font-size: 1.5rem;
    color: var(--text-color);
  }

  .video-meta {
    color: var(--text-secondary);
    font-size: 0.9rem;
  }

  /* Detail Labels */
  .detail-label {
    font-weight: 600;
    color: var(--text-secondary);
  }

  /* Highlighted Face */
  .face-card.highlighted {
    border-color: #f59e0b;
    background-color: rgba(245, 158, 11, 0.1);
    box-shadow: 0 0 0 2px #f59e0b;
  }

  .face-card:focus {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
  }



  /* Recognition Stats */
  .recognition-stats {
    padding: 1rem;
    background-color: var(--background-color);
    border-radius: 0.5rem;
    margin-bottom: 1rem;
  }

  .recognition-stats h4 {
    margin: 0 0 0.5rem 0;
    font-size: 1rem;
    color: var(--text-color);
  }

  .stat-item {
    display: flex;
    justify-content: space-between;
    margin-bottom: 0.25rem;
    font-size: 0.9rem;
  }

  .stat-label {
    color: var(--text-secondary);
  }

  .stat-value {
    font-weight: 600;
    color: var(--text-color);
  }

  /* Mobile Menu Button */
  .mobile-menu-button {
    position: fixed;
    bottom: 1rem;
    right: 1rem;
    width: 3rem;
    height: 3rem;
    background-color: var(--primary-color);
    color: white;
    border: none;
    border-radius: 50%;
    font-size: 1.5rem;
    cursor: pointer;
    box-shadow: var(--shadow);
    display: none;
    z-index: 100;
  }

  .mobile-menu-button.visible {
    display: flex;
    align-items: center;
    justify-content: center;
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

    .face-sidebar {
      display: none;
    }

    .face-sidebar.hidden {
      display: none;
    }

    .face-sidebar.sm\:block {
      display: block;
      position: fixed;
      top: 0;
      right: 0;
      width: 90%;
      max-width: 400px;
      height: 100vh;
      background-color: var(--surface-color);
      border-left: 1px solid var(--border-color);
      z-index: 1000;
      overflow-y: auto;
      padding: 1rem;
    }

    .mobile-menu-button {
      display: flex;
    }

    .mobile-menu-button.visible {
      display: flex;
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

    .export-dialog {
      margin: 1rem;
      padding: 1.5rem;
    }
  }

  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }
</style>
