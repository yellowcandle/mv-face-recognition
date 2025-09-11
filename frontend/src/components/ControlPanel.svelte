<script>
  import { onMount } from 'svelte';
  import { videoStore, videoManager } from '../stores/video.js';
  import { processingStore } from '../stores/processing.js';
  import { websocketStore } from '../stores/websocket.js';

  let availableVideos = [];
  let selectedVideo = null;
  let videoInfo = null;
  let isProcessing = false;
  let loading = false;
  let error = null;

  // Processing parameters
  let parameters = {
    detectionThreshold: 0.5,
    similarityThreshold: 0.15,
    frameSkip: 5
  };

  // Time range controls
  let startTime = 0;
  let endTime = null;
  let useTimeRange = false;

  // Subscribe to stores
  videoStore.subscribe(state => {
    availableVideos = state.availableVideos;
    selectedVideo = state.selectedVideo;
    videoInfo = state.videoInfo;
    loading = state.loading;
    error = state.error;
  });

  processingStore.subscribe(state => {
    isProcessing = state.isProcessing;
    parameters = { ...state.parameters };
    startTime = state.startTime;
    endTime = state.endTime;
  });

  onMount(() => {
    // Load available videos on mount
    videoStore.loadVideos();
  });

  async function handleVideoSelect(event) {
    const videoName = event.target.value;
    if (videoName) {
      await videoStore.selectVideo(videoName);
    }
  }

  async function handleStartProcessing() {
    if (!selectedVideo) {
      alert('Please select a video first');
      return;
    }

    try {
      // Update parameters first
      await videoStore.updateParameters(parameters);

      // Determine time range
      const processingStartTime = useTimeRange ? startTime : 0;
      const processingEndTime = useTimeRange ? endTime : null;

      // Start WebSocket processing
      const success = websocketStore.startProcessing(
        selectedVideo, 
        processingStartTime, 
        processingEndTime
      );

      if (success) {
        // Also start via API for background processing
        await videoStore.startProcessing(selectedVideo, processingStartTime, processingEndTime);
      } else {
        alert('Failed to start processing - WebSocket not connected');
      }
    } catch (error) {
      console.error('Error starting processing:', error);
      alert(`Failed to start processing: ${error.message}`);
    }
  }

  function handleStopProcessing() {
    videoStore.stopProcessing();
  }

  function handleParameterChange(parameter, value) {
    parameters[parameter] = value;
    
    // Update parameter in real-time if processing is active
    if (isProcessing) {
      websocketStore.updateParameter(parameter, value);
    }
  }

  function handleTimeRangeToggle() {
    if (!useTimeRange) {
      startTime = 0;
      endTime = videoInfo?.duration_seconds || null;
    }
  }

  function formatTime(seconds) {
    if (!seconds) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  }
</script>

