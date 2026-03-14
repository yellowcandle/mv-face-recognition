<script lang="ts">
  import { onMount } from 'svelte';
  import Card from '$lib/components/Card.svelte';
  import Button from '$lib/components/Button.svelte';
  import Badge from '$lib/components/Badge.svelte';

  // Types
  interface Contestant {
    id: string;
    name: string;
    nickname: string;
    age: number | null;
    has_embedding: boolean;
    embedding_dim: number;
    avg_confidence: number;
    max_confidence: number;
    detection_count: number;
    videos_seen_in: number;
    quality: 'good' | 'weak' | 'missing';
  }

  interface CoverageSummary {
    total: number;
    good: number;
    weak: number;
    missing: number;
    avg_confidence: number;
    recognition_rate: number;
    total_faces_detected: number;
    total_faces_recognized: number;
  }

  interface ConfusionPair {
    contestant_a: { id: string; name: string; nickname: string };
    contestant_b: { id: string; name: string; nickname: string };
    similarity: number;
  }

  interface SimilarityData {
    labels: { id: string; name: string; nickname: string }[];
    matrix: number[][];
    stats: { min_off_diagonal: number; max_off_diagonal: number; mean_off_diagonal: number; contestant_count: number };
  }

  // State
  type Tab = 'coverage' | 'detail' | 'confusion' | 'unmatched';
  let activeTab: Tab = 'coverage';

  // Coverage tab
  let contestants: Contestant[] = [];
  let summary: CoverageSummary | null = null;
  let isLoading = true;
  let error: string | null = null;

  // Detail tab
  let selectedContestant: Contestant | null = null;

  // Confusion tab
  let similarityData: SimilarityData | null = null;
  let topPairs: ConfusionPair[] = [];
  let confusionLoading = false;

  // Heatmap canvas
  let heatmapCanvas: HTMLCanvasElement;
  let heatmapTooltip = { visible: false, x: 0, y: 0, text: '' };

  const tabs: { id: Tab; label: string }[] = [
    { id: 'coverage', label: 'Coverage' },
    { id: 'detail', label: 'Detail' },
    { id: 'confusion', label: 'Confusion' },
    { id: 'unmatched', label: 'Unmatched' },
  ];

  // ─── Data Loading ───

  async function loadCoverage() {
    try {
      isLoading = true;
      const res = await fetch('/data/coverage.json');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      contestants = data.contestants;
      summary = data.summary;
    } catch (e: any) {
      error = `Failed to load coverage data: ${e.message}. Run: cd mvp-processor && python scripts/generate_coverage.py`;
    } finally {
      isLoading = false;
    }
  }

  async function loadSimilarity() {
    if (similarityData) return; // already loaded
    confusionLoading = true;
    try {
      const [matrixRes, pairsRes] = await Promise.all([
        fetch('/data/similarity_matrix.json'),
        fetch('/data/top_pairs.json'),
      ]);
      if (matrixRes.ok) similarityData = await matrixRes.json();
      if (pairsRes.ok) {
        const d = await pairsRes.json();
        topPairs = d.pairs || [];
      }
    } catch (e: any) {
      error = `Failed to load similarity data: ${e.message}`;
    } finally {
      confusionLoading = false;
    }
  }

  function switchTab(tab: Tab) {
    activeTab = tab;
    if (tab === 'confusion') loadSimilarity();
  }

  function selectContestantForDetail(c: Contestant) {
    selectedContestant = c;
    activeTab = 'detail';
  }

  // ─── Coverage Grid helpers ───

  function qualityColor(q: string): string {
    if (q === 'good') return '#22c55e';
    if (q === 'weak') return '#f59e0b';
    return '#ef4444';
  }

  function qualityBg(q: string): string {
    if (q === 'good') return 'rgba(34,197,94,0.1)';
    if (q === 'weak') return 'rgba(245,158,11,0.1)';
    return 'rgba(239,68,68,0.1)';
  }

  // ─── Confusion Matrix rendering ───

  function drawHeatmap() {
    if (!heatmapCanvas || !similarityData) return;

    const { matrix, labels } = similarityData;
    const n = matrix.length;
    const cellSize = Math.min(6, Math.floor(600 / n));
    const size = n * cellSize;

    const dpr = window.devicePixelRatio || 1;
    heatmapCanvas.width = size * dpr;
    heatmapCanvas.height = size * dpr;
    heatmapCanvas.style.width = `${size}px`;
    heatmapCanvas.style.height = `${size}px`;

    const ctx = heatmapCanvas.getContext('2d');
    if (!ctx) return;
    ctx.scale(dpr, dpr);

    for (let i = 0; i < n; i++) {
      for (let j = 0; j < n; j++) {
        const val = matrix[i][j];
        // Orange intensity: higher similarity = more saturated
        const alpha = i === j ? 1.0 : Math.min(1, val * 2);
        ctx.fillStyle = `rgba(255, 132, 0, ${alpha})`;
        ctx.fillRect(j * cellSize, i * cellSize, cellSize, cellSize);
      }
    }
  }

  function handleHeatmapHover(e: MouseEvent) {
    if (!similarityData || !heatmapCanvas) return;
    const rect = heatmapCanvas.getBoundingClientRect();
    const n = similarityData.matrix.length;
    const cellSize = Math.min(6, Math.floor(600 / n));

    const col = Math.floor((e.clientX - rect.left) / cellSize);
    const row = Math.floor((e.clientY - rect.top) / cellSize);

    if (row >= 0 && row < n && col >= 0 && col < n) {
      const a = similarityData.labels[row].nickname;
      const b = similarityData.labels[col].nickname;
      const sim = similarityData.matrix[row][col];
      heatmapTooltip = {
        visible: true,
        x: e.clientX - rect.left + 10,
        y: e.clientY - rect.top - 20,
        text: `${a} ↔ ${b}: ${(sim * 100).toFixed(1)}%`,
      };
    }
  }

  function hideHeatmapTooltip() {
    heatmapTooltip = { ...heatmapTooltip, visible: false };
  }

  // Reactive: draw heatmap when data loads or tab switches
  $: if (activeTab === 'confusion' && similarityData && heatmapCanvas) {
    drawHeatmap();
  }

  onMount(() => {
    loadCoverage();
  });
