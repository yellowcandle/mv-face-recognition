<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  
  // Navigation items
  const navItems = [
    { href: '/', label: 'Dashboard', icon: '🎬' },
    { href: '/video-player', label: 'Video Player', icon: '▶️' },
    { href: '/processing', label: 'Processing', icon: '⚙️' },
    { href: '/analytics', label: 'Analytics', icon: '📊' },
    { href: '/admin', label: 'Admin', icon: '🔐' }
  ];
  
  let mobileMenuOpen = false;
  let systemStatus = 'checking';
  let currentTime = new Date().toLocaleString();
  
  onMount(() => {
    const timeInterval = setInterval(() => {
      currentTime = new Date().toLocaleString();
    }, 1000);

    const checkStatus = async () => {
      try {
        const response = await fetch('/api/system/status');
        systemStatus = response.ok ? 'LIVE' : 'OFFLINE';
      } catch {
        systemStatus = 'OFFLINE';
      }
    };

    void checkStatus();

    return () => {
      clearInterval(timeInterval);
    };
  });
  
  function toggleMobileMenu() {
    mobileMenuOpen = !mobileMenuOpen;
  }
  
  function closeMobileMenu() {
    mobileMenuOpen = false;
  }
</script>

<div class="dashboard-layout">
  <!-- Header Bar -->
  <div class="header-bar">
    <div class="app-title">Face Recognition Dashboard</div>
    <div class="status-indicator" class:offline={systemStatus === 'OFFLINE'}>
      {systemStatus}
    </div>
    <div class="timestamp">{currentTime}</div>
  </div>

  <!-- Navigation -->
  <nav class="nav-bar">
    <div class="nav-content">
      <button class="mobile-menu-button" on:click={toggleMobileMenu} aria-label="Toggle menu">
        <span class="hamburger"></span>
      </button>
      
      <div class="nav-links" class:mobile-open={mobileMenuOpen}>
        {#each navItems as item}
          <a 
            href={item.href} 
            class="nav-link"
            class:active={$page.url.pathname === item.href}
            on:click={closeMobileMenu}
          >
            <span class="nav-icon">{item.icon}</span>
            {item.label}
          </a>
        {/each}
      </div>
    </div>
  </nav>
  
  <!-- Main Content -->
  <main class="main-content">
    <slot />
  </main>
</div>

<style>
  .dashboard-layout {
    min-height: 100vh;
    background-color: #1a1a1a;
    color: #ffffff;
    display: flex;
    flex-direction: column;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
  }

  .header-bar {
    height: 60px;
    background-color: #2a2a2a;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 20px;
    border-bottom: 1px solid #444;
    flex-shrink: 0;
  }

  .app-title {
    font-size: 20px;
    font-weight: 600;
    color: #ffffff;
  }

  .status-indicator {
    background-color: #22c55e;
    color: #000;
    padding: 6px 12px;
    border-radius: 4px;
    font-weight: 600;
    font-size: 12px;
    animation: pulse 2s infinite;
  }

  .status-indicator.offline {
    background-color: #ef4444;
    color: #fff;
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.7; }
  }

  .timestamp {
    font-size: 14px;
    color: #9ca3af;
  }

  .nav-bar {
    background-color: #374151;
    border-bottom: 1px solid #444;
    flex-shrink: 0;
  }

  .nav-content {
    display: flex;
    align-items: center;
    padding: 0 20px;
    height: 50px;
  }

  .mobile-menu-button {
    display: none;
    background: none;
    border: none;
    cursor: pointer;
    padding: 0.5rem;
    color: #ffffff;
  }

  .nav-links {
    display: flex;
    gap: 0.5rem;
    align-items: center;
  }

  .nav-link {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 1rem;
    border-radius: 0.375rem;
    text-decoration: none;
    color: #9ca3af;
    font-weight: 500;
    transition: all 0.2s;
    white-space: nowrap;
  }

  .nav-link:hover {
    background-color: #4b5563;
    color: #ffffff;
  }

  .nav-link.active {
    background-color: #2563eb;
    color: white;
  }

  .nav-icon {
    font-size: 1.1rem;
  }

  .main-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }

  /* Mobile Styles */
  @media (max-width: 768px) {
    .mobile-menu-button {
      display: block;
    }
    
    .nav-links {
      position: absolute;
      top: 100%;
      left: 0;
      right: 0;
      background-color: #374151;
      flex-direction: column;
      border-bottom: 1px solid #444;
      display: none;
      z-index: 50;
    }
    
    .nav-links.mobile-open {
      display: flex;
    }
    
    .nav-link {
      width: 100%;
      padding: 1rem 1.5rem;
      border-radius: 0;
    }
    
    .app-title {
      font-size: 16px;
    }
    
    .timestamp {
      display: none;
    }
  }
</style>