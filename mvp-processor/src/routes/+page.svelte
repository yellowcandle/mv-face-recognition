<script lang="ts">
  import { onMount } from 'svelte';
  
  interface DetectedFace {
    id: string;
    name: string;
    confidence: number;
    x: number;
    y: number;
    width: number;
    height: number;
  }
  
  let detectedFaces: DetectedFace[] = [
    { id: '1', name: 'John Doe', confidence: 95, x: 25, y: 20, width: 80, height: 100 },
    { id: '2', name: 'Sarah Wilson', confidence: 78, x: 65, y: 30, width: 75, height: 95 },
    { id: '3', name: 'Mike Johnson', confidence: 92, x: 15, y: 60, width: 70, height: 90 },
    { id: '4', name: 'Unknown', confidence: 45, x: 80, y: 50, width: 65, height: 85 },
    { id: '5', name: 'Emma Davis', confidence: 81, x: 40, y: 70, width: 75, height: 95 },
    { id: '6', name: 'Alex Chen', confidence: 97, x: 55, y: 15, width: 80, height: 100 }
  ];
  
  let frameRate = 30;
  let resolution = '1920x1080';
  let isProcessing = true;
  
  function getConfidenceClass(confidence: number): string {
    if (confidence >= 80) return 'high-confidence';
    if (confidence >= 60) return 'medium-confidence';
    return 'low-confidence';
  }
  
  function getBarClass(confidence: number): string {
    if (confidence >= 80) return '';
    if (confidence >= 60) return 'medium';
    return 'low';
  }
  
  onMount(() => {
    // Simulate real-time updates
    const interval = setInterval(() => {
      detectedFaces = detectedFaces.map(face => ({
        ...face,
        confidence: Math.max(40, Math.min(99, face.confidence + (Math.random() - 0.5) * 5))
      }));
    }, 2000);
    
    return () => clearInterval(interval);
  });
</script>

<svelte:head>
  <title>Face Recognition Dashboard</title>
</svelte:head>

