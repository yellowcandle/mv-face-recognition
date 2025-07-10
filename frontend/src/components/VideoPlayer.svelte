<script>
  import { onMount, onDestroy } from 'svelte';
  // Note: This component is simplified for demo purposes
  // In offline mode, no video processing functionality is available

  let videoContainer;
  let videoElement;
  
  let selectedVideo = null;
  let videoInfo = null;

  onMount(() => {
    // Simple demo video player
  });

  onDestroy(() => {
    // Cleanup
  });

  // Simplified for demo mode
</script>

<div class="video-player-container" bind:this={videoContainer}>
  <div class="demo-video">
    <div class="demo-video-content">
      <h3>🎬 Video Player</h3>
      <p>Video playback functionality is available when connected to the backend API.</p>
      <p>In offline mode, this shows a placeholder for the video processing interface.</p>
      <div class="demo-features">
        <h4>Features when connected:</h4>
        <ul>
          <li>Real-time face detection and recognition</li>
          <li>Frame-by-frame analysis with overlays</li>
          <li>Performance statistics</li>
          <li>Interactive timeline navigation</li>
        </ul>
      </div>
    </div>
  </div>
</div>

<style>
  .video-player-container {
    height: 100%;
    display: flex;
    flex-direction: column;
    background: var(--surface-color);
    border-radius: 8px;
    overflow: hidden;
    border: 1px solid rgba(0, 0, 0, 0.1);
  }

  .demo-video {
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 32px;
  }

  .demo-video-content {
    text-align: center;
    max-width: 500px;
  }

  .demo-video-content h3 {
    margin: 0 0 16px 0;
    font-size: 1.5rem;
    font-weight: 600;
  }

  .demo-video-content p {
    margin: 0 0 16px 0;
    font-size: 1rem;
    opacity: 0.9;
  }

  .demo-features {
    margin-top: 24px;
    text-align: left;
  }

  .demo-features h4 {
    margin: 0 0 12px 0;
    font-size: 1.1rem;
    font-weight: 500;
    text-align: center;
  }

  .demo-features ul {
    list-style: none;
    padding: 0;
    margin: 0;
  }

  .demo-features li {
    padding: 8px 0;
    font-size: 0.9rem;
    opacity: 0.9;
    position: relative;
    padding-left: 24px;
  }

  .demo-features li:before {
    content: '✓';
    position: absolute;
    left: 0;
    color: #4ade80;
    font-weight: bold;
  }

  @media (max-width: 768px) {
    .demo-video {
      padding: 16px;
    }
    
    .demo-video-content h3 {
      font-size: 1.3rem;
    }
  }
</style>