<script lang="ts">
  import { onMount } from 'svelte';
  
  let recognitionResults: any[] = [];
  let filteredResults: any[] = [];
  let videos: any[] = [];
  let contestants: any[] = [];
  let loading = true;
  let error = '';
  
  // Filters
  let selectedVideo = '';
  let selectedContestant = '';
  let minConfidence = 0.5;
  let searchQuery = '';
  let sortBy = 'timestamp';
  let sortOrder = 'desc';
  
  // Pagination
  let currentPage = 1;
  let itemsPerPage = 20;
  let totalItems = 0;
  
  onMount(async () => {
    try {
      await Promise.all([
        loadRecognitionResults(),
        loadVideos(),
        loadContestants()
      ]);
      applyFilters();
    } catch (err) {
      error = 'Failed to load recognition data';
      console.error('Recognition page error:', err);
    } finally {
      loading = false;
    }
  });
  
  async function loadRecognitionResults() {
    try {
      const response = await fetch('/api/recognition/results');
      if (response.ok) {
        const data = await response.json();
        recognitionResults = data.results || [];
      }
    } catch (err) {
      console.error('Failed to load recognition results:', err);
      // Mock data for demonstration
      recognitionResults = [
        {
          id: '1',
          confidence: 0.89,
          video_id: '1',
          contestant_id: '1',
          contestant_name: '張三',
          contestant_nickname: '小張',
          timestamp: 12.5,
          bounding_box: { x: 120, y: 80, width: 180, height: 240 },
          created_at: '2024-07-14T10:30:00Z'
        },
        {
          id: '2',
          confidence: 0.92,
          video_id: '1',
          contestant_id: '2', 
          contestant_name: '李四',
          contestant_nickname: '小李',
          timestamp: 15.2,
          bounding_box: { x: 350, y: 90, width: 160, height: 220 },
          created_at: '2024-07-14T10:30:15Z'
        },
        {
          id: '3',
          confidence: 0.78,
          video_id: '2',
          contestant_id: '3',
          contestant_name: '王五',
          contestant_nickname: '小王',
          timestamp: 28.7,
          bounding_box: { x: 200, y: 150, width: 170, height: 230 },
          created_at: '2024-07-14T11:15:28Z'
        },
        {
          id: '4',
          confidence: 0.85,
          video_id: '2',
          contestant_id: '1',
          contestant_name: '張三',
          contestant_nickname: '小張',
          timestamp: 45.3,
          bounding_box: { x: 180, y: 120, width: 175, height: 235 },
          created_at: '2024-07-14T11:15:45Z'
        },
        {
          id: '5',
          confidence: 0.94,
          video_id: '3',
          contestant_id: '4',
          contestant_name: '趙六',
          contestant_nickname: '小趙',
          timestamp: 67.8,
          bounding_box: { x: 300, y: 100, width: 165, height: 225 },
          created_at: '2024-07-14T12:00:67Z'
        }
      ];
    }
  }
  
  async function loadVideos() {
    try {
      const response = await fetch('/api/videos');
      if (response.ok) {
        const data = await response.json();
        videos = data.videos || [];
      }
    } catch (err) {
      console.error('Failed to load videos:', err);
    }
  }
  
  async function loadContestants() {
    try {
      const response = await fetch('/api/contestants');
      if (response.ok) {
        const data = await response.json();
        contestants = data.contestants || [];
      }
    } catch (err) {
      console.error('Failed to load contestants:', err);
    }
  }
  
  function applyFilters() {
    let results = [...recognitionResults];
    
    // Filter by video
    if (selectedVideo) {
      results = results.filter(r => r.video_id === selectedVideo);
    }
    
    // Filter by contestant
    if (selectedContestant) {
      results = results.filter(r => r.contestant_id === selectedContestant);
    }
    
    // Filter by confidence
    results = results.filter(r => r.confidence >= minConfidence);
    
    // Filter by search query
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      results = results.filter(r => 
        r.contestant_name?.toLowerCase().includes(query) ||
        r.contestant_nickname?.toLowerCase().includes(query) ||
        getVideoName(r.video_id)?.toLowerCase().includes(query)
      );
    }
    
    // Sort results
    results.sort((a, b) => {
      let aVal, bVal;
      
      switch (sortBy) {
        case 'confidence':
          aVal = a.confidence;
          bVal = b.confidence;
          break;
        case 'contestant':
          aVal = a.contestant_name || '';
          bVal = b.contestant_name || '';
          break;
        case 'video':
          aVal = getVideoName(a.video_id) || '';
          bVal = getVideoName(b.video_id) || '';
          break;
        case 'timestamp':
        default:
          aVal = a.timestamp;
          bVal = b.timestamp;
          break;
      }
      
      if (typeof aVal === 'string') {
        aVal = aVal.toLowerCase();
        bVal = bVal.toLowerCase();
      }
      
      if (sortOrder === 'asc') {
        return aVal < bVal ? -1 : aVal > bVal ? 1 : 0;
      } else {
        return aVal > bVal ? -1 : aVal < bVal ? 1 : 0;
      }
    });
    
    totalItems = results.length;
    
    // Paginate results
    const startIndex = (currentPage - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;
    filteredResults = results.slice(startIndex, endIndex);
  }
  
  function getVideoName(videoId: string) {
    const video = videos.find(v => v.id === videoId);
    return video?.name || `Video ${videoId}`;
  }
  
  function getContestantName(contestantId: string) {
    const contestant = contestants.find(c => c.id.toString() === contestantId);
    return contestant?.name || `Contestant ${contestantId}`;
  }
  
  function getConfidenceColor(confidence: number) {
    if (confidence >= 0.8) return '#10b981';
    if (confidence >= 0.6) return '#f59e0b';
    return '#ef4444';
  }
  
  function formatTime(seconds: number) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  }
  
  function formatDateTime(dateString: string) {
    try {
      return new Date(dateString).toLocaleString();
    } catch {
      return 'Invalid date';
    }
  }
  
  function clearFilters() {
    selectedVideo = '';
    selectedContestant = '';
    minConfidence = 0.5;
    searchQuery = '';
    sortBy = 'timestamp';
    sortOrder = 'desc';
    currentPage = 1;
    applyFilters();
  }
  
  function goToPage(page: number) {
    currentPage = page;
    applyFilters();
  }
  
  function getTotalPages() {
    return Math.ceil(totalItems / itemsPerPage);
  }
  
  // Reactive statements
  $: {
    if (!loading) {
      currentPage = 1; // Reset to first page when filters change
      applyFilters();
    }
  }
