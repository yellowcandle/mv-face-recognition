<script lang="ts">
  import { onMount } from 'svelte';
  import { Card, Badge, Button } from '$lib/components';

  interface FlaggedFace {
    id: string;
    video_id: string;
    timestamp: number;
    contestant_id: number;
    contestant_name?: string;
    confidence: number;
    status: 'pending' | 'accepted' | 'rejected';
    user_label?: string;
    created_at?: string;
    thumbnail?: string;
  }

  interface Contestant {
    number: number;
    name: string;
    nickname: string;
  }

  let flaggedFaces: FlaggedFace[] = [];
  let contestants: Contestant[] = [];
  let isLoading = true;
  let error: string | null = null;
  
  let statusFilter: 'all' | 'pending' | 'accepted' | 'rejected' = 'all';
  let videoFilter = '';
  let contestantFilter = '';
  let confidenceThreshold = 0;
  
  let selectedFaces: Set<string> = new Set();
  let showReassignModal = false;
  let reassignContestantId: number | null = null;
  let selectedFaceForComparison: FlaggedFace | null = null;

  async function loadFlaggedFaces() {
    try {
      isLoading = true;
      const response = await fetch('/api/faces/flagged?details=true');
      if (response.ok) {
        const data = await response.json();
        flaggedFaces = data.flagged_faces || [];
      } else {
        error = 'Failed to load flagged faces';
      }
    } catch (e) {
      console.error('Failed to load flagged faces:', e);
      error = 'Failed to load flagged faces';
    } finally {
      isLoading = false;
    }
  }

  async function loadContestants() {
    try {
      const response = await fetch('/api/contestants');
      if (response.ok) {
        contestants = await response.json();
      }
    } catch (e) {
      console.error('Failed to load contestants:', e);
    }
  }

  async function updateFaceStatus(faceId: string, status: 'accepted' | 'rejected') {
    try {
      const response = await fetch(`/api/faces/flagged/${faceId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status })
      });
      if (response.ok) {
        await loadFlaggedFaces();
      }
    } catch (e) {
      console.error('Failed to update face status:', e);
    }
  }

  async function bulkUpdateStatus(status: 'accepted' | 'rejected') {
    const faceIds = Array.from(selectedFaces);
    for (const faceId of faceIds) {
      await updateFaceStatus(faceId, status);
    }
    selectedFaces.clear();
    selectedFaces = selectedFaces;
  }

  function toggleSelection(faceId: string) {
    if (selectedFaces.has(faceId)) {
      selectedFaces.delete(faceId);
    } else {
      selectedFaces.add(faceId);
    }
    selectedFaces = selectedFaces;
  }

  function selectAll() {
    filteredFaces.forEach(f => selectedFaces.add(f.id));
    selectedFaces = selectedFaces;
  }

  function clearSelection() {
    selectedFaces.clear();
    selectedFaces = selectedFaces;
  }

  function formatTime(seconds: number): string {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  }

  function getStatusBadgeVariant(status: string): 'warning' | 'success' | 'error' {
    switch (status) {
      case 'pending': return 'warning';
      case 'accepted': return 'success';
      case 'rejected': return 'error';
      default: return 'warning';
    }
  }

  function getContestantPhoto(contestantId: number): string {
    return `/api/contestants/${contestantId}/photo`;
  }

  function getContestantByNumber(num: number): Contestant | undefined {
    return contestants.find(c => c.number === num);
  }

  function getConfidenceColor(confidence: number): string {
    if (confidence >= 0.8) return 'var(--color-success-500)';
    if (confidence >= 0.6) return 'var(--color-warning-500)';
    return 'var(--color-error-500)';
  }

  $: uniqueVideos = [...new Set(flaggedFaces.map(f => f.video_id))];

  $: filteredFaces = flaggedFaces.filter(f => {
    if (statusFilter !== 'all' && f.status !== statusFilter) return false;
    if (videoFilter && f.video_id !== videoFilter) return false;
    if (contestantFilter && String(f.contestant_id) !== contestantFilter) return false;
    if (f.confidence < confidenceThreshold) return false;
    return true;
  });

  onMount(() => {
    loadFlaggedFaces();
    loadContestants();
  });
</script>

<svelte:head>
  <title>Face Flagging - Face Recognition Dashboard</title>
</svelte:head>

<div class="flagging-page">
  <div class="page-header">
    <div class="header-content">
      <h1>🚩 Face Flagging</h1>
      <p class="page-description">Review and correct face identifications to improve recognition accuracy</p>
    </div>
    <div class="header-actions">
      {#if selectedFaces.size > 0}
        <Badge variant="primary" size="md">{selectedFaces.size} selected</Badge>
        <Button variant="secondary" size="sm" on:click={clearSelection}>Clear</Button>
        <Button variant="primary" size="sm" on:click={() => bulkUpdateStatus('accepted')}>✓ Accept All</Button>
        <Button variant="secondary" size="sm" on:click={() => bulkUpdateStatus('rejected')}>✗ Reject All</Button>
      {/if}
      <Button variant="primary" size="md" on:click={loadFlaggedFaces}>Refresh</Button>
    </div>
  </div>

  <div class="filters">
    <div class="filter-group">
      <label>Status:</label>
      <select bind:value={statusFilter}>
        <option value="all">All</option>
        <option value="pending">Pending</option>
        <option value="accepted">Accepted</option>
        <option value="rejected">Rejected</option>
      </select>
    </div>
    
    <div class="filter-group">
      <label>Video:</label>
      <select bind:value={videoFilter}>
        <option value="">All Videos</option>
        {#each uniqueVideos as videoId}
          <option value={videoId}>{videoId}</option>
        {/each}
      </select>
    </div>
    
    <div class="filter-group">
      <label>Contestant:</label>
      <select bind:value={contestantFilter}>
        <option value="">All Contestants</option>
        {#each contestants as contestant}
          <option value={String(contestant.number)}>#{contestant.number} - {contestant.nickname}</option>
        {/each}
      </select>
    </div>
    
    <div class="filter-group">
      <label>Min Confidence:</label>
      <input 
        type="range" 
        min="0" 
        max="1" 
        step="0.1" 
        bind:value={confidenceThreshold}
      />
      <span class="confidence-value">{(confidenceThreshold * 100).toFixed(0)}%</span>
    </div>

    <Badge variant="secondary" size="md">
      {filteredFaces.length} flagged faces
    </Badge>
    
    {#if filteredFaces.length > 0}
      <Button variant="secondary" size="sm" on:click={selectAll}>Select All</Button>
    {/if}
  </div>

  {#if isLoading}
    <div class="loading-state">
      <div class="spinner"></div>
      <p>Loading flagged faces...</p>
    </div>
  {:else if error}
    <div class="error-state">
      <p>❌ {error}</p>
      <Button variant="primary" on:click={loadFlaggedFaces}>Retry</Button>
    </div>
  {:else if filteredFaces.length === 0}
    <Card variant="bordered" padding="lg">
      <div class="empty-state">
        <span class="empty-icon">✅</span>
        <h3>No flagged faces</h3>
        <p>All faces have been reviewed or no corrections have been submitted yet.</p>
        <p class="hint">You can flag faces from the Video Player while watching videos.</p>
      </div>
    </Card>
  {:else}
    <div class="flagged-grid">
      {#each filteredFaces as face}
        <div 
          class="flagged-card" 
          class:selected={selectedFaces.has(face.id)}
          role="button"
          tabindex="0"
          on:click={() => toggleSelection(face.id)}
          on:keypress={(e) => e.key === 'Enter' && toggleSelection(face.id)}
        >
          <div class="selection-checkbox">
            <input 
              type="checkbox" 
              checked={selectedFaces.has(face.id)} 
              on:click|stopPropagation
              on:change={() => toggleSelection(face.id)}
            />
          </div>
          
          <div class="comparison-view">
            <div class="face-column">
              <span class="column-label">Detected</span>
              <div class="face-preview">
                {#if face.thumbnail}
                  <img src={face.thumbnail} alt="Detected face" />
                {:else}
                  <div class="face-placeholder">👤</div>
                {/if}
              </div>
            </div>
            
            <div class="comparison-arrow">→</div>
            
            <div class="face-column">
              <span class="column-label">Assigned</span>
              <div class="face-preview contestant-photo">
                <img 
                  src={getContestantPhoto(face.contestant_id)} 
                  alt="Contestant photo"
                  on:error={(e) => { e.currentTarget.style.display = 'none'; }}
                />
                <div class="face-placeholder fallback">#{face.contestant_id}</div>
              </div>
            </div>
          </div>
          
          <div class="face-details">
            <div class="face-header">
              <span class="contestant-name">
                {#if getContestantByNumber(face.contestant_id)}
                  {getContestantByNumber(face.contestant_id)?.nickname}
                  <span class="name-full">({getContestantByNumber(face.contestant_id)?.name})</span>
                {:else}
                  Contestant #{face.contestant_id}
                {/if}
              </span>
              <Badge variant={getStatusBadgeVariant(face.status)} size="sm">
                {face.status}
              </Badge>
            </div>
            
            <div class="confidence-bar">
              <div 
                class="confidence-fill" 
                style="width: {face.confidence * 100}%; background-color: {getConfidenceColor(face.confidence)}"
              ></div>
              <span class="confidence-text">{(face.confidence * 100).toFixed(1)}%</span>
            </div>
            
            <div class="face-meta">
              <span class="meta-item">📹 {face.video_id}</span>
              <span class="meta-item">⏱️ {formatTime(face.timestamp)}</span>
            </div>
            
            {#if face.user_label}
              <p class="user-note">💬 {face.user_label}</p>
            {/if}
            
            {#if face.status === 'pending'}
              <div class="action-buttons">
                <button 
                  class="action-btn accept" 
                  on:click|stopPropagation={() => updateFaceStatus(face.id, 'accepted')}
                >
                  ✓ Accept
                </button>
                <button 
                  class="action-btn reject" 
                  on:click|stopPropagation={() => updateFaceStatus(face.id, 'rejected')}
                >
                  ✗ Reject
                </button>
              </div>
            {/if}
          </div>
        </div>
      {/each}
    </div>
  {/if}

  <Card variant="bordered" padding="lg" class="info-card">
    <h3>📖 How Face Flagging Works</h3>
    <ol class="info-list">
      <li>While watching videos in the <strong>Video Player</strong>, click on any detected face to flag it</li>
      <li>Select the correct contestant from the dropdown</li>
      <li>Optionally add notes about the correction</li>
      <li>Submit the flag for review</li>
      <li>Use this page to <strong>Accept</strong> or <strong>Reject</strong> flagged corrections</li>
      <li>Accepted corrections help improve future face recognition accuracy</li>
    </ol>
  </Card>
</div>

<style>
  .flagging-page {
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
    font-size: var(--text-body-size);
    margin: 0;
  }

  .header-actions {
    display: flex;
    gap: var(--space-2);
    align-items: center;
    flex-wrap: wrap;
  }

  .filters {
    display: flex;
    gap: var(--space-4);
    align-items: center;
    margin-bottom: var(--space-6);
    flex-wrap: wrap;
    background: var(--bg-secondary);
    padding: var(--space-4);
    border-radius: var(--radius-lg);
  }

  .filter-group {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  .filter-group label {
    font-size: var(--text-body-sm-size);
    color: var(--text-secondary);
    white-space: nowrap;
  }

  .filter-group select,
  .filter-group input[type="range"] {
    padding: var(--space-2) var(--space-3);
    background-color: var(--bg-tertiary);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-md);
    color: var(--text-primary);
    font-size: var(--text-body-sm-size);
  }

  .filter-group input[type="range"] {
    width: 100px;
  }

  .confidence-value {
    font-size: var(--text-body-sm-size);
    color: var(--text-tertiary);
    min-width: 40px;
  }

  .loading-state,
  .error-state {
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

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .empty-state {
    text-align: center;
    padding: var(--space-8);
  }

  .empty-icon {
    font-size: 3rem;
    display: block;
    margin-bottom: var(--space-4);
  }

  .empty-state h3 {
    font-size: var(--text-h4-size);
    margin: 0 0 var(--space-2);
  }

  .empty-state p {
    color: var(--text-secondary);
    margin: 0;
  }

  .empty-state .hint {
    margin-top: var(--space-4);
    font-size: var(--text-body-sm-size);
    color: var(--text-tertiary);
  }

  .flagged-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
    gap: var(--space-4);
    margin-bottom: var(--space-8);
  }

  .flagged-card {
    background: var(--bg-secondary);
    border: 2px solid var(--border-default);
    border-radius: var(--radius-lg);
    padding: var(--space-4);
    cursor: pointer;
    transition: all 0.2s;
    position: relative;
  }

  .flagged-card:hover {
    border-color: var(--color-primary-400);
    transform: translateY(-2px);
  }

  .flagged-card.selected {
    border-color: var(--color-primary-500);
    background: var(--color-primary-500/10);
  }

  .selection-checkbox {
    position: absolute;
    top: var(--space-3);
    right: var(--space-3);
    z-index: 1;
  }

  .selection-checkbox input {
    width: 20px;
    height: 20px;
    cursor: pointer;
  }

  .comparison-view {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-4);
    margin-bottom: var(--space-4);
  }

  .face-column {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-2);
  }

  .column-label {
    font-size: var(--text-body-xs-size);
    color: var(--text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .comparison-arrow {
    font-size: 1.5rem;
    color: var(--text-tertiary);
  }

  .face-preview {
    width: 80px;
    height: 80px;
    flex-shrink: 0;
    background-color: var(--bg-tertiary);
    border-radius: var(--radius-md);
    overflow: hidden;
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
  }

  .face-preview img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .face-placeholder {
    font-size: 2rem;
    color: var(--text-tertiary);
  }

  .contestant-photo .fallback {
    position: absolute;
    font-size: 1rem;
  }

  .contestant-photo img + .fallback {
    display: none;
  }

  .face-details {
    flex: 1;
    min-width: 0;
  }

  .face-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--space-2);
  }

  .contestant-name {
    font-weight: 600;
    font-size: var(--text-body-size);
    color: var(--text-primary);
  }

  .name-full {
    font-weight: 400;
    font-size: var(--text-body-sm-size);
    color: var(--text-secondary);
  }

  .confidence-bar {
    height: 8px;
    background: var(--bg-tertiary);
    border-radius: 4px;
    margin-bottom: var(--space-3);
    position: relative;
    overflow: hidden;
  }

  .confidence-fill {
    height: 100%;
    border-radius: 4px;
    transition: width 0.3s;
  }

  .confidence-text {
    position: absolute;
    right: var(--space-2);
    top: 50%;
    transform: translateY(-50%);
    font-size: 10px;
    font-weight: 600;
    color: var(--text-primary);
  }

  .face-meta {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-3);
    font-size: var(--text-body-xs-size);
    color: var(--text-tertiary);
    margin-bottom: var(--space-2);
  }

  .user-note {
    font-size: var(--text-body-sm-size);
    color: var(--text-secondary);
    margin: 0 0 var(--space-3);
    padding: var(--space-2);
    background: var(--bg-tertiary);
    border-radius: var(--radius-sm);
  }

  .action-buttons {
    display: flex;
    gap: var(--space-2);
    margin-top: var(--space-3);
  }

  .action-btn {
    flex: 1;
    padding: var(--space-2) var(--space-3);
    border: none;
    border-radius: var(--radius-md);
    font-size: var(--text-body-sm-size);
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
  }

  .action-btn.accept {
    background: var(--color-success-500);
    color: white;
  }

  .action-btn.accept:hover {
    background: var(--color-success-600);
  }

  .action-btn.reject {
    background: var(--color-gray-600);
    color: white;
  }

  .action-btn.reject:hover {
    background: var(--color-error-500);
  }

  :global(.info-card) {
    margin-top: var(--space-8);
  }

  .info-card h3 {
    font-size: var(--text-h5-size);
    margin: 0 0 var(--space-4);
  }

  .info-list {
    margin: 0;
    padding-left: var(--space-6);
    color: var(--text-secondary);
  }

  .info-list li {
    margin-bottom: var(--space-2);
  }

  .info-list strong {
    color: var(--color-primary-400);
  }

  @media (max-width: 768px) {
    .page-header {
      flex-direction: column;
      gap: var(--space-4);
    }

    .filters {
      flex-direction: column;
      align-items: flex-start;
    }

    .flagged-grid {
      grid-template-columns: 1fr;
    }

    .comparison-view {
      flex-direction: column;
    }

    .comparison-arrow {
      transform: rotate(90deg);
    }
  }
</style>
