<script lang="ts">
  export let contestant: {
    id: number;
    name: string;
    nickname: string;
    age: number;
  };
  export let confidence: number;
  export let timestamp: number;
  export let faceLocation: [number, number, number, number] = [0, 0, 0, 0];
  export let onFaceClick: ((contestant: any, timestamp: number) => void) | null = null;

  // Format confidence as percentage
  $: confidencePercent = Math.round(confidence * 100);
  
  // Get confidence color and label
  $: confidenceData = getConfidenceData(confidence);
  
  function getConfidenceData(conf: number) {
    if (conf >= 0.8) return { color: '#10b981', label: 'High', bgColor: '#d1fae5' };
    if (conf >= 0.6) return { color: '#f59e0b', label: 'Medium', bgColor: '#fef3c7' };
    if (conf >= 0.4) return { color: '#f97316', label: 'Low', bgColor: '#fed7aa' };
    return { color: '#ef4444', label: 'Very Low', bgColor: '#fecaca' };
  }

  // Format timestamp to MM:SS
  function formatTimestamp(seconds: number): string {
    const minutes = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
  }

  function handleClick() {
    if (onFaceClick) {
      onFaceClick(contestant, timestamp);
    }
  }
</script>

<div 
  class="face-card"
  class:clickable={onFaceClick !== null}
  on:click={handleClick}
  on:keydown={(e) => e.key === 'Enter' && handleClick()}
  role={onFaceClick ? 'button' : 'article'}
  tabindex={onFaceClick ? '0' : undefined}
>
  <div class="face-photo">
    <img 
      src="/api/contestants/{contestant.id}/photo" 
      alt="{contestant.name} ({contestant.nickname})"
      loading="lazy"
      on:error={(e) => {
        // Fallback to default avatar if photo fails to load
        e.currentTarget.src = '/api/contestants/default/photo';
      }}
    />
    <div class="confidence-badge" 
         style="background-color: {confidenceData.color}; color: white"
         title="Confidence: {confidencePercent}% ({confidenceData.label})"
         aria-label="Recognition confidence {confidencePercent} percent, {confidenceData.label} certainty"
    >
      <span class="confidence-percentage">{confidencePercent}%</span>
      <span class="confidence-level">{confidenceData.label}</span>
    </div>
  </div>
  
  <div class="face-info">
    <div class="contestant-name">
      <h4 class="name">{contestant.name}</h4>
      <p class="nickname">{contestant.nickname}</p>
    </div>
    
    <div class="metadata">
      <button class="timestamp-button" 
              on:click|stopPropagation={() => onFaceClick && onFaceClick(contestant, timestamp)}
              title="Jump to {formatTimestamp(timestamp)}"
              aria-label="Jump to timestamp {formatTimestamp(timestamp)}"
      >
        <svg class="clock-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"/>
          <polyline points="12,6 12,12 16,14"/>
        </svg>
        {formatTimestamp(timestamp)}
      </button>
      <span class="age-badge">年齡 {contestant.age}</span>
    </div>
  </div>
</div>

<style>
  .face-card {
    background: white;
    border-radius: 0.75rem;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    overflow: hidden;
    transition: all 0.2s ease;
    border: 1px solid #e5e7eb;
  }

  .face-card:hover {
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    transform: translateY(-2px);
  }

  .face-card.clickable {
    cursor: pointer;
  }

  .face-card.clickable:hover {
    border-color: #3b82f6;
  }

  .face-card.clickable:focus {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
  }

  .face-card.clickable:focus-visible {
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.2);
  }

  .face-photo {
    position: relative;
    width: 100%;
    height: 120px;
    overflow: hidden;
    background: #f3f4f6;
  }

  .face-photo img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    transition: transform 0.2s ease;
  }

  .face-card:hover .face-photo img {
    transform: scale(1.05);
  }

  .confidence-badge {
    position: absolute;
    top: 0.5rem;
    right: 0.5rem;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 0.375rem 0.5rem;
    border-radius: 0.5rem;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25);
    backdrop-filter: blur(4px);
    min-width: 60px;
  }

  .confidence-percentage {
    font-size: 0.75rem;
    font-weight: 700;
    line-height: 1;
  }

  .confidence-level {
    font-size: 0.625rem;
    font-weight: 500;
    opacity: 0.9;
    margin-top: 1px;
  }

  .face-info {
    padding: 0.75rem;
  }

  .contestant-name {
    margin-bottom: 0.5rem;
  }

  .name {
    font-size: 0.9rem;
    font-weight: 600;
    margin: 0 0 0.25rem;
    color: #111827;
    line-height: 1.2;
  }

  .nickname {
    font-size: 0.8rem;
    color: #6b7280;
    margin: 0;
    font-style: italic;
  }

  .metadata {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.75rem;
    color: #9ca3af;
  }

  .timestamp-button {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    background: var(--primary-color);
    color: white;
    border: none;
    padding: 0.25rem 0.5rem;
    border-radius: 0.375rem;
    font-size: 0.7rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .timestamp-button:hover {
    background: var(--primary-hover);
    transform: translateY(-1px);
    box-shadow: 0 2px 4px rgba(59, 130, 246, 0.3);
  }

  .clock-icon {
    width: 0.75rem;
    height: 0.75rem;
  }

  .age-badge {
    background: var(--surface-color);
    color: var(--text-secondary);
    padding: 0.25rem 0.5rem;
    border-radius: 0.375rem;
    font-size: 0.7rem;
    font-weight: 500;
    border: 1px solid var(--border-color);
  }

  /* Responsive adjustments */
  @media (max-width: 768px) {
    .face-photo {
      height: 100px;
    }

    .face-info {
      padding: 0.5rem;
    }

    .name {
      font-size: 0.85rem;
    }

    .nickname {
      font-size: 0.75rem;
    }

    .metadata {
      font-size: 0.65rem;
    }

    .confidence-badge {
      padding: 0.25rem 0.375rem;
      min-width: 50px;
    }

    .confidence-percentage {
      font-size: 0.7rem;
    }

    .confidence-level {
      font-size: 0.55rem;
    }
  }

  /* Animation for new face cards */
  .face-card {
    animation: fadeInUp 0.3s ease-out;
  }

  @keyframes fadeInUp {
    from {
      opacity: 0;
      transform: translateY(10px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }
</style>