<script>
  import { onMount } from 'svelte';
  import Header from './components/Header.svelte';
  import VideoPlayer from './components/VideoPlayer.svelte';
  import ControlPanel from './components/ControlPanel.svelte';
  import StatusPanel from './components/StatusPanel.svelte';
  import ResultsPanel from './components/ResultsPanel.svelte';
  import { websocketStore } from './stores/websocket.js';
  import { videoStore } from './stores/video.js';
  import { processingStore } from './stores/processing.js';

  let currentView = 'dashboard';

  onMount(() => {
    // Initialize WebSocket connection
    websocketStore.connect();
    
    // Load available videos
    videoStore.loadVideos();
  });
</script>

<div class="app">
  <Header bind:currentView />
  
  <main class="main-content">
    {#if currentView === 'dashboard'}
      <div class="dashboard">
        <div class="video-section">
          <VideoPlayer />
        </div>
        
        <div class="control-section">
          <ControlPanel />
        </div>
        
        <div class="status-section">
          <StatusPanel />
        </div>
        
        <div class="results-section">
          <ResultsPanel />
        </div>
      </div>
    {:else if currentView === 'settings'}
      <div class="settings">
        <h2>Settings</h2>
        <p>Settings panel coming soon...</p>
      </div>
    {:else if currentView === 'database'}
      <div class="database">
        <h2>Database Management</h2>
        <p>Database management coming soon...</p>
      </div>
    {/if}
  </main>
</div>

<style>
  .app {
    height: 100vh;
    display: flex;
    flex-direction: column;
    background: #1a1a1a;
    color: #ffffff;
  }

  .main-content {
    flex: 1;
    overflow: hidden;
  }

  .dashboard {
    height: 100%;
    display: grid;
    grid-template-columns: 2fr 1fr;
    grid-template-rows: 2fr 1fr;
    grid-template-areas: 
      "video control"
      "status results";
    gap: 16px;
    padding: 16px;
  }

  .video-section {
    grid-area: video;
    background: #2a2a2a;
    border-radius: 8px;
    overflow: hidden;
  }

  .control-section {
    grid-area: control;
    background: #2a2a2a;
    border-radius: 8px;
    padding: 16px;
  }

  .status-section {
    grid-area: status;
    background: #2a2a2a;
    border-radius: 8px;
    padding: 16px;
  }

  .results-section {
    grid-area: results;
    background: #2a2a2a;
    border-radius: 8px;
    padding: 16px;
  }

  .settings, .database {
    padding: 24px;
    max-width: 1200px;
    margin: 0 auto;
  }

  /* Responsive design */
  @media (max-width: 1024px) {
    .dashboard {
      grid-template-columns: 1fr;
      grid-template-rows: auto auto auto auto;
      grid-template-areas: 
        "video"
        "control"
        "status"
        "results";
    }
  }
</style>