<script lang="ts">
  import FaceCard from './FaceCard.svelte';
  
  export let currentFaces: Array<{
    contestant: {
      id: number;
      name: string;
      nickname: string;
      age: number;
    };
    confidence: number;
    timestamp: number;
    face_location: [number, number, number, number];
  }> = [];
  
  export let onFaceClick: ((contestant: any, timestamp: number) => void) | null = null;
  export let showTimestamp: boolean = true;
  export let minConfidence: number = 0.3;
  export let maxFaces: number = 8;

  // Filter faces by confidence and limit count
  $: filteredFaces = currentFaces
    .filter(face => face.confidence >= minConfidence)
    .slice(0, maxFaces)
    .sort((a, b) => b.confidence - a.confidence);

  // Group faces by contestant to avoid duplicates
  $: uniqueFaces = filteredFaces.reduce((acc, face) => {
    const existing = acc.find(f => f.contestant.id === face.contestant.id);
    if (!existing || face.confidence > existing.confidence) {
      return acc.filter(f => f.contestant.id !== face.contestant.id).concat(face);
    }
    return acc;
  }, [] as typeof filteredFaces);

  // Statistics
  $: totalFaces = currentFaces.length;
  $: uniqueContestants = new Set(currentFaces.map(f => f.contestant.id)).size;
  $: averageConfidence = currentFaces.length > 0 
    ? currentFaces.reduce((sum, f) => sum + f.confidence, 0) / currentFaces.length 
    : 0;
  
  function getConfidenceLabel(confidence: number): string {
    if (confidence >= 0.8) return 'High';
    if (confidence >= 0.6) return 'Medium';
    if (confidence >= 0.4) return 'Low';
    return 'Very Low';
  }
  
  function getConfidenceColor(confidence: number): string {
    if (confidence >= 0.8) return '#10b981';
    if (confidence >= 0.6) return '#f59e0b';
    if (confidence >= 0.4) return '#f97316';
    return '#ef4444';
  }
</script>