<div class="control-panel">
  <h3>🎮 Processing Controls</h3>

  <!-- Video Selection -->
  <div class="control-section">
    <h4>Video Selection</h4>
    
    <div class="video-select-wrapper">
      <select 
        bind:value={selectedVideo} 
        on:change={handleVideoSelect}
        disabled={loading || isProcessing}
        class="video-select"
      >
        <option value="">Select a video...</option>
        {#each availableVideos as video}
          <option value={video}>{video}</option>
        {/each}
      </select>
      
      {#if loading}
        <div class="loading-indicator">Loading...</div>
      {/if}
    </div>

    {#if error}
      <div class="error-message">{error}</div>
    {/if}
  </div>

  <!-- Time Range Controls -->
  {#if videoInfo}
    <div class="control-section">
      <h4>Time Range</h4>
      
      <label class="checkbox-label">
        <input 
          type="checkbox" 
          bind:checked={useTimeRange}
          on:change={handleTimeRangeToggle}
          disabled={isProcessing}
        />
        <span>Use custom time range</span>
      </label>

      {#if useTimeRange}
        <div class="time-controls">
          <div class="time-input">
            <label for="start-time-input">Start Time:</label>
            <input 
              id="start-time-input"
              type="range" 
              min="0" 
              max={videoInfo.duration_seconds || 100}
              step="0.1"
              bind:value={startTime}
              disabled={isProcessing}
            />
            <span>{formatTime(startTime)}</span>
          </div>
          
          <div class="time-input">
            <label for="end-time-input">End Time:</label>
            <input 
              id="end-time-input"
              type="range" 
              min={startTime}
              max={videoInfo.duration_seconds || 100}
              step="0.1"
              bind:value={endTime}
              disabled={isProcessing}
            />
            <span>{formatTime(endTime)}</span>
          </div>
        </div>
      {/if}
    </div>
  {/if}

  <!-- Processing Parameters -->
  <div class="control-section">
    <h4>Parameters</h4>
    
    <div class="parameter-group">
      <label for="detection-threshold-input">Detection Threshold: {parameters.detection_threshold.toFixed(2)}</label>
      <input 
        id="detection-threshold-input"
        type="range" 
        min="0.1" 
        max="0.9" 
        step="0.05"
        bind:value={parameters.detection_threshold}
        on:input={e => handleParameterChange('detection_threshold', parseFloat(e.target.value))}
        class="parameter-slider"
      />
      <div class="parameter-hint">Lower = more faces detected, higher = fewer false positives</div>
    </div>

    <div class="parameter-group">
      <label for="similarity-threshold-input">Similarity Threshold: {parameters.similarity_threshold.toFixed(2)}</label>
      <input 
        id="similarity-threshold-input"
        type="range" 
        min="0.05" 
        max="0.5" 
        step="0.05"
        bind:value={parameters.similarity_threshold}
        on:input={e => handleParameterChange('similarity_threshold', parseFloat(e.target.value))}
        class="parameter-slider"
      />
      <div class="parameter-hint">Lower = more matches, higher = stricter matching</div>
    </div>

    <div class="parameter-group">
      <label for="frame-skip-input">Frame Skip: {parameters.frame_skip}</label>
      <input 
        id="frame-skip-input"
        type="range" 
        min="1" 
        max="30" 
        step="1"
        bind:value={parameters.frame_skip}
        on:input={e => handleParameterChange('frame_skip', parseInt(e.target.value))}
        class="parameter-slider"
      />
      <div class="parameter-hint">Higher = faster processing, lower = more thorough</div>
    </div>
  </div>

  <!-- Processing Controls -->
  <div class="control-section">
    <h4>Processing</h4>
    
    <div class="processing-buttons">
      {#if !isProcessing}
        <button 
          class="btn btn-primary"
          on:click={handleStartProcessing}
          disabled={!selectedVideo || loading}
        >
          ▶️ Start Processing
        </button>
      {:else}
        <button 
          class="btn btn-danger"
          on:click={handleStopProcessing}
        >
          ⏹️ Stop Processing
        </button>
      {/if}
    </div>

    {#if isProcessing}
      <div class="processing-status">
        <div class="status-indicator processing">●</div>
        <span>Processing in real-time...</span>
      </div>
    {/if}
  </div>
</div>

<style>
  .control-panel {
    height: 100%;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 20px;
  }

  h3 {
    margin: 0 0 16px 0;
    color: #ffffff;
    font-size: 1.2rem;
    border-bottom: 2px solid #74b9ff;
    padding-bottom: 8px;
  }

  h4 {
    margin: 0 0 12px 0;
    color: #b2bec3;
    font-size: 1rem;
    font-weight: 600;
  }

  .control-section {
    background: rgba(255, 255, 255, 0.05);
    border-radius: 6px;
    padding: 16px;
    border: 1px solid rgba(255, 255, 255, 0.1);
  }

  .video-select-wrapper {
    position: relative;
  }

  .video-select {
    width: 100%;
    padding: 12px;
    background: #1a1a1a;
    border: 1px solid #3a3a3a;
    border-radius: 4px;
    color: #ffffff;
    font-size: 0.9rem;
  }

  .video-select:focus {
    outline: none;
    border-color: #74b9ff;
  }

  .video-select:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .loading-indicator {
    position: absolute;
    right: 12px;
    top: 50%;
    transform: translateY(-50%);
    color: #74b9ff;
    font-size: 0.8rem;
  }

  .error-message {
    color: #e17055;
    font-size: 0.85rem;
    margin-top: 8px;
    padding: 8px;
    background: rgba(225, 112, 85, 0.1);
    border-radius: 4px;
  }

  .checkbox-label {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
    cursor: pointer;
    color: #b2bec3;
  }

  .checkbox-label input[type="checkbox"] {
    accent-color: #74b9ff;
  }

  .time-controls {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .time-input {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .time-input label {
    min-width: 80px;
    font-size: 0.85rem;
    color: #b2bec3;
  }

  .time-input input[type="range"] {
    flex: 1;
  }

  .time-input span {
    min-width: 50px;
    font-size: 0.85rem;
    color: #ffffff;
    font-family: monospace;
  }

  .parameter-group {
    margin-bottom: 20px;
  }

  .parameter-group label {
    display: block;
    margin-bottom: 8px;
    color: #ffffff;
    font-size: 0.9rem;
    font-weight: 500;
  }

  .parameter-slider {
    width: 100%;
    margin-bottom: 4px;
    accent-color: #74b9ff;
  }

  .parameter-hint {
    font-size: 0.75rem;
    color: #636e72;
    font-style: italic;
  }

  .processing-buttons {
    margin-bottom: 16px;
  }

  .btn {
    width: 100%;
    padding: 12px 16px;
    border: none;
    border-radius: 6px;
    font-size: 0.9rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
  }

  .btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .btn-primary {
    background: linear-gradient(135deg, #74b9ff 0%, #0984e3 100%);
    color: #ffffff;
  }

  .btn-primary:hover:not(:disabled) {
    background: linear-gradient(135deg, #0984e3 0%, #0770d1 100%);
    transform: translateY(-1px);
  }

  .btn-danger {
    background: linear-gradient(135deg, #e17055 0%, #d63031 100%);
    color: #ffffff;
  }

  .btn-danger:hover:not(:disabled) {
    background: linear-gradient(135deg, #d63031 0%, #c1261e 100%);
    transform: translateY(-1px);
  }

  .processing-status {
    display: flex;
    align-items: center;
    gap: 8px;
    color: #00b894;
    font-size: 0.85rem;
  }

  .status-indicator {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: currentColor;
  }

  .status-indicator.processing {
    animation: pulse 1.5s ease-in-out infinite;
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
  }

  /* Responsive design */
  @media (max-width: 768px) {
    .control-panel {
      gap: 16px;
    }

    .control-section {
      padding: 12px;
    }

    .time-input {
      flex-direction: column;
      align-items: stretch;
    }

    .time-input label {
      min-width: auto;
    }
  }
</style>