<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';

  // Import design system
  import '$lib/styles/design-tokens.css';
  import { StatusIndicator, NavigationLink, IconButton } from '$lib/components';
  
  // Navigation items (YouTube moved to Admin for Cloudflare Zero Trust auth)
  const navItems = [
    { href: '/', label: 'Dashboard', icon: '🎬' },
    { href: '/video-player', label: 'Video Player', icon: '▶️' },
    { href: '/processing', label: 'Processing', icon: '⚙️' },
    { href: '/analytics', label: 'Analytics', icon: '📊' },
    { href: '/admin', label: 'Admin', icon: '🔐' }
  ];
  
  let mobileMenuOpen = false;
  let systemStatus: 'online' | 'offline' | 'checking' = 'checking';
  let currentTime = new Date().toLocaleString();

  onMount(() => {
    const timeInterval = setInterval(() => {
      currentTime = new Date().toLocaleString();
    }, 1000);

    const checkStatus = async () => {
      try {
        const response = await fetch('/api/system/status');
        systemStatus = response.ok ? 'online' : 'offline';
      } catch {
        systemStatus = 'offline';
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
    <StatusIndicator status={systemStatus} size="md" />
    <div class="timestamp">{currentTime}</div>
  </div>

  <!-- Navigation -->
  <nav class="nav-bar">
    <div class="nav-content">
      <IconButton
        variant="ghost"
        size="md"
        on:click={toggleMobileMenu}
        aria-label="Toggle menu"
        class="mobile-menu-button"
      >
        ☰
      </IconButton>

      <div class="nav-links" class:mobile-open={mobileMenuOpen}>
        {#each navItems as item}
          <NavigationLink
            href={item.href}
            active={$page.url.pathname === item.href}
            icon={item.icon}
            on:click={closeMobileMenu}
          >
            {item.label}
          </NavigationLink>
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
    background-color: var(--bg-primary);
    color: var(--text-primary);
    display: flex;
    flex-direction: column;
    font-family: var(--font-sans);
  }

  .header-bar {
    height: 60px;
    background-color: var(--bg-secondary);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 var(--space-5);
    border-bottom: 1px solid var(--border-default);
    flex-shrink: 0;
  }

  .app-title {
    font-size: var(--text-h4-size);
    font-weight: var(--text-label-weight);
    color: var(--text-primary);
  }

  .timestamp {
    font-size: var(--text-body-sm-size);
    color: var(--text-secondary);
  }

  .nav-bar {
    background-color: var(--bg-tertiary);
    border-bottom: 1px solid var(--border-default);
    flex-shrink: 0;
  }

  .nav-content {
    display: flex;
    align-items: center;
    padding: 0 var(--space-5);
    height: 50px;
  }

  :global(.mobile-menu-button) {
    display: none;
  }

  .nav-links {
    display: flex;
    gap: var(--space-2);
    align-items: center;
  }

  .main-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }

  /* Mobile Styles */
  @media (max-width: 768px) {
    :global(.mobile-menu-button) {
      display: inline-flex;
    }

    .nav-links {
      position: absolute;
      top: 100%;
      left: 0;
      right: 0;
      background-color: var(--bg-tertiary);
      flex-direction: column;
      border-bottom: 1px solid var(--border-default);
      display: none;
      z-index: var(--z-overlay);
    }

    .nav-links.mobile-open {
      display: flex;
    }

    .app-title {
      font-size: var(--text-body-size);
    }

    .timestamp {
      display: none;
    }
  }
</style>