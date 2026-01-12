<script>
  import { websocketStore } from '../stores/websocket.js';
  
  export let currentView = 'dashboard';
  
  let connectionStatus = false;
  
  websocketStore.subscribe(state => {
    connectionStatus = state.connected;
  });
  
  const navigation = [
    { id: 'dashboard', label: 'Dashboard', icon: '🎬' },
    { id: 'database', label: 'Database', icon: '👥' },
    { id: 'settings', label: 'Settings', icon: '⚙️' }
  ];
</script>

<header class="header">
  <div class="header-content">
    <div class="logo">
      <h1>🎭 MV Face Recognition</h1>
      <span class="version">v2.0 - FastAPI + Svelte</span>
    </div>
    
    <nav class="navigation">
      {#each navigation as nav}
        <button 
          class="nav-button"
          class:active={currentView === nav.id}
          on:click={() => currentView = nav.id}
        >
          <span class="nav-icon">{nav.icon}</span>
          <span class="nav-label">{nav.label}</span>
        </button>
      {/each}
    </nav>
    
    <div class="status">
      <div class="connection-status" class:connected={connectionStatus}>
        <div class="status-indicator"></div>
        <span class="status-text">
          {connectionStatus ? 'Connected' : 'Disconnected'}
        </span>
      </div>
    </div>
  </div>
</header>

<style>
  .header {
    background: linear-gradient(135deg, #2d3436 0%, #636e72 100%);
    border-bottom: 1px solid #3a3a3a;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
  }

  .header-content {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 24px;
    max-width: 1400px;
    margin: 0 auto;
  }

  .logo h1 {
    margin: 0;
    font-size: 1.5rem;
    font-weight: 700;
    color: #ffffff;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .version {
    font-size: 0.75rem;
    color: #b2bec3;
    font-weight: 400;
    margin-left: 12px;
  }

  .navigation {
    display: flex;
    gap: 8px;
  }

  .nav-button {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 16px;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    color: #b2bec3;
    font-size: 0.9rem;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .nav-button:hover {
    background: rgba(255, 255, 255, 0.1);
    color: #ffffff;
  }

  .nav-button.active {
    background: rgba(116, 185, 255, 0.2);
    border-color: #74b9ff;
    color: #74b9ff;
  }

  .nav-icon {
    font-size: 1.1rem;
  }

  .nav-label {
    font-weight: 500;
  }

  .status {
    display: flex;
    align-items: center;
    gap: 16px;
  }

  .connection-status {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px;
    border-radius: 20px;
    background: rgba(0, 0, 0, 0.2);
    font-size: 0.85rem;
  }

  .status-indicator {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #e17055;
    transition: background-color 0.3s ease;
  }

  .connection-status.connected .status-indicator {
    background: #00b894;
  }

  .status-text {
    color: #b2bec3;
    font-weight: 500;
  }

  .connection-status.connected .status-text {
    color: #00b894;
  }

  /* Responsive design */
  @media (max-width: 768px) {
    .header-content {
      flex-direction: column;
      gap: 16px;
      padding: 16px;
    }

    .logo h1 {
      font-size: 1.25rem;
    }

    .version {
      display: none;
    }

    .navigation {
      width: 100%;
      justify-content: center;
    }

    .nav-button {
      flex: 1;
      justify-content: center;
    }

    .nav-label {
      display: none;
    }

    .nav-icon {
      font-size: 1.3rem;
    }
  }
</style>