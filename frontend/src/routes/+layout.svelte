<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  
  // Navigation items
  const navItems = [
    { href: '/', label: 'Dashboard', icon: '🏠' },
    { href: '/video-player', label: 'Video Player', icon: '▶️' },
    { href: '/face-recognition', label: 'Face Recognition', icon: '🎯' },
    { href: '/analytics', label: 'Analytics', icon: '📊' },
    { href: '/settings', label: 'Settings', icon: '⚙️' }
  ];
  
  let mobileMenuOpen = false;
  let systemStatus = 'checking';
  
  onMount(async () => {
    // Check system status
    try {
      const response = await fetch('/api/system/status');
      if (response.ok) {
        systemStatus = 'online';
      } else {
        systemStatus = 'offline';
      }
    } catch (error) {
      systemStatus = 'offline';
    }
  });
  
  function toggleMobileMenu() {
    mobileMenuOpen = !mobileMenuOpen;
  }
  
  function closeMobileMenu() {
    mobileMenuOpen = false;
  }
</script>

<div class="app">
  <!-- Header -->
  <header class="header">
    <div class="header-content">
      <div class="header-left">
        <button class="mobile-menu-button" on:click={toggleMobileMenu} aria-label="Toggle mobile menu">
          <span class="hamburger"></span>
        </button>
        <h1 class="logo">
          <span class="logo-icon">🎬</span>
          MV Face Recognition
        </h1>
      </div>
      
      <nav class="desktop-nav">
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
      </nav>
      
      <div class="header-right">
        <div class="status-indicator">
          <span class="status-dot" class:online={systemStatus === 'online'} class:offline={systemStatus === 'offline'}></span>
          <span class="status-text">{systemStatus}</span>
        </div>
      </div>
    </div>
  </header>
  
  <!-- Mobile Navigation -->
  {#if mobileMenuOpen}
    <nav class="mobile-nav">
      <div class="mobile-nav-content">
        {#each navItems as item}
          <a 
            href={item.href} 
            class="mobile-nav-link"
            class:active={$page.url.pathname === item.href}
            on:click={closeMobileMenu}
          >
            <span class="nav-icon">{item.icon}</span>
            {item.label}
          </a>
        {/each}
      </div>
      <div class="mobile-nav-overlay" on:click={closeMobileMenu} aria-hidden="true"></div>
    </nav>
  {/if}
  
  <!-- Main Content -->
  <main class="main">
    <slot />
  </main>
  
  <!-- Footer -->
  <footer class="footer">
    <div class="footer-content">
      <p>&copy; 2024 MV Face Recognition. Powered by SvelteKit & Cloudflare Workers.</p>
    </div>
  </footer>
</div>

<style>
  .app {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }
  
  /* Header */
  .header {
    background-color: var(--surface-color);
    border-bottom: 1px solid var(--border-color);
    position: sticky;
    top: 0;
    z-index: 50;
    box-shadow: var(--shadow);
  }
  
  .header-content {
    max-width: 1200px;
    margin: 0 auto;
    padding: 0 1rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 4rem;
  }
  
  .header-left {
    display: flex;
    align-items: center;
    gap: 1rem;
  }
  
  .mobile-menu-button {
    display: none;
    background: none;
    border: none;
    cursor: pointer;
    padding: 0.5rem;
    border-radius: 0.375rem;
    transition: background-color 0.2s;
  }
  
  .mobile-menu-button:hover {
    background-color: var(--border-color);
  }
  
  .hamburger {
    display: block;
    width: 1.5rem;
    height: 1.5rem;
    position: relative;
  }
  
  .hamburger::before,
  .hamburger::after,
  .hamburger {
    background-color: var(--text-color);
  }
  
  .hamburger::before,
  .hamburger::after {
    content: '';
    position: absolute;
    width: 100%;
    height: 2px;
    left: 0;
    transition: all 0.3s;
  }
  
  .hamburger::before {
    top: 0;
  }
  
  .hamburger::after {
    bottom: 0;
  }
  
  .hamburger {
    height: 2px;
    top: 50%;
    transform: translateY(-50%);
  }
  
  .logo {
    font-size: 1.5rem;
    font-weight: 700;
    margin: 0;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    color: var(--text-color);
  }
  
  .logo-icon {
    font-size: 1.75rem;
  }
  
  /* Desktop Navigation */
  .desktop-nav {
    display: flex;
    gap: 0.5rem;
  }
  
  .nav-link {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 1rem;
    border-radius: 0.5rem;
    text-decoration: none;
    color: var(--text-secondary);
    font-weight: 500;
    transition: all 0.2s;
    white-space: nowrap;
  }
  
  .nav-link:hover {
    background-color: var(--border-color);
    color: var(--text-color);
  }
  
  .nav-link.active {
    background-color: var(--primary-color);
    color: white;
  }
  
  .nav-icon {
    font-size: 1.1rem;
  }
  
  /* Header Right */
  .header-right {
    display: flex;
    align-items: center;
    gap: 1rem;
  }
  
  .status-indicator {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.875rem;
    color: var(--text-secondary);
  }
  
  .status-dot {
    width: 0.5rem;
    height: 0.5rem;
    border-radius: 50%;
    background-color: var(--secondary-color);
    transition: background-color 0.3s;
  }
  
  .status-dot.online {
    background-color: var(--success-color);
  }
  
  .status-dot.offline {
    background-color: var(--error-color);
  }
  
  /* Mobile Navigation */
  .mobile-nav {
    position: fixed;
    top: 4rem;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 40;
    display: none;
  }
  
  .mobile-nav-content {
    background-color: var(--surface-color);
    border-bottom: 1px solid var(--border-color);
    padding: 1rem 0;
  }
  
  .mobile-nav-link {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 0.75rem 1.5rem;
    text-decoration: none;
    color: var(--text-secondary);
    font-weight: 500;
    transition: all 0.2s;
  }
  
  .mobile-nav-link:hover {
    background-color: var(--border-color);
    color: var(--text-color);
  }
  
  .mobile-nav-link.active {
    background-color: var(--primary-color);
    color: white;
  }
  
  .mobile-nav-overlay {
    flex: 1;
    background-color: rgba(0, 0, 0, 0.5);
  }
  
  /* Main Content */
  .main {
    flex: 1;
    max-width: 1200px;
    margin: 0 auto;
    padding: 2rem 1rem;
    width: 100%;
  }
  
  /* Footer */
  .footer {
    background-color: var(--surface-color);
    border-top: 1px solid var(--border-color);
    margin-top: auto;
  }
  
  .footer-content {
    max-width: 1200px;
    margin: 0 auto;
    padding: 1.5rem 1rem;
    text-align: center;
    color: var(--text-secondary);
    font-size: 0.875rem;
  }
  
  /* Mobile Styles */
  @media (max-width: 768px) {
    .mobile-menu-button {
      display: block;
    }
    
    .desktop-nav {
      display: none;
    }
    
    .mobile-nav {
      display: block;
    }
    
    .logo {
      font-size: 1.25rem;
    }
    
    .logo-icon {
      font-size: 1.5rem;
    }
    
    .main {
      padding: 1rem;
    }
    
    .header-content {
      padding: 0 1rem;
    }
  }
  
  @media (max-width: 480px) {
    .logo {
      font-size: 1.1rem;
    }
    
    .status-indicator {
      display: none;
    }
  }
</style>