</script>

<svelte:head>
  <title>Embedding Workbench - MV Face Recognition</title>
</svelte:head>

<div class="workbench">
  <!-- Header -->
  <div class="header">
    <h1>Embedding Workbench</h1>
    <Button variant="primary" size="sm">Regenerate All</Button>
  </div>

  <!-- Tab Bar -->
  <div class="tab-bar">
    {#each tabs as tab}
      <button
        class="tab"
        class:active={activeTab === tab.id}
        on:click={() => switchTab(tab.id)}
      >
        {tab.label}
      </button>
    {/each}
  </div>

  {#if isLoading}
    <div class="loading">Loading coverage data...</div>
  {:else if error}
    <div class="error-msg">{error}</div>
  {:else}

    <!-- ═══ COVERAGE TAB ═══ -->
    {#if activeTab === 'coverage' && summary}
      <div class="stats-row">
        <div class="stat-card">
          <span class="stat-label">COVERAGE</span>
          <div class="stat-value-row">
            <span class="stat-value">{summary.good + summary.weak}/{summary.total}</span>
            <span class="stat-pct">{((summary.good + summary.weak) / summary.total * 100).toFixed(0)}%</span>
          </div>
          <div class="progress-bar">
            <div class="progress-fill" style="width: {(summary.good + summary.weak) / summary.total * 100}%"></div>
          </div>
        </div>
        <div class="stat-card">
          <span class="stat-label">AVG CONFIDENCE</span>
          <div class="stat-value-row">
            <span class="stat-value">{summary.avg_confidence.toFixed(2)}</span>
          </div>
        </div>
        <div class="stat-card">
          <span class="stat-label">RECOGNITION RATE</span>
          <div class="stat-value-row">
            <span class="stat-value">{(summary.recognition_rate * 100).toFixed(1)}%</span>
          </div>
        </div>
      </div>

      <!-- Grid Header -->
      <div class="grid-header">
        <span class="grid-title">Contestants</span>
        <div class="legend">
          <span class="legend-item"><span class="legend-dot" style="background: #22c55e"></span> Good ({summary.good})</span>
          <span class="legend-item"><span class="legend-dot" style="background: #f59e0b"></span> Weak ({summary.weak})</span>
          <span class="legend-item"><span class="legend-dot" style="background: #ef4444"></span> Missing ({summary.missing})</span>
        </div>
      </div>

      <!-- Contestant Grid -->
      <div class="contestant-grid">
        {#each contestants as c}
          <button
            class="contestant-tile"
            style="border-color: {qualityColor(c.quality)}; background: {qualityBg(c.quality)}"
            on:click={() => selectContestantForDetail(c)}
          >
            <span class="tile-number">#{c.id}</span>
            <span class="tile-nickname">{c.nickname}</span>
            <span class="tile-confidence">{(c.avg_confidence * 100).toFixed(0)}%</span>
          </button>
        {/each}
      </div>
    {/if}

    <!-- ═══ DETAIL TAB ═══ -->
    {#if activeTab === 'detail'}
      {#if selectedContestant}
        <div class="detail-header">
          <button class="back-btn" on:click={() => { activeTab = 'coverage'; }}>← Back</button>
          <h2>#{selectedContestant.id} {selectedContestant.name}</h2>
          <Badge variant={selectedContestant.quality === 'good' ? 'success' : selectedContestant.quality === 'weak' ? 'warning' : 'error'}>
            {selectedContestant.quality}
          </Badge>
          <Button variant="primary" size="sm">Regenerate Embedding</Button>
        </div>

        <div class="detail-layout">
          <div class="detail-left">
            <Card>
              <div class="detail-section">
                <h3>Reference Sources</h3>
                <div class="photo-placeholder">
                  <span>📷 {selectedContestant.nickname}</span>
                  <p class="hint">Current embedding from Instagram screenshot</p>
                </div>
                <Button variant="secondary" size="sm">Upload New Photo</Button>
              </div>
              <div class="detail-section">
                <h3>Stats</h3>
                <div class="detail-stat">
                  <span>Avg Confidence</span>
                  <strong>{(selectedContestant.avg_confidence * 100).toFixed(1)}%</strong>
                </div>
                <div class="detail-stat">
                  <span>Max Confidence</span>
                  <strong>{(selectedContestant.max_confidence * 100).toFixed(1)}%</strong>
                </div>
                <div class="detail-stat">
                  <span>Detection Count</span>
                  <strong>{selectedContestant.detection_count}</strong>
                </div>
                <div class="detail-stat">
                  <span>Videos Seen In</span>
                  <strong>{selectedContestant.videos_seen_in}</strong>
                </div>
                <div class="detail-stat">
                  <span>Embedding Dim</span>
                  <strong>{selectedContestant.embedding_dim}</strong>
                </div>
              </div>
            </Card>
          </div>
          <div class="detail-right">
            <Card>
              <div class="detail-section">
                <h3>Detected Faces from Videos</h3>
                <p class="hint">Face crops will be extracted on-demand from video frames using canvas (Phase 3).</p>
              </div>
            </Card>
          </div>
        </div>
      {:else}
        <div class="empty-state">
          <p>Select a contestant from the Coverage tab to see details.</p>
          <Button variant="secondary" size="sm" on:click={() => { activeTab = 'coverage'; }}>Go to Coverage</Button>
        </div>
      {/if}
    {/if}

    <!-- ═══ CONFUSION TAB ═══ -->
    {#if activeTab === 'confusion'}
      {#if confusionLoading}
        <div class="loading">Loading similarity data...</div>
      {:else if similarityData}
        <div class="confusion-layout">
          <div class="confusion-heatmap">
            <h3>Pairwise Similarity ({similarityData.stats.contestant_count}×{similarityData.stats.contestant_count})</h3>
            <div class="heatmap-container" on:mouseleave={hideHeatmapTooltip}>
              <canvas
                bind:this={heatmapCanvas}
                on:mousemove={handleHeatmapHover}
              ></canvas>
              {#if heatmapTooltip.visible}
                <div class="heatmap-tooltip" style="left: {heatmapTooltip.x}px; top: {heatmapTooltip.y}px">
                  {heatmapTooltip.text}
                </div>
              {/if}
            </div>
            <div class="heatmap-legend">
              <span>Low similarity</span>
              <div class="heatmap-gradient"></div>
              <span>High similarity</span>
            </div>
          </div>
          <div class="confusion-pairs">
            <h3>Top Confusion Pairs</h3>
            <div class="pairs-list">
              {#each topPairs as pair, i}
                <button
                  class="pair-item"
                  on:click={() => {
                    const c = contestants.find(x => x.nickname === pair.contestant_a.nickname);
                    if (c) selectContestantForDetail(c);
                  }}
                >
                  <span class="pair-rank">#{i + 1}</span>
                  <span class="pair-names">{pair.contestant_a.nickname} ↔ {pair.contestant_b.nickname}</span>
                  <span class="pair-score" class:danger={pair.similarity > 0.5}>{(pair.similarity * 100).toFixed(1)}%</span>
                </button>
              {/each}
            </div>
          </div>
        </div>
      {:else}
        <div class="empty-state">
          <p>No similarity data available. Run: <code>python scripts/compute_similarity.py</code></p>
        </div>
      {/if}
    {/if}

    <!-- ═══ UNMATCHED TAB ═══ -->
    {#if activeTab === 'unmatched'}
      <div class="empty-state">
        <h3>Unmatched Faces</h3>
        <p>Clustered unrecognized faces will appear here after running the clustering pipeline (Phase 5).</p>
        <p class="hint">Requires: T0.4 (save unmatched embeddings) + T0.5 (HDBSCAN clustering)</p>
      </div>
    {/if}

  {/if}
</div>

<style>
  .workbench {
    max-width: 1200px;
    display: flex;
    flex-direction: column;
    gap: 24px;
  }

  /* ─── Header ─── */
  .header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .header h1 {
    font-size: 24px;
    font-weight: 700;
    color: var(--text-primary, #fff);
    margin: 0;
  }

  /* ─── Tab Bar ─── */
  .tab-bar {
    display: flex;
    gap: 0;
    background: var(--surface-secondary, #1e293b);
    border-radius: 999px;
    padding: 4px;
  }

  .tab {
    flex: 1;
    padding: 8px 16px;
    border: none;
    background: transparent;
    color: var(--text-secondary, #94a3b8);
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    border-radius: 999px;
    transition: all 0.15s ease;
  }

  .tab:hover {
    color: var(--text-primary, #e2e8f0);
  }

  .tab.active {
    background: var(--color-primary-600, #ea580c);
    color: white;
    font-weight: 600;
  }

  /* ─── Loading / Error ─── */
  .loading, .error-msg, .empty-state {
    padding: 48px 24px;
    text-align: center;
    color: var(--text-secondary, #94a3b8);
  }

  .error-msg {
    color: var(--color-error-500, #ef4444);
    font-size: 13px;
  }

  .empty-state h3 {
    color: var(--text-primary, #e2e8f0);
    margin-bottom: 8px;
  }

  .hint {
    color: var(--text-tertiary, #64748b);
    font-size: 13px;
    margin-top: 4px;
  }

  /* ─── Stats Row ─── */
  .stats-row {
    display: flex;
    gap: 16px;
  }

  .stat-card {
    flex: 1;
    background: var(--surface-secondary, #1e293b);
    border: 1px solid var(--border-medium, #334155);
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .stat-label {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 2px;
    color: var(--text-secondary, #94a3b8);
  }

  .stat-value-row {
    display: flex;
    align-items: baseline;
    gap: 8px;
  }

  .stat-value {
    font-size: 32px;
    font-weight: 600;
    color: var(--text-primary, #fff);
  }

  .stat-pct {
    font-size: 16px;
    color: var(--text-secondary, #94a3b8);
  }

  .progress-bar {
    height: 8px;
    background: var(--surface-tertiary, #334155);
    border-radius: 999px;
    overflow: hidden;
  }

  .progress-fill {
    height: 100%;
    background: #ff8400;
    border-radius: 999px;
    transition: width 0.3s ease;
  }

  /* ─── Grid ─── */
  .grid-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .grid-title {
    font-size: 16px;
    font-weight: 600;
    color: var(--text-primary, #e2e8f0);
  }

  .legend {
    display: flex;
    gap: 16px;
    font-size: 12px;
    color: var(--text-secondary, #94a3b8);
  }

  .legend-item {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .legend-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    display: inline-block;
  }

  .contestant-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 6px;
  }

  .contestant-tile {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
    padding: 10px 6px;
    border: 1px solid;
    border-radius: 4px;
    cursor: pointer;
    background: transparent;
    transition: all 0.15s ease;
  }

  .contestant-tile:hover {
    transform: translateY(-1px);
    filter: brightness(1.2);
  }

  .tile-number {
    font-size: 11px;
    color: var(--text-tertiary, #64748b);
  }

  .tile-nickname {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-primary, #e2e8f0);
    text-align: center;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 100%;
  }

  .tile-confidence {
    font-size: 11px;
    color: var(--text-secondary, #94a3b8);
  }

  /* ─── Detail Tab ─── */
  .detail-header {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .detail-header h2 {
    font-size: 20px;
    font-weight: 600;
    color: var(--text-primary, #e2e8f0);
    margin: 0;
    flex: 1;
  }

  .back-btn {
    background: none;
    border: 1px solid var(--border-medium, #334155);
    color: var(--text-secondary, #94a3b8);
    padding: 6px 12px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 13px;
  }

  .back-btn:hover {
    color: var(--text-primary, #e2e8f0);
    border-color: var(--text-secondary, #94a3b8);
  }

  .detail-layout {
    display: flex;
    gap: 24px;
  }

  .detail-left {
    width: 340px;
    flex-shrink: 0;
  }

  .detail-right {
    flex: 1;
  }

  .detail-section {
    padding: 20px;
  }

  .detail-section h3 {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary, #e2e8f0);
    margin: 0 0 12px 0;
  }

  .photo-placeholder {
    padding: 24px;
    background: var(--surface-tertiary, #334155);
    border-radius: 8px;
    text-align: center;
    margin-bottom: 12px;
    color: var(--text-secondary, #94a3b8);
  }

  .detail-stat {
    display: flex;
    justify-content: space-between;
    padding: 8px 0;
    border-bottom: 1px solid var(--border-light, #1e293b);
    font-size: 13px;
    color: var(--text-secondary, #94a3b8);
  }

  .detail-stat strong {
    color: var(--text-primary, #e2e8f0);
  }

  /* ─── Confusion Tab ─── */
  .confusion-layout {
    display: flex;
    gap: 24px;
  }

  .confusion-heatmap {
    flex: 1;
  }

  .confusion-heatmap h3,
  .confusion-pairs h3 {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary, #e2e8f0);
    margin: 0 0 12px 0;
  }

  .heatmap-container {
    position: relative;
    display: inline-block;
  }

  .heatmap-container canvas {
    border: 1px solid var(--border-medium, #334155);
  }

  .heatmap-tooltip {
    position: absolute;
    background: #0f172a;
    border: 1px solid #475569;
    color: #e2e8f0;
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 12px;
    pointer-events: none;
    white-space: nowrap;
    z-index: 10;
  }

  .heatmap-legend {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 8px;
    font-size: 11px;
    color: var(--text-tertiary, #64748b);
  }

  .heatmap-gradient {
    flex: 1;
    height: 8px;
    border-radius: 4px;
    background: linear-gradient(to right, rgba(255,132,0,0.05), rgba(255,132,0,1));
  }

  .confusion-pairs {
    width: 320px;
    flex-shrink: 0;
  }

  .pairs-list {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .pair-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 12px;
    background: var(--surface-secondary, #1e293b);
    border: 1px solid var(--border-medium, #334155);
    border-radius: 4px;
    cursor: pointer;
    transition: background 0.15s ease;
    text-align: left;
    width: 100%;
    color: inherit;
  }

  .pair-item:hover {
    background: var(--surface-tertiary, #334155);
  }

  .pair-rank {
    font-size: 11px;
    color: var(--text-tertiary, #64748b);
    width: 24px;
  }

  .pair-names {
    flex: 1;
    font-size: 13px;
    color: var(--text-primary, #e2e8f0);
  }

  .pair-score {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-secondary, #94a3b8);
  }

  .pair-score.danger {
    color: #ef4444;
  }

  @media (max-width: 768px) {
    .contestant-grid {
      grid-template-columns: repeat(2, 1fr);
    }

    .stats-row {
      flex-direction: column;
    }

    .detail-layout,
    .confusion-layout {
      flex-direction: column;
    }

    .detail-left,
    .confusion-pairs {
      width: 100%;
    }
  }
</style>
