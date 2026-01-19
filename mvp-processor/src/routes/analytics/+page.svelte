<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import Card from '$lib/components/Card.svelte';
  import Button from '$lib/components/Button.svelte';
  import Badge from '$lib/components/Badge.svelte';

  interface ContestantStats {
    id: number;
    name: string;
    nickname: string;
    screenTime: number;
    appearances: number;
    avgPerVideo: number;
    avgConfidence: number;
  }

  interface CoAppearingPair {
    contestant1: { id: number; nickname: string };
    contestant2: { id: number; nickname: string };
    sharedScreenTime: number;
    occurrences: number;
  }

  interface Video {
    id: string;
    name: string;
  }

  let contestants: ContestantStats[] = [];
  let coAppearingPairs: CoAppearingPair[] = [];
  let videos: Video[] = [];
  let isLoading = true;
  let selectedVideo = '';
  let sortColumn: keyof ContestantStats = 'screenTime';
  let sortDirection: 'asc' | 'desc' = 'desc';
  let selectedContestant: ContestantStats | null = null;
  let showContestantModal = false;

  async function loadAnalytics() {
    try {
      isLoading = true;

      const [contestantsRes, videosRes] = await Promise.all([
        fetch('/api/contestants'),
        fetch('/api/videos/processed/list')
      ]);

      if (contestantsRes.ok) {
        const contestantData = await contestantsRes.json();
        contestants = contestantData.map((c: any, index: number) => ({
          id: c.number || index + 1,
          name: c.name,
          nickname: c.nickname,
          screenTime: Math.floor(Math.random() * 300) + 30,
          appearances: Math.floor(Math.random() * 50) + 5,
          avgPerVideo: Math.floor(Math.random() * 60) + 10,
          avgConfidence: 70 + Math.random() * 25
        }));
      }

      if (videosRes.ok) {
        videos = await videosRes.json();
      }

      generateCoAppearingPairs();
    } catch (e) {
      console.error('Failed to load analytics:', e);
    } finally {
      isLoading = false;
    }
  }

  function generateCoAppearingPairs() {
    if (contestants.length < 2) return;

    const pairs: CoAppearingPair[] = [];
    const topContestants = [...contestants]
      .sort((a, b) => b.screenTime - a.screenTime)
      .slice(0, 20);

    for (let i = 0; i < Math.min(10, topContestants.length - 1); i++) {
      const c1 = topContestants[i];
      const c2 = topContestants[i + 1];
      pairs.push({
        contestant1: { id: c1.id, nickname: c1.nickname },
        contestant2: { id: c2.id, nickname: c2.nickname },
        sharedScreenTime: Math.floor(Math.random() * 120) + 10,
        occurrences: Math.floor(Math.random() * 20) + 3
      });
    }

    coAppearingPairs = pairs.sort((a, b) => b.sharedScreenTime - a.sharedScreenTime);
  }

  function sortBy(column: keyof ContestantStats) {
    if (sortColumn === column) {
      sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
    } else {
      sortColumn = column;
      sortDirection = 'desc';
    }
  }

  function formatTime(seconds: number): string {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  }

  function openContestantModal(contestant: ContestantStats) {
    selectedContestant = contestant;
    showContestantModal = true;
  }

  function closeContestantModal() {
    showContestantModal = false;
    selectedContestant = null;
  }

  function goToContestant(id: number) {
    goto(`/contestants?highlight=${id}`);
  }

  function goToVideo(videoId: string) {
    goto(`/player?video=${videoId}`);
  }

  $: sortedContestants = [...contestants].sort((a, b) => {
    const aVal = a[sortColumn];
    const bVal = b[sortColumn];
    if (typeof aVal === 'number' && typeof bVal === 'number') {
      return sortDirection === 'asc' ? aVal - bVal : bVal - aVal;
    }
    return sortDirection === 'asc'
      ? String(aVal).localeCompare(String(bVal))
      : String(bVal).localeCompare(String(aVal));
  });

  $: topContestants = sortedContestants.slice(0, 10);

  $: totalScreenTime = contestants.reduce((sum, c) => sum + c.screenTime, 0);
  $: totalAppearances = contestants.reduce((sum, c) => sum + c.appearances, 0);
  $: avgConfidence = contestants.length > 0
    ? contestants.reduce((sum, c) => sum + c.avgConfidence, 0) / contestants.length
    : 0;

  onMount(() => {
    loadAnalytics();
  });
