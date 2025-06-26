<script>
  import { onMount, onDestroy } from 'svelte';
  import { videoStore } from '../stores/video.js';
  import { processingStore, resultsStore } from '../stores/processing.js';
  import { processingUpdates } from '../stores/websocket.js';
  import videojs from 'video.js';

  let videoContainer;
  let overlayCanvas;
  let player = null;
  let ctx = null;
  
  let selectedVideo = null;
  let videoInfo = null;
  let currentFrameResults = [];
  let processingActive = false;

  // Subscribe to stores
  videoStore.subscribe(state => {
    selectedVideo = state.selectedVideo;
    videoInfo = state.videoInfo;
  });

  processingStore.subscribe(state => {
    processingActive = state.isProcessing;
  });

  resultsStore.subscribe(state => {
    currentFrameResults = state.currentFrameResults;
  });

  // Subscribe to real-time processing updates
  processingUpdates.subscribe(update => {
    if (update.frameData) {
      drawFaceOverlays(update.frameData);
    }
  });

  onMount(() => {
    initializeVideoPlayer();
    initializeCanvas();
  });

  onDestroy(() => {
    if (player) {
      player.dispose();
    }
  });

  function initializeVideoPlayer() {
    if (!videoContainer) return;

    const videoElement = videoContainer.querySelector('video');
    
    player = videojs(videoElement, {
      controls: true,
      responsive: true,
      fluid: true,
      playbackRates: [0.25, 0.5, 1, 1.25, 1.5, 2],
      plugins: {
        // Custom plugins can be added here
      }
    });

    // Add event listeners for frame-accurate processing
    player.ready(() => {
      console.log('Video.js player ready');
      
      // Set up requestVideoFrameCallback for precise frame correlation
      if (videoElement.requestVideoFrameCallback) {
        const updateFrame = (now, metadata) => {
          if (processingActive) {
            // Correlate video frame with face detection results
            correlateFrameWithResults(metadata);
          }
          
          videoElement.requestVideoFrameCallback(updateFrame);
        };
        
        videoElement.requestVideoFrameCallback(updateFrame);
      }
    });

    player.on('loadeddata', () => {
      setupCanvasOverlay();
    });

    player.on('timeupdate', () => {
      updateCanvasPosition();
    });

    player.on('resize', () => {
      resizeCanvas();
    });
  }

  function initializeCanvas() {
    if (overlayCanvas) {
      ctx = overlayCanvas.getContext('2d');
      
      // Optimize canvas for performance
      ctx.imageSmoothingEnabled = false;
      ctx.globalCompositeOperation = 'source-over';
    }
  }

  function setupCanvasOverlay() {
    if (!player || !overlayCanvas) return;

    const videoElement = player.el().querySelector('video');
    const playerElement = player.el();

    // Position canvas over video
    const updateCanvasPosition = () => {
      const rect = videoElement.getBoundingClientRect();
      const playerRect = playerElement.getBoundingClientRect();
      
      overlayCanvas.style.position = 'absolute';
      overlayCanvas.style.left = `${rect.left - playerRect.left}px`;
      overlayCanvas.style.top = `${rect.top - playerRect.top}px`;
      overlayCanvas.width = rect.width;
      overlayCanvas.height = rect.height;
    };

    updateCanvasPosition();
    
    // Update on resize
    const resizeObserver = new ResizeObserver(updateCanvasPosition);
    resizeObserver.observe(playerElement);
  }

  function resizeCanvas() {
    setTimeout(setupCanvasOverlay, 100);
  }

  function updateCanvasPosition() {
    setupCanvasOverlay();
  }

  function correlateFrameWithResults(metadata) {
    // Use metadata.presentationTime and metadata.rtpTimestamp for precise correlation
    const currentTime = metadata.presentationTime || performance.now();
    
    // This would correlate with the real-time processing results
    // Based on timestamp matching
  }

  function drawFaceOverlays(frameData) {
    if (!ctx || !overlayCanvas) return;

    // Clear previous overlays
    ctx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);

    if (!frameData.faces || frameData.faces.length === 0) return;

    // Calculate scaling factors
    const videoElement = player?.el()?.querySelector('video');
    if (!videoElement) return;

    const rect = videoElement.getBoundingClientRect();
    const scaleX = rect.width / (videoElement.videoWidth || rect.width);
    const scaleY = rect.height / (videoElement.videoHeight || rect.height);

    // Draw face bounding boxes and labels
    frameData.faces.forEach(face => {
      drawFaceBox(face, scaleX, scaleY);
    });

    // Draw frame statistics
    drawFrameStats(frameData);
  }

  function drawFaceBox(face, scaleX, scaleY) {
    const bbox = face.b || face.bbox;
    if (!bbox || bbox.length !== 4) return;

    const [x1, y1, x2, y2] = bbox;
    const scaledX = x1 * scaleX;
    const scaledY = y1 * scaleY;
    const scaledWidth = (x2 - x1) * scaleX;
    const scaledHeight = (y2 - y1) * scaleY;

    // Determine color based on recognition status
    const isMatched = face.m || face.matched;
    const color = isMatched ? '#00ff00' : '#ff0000';
    const confidence = face.r || face.recognition_confidence || face.c || face.detection_confidence;
    const name = face.n || face.contestant_name || 'Unknown';

    // Draw bounding box
    ctx.strokeStyle = color;
    ctx.lineWidth = 3;
    ctx.strokeRect(scaledX, scaledY, scaledWidth, scaledHeight);

    // Draw label background
    const label = isMatched ? `${name} (${(confidence * 100).toFixed(1)}%)` : `Unknown (${(confidence * 100).toFixed(1)}%)`;
    const labelMetrics = ctx.measureText(label);
    const labelHeight = 20;
    const labelPadding = 8;

    ctx.fillStyle = color;
    ctx.fillRect(
      scaledX, 
      scaledY - labelHeight - labelPadding, 
      labelMetrics.width + labelPadding * 2, 
      labelHeight + labelPadding
    );

    // Draw label text
    ctx.fillStyle = '#ffffff';
    ctx.font = '14px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
    ctx.fontWeight = 'bold';
    ctx.fillText(label, scaledX + labelPadding, scaledY - labelPadding);
  }

  function drawFrameStats(frameData) {
    const stats = frameData.stats;
    if (!stats) return;

    // Draw frame statistics in top-left corner
    const statsText = [
      `Frame: ${frameData.f || frameData.frame_number || 0}`,
      `Faces: ${frameData.faces?.length || 0}`,
      `FPS: ${(stats.fps || 0).toFixed(1)}`,
      `Total Detected: ${stats.total_faces || 0}`,
      `Total Recognized: ${stats.recognized || 0}`
    ];

    // Background
    const lineHeight = 18;
    const padding = 12;
    const maxWidth = Math.max(...statsText.map(text => ctx.measureText(text).width));
    
    ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
    ctx.fillRect(10, 10, maxWidth + padding * 2, statsText.length * lineHeight + padding * 2);

    // Text
    ctx.fillStyle = '#ffffff';
    ctx.font = '12px monospace';
    
    statsText.forEach((text, index) => {
      ctx.fillText(text, 10 + padding, 10 + padding + lineHeight + (index * lineHeight));
    });
  }

  function loadVideo(videoPath) {
    if (player && videoPath) {
      player.src({
        src: videoPath,
        type: 'video/mp4'
      });
    }
  }

  // Reactive statement to load video when selected
  $: if (selectedVideo && videoInfo && player) {
    const videoPath = `/api/videos/${encodeURIComponent(selectedVideo)}/stream`;
    loadVideo(videoPath);
  }
