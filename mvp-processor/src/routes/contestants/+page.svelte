<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { Card, Badge, Input } from '$lib/components';

  interface Contestant {
    id: string;
    number: number;
    name: string;
    nickname: string;
    age?: number;
    has_photos?: boolean;
    has_embedding?: boolean;
  }

  interface Appearance {
    video_id: string;
    video_name?: string;
    timestamp: number;
    confidence: number;
  }

  interface ContestantStats {
    total_appearances: number;
    screen_time_seconds: number;
    videos_appeared_in: number;
  }

  let contestants: Contestant[] = [];
  let filteredContestants: Contestant[] = [];
  let searchQuery = '';
  let isLoading = true;
  let error: string | null = null;
  
  let selectedContestant: Contestant | null = null;
  let selectedContestantAppearances: Appearance[] = [];
  let selectedContestantStats: ContestantStats | null = null;
  let isLoadingAppearances = false;

  async function loadContestants() {
    try {
      isLoading = true;
      error = null;
      const response = await fetch('/api/contestants');
      if (response.ok) {
        contestants = await response.json();
        filteredContestants = contestants;
      } else {
        error = 'Failed to load contestants';
      }
    } catch (e) {
      console.error('Failed to load contestants:', e);
      error = 'Failed to load contestants';
    } finally {
      isLoading = false;
    }
  }

  function handleSearch() {
    const query = searchQuery.toLowerCase().trim();
    if (!query) {
      filteredContestants = contestants;
      return;
    }
    filteredContestants = contestants.filter(c =>
      c.name.toLowerCase().includes(query) ||
      c.nickname.toLowerCase().includes(query) ||
      String(c.number).includes(query)
    );
  }

  async function loadContestantAppearances(contestant: Contestant) {
    try {
      isLoadingAppearances = true;
      const response = await fetch(`/api/recognition/results?contestant_id=${contestant.id}`);
      if (response.ok) {
        const data = await response.json();
        const results = data.results || data || [];
        
        selectedContestantAppearances = results.map((r: any) => ({
          video_id: r.video_id,
          video_name: `Video ${r.video_id}`,
          timestamp: r.timestamp,
          confidence: r.confidence
        }));

        const uniqueVideos = new Set(results.map((r: any) => r.video_id));
        selectedContestantStats = {
          total_appearances: results.length,
          screen_time_seconds: results.length * 2,
          videos_appeared_in: uniqueVideos.size
        };
      }
    } catch (e) {
      console.error('Failed to load appearances:', e);
      selectedContestantAppearances = [];
      selectedContestantStats = null;
    } finally {
      isLoadingAppearances = false;
    }
  }

  async function openModal(contestant: Contestant) {
    selectedContestant = contestant;
    selectedContestantAppearances = [];
    selectedContestantStats = null;
    await loadContestantAppearances(contestant);
  }

  function closeModal() {
    selectedContestant = null;
    selectedContestantAppearances = [];
    selectedContestantStats = null;
  }

  function formatTime(seconds: number): string {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  }

  function formatScreenTime(seconds: number): string {
    if (seconds < 60) return `${seconds}s`;
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    if (mins < 60) return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`;
    const hours = Math.floor(mins / 60);
    const remainingMins = mins % 60;
    return `${hours}h ${remainingMins}m`;
  }

  function navigateToVideo(videoId: string, timestamp: number) {
    goto(`/player?video=${videoId}&t=${timestamp}`);
  }

  function getContestantInitials(contestant: Contestant): string {
    if (contestant.nickname && contestant.nickname.length <= 3) {
      return contestant.nickname;
    }
    return `#${contestant.number}`;
  }

  onMount(() => {
    loadContestants();
  });

  $: if (searchQuery !== undefined) {
    handleSearch();
  }
</script>

<svelte:head>
  <title>Contestants - Face Recognition Dashboard</title>
</svelte:head>

