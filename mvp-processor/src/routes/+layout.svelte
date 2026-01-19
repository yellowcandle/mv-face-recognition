<script lang="ts">
  import { onMount } from 'svelte';
  import '$lib/styles/design-tokens.css';
  import { Sidebar, MobileNav, StatusIndicator } from '$lib/components';

  let systemStatus: 'online' | 'offline' | 'checking' = 'checking';
  let sidebarCollapsed = false;

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

<div class="app-layout">
  <Sidebar bind:collapsed={sidebarCollapsed} />

  <div class="main-area">
    <header class="app-header">
      <div class="header-left">
        <h1 class="header-title">Face Recognition Dashboard</h1>
      </div>
      <div class="header-right">
        <StatusIndicator status={systemStatus} size="md" />
      </div>
    </header>

    <main class="main-content">
      <slot />
    </main>
  </div>

  <MobileNav />
</div>

<style>
  .app-layout {
    display: flex;
    min-height: 100vh;
    background-color: var(--bg-primary);
    color: var(--text-primary);
  }

  .main-area {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-width: 0;
    min-height: 100vh;
  }

  .app-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: var(--header-height);
    padding: 0 var(--space-6);
    background-color: var(--bg-secondary);
    border-bottom: 1px solid var(--border-default);
    flex-shrink: 0;
  }

  .header-left {
    display: flex;
    align-items: center;
    gap: var(--space-4);
  }

  .header-title {
    font-family: var(--font-sans);
    font-size: var(--text-h4-size);
    font-weight: 600;
    color: var(--text-primary);
    margin: 0;
  }

  .header-right {
    display: flex;
    align-items: center;
    gap: var(--space-4);
  }

  .main-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 0;
    overflow: auto;
    background-color: var(--color-neutral-950, #030712);
  }

  @media (max-width: 768px) {
    .app-header {
      padding: 0 var(--space-4);
    }

    .header-title {
      font-size: var(--text-body-size);
    }

    .main-content {
      padding-bottom: var(--mobile-nav-height);
    }
  }
</style>
