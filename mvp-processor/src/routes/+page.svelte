<script lang="ts">
  import { onMount } from 'svelte';
  import { Card, Badge, Button, Flex, Grid, Background } from '$lib/components';

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
  <Flex direction="column" gap="lg">
    <Flex direction="column" gap="sm" align="center">
      <h1>🎬 Welcome to MV Face Recognition</h1>
      <p class="welcome-text">
        Automatically identify contestants in video content with real-time face overlays
      </p>
    </Flex>

    <Grid columns="auto" minWidth="280px" gap="md">
      <Card variant="elevated" padding="md" class="stat-card-wrapper">
        <Flex direction="row" gap="md" align="center">
          <span class="stat-icon">🎬</span>
          <Flex direction="column" gap="xs">
            <div class="stat-value">{stats.totalVideos}</div>
            <div class="stat-label">Videos Processed</div>
          </Flex>
        </Flex>
      </Card>

      <Card variant="elevated" padding="md" class="stat-card-wrapper">
        <Flex direction="row" gap="md" align="center">
          <span class="stat-icon">👥</span>
          <Flex direction="column" gap="xs">
            <div class="stat-value">{stats.totalContestants}</div>
            <div class="stat-label">Contestants</div>
          </Flex>
        </Flex>
      </Card>

      <Card variant="elevated" padding="md" class="stat-card-wrapper">
        <Flex direction="row" gap="md" align="center">
          <span class="stat-icon">🚩</span>
          <Flex direction="column" gap="xs">
            <div class="stat-value">{stats.pendingFlags}</div>
            <div class="stat-label">Pending Flags</div>
          </Flex>
        </Flex>
      </Card>
    </Grid>

    <Flex direction="column" gap="md">
      <h2>Quick Actions</h2>
      <Grid columns="auto" minWidth="280px" gap="md">
        {#each quickLinks as link}
          <Card variant="bordered" padding="md" interactive class="action-card">
            <a href={link.href} class="card-link">
              <Flex direction="row" gap="md" align="center">
                <span class="action-icon">{link.icon}</span>
                <Flex direction="column" gap="xs" class="action-content">
                  <div class="action-label">{link.label}</div>
                  <div class="action-description">{link.description}</div>
                </Flex>
                <span class="action-arrow">→</span>
              </Flex>
            </a>
          </Card>
        {/each}
      </Grid>
    </Flex>

    <Card variant="bordered" padding="lg" class="cta-card" shadow={true}>
      <Flex direction="row" justify="between" align="center" gap="lg">
        <Flex direction="column" gap="sm">
          <h3>Ready to watch annotated videos?</h3>
          <p>Jump into the video player to see face recognition in action</p>
        </Flex>
        <Button variant="primary" size="lg" href="/video-player">
          ▶️ Open Video Player
        </Button>
      </Flex>
    </Card>
  </Flex>
</div>

<style>
  .dashboard-page {
    padding: var(--space-6);
    max-width: 1400px;
    margin: 0 auto;
  }

  h1 {
    font-size: var(--text-h1-size);
    font-weight: 700;
    margin: 0;
    background: linear-gradient(135deg, var(--brand-medium), var(--color-secondary-400));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }

  h2 {
    font-size: var(--text-h4-size);
    font-weight: 600;
    margin: 0;
  }

  h3 {
    font-size: var(--text-h4-size);
    font-weight: 600;
    margin: 0;
  }

  .welcome-text {
    font-size: var(--text-body-lg-size);
    color: var(--text-secondary);
    margin: 0;
  }

  :global(.stat-card-wrapper) {
    transition: transform var(--duration-normal) var(--ease-out),
                box-shadow var(--duration-normal) var(--ease-out);
  }

  :global(.stat-card-wrapper:hover) {
    transform: translateY(-2px);
  }

  .stat-icon {
    font-size: 2rem;
    line-height: 1;
  }

  .stat-value {
    font-size: var(--text-h2-size);
    font-weight: 700;
    color: var(--brand-medium);
  }

  .stat-label {
    font-size: var(--text-body-sm-size);
    color: var(--text-secondary);
  }

  :global(.action-card) {
    transition: all var(--duration-normal) var(--ease-out);
  }

  :global(.action-card:hover) {
    border-color: var(--brand-medium);
    background-color: var(--surface-tertiary);
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

  :global(.action-card:hover) .action-arrow {
    transform: translateX(4px);
    color: var(--brand-medium);
  }

  .card-link {
    text-decoration: none;
    color: inherit;
    width: 100%;
    display: block;
  }

  :global(.cta-card) {
    background: linear-gradient(135deg, var(--brand-alpha-weak), rgba(14, 165, 233, 0.1));
    border-color: var(--border-medium);
  }

  p {
    color: var(--text-secondary);
    margin: 0;
  }

  @media (max-width: 768px) {
    h1 {
      font-size: var(--text-h2-size);
    }

    :global(.cta-card) {
      flex-direction: column;
      text-align: center;
    }
  }
</style>
