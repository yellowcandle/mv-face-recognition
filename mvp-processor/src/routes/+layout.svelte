<script lang="ts">
  import { onMount } from 'svelte';
  import { browser } from '$app/environment';
  import { page } from '$app/stores';
  import { QueryClient, QueryClientProvider } from '@tanstack/svelte-query';

  import '$lib/styles/design-tokens.css';
  import { StatusIndicator, NavigationLink, IconButton, Flex, Background } from '$lib/components';
  
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        enabled: browser,
        staleTime: 1000 * 60 * 5,
        gcTime: 1000 * 60 * 10,
      }
    }
  });
  
  const navItems = [
    { href: '/', label: 'Dashboard', icon: '📊' },
    { href: '/player', label: 'Video Player', icon: '▶️' },
    { href: '/contestants', label: 'Contestants', icon: '👥' },
    { href: '/ingestion', label: 'Ingestion', icon: '📤' },
    { href: '/analytics', label: 'Analytics', icon: '📈' },
    { href: '/flagging', label: 'Flagging', icon: '🚩' },
    { href: '/processing', label: 'Processing', icon: '⚙️', separator: true },
    { href: '/admin', label: 'Admin', icon: '🔐' }
  ];
  
  let mobileMenuOpen = false;
  let systemStatus: 'online' | 'offline' | 'checking' = 'checking';

  onMount(() => {
    const checkStatus = async () => {
      try {
        const response = await fetch('/api/system/status');
        systemStatus = response.ok ? 'online' : 'offline';
      } catch {
        systemStatus = 'offline';
      }
    };

    void checkStatus();
    const statusInterval = setInterval(checkStatus, 30000);

    return () => {
      clearInterval(statusInterval);
    };
  });
</script>

<svelte:head>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin="anonymous" />
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&family=Noto+Sans+TC:wght@400;500;600;700&display=swap" rel="stylesheet" />
</svelte:head>

<QueryClientProvider client={queryClient}>
  <div class="layout">
    <Background variant="primary" radius="none" padding="none" class="header">
      <Flex direction="row" justify="between" align="center" gap="md" padding="md" class="header-content">
        <Flex direction="row" align="center" gap="sm">
          <button class="mobile-menu-toggle" on:click={() => mobileMenuOpen = !mobileMenuOpen}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M3 12h18M3 6h18M3 18h18"></path>
            </svg>
          </button>
          <h1 class="app-title">MV Face Recognition</h1>
        </Flex>
        
        <StatusIndicator status={systemStatus} />
      </Flex>
    </Background>

    <nav class="nav {mobileMenuOpen ? 'mobile-open' : ''}">
      {#each navItems as item}
        {#if item.separator}
          <div class="nav-separator"></div>
        {/if}
        <NavigationLink href={item.href} active={$page.url.pathname === item.href} icon={item.icon}>
          {item.label}
        </NavigationLink>
      {/each}
    </nav>

    {#if mobileMenuOpen}
      <div class="mobile-overlay" on:click={() => mobileMenuOpen = false}></div>
    {/if}

    <main class="main">
      <slot />
    </main>
  </div>
</QueryClientProvider>

<style>
  :global(.layout) {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }

  :global(.header) {
    position: sticky;
    top: 0;
    z-index: 50;
    border-bottom: 1px solid var(--border-medium);
    backdrop-filter: blur(8px);
    background-color: rgba(15, 23, 42, 0.8);
  }

  :global(.header-content) {
    height: 60px;
  }

  .app-title {
    font-family: var(--font-sans);
    font-size: var(--text-h4-size);
    font-weight: 600;
    color: var(--text-primary);
    margin: 0;
    white-space: nowrap;
  }

  .mobile-menu-toggle {
    display: none;
    background: none;
    border: none;
    color: var(--text-primary);
    cursor: pointer;
    padding: var(--space-2);
    border-radius: var(--radius-md);
    transition: background-color var(--duration-fast) var(--ease-in-out);
  }

  .mobile-menu-toggle:hover {
    background-color: var(--brand-alpha-weak);
  }

  .nav {
    background-color: var(--surface-secondary);
    border-right: 1px solid var(--border-medium);
    width: 240px;
    position: fixed;
    top: 60px;
    bottom: 0;
    overflow-y: auto;
    padding: var(--space-4) 0;
    z-index: 40;
  }

  .nav-separator {
    height: 1px;
    background-color: var(--border-medium);
    margin: var(--space-2) var(--space-4);
  }

  .main {
    margin-left: 240px;
    flex: 1;
    padding: var(--space-5);
    background-color: var(--surface-primary);
  }

  .mobile-overlay {
    position: fixed;
    top: 60px;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: rgba(0, 0, 0, 0.5);
    z-index: 35;
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
      transition: left var(--duration-normal) var(--ease-out);
    }

    .nav.mobile-open {
      left: 0;
    }

    .mobile-overlay {
      display: block;
    }

    .main {
      margin-left: 0;
    }
  }
</style>