</script>

<div class="video-player-container" bind:this={videoContainer}>
  {#if selectedVideo && videoInfo}
    <div class="video-wrapper">
      <video
        class="video-js vjs-default-skin"
        controls
        preload="auto"
        data-setup="{{}}"
      >
        <track kind="captions" label="No captions available" />
        <p class="vjs-no-js">
          To view this video please enable JavaScript, and consider upgrading to a web browser that
          <a href="https://videojs.com/html5-video-support/" target="_blank">supports HTML5 video</a>.
        </p>
      </video>
      
      <!-- Face detection overlay canvas -->
      <canvas 
        bind:this={overlayCanvas}
        class="face-overlay-canvas"
        class:active={processingActive}
      ></canvas>
    </div>
    
    <div class="video-info">
      <h3>{videoInfo.filename}</h3>
      <div class="video-metadata">
        <span>📏 {videoInfo.width}×{videoInfo.height}</span>
        <span>⏱️ {videoInfo.duration_formatted || 'Unknown'}</span>
        <span>🎞️ {videoInfo.fps?.toFixed(1) || 0} FPS</span>
        <span>💾 {videoInfo.file_size_mb} MB</span>
      </div>
    </div>
  {:else}
    <div class="no-video">
      <div class="no-video-content">
        <h3>No Video Selected</h3>
        <p>Please select a video from the control panel to start processing.</p>
      </div>
    </div>
  {/if}
</div>

<style>
  .video-player-container {
    height: 100%;
    display: flex;
    flex-direction: column;
    background: #000;
    border-radius: 8px;
    overflow: hidden;
  }

  .video-wrapper {
    flex: 1;
    position: relative;
    min-height: 0;
  }

  .face-overlay-canvas {
    pointer-events: none;
    z-index: 10;
    opacity: 0;
    transition: opacity 0.3s ease;
  }

  .face-overlay-canvas.active {
    opacity: 1;
  }

  .video-info {
    padding: 16px;
    background: rgba(0, 0, 0, 0.8);
    border-top: 1px solid #333;
  }

  .video-info h3 {
    margin: 0 0 8px 0;
    font-size: 1rem;
    color: #ffffff;
    font-weight: 600;
  }

  .video-metadata {
    display: flex;
    gap: 16px;
    font-size: 0.85rem;
    color: #b2bec3;
  }

  .video-metadata span {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .no-video {
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, #2d3436 0%, #636e72 100%);
  }

  .no-video-content {
    text-align: center;
    color: #b2bec3;
  }

  .no-video-content h3 {
    margin: 0 0 8px 0;
    font-size: 1.25rem;
    color: #ffffff;
  }

  .no-video-content p {
    margin: 0;
    font-size: 0.9rem;
  }

  /* Video.js custom styling */
  :global(.video-js) {
    width: 100% !important;
    height: 100% !important;
    background: #000;
  }

  :global(.vjs-control-bar) {
    background: rgba(0, 0, 0, 0.8);
    backdrop-filter: blur(8px);
  }

  :global(.vjs-play-progress) {
    background: #74b9ff;
  }

  :global(.vjs-volume-level) {
    background: #74b9ff;
  }

  /* Responsive design */
  @media (max-width: 768px) {
    .video-metadata {
      flex-direction: column;
      gap: 8px;
    }

    .video-info {
      padding: 12px;
    }
  }
</style>