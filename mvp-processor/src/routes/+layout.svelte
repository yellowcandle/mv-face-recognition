<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { QueryClient, QueryClientProvider } from '@tanstack/svelte-query';

  // Import design system
  import '$lib/styles/design-tokens.css';
  import { StatusIndicator, NavigationLink, IconButton } from '$lib/components';
  
  // Create QueryClient instance
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 1000 * 60 * 5, // 5 minutes
        cacheTime: 1000 * 60 * 10, // 10 minutes
      }
    }
  });
  
  // Navigation items
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
</script>

<QueryClientProvider {queryClient}>
  <div class="layout">
    <!-- Header -->
    <header class="header">
      <div class="header-left">
        <button class="mobile-menu-toggle" on:click={() => mobileMenuOpen = !mobileMenuOpen}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M3 12h18M3 6h18M3 18h18"></path>
          </svg>
        </button>
        <h1 class="app-title">MV Face Recognition</h1>
      </div>
      
      <div class="header-right">
        <div class="time-display">{currentTime}</div>
        <StatusIndicator status={systemStatus} />
      </div>
    </header>

    <!-- Navigation -->
    <nav class="nav {mobileMenuOpen ? 'mobile-open' : ''}">
      {#each navItems as item}
        <NavigationLink {item} currentPath={$page.url.pathname} />
      {/each}
    </nav>

    <!-- Mobile menu overlay -->
    {#if mobileMenuOpen}
      <div class="mobile-overlay" on:click={() => mobileMenuOpen = false}></div>
    {/if}

    <!-- Main Content -->
    <main class="main">
      <slot />
    </main>
  </div>
</QueryClientProvider>

<style>
  .layout {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }

  .header {
    height: 60px;
    background-color: var(--bg-primary);
    border-bottom: 1px solid var(--border-default);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 var(--space-4);
    position: sticky;
    top: 0;
    z-index: 50;
  }

  .header-left {
    display: flex;
    align-items: center;
    gap: var(--space-3);
  }

  .header-right {
    display: flex;
    align-items: center;
    gap: var(--space-4);
  }

  .app-title {
    font-size: var(--text-h3-size);
    font-weight: var(--text-h3-weight);
    color: var(--text-primary);
    margin: 0;
  }

  .mobile-menu-toggle {
    display: none;
    background: none;
    border: none;
    color: var(--text-primary);
    cursor: pointer;
    padding: var(--space-2);
  }

  .time-display {
    font-size: var(--text-body-sm-size);
    color: var(--text-secondary);
    font-family: var(--font-mono);
  }

  .nav {
    background-color: var(--bg-secondary);
    border-right: 1px solid var(--border-default);
    width: 240px;
    position: fixed;
    top: 60px;
    bottom: 0;
    overflow-y: auto;
    padding: var(--space-4) 0;
  }

  .main {
    margin-left: 240px;
    flex: 1;
    padding: var(--space-5);
    background-color: var(--bg-primary);
  }

  .mobile-overlay {
    position: fixed;
    top: 60px;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: rgba(0, 0, 0, 0.5);
    z-index: 40;
    display: none;
  }

  @media (max-width: 768px) {
    .mobile-menu-toggle {
      display: block;
    }

    .nav {
      position: fixed;
      top: 60px;
      left: -240px;
      z-index: 50;
      transition: left 0.3s ease;
    }

    .nav.mobile-open {
      left: 0;
    }

    .mobile-overlay {
      display: block;
    }

    .main {
      margin-left: 0;
      padding: var(--space-3);
    }

    .header-right {
      gap: var(--space-2);
    }

    .time-display {
      display: none;
    }
  }
</style>
