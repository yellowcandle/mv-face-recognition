<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  
  let videos: any[] = [];
  let loading = true;
  let error = '';
  
  onMount(async () => {
    try {
      await loadVideos();
    } catch (err) {
      error = 'Failed to load videos';
      console.error('Error:', err);
    } finally {
      loading = false;
    }
  });
  
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
  
  function goToVideoPlayer() {
    goto('/video-player');
  }
  
  function formatDuration(seconds: number): string {
    const minutes = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
  }
</script>

<svelte:head>
  <title>MV Video Gallery</title>
</svelte:head>

<main class="home-container">
  <div class="header">
    <h1>MV Video Gallery</h1>
    <p>Watch your favorite MV performances with face recognition annotations</p>
  </div>

  {#if loading}
    <div class="loading">
      <div class="spinner"></div>
      <p>Loading videos...</p>
    </div>
  {:else if error}
    <div class="error">
      <p>{error}</p>
    </div>
  {:else}
    <div class="content">
      <div class="hero-section">
        <div class="hero-content">
          <h2>Ready to Watch?</h2>
          <p>Browse and watch your video collection with pre-processed face recognition annotations.</p>
          <button on:click={goToVideoPlayer} class="cta-button">
            Start Watching ▶️
          </button>
        </div>
      </div>

      <div class="video-grid">
        <h3>Available Videos ({videos.length})</h3>
        
        {#if videos.length > 0}
          <div class="videos">
            {#each videos as video}
              <div class="video-card" on:click={goToVideoPlayer}>
                <div class="video-thumbnail">
                  <img 
                    src="/api/videos/{video.id}/thumbnail" 
                    alt={video.name}
                    loading="lazy"
                    on:error={(e) => e.target.style.display = 'none'}
                  />
                  <div class="play-overlay">▶️</div>
                </div>
                <div class="video-info">
                  <h4>{video.name}</h4>
                  <div class="video-meta">
                    <span class="duration">{formatDuration(video.duration || 0)}</span>
                    <span class="status">Ready</span>
                  </div>
                </div>
              </div>
            {/each}
          </div>
        {:else}
          <div class="no-videos">
            <div class="no-videos-icon">📹</div>
            <h4>No videos available</h4>
            <p>Process some videos locally and upload them to get started.</p>
          </div>
        {/if}
      </div>
    </div>
  {/if}
</main>

<style>
  .home-container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 2rem;
  }

  .header {
    text-align: center;
    margin-bottom: 3rem;
  }

  .header h1 {
    font-size: 3rem;
    font-weight: bold;
    margin: 0 0 1rem 0;
    color: #111827;
  }

  .header p {
    font-size: 1.1rem;
    color: #6b7280;
    margin: 0;
  }

  .loading, .error {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 4rem 2rem;
    text-align: center;
  }

  .spinner {
    width: 2rem;
    height: 2rem;
    border: 2px solid #e5e7eb;
    border-top: 2px solid #3b82f6;
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin-bottom: 1rem;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .error {
    color: #dc2626;
  }

  .content {
    display: flex;
    flex-direction: column;
    gap: 3rem;
  }

  .hero-section {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 1rem;
    padding: 3rem;
    text-align: center;
    color: white;
  }

  .hero-content h2 {
    font-size: 2.5rem;
    font-weight: bold;
    margin: 0 0 1rem 0;
  }

  .hero-content p {
    font-size: 1.1rem;
    margin: 0 0 2rem 0;
    opacity: 0.9;
  }

  .cta-button {
    background: white;
    color: #667eea;
    border: none;
    border-radius: 0.5rem;
    padding: 1rem 2rem;
    font-size: 1.1rem;
    font-weight: 600;
    cursor: pointer;
    transition: transform 0.2s;
  }

  .cta-button:hover {
    transform: translateY(-2px);
  }

  .video-grid h3 {
    font-size: 1.5rem;
    font-weight: 600;
    margin: 0 0 1.5rem 0;
    color: #111827;
  }

  .videos {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 1.5rem;
  }

  .video-card {
    background: white;
    border-radius: 0.75rem;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.07);
    overflow: hidden;
    cursor: pointer;
    transition: transform 0.2s, box-shadow 0.2s;
  }

  .video-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 8px 25px rgba(0, 0, 0, 0.12);
  }

  .video-thumbnail {
    position: relative;
    height: 160px;
    background: #f3f4f6;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .video-thumbnail img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .play-overlay {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    background: rgba(0, 0, 0, 0.7);
    color: white;
    border-radius: 50%;
    width: 60px;
    height: 60px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.5rem;
    opacity: 0;
    transition: opacity 0.2s;
  }

  .video-card:hover .play-overlay {
    opacity: 1;
  }

  .video-info {
    padding: 1rem;
  }

  .video-info h4 {
    font-size: 1rem;
    font-weight: 600;
    margin: 0 0 0.5rem 0;
    color: #111827;
    line-height: 1.4;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .video-meta {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .duration {
    font-size: 0.9rem;
    color: #6b7280;
  }

  .status {
    font-size: 0.8rem;
    padding: 0.25rem 0.5rem;
    background: #d1fae5;
    color: #065f46;
    border-radius: 0.375rem;
  }

  .no-videos {
    text-align: center;
    padding: 3rem;
    background: white;
    border-radius: 0.75rem;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  }

  .no-videos-icon {
    font-size: 3rem;
    margin-bottom: 1rem;
  }

  .no-videos h4 {
    font-size: 1.25rem;
    font-weight: 600;
    margin: 0 0 0.5rem 0;
    color: #374151;
  }

  .no-videos p {
    color: #6b7280;
    margin: 0;
  }

  @media (max-width: 768px) {
    .home-container {
      padding: 1rem;
    }
    
    .header h1 {
      font-size: 2rem;
    }
    
    .hero-section {
      padding: 2rem;
    }
    
    .hero-content h2 {
      font-size: 1.8rem;
    }
    
    .videos {
      grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
    }
  }
</style>