</script>

<svelte:head>
  <title>Face Recognition Results - MV Face Recognition</title>
  <meta name="description" content="Browse and analyze face recognition results across all processed videos" />
</svelte:head>

<div class="recognition-page">
  <header class="page-header">
    <h1>Face Recognition Results</h1>
    <p>Browse and analyze face recognition results across all processed videos</p>
  </header>
  
  {#if loading}
    <div class="loading">
      <div class="spinner"></div>
      <p>Loading recognition results...</p>
    </div>
  {:else if error}
    <div class="error">
      <p>{error}</p>
      <button on:click={() => window.location.reload()}>Retry</button>
    </div>
  {:else}
    <!-- Filters Section -->
    <section class="filters-section">
      <div class="filters-header">
        <h2>Filters & Search</h2>
        <button class="clear-filters-btn" on:click={clearFilters}>
          Clear All Filters
        </button>
      </div>
      
      <div class="filters-grid">
        <!-- Search -->
        <div class="filter-group">
          <label for="search">Search</label>
          <input
            id="search"
            type="text"
            placeholder="Search by contestant name or video..."
            bind:value={searchQuery}
          />
        </div>
        
        <!-- Video Filter -->
        <div class="filter-group">
          <label for="video-filter">Video</label>
          <select id="video-filter" bind:value={selectedVideo}>
            <option value="">All Videos</option>
            {#each videos as video}
              <option value={video.id}>{video.name}</option>
            {/each}
          </select>
        </div>
        
        <!-- Contestant Filter -->
        <div class="filter-group">
          <label for="contestant-filter">Contestant</label>
          <select id="contestant-filter" bind:value={selectedContestant}>
            <option value="">All Contestants</option>
            {#each contestants as contestant}
              <option value={contestant.id.toString()}>{contestant.name}</option>
            {/each}
          </select>
        </div>
        
        <!-- Confidence Filter -->
        <div class="filter-group">
          <label for="confidence-filter">
            Min Confidence: {Math.round(minConfidence * 100)}%
          </label>
          <input
            id="confidence-filter"
            type="range"
            min="0"
            max="1"
            step="0.05"
            bind:value={minConfidence}
          />
        </div>
        
        <!-- Sort Options -->
        <div class="filter-group">
          <label for="sort-by">Sort By</label>
          <select id="sort-by" bind:value={sortBy}>
            <option value="timestamp">Timestamp</option>
            <option value="confidence">Confidence</option>
            <option value="contestant">Contestant</option>
            <option value="video">Video</option>
          </select>
        </div>
        
        <div class="filter-group">
          <label for="sort-order">Order</label>
          <select id="sort-order" bind:value={sortOrder}>
            <option value="desc">Descending</option>
            <option value="asc">Ascending</option>
          </select>
        </div>
      </div>
    </section>
    
    <!-- Results Summary -->
    <section class="results-summary">
      <div class="summary-stats">
        <div class="stat-item">
          <span class="stat-value">{totalItems}</span>
          <span class="stat-label">Total Results</span>
        </div>
        <div class="stat-item">
          <span class="stat-value">{recognitionResults.filter(r => r.confidence >= 0.8).length}</span>
          <span class="stat-label">High Confidence</span>
        </div>
        <div class="stat-item">
          <span class="stat-value">{new Set(recognitionResults.map(r => r.video_id)).size}</span>
          <span class="stat-label">Videos</span>
        </div>
        <div class="stat-item">
          <span class="stat-value">{new Set(recognitionResults.map(r => r.contestant_id)).size}</span>
          <span class="stat-label">Contestants</span>
        </div>
      </div>
    </section>
    
    <!-- Results List -->
    {#if filteredResults.length > 0}
      <section class="results-section">
        <div class="results-header">
          <h3>Recognition Results</h3>
          <span class="results-count">
            {(currentPage - 1) * itemsPerPage + 1}-{Math.min(currentPage * itemsPerPage, totalItems)} of {totalItems}
          </span>
        </div>
        
        <div class="results-list">
          {#each filteredResults as result}
            <div class="result-card">
              <div class="result-main">
                <div class="result-avatar">
                  <span>{result.contestant_name?.charAt(0) || '?'}</span>
                </div>
                
                <div class="result-info">
                  <div class="result-header-info">
                    <h4>{result.contestant_name || 'Unknown Contestant'}</h4>
                    <span class="result-nickname">{result.contestant_nickname || ''}</span>
                  </div>
                  
                  <div class="result-details">
                    <div class="detail-item">
                      <span class="detail-label">Video:</span>
                      <span class="detail-value">{getVideoName(result.video_id)}</span>
                    </div>
                    <div class="detail-item">
                      <span class="detail-label">Timestamp:</span>
                      <span class="detail-value">{formatTime(result.timestamp)}</span>
                    </div>
                    <div class="detail-item">
                      <span class="detail-label">Detected:</span>
                      <span class="detail-value">{formatDateTime(result.created_at)}</span>
                    </div>
                  </div>
                </div>
                
                <div class="result-metrics">
                  <div class="confidence-display">
                    <div class="confidence-circle">
                      <svg viewBox="0 0 36 36" class="confidence-svg">
                        <path
                          d="M18 2.0845
                          a 15.9155 15.9155 0 0 1 0 31.831
                          a 15.9155 15.9155 0 0 1 0 -31.831"
                          fill="none"
                          stroke="var(--border-color)"
                          stroke-width="2"
                        />
                        <path
                          d="M18 2.0845
                          a 15.9155 15.9155 0 0 1 0 31.831
                          a 15.9155 15.9155 0 0 1 0 -31.831"
                          fill="none"
                          stroke="{getConfidenceColor(result.confidence)}"
                          stroke-width="2"
                          stroke-dasharray="{result.confidence * 100}, 100"
                        />
                      </svg>
                      <div class="confidence-text">
                        {Math.round(result.confidence * 100)}%
                      </div>
                    </div>
                  </div>
                  
                  <div class="bounding-box-info">
                    <span class="bbox-label">Bounding Box</span>
                    <span class="bbox-value">
                      {Math.round(result.bounding_box.width)}×{Math.round(result.bounding_box.height)}
                    </span>
                    <span class="bbox-position">
                      ({Math.round(result.bounding_box.x)}, {Math.round(result.bounding_box.y)})
                    </span>
                  </div>
                </div>
              </div>
            </div>
          {/each}
        </div>
        
        <!-- Pagination -->
        {#if getTotalPages() > 1}
          <div class="pagination">
            <button 
              class="page-btn"
              disabled={currentPage === 1}
              on:click={() => goToPage(currentPage - 1)}
            >
              ← Previous
            </button>
            
            {#each Array(Math.min(5, getTotalPages())) as _, i}
              {@const pageNum = Math.max(1, currentPage - 2) + i}
              {#if pageNum <= getTotalPages()}
                <button
                  class="page-btn"
                  class:active={pageNum === currentPage}
                  on:click={() => goToPage(pageNum)}
                >
                  {pageNum}
                </button>
              {/if}
            {/each}
            
            <button
              class="page-btn"
              disabled={currentPage === getTotalPages()}
              on:click={() => goToPage(currentPage + 1)}
            >
              Next →
            </button>
          </div>
        {/if}
      </section>
    {:else}
      <div class="empty-state">
        <div class="empty-icon">🔍</div>
        <h3>No Results Found</h3>
        <p>Try adjusting your filters or search terms to find recognition results.</p>
        <button class="clear-filters-btn" on:click={clearFilters}>
          Clear Filters
        </button>
      </div>
    {/if}
  {/if}
</div>

<style>
  .recognition-page {
    max-width: 100%;
  }
  
  .page-header {
    margin-bottom: 2rem;
  }
  
  .page-header h1 {
    font-size: 2.5rem;
    font-weight: 700;
    margin: 0 0 0.5rem 0;
  }
  
  .page-header p {
    font-size: 1.1rem;
    color: var(--text-secondary);
    margin: 0;
  }
  
  .loading, .error {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 4rem 2rem;
    text-align: center;
  }
  
  .spinner {
    width: 2rem;
    height: 2rem;
    border: 3px solid var(--border-color);
    border-top: 3px solid var(--primary-color);
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin-bottom: 1rem;
  }
  
  .error button {
    margin-top: 1rem;
    padding: 0.5rem 1rem;
    background-color: var(--primary-color);
    color: white;
    border: none;
    border-radius: 0.375rem;
    cursor: pointer;
  }
  
  /* Filters Section */
  .filters-section {
    background-color: var(--surface-color);
    border: 1px solid var(--border-color);
    border-radius: 0.75rem;
    padding: 1.5rem;
    margin-bottom: 2rem;
    box-shadow: var(--shadow);
  }
  
  .filters-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1.5rem;
  }
  
  .filters-header h2 {
    margin: 0;
    font-size: 1.25rem;
    font-weight: 600;
  }
  
  .clear-filters-btn {
    padding: 0.5rem 1rem;
    background-color: var(--secondary-color);
    color: white;
    border: none;
    border-radius: 0.375rem;
    cursor: pointer;
    font-size: 0.9rem;
    transition: background-color 0.2s;
  }
  
  .clear-filters-btn:hover {
    background-color: var(--text-secondary);
  }
  
  .filters-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 1.5rem;
  }
  
  .filter-group {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  
  .filter-group label {
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--text-color);
  }
  
  .filter-group input,
  .filter-group select {
    padding: 0.5rem;
    border: 1px solid var(--border-color);
    border-radius: 0.375rem;
    background-color: var(--background-color);
    color: var(--text-color);
    font-size: 0.9rem;
  }
  
  .filter-group input[type="range"] {
    padding: 0;
  }
  
  /* Results Summary */
  .results-summary {
    margin-bottom: 2rem;
  }
  
  .summary-stats {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 1rem;
  }
  
  .stat-item {
    background-color: var(--surface-color);
    border: 1px solid var(--border-color);
    border-radius: 0.5rem;
    padding: 1rem;
    text-align: center;
    box-shadow: var(--shadow);
  }
  
  .stat-value {
    display: block;
    font-size: 2rem;
    font-weight: 700;
    color: var(--primary-color);
    margin-bottom: 0.25rem;
  }
  
  .stat-label {
    font-size: 0.9rem;
    color: var(--text-secondary);
  }
  
  /* Results Section */
  .results-section {
    background-color: var(--surface-color);
    border: 1px solid var(--border-color);
    border-radius: 0.75rem;
    overflow: hidden;
    box-shadow: var(--shadow);
  }
  
  .results-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1.5rem;
    background-color: var(--background-color);
    border-bottom: 1px solid var(--border-color);
  }
  
  .results-header h3 {
    margin: 0;
    font-size: 1.25rem;
    font-weight: 600;
  }
  
  .results-count {
    font-size: 0.9rem;
    color: var(--text-secondary);
  }
  
  .results-list {
    padding: 1rem;
  }
  
  .result-card {
    border: 1px solid var(--border-color);
    border-radius: 0.5rem;
    margin-bottom: 1rem;
    overflow: hidden;
    transition: transform 0.2s, box-shadow 0.2s;
  }
  
  .result-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px 0 rgb(0 0 0 / 0.15);
  }
  
  .result-main {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 1rem;
    background-color: var(--background-color);
  }
  
  .result-avatar {
    width: 3rem;
    height: 3rem;
    border-radius: 50%;
    background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-weight: 600;
    font-size: 1.2rem;
    flex-shrink: 0;
  }
  
  .result-info {
    flex: 1;
    min-width: 0;
  }
  
  .result-header-info {
    margin-bottom: 0.5rem;
  }
  
  .result-header-info h4 {
    margin: 0;
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--text-color);
  }
  
  .result-nickname {
    font-size: 0.9rem;
    color: var(--text-secondary);
    margin-left: 0.5rem;
  }
  
  .result-details {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 0.5rem;
  }
  
  .detail-item {
    display: flex;
    gap: 0.5rem;
  }
  
  .detail-label {
    font-size: 0.85rem;
    color: var(--text-secondary);
    font-weight: 500;
  }
  
  .detail-value {
    font-size: 0.85rem;
    color: var(--text-color);
    font-weight: 600;
  }
  
  .result-metrics {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1rem;
    flex-shrink: 0;
  }
  
  .confidence-display {
    display: flex;
    align-items: center;
    justify-content: center;
  }
  
  .confidence-circle {
    position: relative;
    width: 4rem;
    height: 4rem;
  }
  
  .confidence-svg {
    width: 100%;
    height: 100%;
    transform: rotate(-90deg);
  }
  
  .confidence-text {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--text-color);
  }
  
  .bounding-box-info {
    text-align: center;
  }
  
  .bbox-label {
    display: block;
    font-size: 0.75rem;
    color: var(--text-secondary);
    margin-bottom: 0.25rem;
  }
  
  .bbox-value {
    display: block;
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--text-color);
  }
  
  .bbox-position {
    display: block;
    font-size: 0.75rem;
    color: var(--text-secondary);
  }
  
  /* Pagination */
  .pagination {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 0.5rem;
    padding: 1.5rem;
    background-color: var(--background-color);
    border-top: 1px solid var(--border-color);
  }
  
  .page-btn {
    padding: 0.5rem 1rem;
    border: 1px solid var(--border-color);
    border-radius: 0.375rem;
    background-color: var(--surface-color);
    color: var(--text-color);
    cursor: pointer;
    transition: all 0.2s;
    font-size: 0.9rem;
  }
  
  .page-btn:hover:not(:disabled) {
    background-color: var(--border-color);
  }
  
  .page-btn.active {
    background-color: var(--primary-color);
    color: white;
    border-color: var(--primary-color);
  }
  
  .page-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  
  /* Empty State */
  .empty-state {
    text-align: center;
    padding: 4rem 2rem;
  }
  
  .empty-icon {
    font-size: 4rem;
    margin-bottom: 1rem;
  }
  
  .empty-state h3 {
    font-size: 1.5rem;
    margin-bottom: 0.5rem;
    color: var(--text-color);
  }
  
  .empty-state p {
    color: var(--text-secondary);
    margin-bottom: 1.5rem;
  }
  
  /* Mobile Responsiveness */
  @media (max-width: 768px) {
    .page-header h1 {
      font-size: 2rem;
    }
    
    .filters-grid {
      grid-template-columns: 1fr;
      gap: 1rem;
    }
    
    .summary-stats {
      grid-template-columns: repeat(2, 1fr);
    }
    
    .result-main {
      flex-direction: column;
      text-align: center;
      gap: 1rem;
    }
    
    .result-info {
      width: 100%;
    }
    
    .result-details {
      grid-template-columns: 1fr;
    }
    
    .result-metrics {
      flex-direction: row;
      justify-content: center;
    }
    
    .pagination {
      flex-wrap: wrap;
    }
  }
  
  @media (max-width: 480px) {
    .page-header h1 {
      font-size: 1.75rem;
    }
    
    .summary-stats {
      grid-template-columns: 1fr;
    }
    
    .filters-section {
      padding: 1rem;
    }
    
    .results-list {
      padding: 0.5rem;
    }
    
    .result-main {
      padding: 0.75rem;
    }
    
    .confidence-circle {
      width: 3rem;
      height: 3rem;
    }
  }
  
  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }
</style>