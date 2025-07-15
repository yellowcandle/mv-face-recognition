<script lang="ts">
  import { onMount } from 'svelte';
  import { parseMetadata, type DetectedFace, type ParsedMetadata } from '$lib/utils/metadata.js';
  import { createVideoSynchronizer, type VideoTimestampSynchronizer, type TimestampSyncResult } from '$lib/utils/synchronization.js';
  
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
  let currentFaces: DetectedFace[] = [];
  let selectedFace: DetectedFace | null = null;
  let metadata: any = null;
  let parsedMetadata: ParsedMetadata | null = null;
  let synchronizer: VideoTimestampSynchronizer | null = null;
  let animationId: number;
  let resizeObserver: ResizeObserver;
  let hoveredFace: DetectedFace | null = null;
  let mousePosition = { x: 0, y: 0 };
  let syncStats = {
    averageLatency: 0,
    frameDrops: 0,
    cacheHitRate: 0,
    confidence: 0
  };
  let performanceMonitoring = true;
  
  onMount(async () => {
    await loadVideos();
    loading = false;
    
    // Setup resize observer for canvas scaling
    if (typeof ResizeObserver !== 'undefined') {
      resizeObserver = new ResizeObserver(() => {
        if (videoElement && canvas) {
          updateCanvasSize();
        }
      });
    }
    
    return () => {
      if (resizeObserver) {
        resizeObserver.disconnect();
      }
      if (animationId) {
        cancelAnimationFrame(animationId);
      }
    };
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
    
    // Stop existing synchronizer
    if (synchronizer) {
      synchronizer.stop();
      synchronizer = null;
    }
    
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
        processing_info: {
          processing_interval: 5,
          interpolation_enabled: true,
          total_processed_frames: Math.floor(video.duration * 30 / 5),
          total_interpolated_frames: Math.floor(video.duration * 30 * 0.8)
        },
        timeline: generateMockTimeline(video.duration)
      };
    }
    
    // Parse metadata and initialize synchronizer
    if (metadata) {
      parsedMetadata = parseMetadata(metadata);
      
      if (parsedMetadata.isValid) {
        // Create advanced synchronizer with performance optimizations
        synchronizer = createVideoSynchronizer({
          toleranceSeconds: 0.5,
          interpolationEnabled: true,
          preloadBufferSeconds: performanceMonitoring ? 15 : 10,
          maxCacheSize: performanceMonitoring ? 300 : 200
        });
        
        // Initialize synchronizer with parsed metadata
        const initialized = synchronizer.initialize(parsedMetadata);
        if (initialized) {
          console.log('Advanced synchronizer initialized successfully');
          
          // Setup synchronization callback for face updates
          synchronizer.onSync((result: TimestampSyncResult) => {
            currentFaces = result.faces;
            syncStats.confidence = result.confidence;
            
            // Update performance stats if monitoring is enabled
            if (performanceMonitoring) {
              updatePerformanceStats(result);
            }
          });
        } else {
          console.error('Failed to initialize synchronizer');
        }
      } else {
        console.error('Invalid metadata:', parsedMetadata.errors);
      }
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
      updateCanvasSize();
      ctx = canvas.getContext('2d');
      
      // Start observing video element for size changes
      if (resizeObserver) {
        resizeObserver.observe(videoElement);
      }
      
      startAnimation();
    }
  }
  
  function updateCanvasSize() {
    if (!canvas || !videoElement) return;
    
    // Get the displayed size of the video element
    const rect = videoElement.getBoundingClientRect();
    const displayWidth = rect.width;
    const displayHeight = rect.height;
    
    // Get device pixel ratio for crisp rendering
    const devicePixelRatio = window.devicePixelRatio || 1;
    
    // Set canvas size to match displayed video size
    canvas.style.width = displayWidth + 'px';
    canvas.style.height = displayHeight + 'px';
    
    // Scale canvas for device pixel ratio
    canvas.width = displayWidth * devicePixelRatio;
    canvas.height = displayHeight * devicePixelRatio;
    
    // Scale the drawing context to match device pixel ratio
    if (ctx) {
      ctx.scale(devicePixelRatio, devicePixelRatio);
    }
  }
  
  function getVideoScaleFactors() {
    if (!videoElement || !canvas) return { scaleX: 1, scaleY: 1 };
    
    // Get video's natural dimensions
    const videoWidth = videoElement.videoWidth || 1920;
    const videoHeight = videoElement.videoHeight || 1080;
    
    // Get displayed dimensions
    const rect = videoElement.getBoundingClientRect();
    const displayWidth = rect.width;
    const displayHeight = rect.height;
    
    // Calculate how the video is actually displayed (considering object-fit: contain)
    const videoAspect = videoWidth / videoHeight;
    const displayAspect = displayWidth / displayHeight;
    
    let actualVideoWidth, actualVideoHeight;
    let offsetX = 0, offsetY = 0;
    
    if (videoAspect > displayAspect) {
      // Video is wider - letterboxed top/bottom
      actualVideoWidth = displayWidth;
      actualVideoHeight = displayWidth / videoAspect;
      offsetY = (displayHeight - actualVideoHeight) / 2;
    } else {
      // Video is taller - letterboxed left/right
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
  
  function startAnimation() {
    let lastFrameTime = 0;
    const targetFPS = 60;
    const frameInterval = 1000 / targetFPS;
    
    function animate(currentTime: number) {
      // Throttle to 60fps for smooth performance
      if (currentTime - lastFrameTime >= frameInterval) {
        if (showOverlay && ctx && videoElement && metadata) {
          updateFaceOverlay();
        }
        lastFrameTime = currentTime;
      }
      animationId = requestAnimationFrame(animate);
    }
    animationId = requestAnimationFrame(animate);
  }
  
  function updateFaceOverlay() {
    if (!ctx || !canvas) return;
    
    // Clear canvas using display dimensions (since context is scaled)
    const rect = videoElement?.getBoundingClientRect();
    if (rect) {
      ctx.clearRect(0, 0, rect.width, rect.height);
    }
    
    // Use advanced synchronizer if available, fallback to basic lookup
    if (synchronizer && videoElement) {
      const currentTimestamp = videoElement.currentTime;
      
      // Sync to current timestamp - this will trigger the callback
      // which updates currentFaces automatically
      synchronizer.syncToTimestamp(currentTimestamp);
      
      // Draw all current faces
      currentFaces.forEach((face: DetectedFace) => {
        drawFaceBoundingBox(face);
      });
    } else if (metadata) {
      // Fallback to basic synchronization for compatibility
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
    
    // Get proper scaling factors based on video display
    const scaleFactors = getVideoScaleFactors();
    
    const scaledX = x * scaleFactors.scaleX + scaleFactors.offsetX;
    const scaledY = y * scaleFactors.scaleY + scaleFactors.offsetY;
    const scaledWidth = width * scaleFactors.scaleX;
    const scaledHeight = height * scaleFactors.scaleY;
    
    // Check if this face is hovered or selected
    const isHovered = hoveredFace?.id === face.id;
    const isSelected = selectedFace?.id === face.id;
    
    // Enhanced confidence-based colors with alpha for better visibility
    let color = '#ef4444'; // Red for low confidence (< 0.5)
    let alpha = 0.8;
    let lineWidth = 3;
    
    if (confidence >= 0.8) {
      color = '#10b981'; // Green for high confidence
      alpha = 0.9;
    } else if (confidence >= 0.7) {
      color = '#10b981'; // Green for good confidence  
      alpha = 0.8;
    } else if (confidence >= 0.5) {
      color = '#f59e0b'; // Orange for medium confidence
      alpha = 0.8;
    } else {
      color = '#ef4444'; // Red for low confidence
      alpha = 0.7;
    }
    
    // Enhance visual feedback for hover and selection states
    if (isSelected) {
      alpha = 1.0;
      lineWidth = 4;
      color = '#2563eb'; // Blue for selected
    } else if (isHovered) {
      alpha = 0.95;
      lineWidth = 4;
      // Keep original color but make it brighter
    }
    
    // Save context state
    ctx.save();
    
    // Set global alpha for the entire face overlay
    ctx.globalAlpha = alpha;
    
    // Draw main bounding box with rounded corners effect
    ctx.strokeStyle = color;
    ctx.lineWidth = lineWidth;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.strokeRect(scaledX, scaledY, scaledWidth, scaledHeight);
    
    // Draw enhanced corner markers
    const cornerSize = Math.min(25, Math.min(scaledWidth, scaledHeight) * 0.15);
    const cornerThickness = 4;
    
    ctx.fillStyle = color;
    ctx.globalAlpha = 1.0; // Full opacity for corners
    
    // Top-left corner
    ctx.fillRect(scaledX - cornerThickness/2, scaledY - cornerThickness/2, cornerSize, cornerThickness);
    ctx.fillRect(scaledX - cornerThickness/2, scaledY - cornerThickness/2, cornerThickness, cornerSize);
    
    // Top-right corner
    ctx.fillRect(scaledX + scaledWidth - cornerSize + cornerThickness/2, scaledY - cornerThickness/2, cornerSize, cornerThickness);
    ctx.fillRect(scaledX + scaledWidth - cornerThickness/2, scaledY - cornerThickness/2, cornerThickness, cornerSize);
    
    // Bottom-left corner
    ctx.fillRect(scaledX - cornerThickness/2, scaledY + scaledHeight - cornerThickness/2, cornerSize, cornerThickness);
    ctx.fillRect(scaledX - cornerThickness/2, scaledY + scaledHeight - cornerSize + cornerThickness/2, cornerThickness, cornerSize);
    
    // Bottom-right corner
    ctx.fillRect(scaledX + scaledWidth - cornerSize + cornerThickness/2, scaledY + scaledHeight - cornerThickness/2, cornerSize, cornerThickness);
    ctx.fillRect(scaledX + scaledWidth - cornerThickness/2, scaledY + scaledHeight - cornerSize + cornerThickness/2, cornerThickness, cornerSize);
    
    // Draw enhanced label with better styling
    if (confidence >= 0.7) { // Only show labels for confident detections
      const label = `${face.contestant_name} (${Math.round(confidence * 100)}%)`;
      ctx.font = 'bold 14px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
      
      const textMetrics = ctx.measureText(label);
      const labelWidth = textMetrics.width + 16;
      const labelHeight = 24;
      const labelX = Math.max(scaledX, Math.min(scaledX, scaleFactors.actualVideoWidth - labelWidth));
      const labelY = scaledY > labelHeight + 5 ? scaledY - 5 : scaledY + scaledHeight + labelHeight;
      
      // Draw label background with rounded corners
      ctx.fillStyle = color;
      ctx.globalAlpha = 0.9;
      ctx.fillRect(labelX, labelY - labelHeight, labelWidth, labelHeight);
      
      // Add subtle shadow effect
      ctx.fillStyle = 'rgba(0, 0, 0, 0.3)';
      ctx.fillRect(labelX + 2, labelY - labelHeight + 2, labelWidth, labelHeight);
      
      // Draw label background again on top
      ctx.fillStyle = color;
      ctx.fillRect(labelX, labelY - labelHeight, labelWidth, labelHeight);
      
      // Draw label text
      ctx.fillStyle = 'white';
      ctx.globalAlpha = 1.0;
      ctx.textAlign = 'left';
      ctx.textBaseline = 'middle';
      ctx.fillText(label, labelX + 8, labelY - labelHeight/2);
    }
    
    // Restore context state
    ctx.restore();
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
  
  // Interactive canvas functions
  function handleCanvasMouseMove(event: MouseEvent) {
    if (!canvas || !currentFaces.length) return;
    
    const rect = canvas.getBoundingClientRect();
    mousePosition.x = event.clientX - rect.left;
    mousePosition.y = event.clientY - rect.top;
    
    // Check if mouse is over any face bounding box
    const previousHoveredFace = hoveredFace;
    hoveredFace = null;
    
    for (const face of currentFaces) {
      if (isPointInFaceBoundingBox(mousePosition, face)) {
        hoveredFace = face;
        break;
      }
    }
    
    // Update cursor style
    if (hoveredFace) {
      canvas.style.cursor = 'pointer';
    } else {
      canvas.style.cursor = 'default';
    }
    
    // Trigger redraw if hover state changed
    if (hoveredFace?.id !== previousHoveredFace?.id) {
      // Force a redraw on next animation frame
    }
  }
  
  function handleCanvasClick(event: MouseEvent) {
    if (!canvas || !currentFaces.length) return;
    
    const rect = canvas.getBoundingClientRect();
    const clickPosition = {
      x: event.clientX - rect.left,
      y: event.clientY - rect.top
    };
    
    // Check if click is on any face bounding box
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
    
    return point.x >= scaledX && 
           point.x <= scaledX + scaledWidth && 
           point.y >= scaledY && 
           point.y <= scaledY + scaledHeight;
  }

  // Performance monitoring functions
  let performanceStats = {
    frameCount: 0,
    lastFrameTime: 0,
    frameDrops: 0,
    averageLatency: 0,
    latencyMeasurements: [] as number[]
  };

  function updatePerformanceStats(result: TimestampSyncResult) {
    if (!performanceMonitoring) return;
    
    const now = performance.now();
    const targetTimestamp = result.timestamp * 1000; // Convert to milliseconds
    const latency = Math.abs(now - targetTimestamp);
    
    // Track latency measurements
    performanceStats.latencyMeasurements.push(latency);
    if (performanceStats.latencyMeasurements.length > 100) {
      performanceStats.latencyMeasurements.shift(); // Keep only last 100 measurements
    }
    
    // Calculate average latency
    const sum = performanceStats.latencyMeasurements.reduce((a, b) => a + b, 0);
    performanceStats.averageLatency = sum / performanceStats.latencyMeasurements.length;
    
    // Track frame drops (if time between frames is too long)
    if (performanceStats.lastFrameTime > 0) {
      const timeDelta = now - performanceStats.lastFrameTime;
      const expectedFrameTime = 1000 / 60; // 60fps target
      
      if (timeDelta > expectedFrameTime * 1.5) {
        performanceStats.frameDrops++;
      }
    }
    
    performanceStats.frameCount++;
    performanceStats.lastFrameTime = now;
    
    // Update sync stats for UI display
    syncStats.averageLatency = performanceStats.averageLatency;
    syncStats.frameDrops = performanceStats.frameDrops;
    syncStats.confidence = result.confidence;
    
    // Get cache hit rate from synchronizer if available
    if (synchronizer) {
      const stats = synchronizer.getStats();
      syncStats.cacheHitRate = stats.cacheHitRate;
    }
  }

  function resetPerformanceStats() {
    performanceStats = {
      frameCount: 0,
      lastFrameTime: 0,
      frameDrops: 0,
      averageLatency: 0,
      latencyMeasurements: []
    };
    
    syncStats = {
      averageLatency: 0,
      frameDrops: 0,
      cacheHitRate: 0,
      confidence: 0
    };
  }

  function togglePerformanceMonitoring() {
    performanceMonitoring = !performanceMonitoring;
    
    if (performanceMonitoring) {
      resetPerformanceStats();
    }
    
    // Update synchronizer options if available
    if (synchronizer) {
      synchronizer.updateOptions({
        preloadBufferSeconds: performanceMonitoring ? 15 : 10,
        maxCacheSize: performanceMonitoring ? 300 : 200
      });
    }
  }

  // Enhanced video player lifecycle management
  function handleVideoPlay() {
    playing = true;
    
    // Start synchronizer if available
    if (synchronizer && videoElement) {
      synchronizer.start(videoElement);
      console.log('Advanced synchronizer started');
    }
  }

  function handleVideoPause() {
    playing = false;
    
    // Stop synchronizer to save resources
    if (synchronizer) {
      synchronizer.stop();
      console.log('Advanced synchronizer stopped');
    }
  }

  function handleVideoSeeked() {
    // Clear cache and preload around new position
    if (synchronizer && videoElement) {
      const currentTime = videoElement.currentTime;
      synchronizer.clearCache();
      synchronizer.preloadTimeRange(
        Math.max(0, currentTime - 5),
        Math.min(duration, currentTime + 15)
      );
    }
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
            <button class="control-btn" on:click={togglePerformanceMonitoring} class:active={performanceMonitoring}>
              📊 Performance
            </button>
          </div>
          
          <!-- Video Container -->
          <div class="video-container">
            {#if selectedVideo}
              <video
                bind:this={videoElement}
                src="/videos/{selectedVideo.filename}"
                on:timeupdate={handleTimeUpdate}
                on:canplay={handleCanPlay}
                on:play={handleVideoPlay}
                on:pause={handleVideoPause}
                on:seeked={handleVideoSeeked}
                preload="metadata"
                crossorigin="anonymous"
              >
                Your browser does not support the video tag.
              </video>
              
              {#if showOverlay}
                <canvas
                  bind:this={canvas}
                  class="face-overlay"
                  on:mousemove={handleCanvasMouseMove}
                  on:click={handleCanvasClick}
                  on:mouseleave={handleCanvasMouseLeave}
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
                  {#if selectedFace.interpolated}
                    <div class="detail-item">
                      <label>Type:</label>
                      <span class="interpolated-badge">Interpolated</span>
                    </div>
                  {/if}
                </div>
              </div>
            {/if}
            
            <!-- Performance Monitoring Panel -->
            {#if performanceMonitoring}
              <div class="performance-panel">
                <h4>Synchronization Performance</h4>
                <div class="performance-stats">
                  <div class="stat-item">
                    <label>Avg Latency:</label>
                    <span class="stat-value" class:good={syncStats.averageLatency < 16} class:warning={syncStats.averageLatency >= 16 && syncStats.averageLatency < 33} class:bad={syncStats.averageLatency >= 33}>
                      {syncStats.averageLatency.toFixed(1)}ms
                    </span>
                  </div>
                  <div class="stat-item">
                    <label>Frame Drops:</label>
                    <span class="stat-value" class:good={syncStats.frameDrops === 0} class:warning={syncStats.frameDrops < 5} class:bad={syncStats.frameDrops >= 5}>
                      {syncStats.frameDrops}
                    </span>
                  </div>
                  <div class="stat-item">
                    <label>Cache Hit Rate:</label>
                    <span class="stat-value" class:good={syncStats.cacheHitRate > 0.8} class:warning={syncStats.cacheHitRate > 0.6} class:bad={syncStats.cacheHitRate <= 0.6}>
                      {Math.round(syncStats.cacheHitRate * 100)}%
                    </span>
                  </div>
                  <div class="stat-item">
                    <label>Sync Confidence:</label>
                    <span class="stat-value" class:good={syncStats.confidence > 0.8} class:warning={syncStats.confidence > 0.6} class:bad={syncStats.confidence <= 0.6}>
                      {Math.round(syncStats.confidence * 100)}%
                    </span>
                  </div>
                  {#if synchronizer}
                    <div class="stat-item">
                      <label>Synchronizer:</label>
                      <span class="stat-value good">Advanced</span>
                    </div>
                  {:else}
                    <div class="stat-item">
                      <label>Synchronizer:</label>
                      <span class="stat-value warning">Basic</span>
                    </div>
                  {/if}
                </div>
                <div class="performance-actions">
                  <button class="small-btn" on:click={resetPerformanceStats}>
                    Reset Stats
                  </button>
                  {#if synchronizer}
                    <button class="small-btn" on:click={() => synchronizer?.clearCache()}>
                      Clear Cache
                    </button>
                  {/if}
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
    pointer-events: auto;
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

  .interpolated-badge {
    background: #f59e0b;
    color: white;
    padding: 0.125rem 0.5rem;
    border-radius: 12px;
    font-size: 0.75rem;
    font-weight: 600;
  }

  /* Performance Monitoring Panel */
  .performance-panel {
    margin-top: 1rem;
    padding: 1rem;
    background: rgba(59, 130, 246, 0.1);
    border-radius: 8px;
    border: 1px solid rgba(59, 130, 246, 0.3);
  }

  .performance-panel h4 {
    margin: 0 0 1rem 0;
    color: #60a5fa;
    font-size: 0.9rem;
    font-weight: 600;
  }

  .performance-stats {
    display: grid;
    gap: 0.5rem;
    margin-bottom: 1rem;
  }

  .stat-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.25rem 0;
  }

  .stat-item label {
    font-size: 0.8rem;
    color: rgba(255, 255, 255, 0.7);
    font-weight: 500;
  }

  .stat-value {
    font-size: 0.8rem;
    font-weight: 600;
    padding: 0.125rem 0.5rem;
    border-radius: 4px;
    background: rgba(255, 255, 255, 0.1);
  }

  .stat-value.good {
    background: rgba(16, 185, 129, 0.2);
    color: #10b981;
  }

  .stat-value.warning {
    background: rgba(245, 158, 11, 0.2);
    color: #f59e0b;
  }

  .stat-value.bad {
    background: rgba(239, 68, 68, 0.2);
    color: #ef4444;
  }

  .performance-actions {
    display: flex;
    gap: 0.5rem;
  }

  .small-btn {
    padding: 0.25rem 0.5rem;
    font-size: 0.75rem;
    background: rgba(255, 255, 255, 0.1);
    color: white;
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .small-btn:hover {
    background: rgba(255, 255, 255, 0.2);
    border-color: rgba(255, 255, 255, 0.3);
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