<div class="face-gallery">
  <div class="gallery-header">
    <div class="title-section">
      <h3>識別中的參賽者</h3>
      <div class="stats">
        <span class="stat">
          <span class="stat-number">{uniqueContestants}</span>
          <span class="stat-label">位參賽者</span>
        </span>
        {#if totalFaces !== uniqueContestants}
          <span class="stat">
            <span class="stat-number">{totalFaces}</span>
            <span class="stat-label">個人臉</span>
          </span>
        {/if}
        {#if averageConfidence > 0}
          <span class="stat confidence-stat">
            <span class="stat-number">{Math.round(averageConfidence * 100)}%</span>
            <span class="stat-label">平均信心度</span>
            <div class="confidence-bar">
              <div class="confidence-bar-fill" style="width: {averageConfidence * 100}%; background-color: {getConfidenceColor(averageConfidence)}"></div>
            </div>
          </span>
        {/if}
      </div>
    </div>
    
    <div class="controls">
      <div class="confidence-filter">
        <label for="min-confidence">信心度閾值:</label>
        <div class="slider-container">
          <input 
            id="min-confidence"
            type="range" 
            min="0" 
            max="1" 
            step="0.05"
            bind:value={minConfidence}
            aria-label="Minimum confidence threshold"
          />
          <div class="slider-track">
            <div class="slider-fill" style="width: {minConfidence * 100}%"></div>
          </div>
        </div>
        <div class="confidence-display">
          <span class="confidence-value">{Math.round(minConfidence * 100)}%</span>
          <span class="confidence-label">{getConfidenceLabel(minConfidence)}</span>
        </div>
      </div>
    </div>
  </div>

  <div class="gallery-content">
    {#if uniqueFaces.length > 0}
      <div class="faces-grid">
        {#each uniqueFaces as face (face.contestant.id)}
          <FaceCard 
            contestant={face.contestant}
            confidence={face.confidence}
            timestamp={face.timestamp}
            faceLocation={face.face_location}
            {onFaceClick}
          />
        {/each}
      </div>
    {:else if currentFaces.length === 0}
      <div class="empty-state no-faces">
        <svg class="empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
          <circle cx="12" cy="7" r="4"/>
        </svg>
        <h4>沒有識別到參賽者</h4>
        <p>在目前時間點沒有偵測到任何人臉</p>
        <div class="empty-action">
          <button on:click={() => minConfidence = 0.2} class="suggestion-button">
            降低信心度閾值
          </button>
        </div>
      </div>
    {:else}
      <div class="empty-state low-confidence">
        <svg class="empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <circle cx="11" cy="11" r="8"/>
          <path d="m21 21-4.35-4.35"/>
        </svg>
        <h4>信心度閾值過高</h4>
        <p>當前有 {currentFaces.length} 個識別結果，但信心度都低於 {Math.round(minConfidence * 100)}%</p>
        <div class="empty-action">
          <button on:click={() => minConfidence = Math.max(0, minConfidence - 0.2)} class="suggestion-button">
            降低至 {Math.round(Math.max(0, minConfidence - 0.2) * 100)}%
          </button>
        </div>
      </div>
    {/if}
  </div>

  {#if uniqueFaces.length > 0 && filteredFaces.length > maxFaces}
    <div class="more-faces">
      <p>還有 {filteredFaces.length - maxFaces} 個識別結果...</p>
    </div>
  {/if}
</div>

<style>
  .face-gallery {
    background: white;
    border-radius: 0.75rem;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
    border: 1px solid #e5e7eb;
    height: 100%;
    display: flex;
    flex-direction: column;
  }

  .gallery-header {
    padding: 1rem;
    border-bottom: 1px solid #e5e7eb;
    background: #f9fafb;
  }

  .title-section {
    margin-bottom: 0.75rem;
  }

  .title-section h3 {
    font-size: 1.1rem;
    font-weight: 600;
    margin: 0 0 0.5rem;
    color: #111827;
  }

  .stats {
    display: flex;
    gap: 1rem;
    flex-wrap: wrap;
  }

  .stat {
    display: flex;
    align-items: baseline;
    gap: 0.25rem;
    font-size: 0.8rem;
  }

  .stat-number {
    font-weight: 600;
    color: #3b82f6;
    font-size: 0.9rem;
  }

  .stat-label {
    color: #6b7280;
  }

  .controls {
    display: flex;
    align-items: center;
    gap: 1rem;
  }

  .confidence-filter {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.8rem;
  }

  .confidence-filter label {
    color: #374151;
    white-space: nowrap;
  }

  .slider-container {
    position: relative;
    width: 100px;
    margin: 0 0.5rem;
  }

  .confidence-filter input[type="range"] {
    width: 100%;
    height: 20px;
    background: transparent;
    cursor: pointer;
    position: relative;
    z-index: 2;
  }

  .confidence-filter input[type="range"]::-webkit-slider-thumb {
    appearance: none;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: var(--primary-color);
    cursor: pointer;
    border: 2px solid white;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
    transition: all 0.2s ease;
  }

  .confidence-filter input[type="range"]::-webkit-slider-thumb:hover {
    transform: scale(1.1);
    background: var(--primary-hover);
  }

  .slider-track {
    position: absolute;
    top: 50%;
    transform: translateY(-50%);
    width: 100%;
    height: 4px;
    background: var(--border-color);
    border-radius: 2px;
    z-index: 1;
  }

  .slider-fill {
    height: 100%;
    background: var(--primary-color);
    border-radius: 2px;
    transition: width 0.2s ease;
  }

  .confidence-display {
    display: flex;
    flex-direction: column;
    align-items: center;
    min-width: 60px;
  }

  .confidence-value {
    color: var(--primary-color);
    font-weight: 600;
    font-size: 0.8rem;
  }

  .confidence-label {
    color: var(--text-secondary);
    font-size: 0.65rem;
    margin-top: 1px;
  }

  .gallery-content {
    flex: 1;
    padding: 1rem;
    overflow-y: auto;
  }

  .faces-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(min(140px, 100%), 1fr));
    gap: 0.75rem;
    animation: fadeIn 0.3s ease-out;
  }

  @supports (container-type: inline-size) {
    .gallery-content {
      container-type: inline-size;
    }
    
    @container (max-width: 300px) {
      .faces-grid {
        grid-template-columns: 1fr;
      }
    }
    
    @container (min-width: 301px) and (max-width: 450px) {
      .faces-grid {
        grid-template-columns: repeat(2, 1fr);
      }
    }
  }

  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: 2rem 1rem;
    color: #6b7280;
    height: 200px;
  }

  .empty-icon {
    width: 3rem;
    height: 3rem;
    margin-bottom: 1rem;
    opacity: 0.6;
    color: var(--text-secondary);
  }

  .empty-action {
    margin-top: 1rem;
  }

  .suggestion-button {
    background: var(--primary-color);
    color: white;
    border: none;
    padding: 0.5rem 1rem;
    border-radius: 0.375rem;
    font-size: 0.8rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .suggestion-button:hover {
    background: var(--primary-hover);
    transform: translateY(-1px);
  }

  .confidence-stat {
    position: relative;
  }

  .confidence-bar {
    width: 100%;
    height: 3px;
    background: var(--border-color);
    border-radius: 1.5px;
    margin-top: 0.25rem;
    overflow: hidden;
  }

  .confidence-bar-fill {
    height: 100%;
    border-radius: 1.5px;
    transition: width 0.3s ease;
  }

  .empty-state h4 {
    font-size: 1rem;
    font-weight: 500;
    margin: 0 0 0.5rem;
    color: #374151;
  }

  .empty-state p {
    font-size: 0.85rem;
    margin: 0;
    line-height: 1.4;
  }

  .more-faces {
    padding: 0.75rem 1rem;
    text-align: center;
    border-top: 1px solid #e5e7eb;
    background: #f9fafb;
    font-size: 0.8rem;
    color: #6b7280;
  }

  .more-faces p {
    margin: 0;
  }

  @keyframes fadeIn {
    from {
      opacity: 0;
      transform: translateY(10px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  /* Mobile responsive */
  @media (max-width: 768px) {
    .gallery-header {
      padding: 0.75rem;
    }

    .title-section h3 {
      font-size: 1rem;
    }

    .stats {
      gap: 0.75rem;
    }

    .faces-grid {
      grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
      gap: 0.5rem;
    }

    .gallery-content {
      padding: 0.75rem;
    }

    .confidence-filter {
      font-size: 0.75rem;
    }

    .slider-container {
      width: 80px;
    }

    .confidence-display {
      min-width: 50px;
    }

    .confidence-value {
      font-size: 0.75rem;
    }

    .confidence-label {
      font-size: 0.6rem;
    }
  }

  /* Compact mode for smaller sidebars */
  @media (max-width: 1200px) {
    .faces-grid {
      grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
    }
    
    .controls {
      flex-direction: column;
      align-items: flex-start;
      gap: 0.5rem;
    }
  }
</style>