<div class="dashboard-container">
  <!-- Main Content Area -->
  <div class="content-wrapper">
    <!-- Video Player Panel -->
    <div class="video-panel">
      <div class="video-container">
        <div class="video-placeholder">
          <div class="video-info">
            <h3>Live Video Stream</h3>
            <p>Real-time face detection active</p>
          </div>
          
          <!-- Face Detection Overlays -->
          {#each detectedFaces.slice(0, 2) as face, i}
            <div 
              class="detection-overlay" 
              style="left: {face.x}%; top: {face.y}%; width: {face.width}px; height: {face.height}px;"
              class:detection-1={i === 0}
              class:detection-2={i === 1}
            >
              <div class="confidence-label">{Math.round(face.confidence)}%</div>
            </div>
          {/each}
        </div>
        
        <!-- Video Controls -->
        <div class="video-controls">
          <div class="frame-info">{frameRate} FPS</div>
          <div class="processing-status" class:active={isProcessing}>
            {isProcessing ? 'Processing...' : 'Paused'}
          </div>
          <div class="frame-info">{resolution}</div>
        </div>
      </div>
    </div>

    <!-- Face Recognition Panel -->
    <div class="face-panel">
      <div class="face-panel-header">
        <div class="face-panel-title">Detected Faces</div>
        <div class="face-count-badge">{detectedFaces.length}</div>
      </div>

      <div class="face-tiles-grid">
        {#each detectedFaces as face}
          <div class="face-tile {getConfidenceClass(face.confidence)}">
            <div class="face-image">
              <span class="face-placeholder">Face {face.id}</span>
            </div>
            <div class="face-info">
              <div class="face-name">{face.name}</div>
              <div class="face-confidence">{Math.round(face.confidence)}%</div>
            </div>
          </div>
        {/each}
      </div>
    </div>
  </div>

  <!-- Similarity Scores Panel -->
  <div class="similarity-panel">
    <div class="similarity-title">Recognition Confidence Scores</div>
    <div class="chart-container">
      {#each detectedFaces as face}
        <div class="chart-bar">
          <div 
            class="bar {getBarClass(face.confidence)}" 
            style="height: {face.confidence}px;"
          >
            <div class="bar-value">{Math.round(face.confidence)}%</div>
          </div>
          <div class="bar-label">{face.name}</div>
        </div>
      {/each}
    </div>
  </div>
</div>

<style>
  .dashboard-container {
    height: 100vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .content-wrapper {
    flex: 1;
    display: flex;
    min-height: 0;
  }

  /* Video Player Panel */
  .video-panel {
    width: 60%;
    background-color: #000000;
    position: relative;
    border-right: 1px solid #444;
    display: flex;
    flex-direction: column;
  }

  .video-container {
    flex: 1;
    position: relative;
    background: linear-gradient(45deg, #111, #222);
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .video-placeholder {
    width: 90%;
    height: 80%;
    background: #1a1a1a;
    border: 2px dashed #444;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #666;
    font-size: 18px;
    position: relative;
    border-radius: 8px;
  }

  .video-info {
    text-align: center;
  }

  .video-info h3 {
    color: #ffffff;
    font-size: 24px;
    margin-bottom: 8px;
  }

  .video-info p {
    color: #9ca3af;
    font-size: 16px;
  }

  /* Face Detection Overlays */
  .detection-overlay {
    position: absolute;
    border: 2px solid #22c55e;
    background: rgba(34, 197, 94, 0.1);
    border-radius: 4px;
  }

  .detection-1 {
    border-color: #22c55e;
    background: rgba(34, 197, 94, 0.1);
  }

  .detection-2 {
    border-color: #eab308;
    background: rgba(234, 179, 8, 0.1);
  }

  .confidence-label {
    position: absolute;
    top: -25px;
    left: 0;
    background: rgba(0, 0, 0, 0.8);
    padding: 2px 6px;
    font-size: 11px;
    border-radius: 3px;
    color: #ffffff;
    font-weight: 600;
  }

  /* Video Controls */
  .video-controls {
    position: absolute;
    bottom: 10px;
    left: 10px;
    right: 10px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: rgba(0, 0, 0, 0.7);
    padding: 8px 12px;
    border-radius: 6px;
  }

  .frame-info {
    font-size: 12px;
    color: #9ca3af;
    font-weight: 500;
  }

  .processing-status {
    font-size: 12px;
    color: #ef4444;
    font-weight: 600;
  }

  .processing-status.active {
    color: #22c55e;
  }

  /* Face Recognition Panel */
  .face-panel {
    width: 40%;
    background-color: #1e293b;
    padding: 20px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
  }

  .face-panel-header {
    display: flex;
    align-items: center;
    margin-bottom: 20px;
    flex-shrink: 0;
  }

  .face-panel-title {
    font-size: 18px;
    font-weight: 600;
    margin-right: 10px;
    color: #ffffff;
  }

  .face-count-badge {
    background-color: #3b82f6;
    color: white;
    padding: 4px 8px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 600;
  }

  /* Face Tiles Grid */
  .face-tiles-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 10px;
    flex: 1;
  }

  .face-tile {
    width: 120px;
    height: 120px;
    border: 2px solid;
    border-radius: 8px;
    padding: 8px;
    background-color: #2d3748;
    display: flex;
    flex-direction: column;
    align-items: center;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .face-tile:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3);
  }

  .face-tile.high-confidence {
    border-color: #22c55e;
  }

  .face-tile.medium-confidence {
    border-color: #eab308;
  }

  .face-tile.low-confidence {
    border-color: #ef4444;
  }

  .face-image {
    width: 80px;
    height: 80px;
    background: #4a5568;
    border-radius: 4px;
    margin-bottom: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 10px;
    color: #9ca3af;
  }

  .face-placeholder {
    font-size: 9px;
    text-align: center;
  }

  .face-info {
    text-align: center;
    width: 100%;
  }

  .face-name {
    font-size: 10px;
    font-weight: 600;
    margin-bottom: 2px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    color: #ffffff;
  }

  .face-confidence {
    font-size: 9px;
    color: #9ca3af;
  }

  /* Similarity Scores Panel */
  .similarity-panel {
    height: 200px;
    background-color: #374151;
    padding: 20px;
    border-top: 1px solid #444;
    flex-shrink: 0;
  }

  .similarity-title {
    font-size: 16px;
    font-weight: 600;
    margin-bottom: 15px;
    color: #ffffff;
  }

  .chart-container {
    height: 140px;
    display: flex;
    align-items: end;
    gap: 15px;
    padding: 0 10px;
    overflow-x: auto;
  }

  .chart-bar {
    display: flex;
    flex-direction: column;
    align-items: center;
    flex-shrink: 0;
    min-width: 60px;
  }

  .bar {
    width: 40px;
    background-color: #22c55e;
    border-radius: 4px 4px 0 0;
    transition: all 0.3s ease;
    position: relative;
    min-height: 20px;
  }

  .bar.medium {
    background-color: #eab308;
  }

  .bar.low {
    background-color: #ef4444;
  }

  .bar-value {
    position: absolute;
    top: -20px;
    left: 50%;
    transform: translateX(-50%);
    font-size: 10px;
    color: #fff;
    font-weight: 600;
    white-space: nowrap;
  }

  .bar-label {
    margin-top: 8px;
    font-size: 11px;
    color: #9ca3af;
    text-align: center;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    width: 60px;
  }

  /* Mobile Responsive */
  @media (max-width: 768px) {
    .content-wrapper {
      flex-direction: column;
    }
    
    .video-panel {
      width: 100%;
      height: 50vh;
    }
    
    .face-panel {
      width: 100%;
      height: auto;
      flex: 1;
    }
    
    .face-tiles-grid {
      grid-template-columns: repeat(3, 1fr);
    }
    
    .face-tile {
      width: 100%;
    }
    
    .similarity-panel {
      height: 150px;
    }
    
    .chart-container {
      gap: 8px;
    }
  }
</style>