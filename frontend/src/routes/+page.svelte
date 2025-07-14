<script lang="ts">
  import { onMount } from 'svelte';
  
  let systemStatus: any = null;
  let videos: any[] = [];
  let contestants: any[] = [];
  let recentActivity: any[] = [];
  let loading = true;
  let error = '';
  
  onMount(async () => {
    try {
      await Promise.all([
        loadSystemStatus(),
        loadVideos(),
        loadContestants(),
        loadRecentActivity()
      ]);
    } catch (err) {
      error = 'Failed to load dashboard data';
      console.error('Dashboard error:', err);
    } finally {
      loading = false;
    }
  });
  
  async function loadSystemStatus() {
    try {
      const response = await fetch('/api/system/status');
      if (response.ok) {
        systemStatus = await response.json();
      }
    } catch (err) {
      console.error('Failed to load system status:', err);
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
  
  async function loadRecentActivity() {
    // Mock recent activity data
    recentActivity = [
      {
        id: 1,
        type: 'video_processed',
        message: 'Video "《全民造星IV》主題曲" processing completed',
        timestamp: new Date(Date.now() - 30 * 60 * 1000).toISOString(),
        status: 'success'
      },
      {
        id: 2,
        type: 'recognition_complete',
        message: '15 faces recognized in video "女團の駅 Performance"',
        timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
        status: 'success'
      },
      {
        id: 3,
        type: 'video_uploaded',
        message: 'New video "Practice Session" uploaded for processing',
        timestamp: new Date(Date.now() - 4 * 60 * 60 * 1000).toISOString(),
        status: 'info'
      },
      {
        id: 4,
        type: 'system_update',
        message: 'Face recognition model updated to v2.1',
        timestamp: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
        status: 'info'
      }
    ];
  }
  
  function getStatusColor(status: string) {
    switch (status) {
      case 'completed': return 'var(--success-color)';
      case 'processing': return 'var(--warning-color)';
      case 'failed': return 'var(--error-color)';
      default: return 'var(--secondary-color)';
    }
  }
  
  function getActivityIcon(type: string) {
    switch (type) {
      case 'video_processed': return '✅';
      case 'recognition_complete': return '🎯';
      case 'video_uploaded': return '📤';
      case 'system_update': return '🔄';
      default: return 'ℹ️';
    }
  }
  
  function formatTimeAgo(timestamp: string) {
    const now = new Date();
    const time = new Date(timestamp);
    const diffMs = now.getTime() - time.getTime();
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffMinutes = Math.floor(diffMs / (1000 * 60));
    
    if (diffHours > 0) {
      return `${diffHours}h ago`;
    } else if (diffMinutes > 0) {
      return `${diffMinutes}m ago`;
    } else {
      return 'Just now';
    }
  }
</script>

<svelte:head>
  <title>Dashboard - MV Face Recognition</title>
  <meta name="description" content="Dashboard overview of video processing and face recognition system" />
</svelte:head>

<div class="dashboard">
  <header class="page-header">
    <h1>Dashboard</h1>
    <p>System overview and recent activity</p>
  </header>
  
  {#if loading}
    <div class="loading">
      <div class="spinner"></div>
      <p>Loading dashboard...</p>
    </div>
  {:else if error}
    <div class="error">
      <p>{error}</p>
      <button on:click={() => window.location.reload()}>Retry</button>
    </div>
  {:else}
    <!-- System Status Cards -->
    <section class="status-grid">
      <div class="status-card">
        <div class="status-header">
          <h3>System Status</h3>
          <span class="status-badge" class:online={systemStatus?.status === 'online'}>
            {systemStatus?.status || 'unknown'}
          </span>
        </div>
        <div class="status-details">
          <p><strong>Version:</strong> {systemStatus?.version || 'N/A'}</p>
          <p><strong>Environment:</strong> {systemStatus?.environment || 'N/A'}</p>
          <p><strong>Last Updated:</strong> {systemStatus?.timestamp ? new Date(systemStatus.timestamp).toLocaleString() : 'N/A'}</p>
        </div>
      </div>
      
      <div class="status-card">
        <div class="status-header">
          <h3>Videos</h3>
          <span class="count-badge">{videos.length}</span>
        </div>
        <div class="status-details">
          <p><strong>Completed:</strong> {videos.filter(v => v.status === 'completed').length}</p>
          <p><strong>Processing:</strong> {videos.filter(v => v.status === 'processing').length}</p>
          <p><strong>Failed:</strong> {videos.filter(v => v.status === 'failed').length}</p>
        </div>
      </div>
      
      <div class="status-card">
        <div class="status-header">
          <h3>Contestants</h3>
          <span class="count-badge">{contestants.length}</span>
        </div>
        <div class="status-details">
          <p><strong>Database:</strong> Ready</p>
          <p><strong>Embeddings:</strong> Generated</p>
          <p><strong>Recognition:</strong> Active</p>
        </div>
      </div>
      
      <div class="status-card">
        <div class="status-header">
          <h3>Features</h3>
          <span class="feature-indicator">🚀</span>
        </div>
        <div class="status-details">
          <p><strong>Video Streaming:</strong> {systemStatus?.features?.video_streaming ? '✅' : '❌'}</p>
          <p><strong>Face Recognition:</strong> {systemStatus?.features?.face_recognition ? '✅' : '❌'}</p>
          <p><strong>Metadata Storage:</strong> {systemStatus?.features?.metadata_storage ? '✅' : '❌'}</p>
        </div>
      </div>
    </section>
    
    <!-- Quick Actions -->
    <section class="quick-actions">
      <h2>Quick Actions</h2>
      <div class="actions-grid">
        <a href="/video-player" class="action-card">
          <div class="action-icon">▶️</div>
          <div class="action-content">
            <h3>Watch Videos</h3>
            <p>View processed videos with face recognition overlays</p>
          </div>
        </a>
        
        <a href="/face-recognition" class="action-card">
          <div class="action-icon">🎯</div>
          <div class="action-content">
            <h3>Recognition Results</h3>
            <p>Browse and filter face recognition results</p>
          </div>
        </a>
        
        <a href="/analytics" class="action-card">
          <div class="action-icon">📊</div>
          <div class="action-content">
            <h3>Analytics</h3>
            <p>View processing statistics and performance metrics</p>
          </div>
        </a>
        
        <a href="/settings" class="action-card">
          <div class="action-icon">⚙️</div>
          <div class="action-content">
            <h3>Settings</h3>
            <p>Configure system preferences and parameters</p>
          </div>
        </a>
      </div>
    </section>
    
    <!-- Recent Activity -->
    <section class="recent-activity">
      <h2>Recent Activity</h2>
      <div class="activity-list">
        {#each recentActivity as activity}
          <div class="activity-item">
            <div class="activity-icon">{getActivityIcon(activity.type)}</div>
            <div class="activity-content">
              <p>{activity.message}</p>
              <span class="activity-time">{formatTimeAgo(activity.timestamp)}</span>
            </div>
          </div>
        {/each}
      </div>
    </section>
    
    <!-- Video Overview -->
    {#if videos.length > 0}
      <section class="video-overview">
        <h2>Recent Videos</h2>
        <div class="video-grid">
          {#each videos.slice(0, 6) as video}
            <div class="video-card">
              <div class="video-thumbnail">
                <div class="thumbnail-placeholder">🎬</div>
                <div class="video-status" style="background-color: {getStatusColor(video.status)}">
                  {video.status}
                </div>
              </div>
              <div class="video-info">
                <h4>{video.name}</h4>
                <p>Duration: {Math.floor(video.duration / 60)}:{(video.duration % 60).toFixed(0).padStart(2, '0')}</p>
                <p>Uploaded: {new Date(video.uploadedAt).toLocaleDateString()}</p>
              </div>
            </div>
          {/each}
        </div>
      </section>
    {/if}
  {/if}
</div>

<style>
  .dashboard {
    max-width: 100%;
  }
  
  .page-header {
    margin-bottom: 2rem;
  }
  
  .page-header h1 {
    font-size: 2.5rem;
    font-weight: 700;
    margin: 0 0 0.5rem 0;
    color: var(--text-color);
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
    justify-content: center;
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
  
  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }
  
  .error button {
    margin-top: 1rem;
    padding: 0.5rem 1rem;
    background-color: var(--primary-color);
    color: white;
    border: none;
    border-radius: 0.375rem;
    cursor: pointer;
    transition: background-color 0.2s;
  }
  
  .error button:hover {
    background-color: var(--primary-hover);
  }
  
  /* Status Grid */
  .status-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 1.5rem;
    margin-bottom: 3rem;
  }
  
  .status-card {
    background-color: var(--surface-color);
    border: 1px solid var(--border-color);
    border-radius: 0.75rem;
    padding: 1.5rem;
    box-shadow: var(--shadow);
    transition: transform 0.2s, box-shadow 0.2s;
  }
  
  .status-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px 0 rgb(0 0 0 / 0.15);
  }
  
  .status-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
  }
  
  .status-header h3 {
    margin: 0;
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--text-color);
  }
  
  .status-badge {
    padding: 0.25rem 0.75rem;
    border-radius: 1rem;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    background-color: var(--secondary-color);
    color: white;
  }
  
  .status-badge.online {
    background-color: var(--success-color);
  }
  
  .count-badge, .feature-indicator {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--primary-color);
  }
  
  .status-details p {
    margin: 0.5rem 0;
    font-size: 0.9rem;
    color: var(--text-secondary);
  }
  
  /* Quick Actions */
  .quick-actions {
    margin-bottom: 3rem;
  }
  
  .quick-actions h2 {
    font-size: 1.5rem;
    font-weight: 600;
    margin-bottom: 1.5rem;
    color: var(--text-color);
  }
  
  .actions-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 1.5rem;
  }
  
  .action-card {
    display: flex;
    align-items: center;
    gap: 1rem;
    background-color: var(--surface-color);
    border: 1px solid var(--border-color);
    border-radius: 0.75rem;
    padding: 1.5rem;
    text-decoration: none;
    color: var(--text-color);
    box-shadow: var(--shadow);
    transition: transform 0.2s, box-shadow 0.2s;
  }
  
  .action-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px 0 rgb(0 0 0 / 0.15);
  }
  
  .action-icon {
    font-size: 2.5rem;
    flex-shrink: 0;
  }
  
  .action-content h3 {
    margin: 0 0 0.5rem 0;
    font-size: 1.1rem;
    font-weight: 600;
  }
  
  .action-content p {
    margin: 0;
    font-size: 0.9rem;
    color: var(--text-secondary);
  }
  
  /* Recent Activity */
  .recent-activity {
    margin-bottom: 3rem;
  }
  
  .recent-activity h2 {
    font-size: 1.5rem;
    font-weight: 600;
    margin-bottom: 1.5rem;
    color: var(--text-color);
  }
  
  .activity-list {
    background-color: var(--surface-color);
    border: 1px solid var(--border-color);
    border-radius: 0.75rem;
    overflow: hidden;
  }
  
  .activity-item {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 1rem 1.5rem;
    border-bottom: 1px solid var(--border-color);
  }
  
  .activity-item:last-child {
    border-bottom: none;
  }
  
  .activity-icon {
    font-size: 1.5rem;
    flex-shrink: 0;
  }
  
  .activity-content {
    flex: 1;
  }
  
  .activity-content p {
    margin: 0;
    font-size: 0.95rem;
    color: var(--text-color);
  }
  
  .activity-time {
    font-size: 0.8rem;
    color: var(--text-secondary);
  }
  
  /* Video Overview */
  .video-overview {
    margin-bottom: 2rem;
  }
  
  .video-overview h2 {
    font-size: 1.5rem;
    font-weight: 600;
    margin-bottom: 1.5rem;
    color: var(--text-color);
  }
  
  .video-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
    gap: 1.5rem;
  }
  
  .video-card {
    background-color: var(--surface-color);
    border: 1px solid var(--border-color);
    border-radius: 0.75rem;
    overflow: hidden;
    box-shadow: var(--shadow);
    transition: transform 0.2s, box-shadow 0.2s;
  }
  
  .video-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px 0 rgb(0 0 0 / 0.15);
  }
  
  .video-thumbnail {
    position: relative;
    height: 140px;
    background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
    display: flex;
    align-items: center;
    justify-content: center;
  }
  
  .thumbnail-placeholder {
    font-size: 3rem;
    color: white;
    opacity: 0.8;
  }
  
  .video-status {
    position: absolute;
    top: 0.5rem;
    right: 0.5rem;
    padding: 0.25rem 0.5rem;
    border-radius: 0.25rem;
    font-size: 0.75rem;
    font-weight: 600;
    color: white;
    text-transform: capitalize;
  }
  
  .video-info {
    padding: 1rem;
  }
  
  .video-info h4 {
    margin: 0 0 0.5rem 0;
    font-size: 1rem;
    font-weight: 600;
    color: var(--text-color);
    line-height: 1.4;
  }
  
  .video-info p {
    margin: 0.25rem 0;
    font-size: 0.85rem;
    color: var(--text-secondary);
  }
  
  /* Mobile Responsiveness */
  @media (max-width: 768px) {
    .page-header h1 {
      font-size: 2rem;
    }
    
    .status-grid {
      grid-template-columns: 1fr;
      gap: 1rem;
    }
    
    .actions-grid {
      grid-template-columns: 1fr;
      gap: 1rem;
    }
    
    .action-card {
      padding: 1rem;
    }
    
    .action-icon {
      font-size: 2rem;
    }
    
    .video-grid {
      grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: 1rem;
    }
  }
  
  @media (max-width: 480px) {
    .page-header h1 {
      font-size: 1.75rem;
    }
    
    .status-card, .action-card {
      padding: 1rem;
    }
    
    .activity-item {
      padding: 0.75rem 1rem;
    }
    
    .video-grid {
      grid-template-columns: 1fr;
    }
  }
</style>