<script lang="ts">
  import { onMount } from 'svelte';
  import { Card, Badge, Button } from '$lib/components';

  interface SystemStats {
    totalVideos: number;
    totalContestants: number;
    totalFacesDetected: number;
    pendingFlags: number;
  }

  let stats: SystemStats = {
    totalVideos: 0,
    totalContestants: 0,
    totalFacesDetected: 0,
    pendingFlags: 0
  };

  let isLoading = true;

  const quickLinks = [
    { href: '/player', icon: '▶️', label: 'Video Player', description: 'Watch annotated videos with face overlays' },
    { href: '/contestants', icon: '👥', label: 'Contestants', description: 'Browse contestant directory' },
    { href: '/analytics', icon: '📊', label: 'Analytics', description: 'View screen time and statistics' },
    { href: '/ingestion', icon: '📤', label: 'Ingestion', description: 'Process new videos' },
    { href: '/flagging', icon: '🚩', label: 'Flagging', description: 'Review face corrections' },
  ];

  async function loadStats() {
    try {
      isLoading = true;
      
      const [videosRes, contestantsRes, flagsRes] = await Promise.allSettled([
        fetch('/api/videos/processed/list'),
        fetch('/api/contestants'),
        fetch('/api/faces/flagged?details=true')
      ]);

      if (videosRes.status === 'fulfilled' && videosRes.value.ok) {
        const videos = await videosRes.value.json();
        stats.totalVideos = Array.isArray(videos) ? videos.length : 0;
      }

      if (contestantsRes.status === 'fulfilled' && contestantsRes.value.ok) {
        const contestants = await contestantsRes.value.json();
        stats.totalContestants = Array.isArray(contestants) ? contestants.length : 0;
      }

      if (flagsRes.status === 'fulfilled' && flagsRes.value.ok) {
        const data = await flagsRes.value.json();
        const flags = data.flagged_faces || [];
        stats.pendingFlags = flags.filter((f: any) => f.status === 'pending').length;
      }

    } catch (e) {
      console.error('Failed to load stats:', e);
    } finally {
      isLoading = false;
    }
  }

  onMount(() => {
    loadStats();
  });
</script>

<svelte:head>
  <title>Dashboard - MV Face Recognition</title>
</svelte:head>

<div class="dashboard-page">
  <div class="welcome-section">
    <h1>🎬 Welcome to MV Face Recognition</h1>
    <p class="welcome-text">
      Automatically identify contestants in video content with real-time face overlays
    </p>
  </div>

  <div class="stats-grid">
    <Card variant="interactive" padding="md">
      <div class="stat-card">
        <span class="stat-icon">🎬</span>
        <div class="stat-content">
          <div class="stat-value">{stats.totalVideos}</div>
          <div class="stat-label">Videos Processed</div>
        </div>
      </div>
    </Card>

    <Card variant="interactive" padding="md">
      <div class="stat-card">
        <span class="stat-icon">👥</span>
        <div class="stat-content">
          <div class="stat-value">{stats.totalContestants}</div>
          <div class="stat-label">Contestants</div>
        </div>
      </div>
    </Card>

    <Card variant="interactive" padding="md">
      <div class="stat-card">
        <span class="stat-icon">🚩</span>
        <div class="stat-content">
          <div class="stat-value">{stats.pendingFlags}</div>
          <div class="stat-label">Pending Flags</div>
        </div>
      </div>
    </Card>
  </div>

  <div class="quick-actions">
    <h2>Quick Actions</h2>
    <div class="actions-grid">
      {#each quickLinks as link}
        <a href={link.href} class="action-card">
          <span class="action-icon">{link.icon}</span>
          <div class="action-content">
            <div class="action-label">{link.label}</div>
            <div class="action-description">{link.description}</div>
          </div>
          <span class="action-arrow">→</span>
        </a>
      {/each}
    </div>
  </div>

  <Card variant="bordered" padding="lg" class="cta-card">
    <div class="cta-content">
      <div class="cta-text">
        <h3>Ready to watch annotated videos?</h3>
        <p>Jump into the video player to see face recognition in action</p>
      </div>
      <Button variant="primary" size="lg" href="/player">
        ▶️ Open Video Player
      </Button>
    </div>
  </Card>
</div>

<style>
  .dashboard-page {
    padding: var(--space-6);
    max-width: 1200px;
    margin: 0 auto;
  }

  .welcome-section {
    text-align: center;
    margin-bottom: var(--space-8);
  }

  .welcome-section h1 {
    font-size: var(--text-h1-size);
    font-weight: 700;
    margin: 0 0 var(--space-3);
    background: linear-gradient(135deg, var(--color-primary-400), var(--color-secondary-400));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }

  .welcome-text {
    font-size: var(--text-body-lg-size);
    color: var(--text-secondary);
    margin: 0;
  }

  .stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: var(--space-4);
    margin-bottom: var(--space-8);
  }

  .stat-card {
    display: flex;
    align-items: center;
    gap: var(--space-4);
  }

  .stat-icon {
    font-size: 2rem;
    line-height: 1;
  }

  .stat-content {
    flex: 1;
  }

  .stat-value {
    font-size: var(--text-h2-size);
    font-weight: 700;
    color: var(--text-primary);
    line-height: 1;
  }

  .stat-label {
    font-size: var(--text-body-sm-size);
    color: var(--text-secondary);
    margin-top: var(--space-1);
  }

  .quick-actions {
    margin-bottom: var(--space-8);
  }

  .quick-actions h2 {
    font-size: var(--text-h4-size);
    font-weight: 600;
    margin: 0 0 var(--space-4);
  }

  .actions-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: var(--space-4);
  }

  .action-card {
    display: flex;
    align-items: center;
    gap: var(--space-4);
    padding: var(--space-4);
    background-color: var(--bg-secondary);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-lg);
    text-decoration: none;
    color: inherit;
    transition: var(--transition-all);
  }

  .action-card:hover {
    border-color: var(--color-primary-500);
    background-color: var(--bg-tertiary);
    transform: translateX(4px);
  }

  .action-icon {
    font-size: 1.5rem;
    line-height: 1;
  }

  .action-content {
    flex: 1;
  }

  .action-label {
    font-weight: 600;
    font-size: var(--text-body-size);
    color: var(--text-primary);
    margin-bottom: var(--space-1);
  }

  .action-description {
    font-size: var(--text-body-sm-size);
    color: var(--text-secondary);
  }

  .action-arrow {
    font-size: 1.25rem;
    color: var(--text-tertiary);
    transition: transform var(--duration-fast) var(--ease-out);
  }

  .action-card:hover .action-arrow {
    transform: translateX(4px);
    color: var(--color-primary-400);
  }

  :global(.cta-card) {
    background: linear-gradient(135deg, rgba(59, 130, 246, 0.1), rgba(14, 165, 233, 0.1));
  }

  .cta-content {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-6);
  }

  .cta-text h3 {
    font-size: var(--text-h4-size);
    font-weight: 600;
    margin: 0 0 var(--space-2);
  }

  .cta-text p {
    color: var(--text-secondary);
    margin: 0;
  }

  @media (max-width: 768px) {
    .welcome-section h1 {
      font-size: var(--text-h2-size);
    }

    .cta-content {
      flex-direction: column;
      text-align: center;
    }

    .actions-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