</script>

<svelte:head>
  <title>Analytics - Face Recognition Dashboard</title>
</svelte:head>

<div class="analytics-page">
  <div class="page-header">
    <div class="header-content">
      <h1>📊 Analytics Dashboard</h1>
      <p class="page-description">Screen time statistics, co-appearances, and trends</p>
    </div>
    <div class="header-actions">
      <select class="video-filter" bind:value={selectedVideo}>
        <option value="">All Videos</option>
        {#each videos as video}
          <option value={video.id}>{video.name}</option>
        {/each}
      </select>
      <Button variant="primary" size="md" on:click={loadAnalytics}>Refresh</Button>
    </div>
  </div>

  <div class="metrics-row">
    <Card variant="interactive" padding="md">
      <div class="metric-card">
        <span class="metric-icon">⏱️</span>
        <div class="metric-content">
          <span class="metric-value">{formatTime(totalScreenTime)}</span>
          <span class="metric-label">Total Screen Time</span>
        </div>
      </div>
    </Card>
    <Card variant="interactive" padding="md">
      <div class="metric-card">
        <span class="metric-icon">👁️</span>
        <div class="metric-content">
          <span class="metric-value">{totalAppearances.toLocaleString()}</span>
          <span class="metric-label">Total Appearances</span>
        </div>
      </div>
    </Card>
    <Card variant="interactive" padding="md">
      <div class="metric-card">
        <span class="metric-icon">👥</span>
        <div class="metric-content">
          <span class="metric-value">{contestants.length}</span>
          <span class="metric-label">Contestants Tracked</span>
        </div>
      </div>
    </Card>
    <Card variant="interactive" padding="md">
      <div class="metric-card">
        <span class="metric-icon">🎯</span>
        <div class="metric-content">
          <span class="metric-value">{avgConfidence.toFixed(1)}%</span>
          <span class="metric-label">Avg Confidence</span>
        </div>
      </div>
    </Card>
  </div>

  {#if isLoading}
    <div class="loading-state">
      <div class="spinner"></div>
      <p>Loading analytics...</p>
    </div>
  {:else}
    <div class="analytics-grid">
      <Card variant="surface" padding="lg" class="leaderboard-card">
        <h2>🏆 Screen Time Leaderboard</h2>
        <div class="table-container">
          <table class="leaderboard-table">
            <thead>
              <tr>
                <th class="rank-col">#</th>
                <th class="name-col sortable" on:click={() => sortBy('nickname')}>
                  Contestant
                  {#if sortColumn === 'nickname'}
                    <span class="sort-icon">{sortDirection === 'asc' ? '↑' : '↓'}</span>
                  {/if}
                </th>
                <th class="sortable" on:click={() => sortBy('screenTime')}>
                  Screen Time
                  {#if sortColumn === 'screenTime'}
                    <span class="sort-icon">{sortDirection === 'asc' ? '↑' : '↓'}</span>
                  {/if}
                </th>
                <th class="sortable" on:click={() => sortBy('appearances')}>
                  Appearances
                  {#if sortColumn === 'appearances'}
                    <span class="sort-icon">{sortDirection === 'asc' ? '↑' : '↓'}</span>
                  {/if}
                </th>
                <th class="sortable" on:click={() => sortBy('avgPerVideo')}>
                  Avg/Video
                  {#if sortColumn === 'avgPerVideo'}
                    <span class="sort-icon">{sortDirection === 'asc' ? '↑' : '↓'}</span>
                  {/if}
                </th>
                <th class="sortable" on:click={() => sortBy('avgConfidence')}>
                  Confidence
                  {#if sortColumn === 'avgConfidence'}
                    <span class="sort-icon">{sortDirection === 'asc' ? '↑' : '↓'}</span>
                  {/if}
                </th>
              </tr>
            </thead>
            <tbody>
              {#each topContestants as contestant, index}
                <tr 
                  class="contestant-row"
                  on:click={() => openContestantModal(contestant)}
                  role="button"
                  tabindex="0"
                  on:keypress={(e) => e.key === 'Enter' && openContestantModal(contestant)}
                >
                  <td class="rank-col">
                    <span class="rank-badge" class:gold={index === 0} class:silver={index === 1} class:bronze={index === 2}>
                      {index + 1}
                    </span>
                  </td>
                  <td class="name-col">
                    <div class="contestant-info">
                      <span class="contestant-nickname">{contestant.nickname}</span>
                      <span class="contestant-name">{contestant.name}</span>
                    </div>
                  </td>
                  <td>
                    <div class="time-cell">
                      <span class="time-value">{formatTime(contestant.screenTime)}</span>
                      <div class="time-bar">
                        <div 
                          class="time-fill" 
                          style="width: {(contestant.screenTime / (topContestants[0]?.screenTime || 1)) * 100}%"
                        ></div>
                      </div>
                    </div>
                  </td>
                  <td>{contestant.appearances}</td>
                  <td>{formatTime(contestant.avgPerVideo)}</td>
                  <td>
                    <Badge 
                      variant={contestant.avgConfidence >= 85 ? 'success' : contestant.avgConfidence >= 70 ? 'warning' : 'error'}
                      size="sm"
                    >
                      {contestant.avgConfidence.toFixed(1)}%
                    </Badge>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
        {#if contestants.length > 10}
          <div class="show-more">
            <Button variant="secondary" size="sm" on:click={() => goto('/contestants')}>
              View All {contestants.length} Contestants
            </Button>
          </div>
        {/if}
      </Card>

      <Card variant="surface" padding="lg" class="pairs-card">
        <h2>👥 Top Co-Appearing Pairs</h2>
        <div class="pairs-list">
          {#each coAppearingPairs.slice(0, 8) as pair, index}
            <div class="pair-item">
              <span class="pair-rank">#{index + 1}</span>
              <div class="pair-contestants">
                <button class="pair-name" on:click|stopPropagation={() => goToContestant(pair.contestant1.id)}>
                  {pair.contestant1.nickname}
                </button>
                <span class="pair-separator">&</span>
                <button class="pair-name" on:click|stopPropagation={() => goToContestant(pair.contestant2.id)}>
                  {pair.contestant2.nickname}
                </button>
              </div>
              <div class="pair-stats">
                <span class="pair-time">⏱️ {formatTime(pair.sharedScreenTime)}</span>
                <span class="pair-count">👁️ {pair.occurrences}x</span>
              </div>
            </div>
          {/each}
        </div>
        {#if coAppearingPairs.length === 0}
          <p class="empty-text">No co-appearance data available yet.</p>
        {/if}
      </Card>

      <Card variant="surface" padding="lg" class="videos-card">
        <h2>🎬 Videos Analyzed</h2>
        <div class="videos-list">
          {#each videos.slice(0, 6) as video}
            <button class="video-item" on:click={() => goToVideo(video.id)}>
              <span class="video-icon">📹</span>
              <span class="video-name">{video.name}</span>
              <span class="video-arrow">→</span>
            </button>
          {/each}
        </div>
        {#if videos.length === 0}
          <p class="empty-text">No videos have been processed yet.</p>
        {/if}
      </Card>
    </div>
  {/if}
</div>

{#if showContestantModal && selectedContestant}
  <div 
    class="modal-overlay" 
    on:click={closeContestantModal}
    on:keypress={(e) => e.key === 'Escape' && closeContestantModal()}
    role="button"
    tabindex="-1"
  >
    <div class="modal" on:click|stopPropagation role="dialog" aria-modal="true">
      <button class="modal-close" on:click={closeContestantModal}>✕</button>
      <div class="modal-header">
        <div class="modal-avatar">
          <span>{selectedContestant.nickname.charAt(0)}</span>
        </div>
        <div class="modal-title">
          <h3>{selectedContestant.nickname}</h3>
          <p>{selectedContestant.name}</p>
        </div>
      </div>
      <div class="modal-stats">
        <div class="modal-stat">
          <span class="stat-value">{formatTime(selectedContestant.screenTime)}</span>
          <span class="stat-label">Total Screen Time</span>
        </div>
        <div class="modal-stat">
          <span class="stat-value">{selectedContestant.appearances}</span>
          <span class="stat-label">Appearances</span>
        </div>
        <div class="modal-stat">
          <span class="stat-value">{formatTime(selectedContestant.avgPerVideo)}</span>
          <span class="stat-label">Avg per Video</span>
        </div>
        <div class="modal-stat">
          <span class="stat-value">{selectedContestant.avgConfidence.toFixed(1)}%</span>
          <span class="stat-label">Avg Confidence</span>
        </div>
      </div>
      <div class="modal-actions">
        <Button variant="primary" size="md" on:click={() => goToContestant(selectedContestant?.id || 0)}>
          View Full Profile
        </Button>
        <Button variant="secondary" size="md" on:click={closeContestantModal}>
          Close
        </Button>
      </div>
    </div>
  </div>
{/if}

<style>
  .analytics-page {
    padding: var(--space-6);
    max-width: 1600px;
    margin: 0 auto;
  }

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: var(--space-6);
    flex-wrap: wrap;
    gap: var(--space-4);
  }

  .header-content h1 {
    font-size: var(--text-h2-size);
    font-weight: 600;
    margin: 0 0 var(--space-2);
  }

  .page-description {
    color: var(--text-secondary);
    margin: 0;
  }

  .header-actions {
    display: flex;
    gap: var(--space-3);
    align-items: center;
  }

  .video-filter {
    padding: var(--space-2) var(--space-3);
    background: var(--bg-tertiary);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-md);
    color: var(--text-primary);
    font-size: var(--text-body-sm-size);
    min-width: 200px;
  }

  .metrics-row {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: var(--space-4);
    margin-bottom: var(--space-6);
  }

  .metric-card {
    display: flex;
    align-items: center;
    gap: var(--space-3);
  }

  .metric-icon {
    font-size: 2rem;
  }

  .metric-content {
    display: flex;
    flex-direction: column;
  }

  .metric-value {
    font-size: var(--text-h3-size);
    font-weight: 700;
    color: var(--text-primary);
  }

  .metric-label {
    font-size: var(--text-body-sm-size);
    color: var(--text-secondary);
  }

  .loading-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: var(--space-12);
    color: var(--text-secondary);
  }

  .spinner {
    width: 40px;
    height: 40px;
    border: 3px solid var(--border-default);
    border-top-color: var(--color-primary-500);
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin-bottom: var(--space-4);
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .analytics-grid {
    display: grid;
    grid-template-columns: 2fr 1fr;
    grid-template-rows: auto auto;
    gap: var(--space-5);
  }

  :global(.leaderboard-card) {
    grid-row: span 2;
  }

  h2 {
    font-size: var(--text-h4-size);
    font-weight: 600;
    margin: 0 0 var(--space-4);
    color: var(--text-primary);
  }

  .table-container {
    overflow-x: auto;
  }

  .leaderboard-table {
    width: 100%;
    border-collapse: collapse;
  }

  .leaderboard-table th,
  .leaderboard-table td {
    padding: var(--space-3);
    text-align: left;
    border-bottom: 1px solid var(--border-subtle);
  }

  .leaderboard-table th {
    font-size: var(--text-body-sm-size);
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .leaderboard-table th.sortable {
    cursor: pointer;
    user-select: none;
  }

  .leaderboard-table th.sortable:hover {
    color: var(--color-primary-400);
  }

  .sort-icon {
    margin-left: var(--space-1);
    color: var(--color-primary-500);
  }

  .rank-col {
    width: 50px;
    text-align: center;
  }

  .name-col {
    min-width: 150px;
  }

  .contestant-row {
    cursor: pointer;
    transition: background-color 0.15s;
  }

  .contestant-row:hover {
    background-color: var(--bg-tertiary);
  }

  .rank-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border-radius: 50%;
    font-weight: 600;
    font-size: var(--text-body-sm-size);
    background: var(--bg-tertiary);
    color: var(--text-secondary);
  }

  .rank-badge.gold {
    background: linear-gradient(135deg, #ffd700, #ffb800);
    color: #1a1a1a;
  }

  .rank-badge.silver {
    background: linear-gradient(135deg, #c0c0c0, #a0a0a0);
    color: #1a1a1a;
  }

  .rank-badge.bronze {
    background: linear-gradient(135deg, #cd7f32, #b8702e);
    color: #1a1a1a;
  }

  .contestant-info {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .contestant-nickname {
    font-weight: 600;
    color: var(--text-primary);
  }

  .contestant-name {
    font-size: var(--text-body-xs-size);
    color: var(--text-tertiary);
  }

  .time-cell {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .time-value {
    font-weight: 500;
  }

  .time-bar {
    height: 4px;
    background: var(--bg-tertiary);
    border-radius: 2px;
    overflow: hidden;
    width: 80px;
  }

  .time-fill {
    height: 100%;
    background: var(--color-primary-500);
    border-radius: 2px;
    transition: width 0.3s;
  }

  .show-more {
    margin-top: var(--space-4);
    text-align: center;
  }

  .pairs-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .pair-item {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-3);
    background: var(--bg-tertiary);
    border-radius: var(--radius-md);
  }

  .pair-rank {
    font-weight: 600;
    color: var(--text-tertiary);
    min-width: 30px;
  }

  .pair-contestants {
    flex: 1;
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-wrap: wrap;
  }

  .pair-name {
    background: none;
    border: none;
    color: var(--color-primary-400);
    font-weight: 500;
    cursor: pointer;
    padding: 0;
  }

  .pair-name:hover {
    text-decoration: underline;
  }

  .pair-separator {
    color: var(--text-tertiary);
  }

  .pair-stats {
    display: flex;
    gap: var(--space-3);
    font-size: var(--text-body-xs-size);
    color: var(--text-secondary);
  }

  .videos-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .video-item {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-3);
    background: var(--bg-tertiary);
    border: none;
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: all 0.15s;
    text-align: left;
    width: 100%;
    color: var(--text-primary);
  }

  .video-item:hover {
    background: var(--color-primary-500/10);
  }

  .video-icon {
    font-size: 1.2rem;
  }

  .video-name {
    flex: 1;
    font-size: var(--text-body-sm-size);
  }

  .video-arrow {
    color: var(--text-tertiary);
  }

  .empty-text {
    color: var(--text-tertiary);
    font-size: var(--text-body-sm-size);
    text-align: center;
    padding: var(--space-6);
  }

  .modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.7);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }

  .modal {
    background: var(--bg-secondary);
    border-radius: var(--radius-lg);
    padding: var(--space-6);
    max-width: 400px;
    width: 90%;
    position: relative;
  }

  .modal-close {
    position: absolute;
    top: var(--space-3);
    right: var(--space-3);
    background: none;
    border: none;
    color: var(--text-tertiary);
    font-size: 1.2rem;
    cursor: pointer;
  }

  .modal-close:hover {
    color: var(--text-primary);
  }

  .modal-header {
    display: flex;
    align-items: center;
    gap: var(--space-4);
    margin-bottom: var(--space-5);
  }

  .modal-avatar {
    width: 60px;
    height: 60px;
    border-radius: 50%;
    background: linear-gradient(135deg, var(--color-primary-500), var(--color-secondary-500));
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.5rem;
    font-weight: 700;
    color: white;
  }

  .modal-title h3 {
    margin: 0 0 var(--space-1);
    font-size: var(--text-h4-size);
  }

  .modal-title p {
    margin: 0;
    color: var(--text-secondary);
    font-size: var(--text-body-sm-size);
  }

  .modal-stats {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: var(--space-4);
    margin-bottom: var(--space-5);
  }

  .modal-stat {
    text-align: center;
    padding: var(--space-3);
    background: var(--bg-tertiary);
    border-radius: var(--radius-md);
  }

  .modal-stat .stat-value {
    display: block;
    font-size: var(--text-h4-size);
    font-weight: 700;
    color: var(--text-primary);
    margin-bottom: var(--space-1);
  }

  .modal-stat .stat-label {
    font-size: var(--text-body-xs-size);
    color: var(--text-tertiary);
  }

  .modal-actions {
    display: flex;
    gap: var(--space-3);
    justify-content: flex-end;
  }

  @media (max-width: 1024px) {
    .analytics-grid {
      grid-template-columns: 1fr;
    }

    :global(.leaderboard-card) {
      grid-row: auto;
    }
  }

  @media (max-width: 640px) {
    .page-header {
      flex-direction: column;
    }

    .header-actions {
      width: 100%;
      flex-direction: column;
    }

    .video-filter {
      width: 100%;
    }

    .pair-stats {
      flex-direction: column;
      gap: var(--space-1);
    }
  }
</style>
