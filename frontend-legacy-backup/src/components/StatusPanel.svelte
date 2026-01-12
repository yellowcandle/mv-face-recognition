<script>
  import { onMount, onDestroy } from 'svelte';
  import { processingStore, resultsStore } from '../stores/processing.js';
  import { websocketStore, processingUpdates } from '../stores/websocket.js';

  let websocketState = { connected: false, error: null };
  let processingState = { isProcessing: false, currentFrame: 0, totalFrames: 0, processingFps: 0 };
  let statistics = { totalFacesDetected: 0, totalFacesRecognized: 0, processingTime: 0 };
  
  let fpsHistory = [];
  let maxFpsHistory = 50;
  let updateInterval;

  // Subscribe to stores
  websocketStore.subscribe(state => {
    websocketState = state;
  });

  processingStore.subscribe(state => {
    processingState = state;
  });

  resultsStore.subscribe(state => {
    statistics = state.statistics;
  });

  processingUpdates.subscribe(update => {
    if (update.frameData?.stats) {
      updateFpsHistory(update.frameData.stats.fps || 0);
    }
  });

  onMount(() => {
    // Update display every second
    updateInterval = setInterval(() => {
      // Force reactivity update
      fpsHistory = [...fpsHistory];
    }, 1000);
  });

  onDestroy(() => {
    if (updateInterval) {
      clearInterval(updateInterval);
    }
  });

  function updateFpsHistory(fps) {
    fpsHistory.push(fps);
    if (fpsHistory.length > maxFpsHistory) {
      fpsHistory.shift();
    }
  }

  function getAverageFps() {
    if (fpsHistory.length === 0) return 0;
    return fpsHistory.reduce((a, b) => a + b, 0) / fpsHistory.length;
  }

  function getProgressPercentage() {
    if (processingState.totalFrames === 0) return 0;
    return (processingState.currentFrame / processingState.totalFrames) * 100;
  }

  function formatDuration(seconds) {
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    if (hrs > 0) {
      return `${hrs}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  }

  function getRecognitionRate() {
    if (statistics.totalFacesDetected === 0) return 0;
    return (statistics.totalFacesRecognized / statistics.totalFacesDetected) * 100;
  }
</script>

<div class="status-panel">
  <h3>📊 System Status</h3>

  <!-- Connection Status -->
  <div class="status-section">
    <h4>Connection</h4>
    <div class="status-row">
      <div class="status-indicator" class:connected={websocketState.connected}></div>
      <span class="status-text">
        {websocketState.connected ? 'WebSocket Connected' : 'WebSocket Disconnected'}
      </span>
    </div>
    
    {#if websocketState.error}
      <div class="error-status">{websocketState.error}</div>
    {/if}
  </div>

  <!-- Processing Status -->
  <div class="status-section">
    <h4>Processing</h4>
    
    <div class="status-row">
      <div class="status-indicator" class:processing={processingState.isProcessing}></div>
      <span class="status-text">
        {processingState.isProcessing ? 'Processing Active' : 'Idle'}
      </span>
    </div>

    {#if processingState.isProcessing}
      <!-- Progress Bar -->
      <div class="progress-container">
        <div class="progress-bar">
          <div 
            class="progress-fill" 
            style="width: {getProgressPercentage()}%"
          ></div>
        </div>
        <span class="progress-text">
          {processingState.currentFrame} / {processingState.totalFrames} frames
        </span>
      </div>

      <!-- Performance Metrics -->
      <div class="metrics-grid">
        <div class="metric">
          <div class="metric-value">{processingState.processingFps.toFixed(1)}</div>
          <div class="metric-label">Current FPS</div>
        </div>
        
        <div class="metric">
          <div class="metric-value">{getAverageFps().toFixed(1)}</div>
          <div class="metric-label">Avg FPS</div>
        </div>
        
        <div class="metric">
          <div class="metric-value">{formatDuration(statistics.processingTime)}</div>
          <div class="metric-label">Duration</div>
        </div>
      </div>
    {/if}
  </div>

  <!-- Detection Statistics -->
  <div class="status-section">
    <h4>Detection Stats</h4>
    
    <div class="stats-grid">
      <div class="stat-item">
        <div class="stat-number">{statistics.totalFacesDetected}</div>
        <div class="stat-label">Faces Detected</div>
      </div>
      
      <div class="stat-item">
        <div class="stat-number">{statistics.totalFacesRecognized}</div>
        <div class="stat-label">Faces Recognized</div>
      </div>
      
      <div class="stat-item">
        <div class="stat-number">{getRecognitionRate().toFixed(1)}%</div>
        <div class="stat-label">Recognition Rate</div>
      </div>
    </div>
  </div>

  <!-- Performance Graph -->
  {#if fpsHistory.length > 0}
    <div class="status-section">
      <h4>Performance</h4>
      
      <div class="fps-graph">
        <svg width="100%" height="60" viewBox="0 0 {maxFpsHistory} 60">
          <!-- Grid lines -->
          <defs>
            <pattern id="grid" width="5" height="10" patternUnits="userSpaceOnUse">
              <path d="M 5 0 L 0 0 0 10" fill="none" stroke="#3a3a3a" stroke-width="0.5"/>
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid)" />
          
          <!-- FPS Line -->
          <polyline
            fill="none"
            stroke="#74b9ff"
            stroke-width="2"
            points={fpsHistory.map((fps, i) => `${i},${60 - (fps / 60) * 60}`).join(' ')}
          />
          
          <!-- Target FPS line (30 FPS) -->
          <line x1="0" y1="30" x2={maxFpsHistory} y2="30" stroke="#00b894" stroke-width="1" stroke-dasharray="2,2" opacity="0.7"/>
        </svg>
        
        <div class="graph-labels">
          <span class="graph-label">0 FPS</span>
          <span class="graph-label">30 FPS</span>
          <span class="graph-label">60 FPS</span>
        </div>
      </div>
    </div>
  {/if}
</div>

<style>
  .status-panel {
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
    border-bottom: 2px solid #00b894;
    padding-bottom: 8px;
  }

  h4 {
    margin: 0 0 12px 0;
    color: #b2bec3;
    font-size: 1rem;
    font-weight: 600;
  }

  .status-section {
    background: rgba(255, 255, 255, 0.05);
    border-radius: 6px;
    padding: 16px;
    border: 1px solid rgba(255, 255, 255, 0.1);
  }

  .status-row {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
  }

  .status-indicator {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: #e17055;
    transition: background-color 0.3s ease;
  }

  .status-indicator.connected {
    background: #00b894;
  }

  .status-indicator.processing {
    background: #74b9ff;
    animation: pulse 1.5s ease-in-out infinite;
  }

  .status-text {
    color: #b2bec3;
    font-size: 0.9rem;
  }

  .error-status {
    color: #e17055;
    font-size: 0.8rem;
    padding: 8px;
    background: rgba(225, 112, 85, 0.1);
    border-radius: 4px;
    margin-top: 8px;
  }

  .progress-container {
    margin: 12px 0;
  }

  .progress-bar {
    width: 100%;
    height: 8px;
    background: #2d3436;
    border-radius: 4px;
    overflow: hidden;
    margin-bottom: 8px;
  }

  .progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #74b9ff 0%, #0984e3 100%);
    border-radius: 4px;
    transition: width 0.3s ease;
  }

  .progress-text {
    font-size: 0.8rem;
    color: #b2bec3;
    font-family: monospace;
  }

  .metrics-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    margin-top: 16px;
  }

  .metric {
    text-align: center;
    background: rgba(0, 0, 0, 0.3);
    padding: 12px 8px;
    border-radius: 4px;
  }

  .metric-value {
    font-size: 1.2rem;
    font-weight: 700;
    color: #74b9ff;
    font-family: monospace;
  }

  .metric-label {
    font-size: 0.75rem;
    color: #636e72;
    margin-top: 4px;
  }

  .stats-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
  }

  .stat-item {
    text-align: center;
    background: rgba(0, 0, 0, 0.3);
    padding: 16px 8px;
    border-radius: 4px;
  }

  .stat-number {
    font-size: 1.5rem;
    font-weight: 700;
    color: #00b894;
    font-family: monospace;
  }

  .stat-label {
    font-size: 0.75rem;
    color: #636e72;
    margin-top: 4px;
  }

  .fps-graph {
    position: relative;
    background: rgba(0, 0, 0, 0.3);
    border-radius: 4px;
    padding: 8px;
  }

  .graph-labels {
    display: flex;
    justify-content: space-between;
    margin-top: 4px;
  }

  .graph-label {
    font-size: 0.7rem;
    color: #636e72;
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
  }

  /* Responsive design */
  @media (max-width: 768px) {
    .metrics-grid, .stats-grid {
      grid-template-columns: 1fr;
      gap: 8px;
    }

    .metric, .stat-item {
      padding: 8px;
    }

    .metric-value, .stat-number {
      font-size: 1rem;
    }
  }
</style>