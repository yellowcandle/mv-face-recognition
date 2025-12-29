<script lang="ts">
  import { onMount } from 'svelte';
  import { Card, Badge } from '$lib/components';

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

  function getConfidenceBadgeVariant(confidence: number): 'success' | 'warning' | 'error' {
    if (confidence >= 80) return 'success';
    if (confidence >= 60) return 'warning';
    return 'error';
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
    <Card variant="elevated" padding="none" class="video-panel">
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
    </Card>

    <!-- Face Recognition Panel -->
    <Card variant="surface" padding="md" class="face-panel">
      <div class="face-panel-header">
        <div class="face-panel-title">Detected Faces</div>
        <Badge variant="primary" size="sm">{detectedFaces.length}</Badge>
      </div>

      <div class="face-tiles-grid">
        {#each detectedFaces as face}
          <div class="face-tile {getConfidenceClass(face.confidence)}">
            <div class="face-image">
              <span class="face-placeholder">Face {face.id}</span>
            </div>
            <div class="face-info">
              <div class="face-name">{face.name}</div>
              <Badge variant={getConfidenceBadgeVariant(face.confidence)} size="sm">
                {Math.round(face.confidence)}%
              </Badge>
            </div>
          </div>
        {/each}
      </div>
    </Card>
  </div>

  <!-- Similarity Scores Panel -->
  <Card variant="bordered" padding="lg" class="similarity-panel">
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
  </Card>
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
  :global(.video-panel) {
    width: 60%;
    position: relative;
    border-right: 1px solid var(--border-default);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .video-container {
    flex: 1;
    position: relative;
    background: linear-gradient(45deg, var(--color-neutral-900), var(--color-neutral-800));
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .video-placeholder {
    width: 90%;
    height: 80%;
    background: var(--bg-primary);
    border: 2px dashed var(--border-default);
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-tertiary);
    font-size: var(--text-body-lg-size);
    position: relative;
    border-radius: var(--radius-lg);
  }

  .video-info {
    text-align: center;
  }

  .video-info h3 {
    color: var(--text-primary);
    font-size: var(--text-h3-size);
    margin-bottom: var(--space-2);
  }

  .video-info p {
    color: var(--text-secondary);
    font-size: var(--text-body-size);
  }

  /* Face Detection Overlays */
  .detection-overlay {
    position: absolute;
    border: 2px solid var(--color-success-500);
    background: rgba(34, 197, 94, 0.1);
    border-radius: var(--radius-sm);
  }

  .detection-1 {
    border-color: var(--color-success-500);
    background: rgba(34, 197, 94, 0.1);
  }

  .detection-2 {
    border-color: var(--color-warning-500);
    background: rgba(234, 179, 8, 0.1);
  }

  .confidence-label {
    position: absolute;
    top: -25px;
    left: 0;
    background: rgba(0, 0, 0, 0.8);
    padding: var(--space-0-5) var(--space-1-5);
    font-size: var(--text-caption-size);
    border-radius: var(--radius-sm);
    color: var(--text-primary);
    font-weight: var(--text-label-weight);
  }

  /* Video Controls */
  .video-controls {
    position: absolute;
    bottom: var(--space-2-5);
    left: var(--space-2-5);
    right: var(--space-2-5);
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: rgba(0, 0, 0, 0.7);
    padding: var(--space-2) var(--space-3);
    border-radius: var(--radius-md);
  }

  .frame-info {
    font-size: var(--text-caption-size);
    color: var(--text-secondary);
    font-weight: 500;
  }

  .processing-status {
    font-size: var(--text-caption-size);
    color: var(--color-error-500);
    font-weight: var(--text-label-weight);
  }

  .processing-status.active {
    color: var(--color-success-500);
  }

  /* Face Recognition Panel */
  :global(.face-panel) {
    width: 40%;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
  }

  .face-panel-header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin-bottom: var(--space-5);
    flex-shrink: 0;
  }

  .face-panel-title {
    font-size: var(--text-body-lg-size);
    font-weight: var(--text-label-weight);
    color: var(--text-primary);
  }

  /* Face Tiles Grid */
  .face-tiles-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: var(--space-2-5);
    flex: 1;
  }

  .face-tile {
    width: 120px;
    height: 120px;
    border: 2px solid;
    border-radius: var(--radius-lg);
    padding: var(--space-2);
    background-color: var(--bg-tertiary);
    display: flex;
    flex-direction: column;
    align-items: center;
    cursor: pointer;
    transition: var(--transition-all);
  }

  .face-tile:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-lg);
  }

  .face-tile.high-confidence {
    border-color: var(--color-success-500);
  }

  .face-tile.medium-confidence {
    border-color: var(--color-warning-500);
  }

  .face-tile.low-confidence {
    border-color: var(--color-error-500);
  }

  .face-image {
    width: 80px;
    height: 80px;
    background: var(--color-neutral-700);
    border-radius: var(--radius-sm);
    margin-bottom: var(--space-1-5);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: var(--text-caption-size);
    color: var(--text-secondary);
  }

  .face-placeholder {
    font-size: var(--text-caption-size);
    text-align: center;
  }

  .face-info {
    text-align: center;
    width: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-1);
  }

  .face-name {
    font-size: var(--text-caption-size);
    font-weight: var(--text-label-weight);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    color: var(--text-primary);
    width: 100%;
  }

  /* Similarity Scores Panel */
  :global(.similarity-panel) {
    height: 200px;
    border-top: 1px solid var(--border-default);
    flex-shrink: 0;
  }

  .similarity-title {
    font-size: var(--text-body-size);
    font-weight: var(--text-label-weight);
    margin-bottom: var(--space-4);
    color: var(--text-primary);
  }

  .chart-container {
    height: 140px;
    display: flex;
    align-items: end;
    gap: var(--space-4);
    padding: 0 var(--space-2-5);
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
    background-color: var(--color-success-500);
    border-radius: var(--radius-sm) var(--radius-sm) 0 0;
    transition: var(--transition-all);
    position: relative;
    min-height: 20px;
  }

  .bar.medium {
    background-color: var(--color-warning-500);
  }

  .bar.low {
    background-color: var(--color-error-500);
  }

  .bar-value {
    position: absolute;
    top: -20px;
    left: 50%;
    transform: translateX(-50%);
    font-size: var(--text-caption-size);
    color: var(--text-primary);
    font-weight: var(--text-label-weight);
    white-space: nowrap;
  }

  .bar-label {
    margin-top: var(--space-2);
    font-size: var(--text-caption-size);
    color: var(--text-secondary);
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

    :global(.video-panel) {
      width: 100%;
      height: 50vh;
    }

    :global(.face-panel) {
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

    :global(.similarity-panel) {
      height: 150px;
    }

    .chart-container {
      gap: var(--space-2);
    }
  }
</style>