<div class="contestants-page">
  <div class="page-header">
    <h1>👥 Contestant Directory</h1>
    <p class="page-description">Browse all 96 contestants and view their appearance history</p>
  </div>

  <div class="search-bar">
    <div class="search-input-wrapper">
      <span class="search-icon">🔍</span>
      <input
        type="text"
        class="search-input"
        placeholder="Search by name or nickname..."
        bind:value={searchQuery}
      />
      {#if searchQuery}
        <button class="clear-btn" on:click={() => searchQuery = ''}>✕</button>
      {/if}
    </div>
    <Badge variant="secondary" size="md">
      {filteredContestants.length} of {contestants.length} contestants
    </Badge>
  </div>

  {#if isLoading}
    <div class="loading-state">
      <div class="spinner"></div>
      <p>Loading contestants...</p>
    </div>
  {:else if error}
    <div class="error-state">
      <p>❌ {error}</p>
      <button class="btn-retry" on:click={loadContestants}>Retry</button>
    </div>
  {:else if filteredContestants.length === 0}
    <div class="empty-state">
      <p>No contestants found matching "{searchQuery}"</p>
      <button class="btn-secondary" on:click={() => searchQuery = ''}>Clear search</button>
    </div>
  {:else}
    <div class="contestants-grid">
      {#each filteredContestants as contestant (contestant.id)}
        <button class="contestant-card" on:click={() => openModal(contestant)}>
          <div class="contestant-photo">
            <span class="photo-initials">{getContestantInitials(contestant)}</span>
            {#if contestant.has_embedding}
              <span class="embedding-badge" title="Has face embedding">✓</span>
            {/if}
          </div>
          <div class="contestant-info">
            <div class="contestant-name">{contestant.name}</div>
            <div class="contestant-nickname">{contestant.nickname}</div>
            {#if contestant.age}
              <div class="contestant-age">{contestant.age} years old</div>
            {/if}
          </div>
        </button>
      {/each}
    </div>
  {/if}

  {#if selectedContestant}
    <div 
      class="modal-overlay" 
      on:click={closeModal} 
      on:keydown={(e) => e.key === 'Escape' && closeModal()} 
      role="button" 
      tabindex="0"
    >
      <div 
        class="modal" 
        on:click|stopPropagation 
        on:keydown={() => {}}
        role="dialog" 
        aria-modal="true" 
        tabindex="-1"
      >
        <button class="modal-close" on:click={closeModal} aria-label="Close modal">✕</button>
        
        <div class="modal-content">
          <div class="modal-header">
            <div class="modal-photo">
              <span class="photo-initials-large">{getContestantInitials(selectedContestant)}</span>
            </div>
            
            <div class="modal-title">
              <h2>{selectedContestant.name}</h2>
              <p class="modal-nickname">{selectedContestant.nickname}</p>
              <div class="modal-meta">
                <Badge variant="primary" size="sm">#{selectedContestant.number}</Badge>
                {#if selectedContestant.age}
                  <span class="meta-age">{selectedContestant.age} years old</span>
                {/if}
                {#if selectedContestant.has_embedding}
                  <Badge variant="success" size="sm">Has Embedding</Badge>
                {/if}
              </div>
            </div>
          </div>

          <div class="modal-stats">
            {#if isLoadingAppearances}
              <div class="stats-loading">Loading stats...</div>
            {:else if selectedContestantStats}
              <div class="stat-card">
                <span class="stat-value">{selectedContestantStats.total_appearances}</span>
                <span class="stat-label">Appearances</span>
              </div>
              <div class="stat-card">
                <span class="stat-value">{formatScreenTime(selectedContestantStats.screen_time_seconds)}</span>
                <span class="stat-label">Screen Time</span>
              </div>
              <div class="stat-card">
                <span class="stat-value">{selectedContestantStats.videos_appeared_in}</span>
                <span class="stat-label">Videos</span>
              </div>
            {:else}
              <div class="stats-empty">No appearance data available</div>
            {/if}
          </div>

          <div class="modal-appearances">
            <h3>📍 Appearance History</h3>
            
            {#if isLoadingAppearances}
              <div class="appearances-loading">
                <div class="spinner-small"></div>
                <span>Loading appearances...</span>
              </div>
            {:else if selectedContestantAppearances.length === 0}
              <div class="appearances-empty">
                <p>No recorded appearances yet.</p>
                <p class="hint">Appearances are recorded when videos are processed with face recognition.</p>
              </div>
            {:else}
              <div class="appearances-list">
                {#each selectedContestantAppearances as appearance}
                  <button 
                    class="appearance-item"
                    on:click={() => navigateToVideo(appearance.video_id, appearance.timestamp)}
                  >
                    <div class="appearance-info">
                      <span class="appearance-video">📹 {appearance.video_name || `Video ${appearance.video_id}`}</span>
                      <span class="appearance-time">@ {formatTime(appearance.timestamp)}</span>
                    </div>
                    <div class="appearance-meta">
                      <Badge 
                        variant={appearance.confidence > 0.85 ? 'success' : appearance.confidence > 0.7 ? 'warning' : 'secondary'} 
                        size="sm"
                      >
                        {(appearance.confidence * 100).toFixed(0)}%
                      </Badge>
                      <span class="appearance-arrow">→</span>
                    </div>
                  </button>
                {/each}
              </div>
            {/if}
          </div>
        </div>
      </div>
    </div>
  {/if}
</div>

<style>
  .contestants-page {
    padding: var(--space-6);
    max-width: 1400px;
    margin: 0 auto;
  }

  .page-header {
    margin-bottom: var(--space-6);
  }

  .page-header h1 {
    font-size: var(--text-h2-size);
    font-weight: 700;
    margin: 0 0 var(--space-2);
  }

  .page-description {
    color: var(--text-secondary);
    font-size: var(--text-body-size);
    margin: 0;
  }

  .search-bar {
    display: flex;
    gap: var(--space-4);
    align-items: center;
    margin-bottom: var(--space-6);
    flex-wrap: wrap;
  }

  .search-input-wrapper {
    position: relative;
    flex: 1;
    max-width: 400px;
    min-width: 200px;
  }

  .search-icon {
    position: absolute;
    left: var(--space-3);
    top: 50%;
    transform: translateY(-50%);
    font-size: 1rem;
    opacity: 0.5;
  }

  .search-input {
    width: 100%;
    padding: var(--space-3) var(--space-10);
    background-color: var(--bg-secondary);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-lg);
    color: var(--text-primary);
    font-size: var(--text-body-size);
  }

  .search-input:focus {
    outline: none;
    border-color: var(--color-primary-500);
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.2);
  }

  .clear-btn {
    position: absolute;
    right: var(--space-3);
    top: 50%;
    transform: translateY(-50%);
    background: none;
    border: none;
    color: var(--text-tertiary);
    cursor: pointer;
    padding: var(--space-1);
  }

  .clear-btn:hover {
    color: var(--text-primary);
  }

  .loading-state,
  .error-state,
  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: var(--space-12);
    text-align: center;
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

  .spinner-small {
    width: 20px;
    height: 20px;
    border: 2px solid var(--border-default);
    border-top-color: var(--color-primary-500);
    border-radius: 50%;
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .btn-retry,
  .btn-secondary {
    margin-top: var(--space-4);
    padding: var(--space-2) var(--space-4);
    background-color: var(--bg-tertiary);
    color: var(--text-primary);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: var(--transition-colors);
  }

  .btn-retry:hover,
  .btn-secondary:hover {
    background-color: var(--color-primary-600);
    border-color: var(--color-primary-600);
  }

  .contestants-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: var(--space-4);
  }

  .contestant-card {
    display: flex;
    flex-direction: column;
    background-color: var(--bg-secondary);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-lg);
    overflow: hidden;
    cursor: pointer;
    transition: var(--transition-all);
    text-align: left;
    padding: 0;
  }

  .contestant-card:hover {
    border-color: var(--color-primary-500);
    transform: translateY(-4px);
    box-shadow: 0 8px 25px rgba(0, 0, 0, 0.3);
  }

  .contestant-photo {
    aspect-ratio: 1;
    background: linear-gradient(135deg, var(--color-primary-900), var(--color-secondary-900));
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
  }

  .photo-initials {
    font-size: 2rem;
    font-weight: 700;
    color: white;
    opacity: 0.9;
  }

  .photo-initials-large {
    font-size: 3rem;
    font-weight: 700;
    color: white;
    opacity: 0.9;
  }

  .embedding-badge {
    position: absolute;
    bottom: var(--space-2);
    right: var(--space-2);
    background: var(--color-success-500);
    color: white;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.75rem;
  }

  .contestant-info {
    padding: var(--space-3);
  }

  .contestant-name {
    font-weight: 600;
    font-size: var(--text-body-size);
    color: var(--text-primary);
    margin-bottom: var(--space-0-5);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .contestant-nickname {
    font-size: var(--text-body-sm-size);
    color: var(--text-secondary);
    margin-bottom: var(--space-1);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .contestant-age {
    font-size: var(--text-body-xs-size);
    color: var(--text-tertiary);
  }

  .modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.85);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: var(--z-modal);
    padding: var(--space-6);
    backdrop-filter: blur(4px);
  }

  .modal {
    background: var(--bg-secondary);
    border-radius: var(--radius-xl);
    max-width: 600px;
    width: 100%;
    max-height: 85vh;
    overflow-y: auto;
    position: relative;
    border: 1px solid var(--border-default);
  }

  .modal-close {
    position: absolute;
    top: var(--space-4);
    right: var(--space-4);
    background: var(--bg-tertiary);
    border: none;
    color: var(--text-secondary);
    font-size: 1.25rem;
    cursor: pointer;
    z-index: 1;
    width: 32px;
    height: 32px;
    border-radius: var(--radius-full);
    display: flex;
    align-items: center;
    justify-content: center;
    transition: var(--transition-colors);
  }

  .modal-close:hover {
    background: var(--color-error-500);
    color: white;
  }

  .modal-content {
    padding: var(--space-6);
  }

  .modal-header {
    display: flex;
    gap: var(--space-5);
    margin-bottom: var(--space-6);
  }

  .modal-photo {
    width: 100px;
    height: 100px;
    flex-shrink: 0;
    background: linear-gradient(135deg, var(--color-primary-800), var(--color-secondary-800));
    border-radius: var(--radius-lg);
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .modal-title {
    flex: 1;
  }

  .modal-title h2 {
    font-size: var(--text-h3-size);
    font-weight: 700;
    margin: 0 0 var(--space-1);
  }

  .modal-nickname {
    font-size: var(--text-body-lg-size);
    color: var(--text-secondary);
    margin: 0 0 var(--space-3);
  }

  .modal-meta {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    flex-wrap: wrap;
  }

  .meta-age {
    font-size: var(--text-body-sm-size);
    color: var(--text-tertiary);
  }

  .modal-stats {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: var(--space-3);
    margin-bottom: var(--space-6);
  }

  .stat-card {
    text-align: center;
    padding: var(--space-4);
    background: var(--bg-tertiary);
    border-radius: var(--radius-lg);
  }

  .stat-value {
    display: block;
    font-size: var(--text-h3-size);
    font-weight: 700;
    color: var(--color-primary-400);
    line-height: 1;
    margin-bottom: var(--space-1);
  }

  .stat-label {
    display: block;
    font-size: var(--text-body-xs-size);
    color: var(--text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .stats-loading,
  .stats-empty {
    grid-column: 1 / -1;
    text-align: center;
    padding: var(--space-4);
    color: var(--text-tertiary);
  }

  .modal-appearances h3 {
    font-size: var(--text-h5-size);
    font-weight: 600;
    margin: 0 0 var(--space-4);
  }

  .appearances-loading {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-4);
    color: var(--text-tertiary);
  }

  .appearances-empty {
    text-align: center;
    padding: var(--space-6);
    background: var(--bg-tertiary);
    border-radius: var(--radius-lg);
    color: var(--text-secondary);
  }

  .appearances-empty .hint {
    font-size: var(--text-body-sm-size);
    color: var(--text-tertiary);
    margin-top: var(--space-2);
  }

  .appearances-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    max-height: 250px;
    overflow-y: auto;
  }

  .appearance-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--space-3) var(--space-4);
    background: var(--bg-tertiary);
    border: 1px solid transparent;
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: var(--transition-all);
    text-align: left;
    width: 100%;
  }

  .appearance-item:hover {
    background: var(--color-primary-900);
    border-color: var(--color-primary-500);
  }

  .appearance-info {
    display: flex;
    flex-direction: column;
    gap: var(--space-0-5);
  }

  .appearance-video {
    font-weight: 500;
    color: var(--text-primary);
    font-size: var(--text-body-sm-size);
  }

  .appearance-time {
    font-size: var(--text-body-xs-size);
    color: var(--text-tertiary);
  }

  .appearance-meta {
    display: flex;
    align-items: center;
    gap: var(--space-3);
  }

  .appearance-arrow {
    color: var(--text-tertiary);
    transition: transform var(--duration-fast);
  }

  .appearance-item:hover .appearance-arrow {
    transform: translateX(4px);
    color: var(--color-primary-400);
  }

  @media (max-width: 768px) {
    .contestants-grid {
      grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
    }

    .modal-header {
      flex-direction: column;
      align-items: center;
      text-align: center;
    }

    .modal-meta {
      justify-content: center;
    }

    .modal-stats {
      grid-template-columns: 1fr;
    }
  }
</style>
