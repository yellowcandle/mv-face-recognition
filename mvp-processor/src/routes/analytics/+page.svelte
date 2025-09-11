<script lang="ts">
  import { onMount } from 'svelte';
  
  interface AnalyticsData {
    totalVideos: number;
    totalFacesDetected: number;
    totalFacesRecognized: number;
    processingTime: number;
    accuracy: number;
  }
  
  let analyticsData: AnalyticsData = {
    totalVideos: 3,
    totalFacesDetected: 342,
    totalFacesRecognized: 267,
    processingTime: 1847, // seconds
    accuracy: 78.1
  };
  
  let topContestants = [
    { name: 'Sarah Wilson', appearances: 45, confidence: 92.3 },
    { name: 'Alex Chen', appearances: 38, confidence: 89.7 },
    { name: 'Mike Johnson', appearances: 32, confidence: 87.1 },
    { name: 'Emma Davis', appearances: 28, confidence: 85.4 },
    { name: 'John Doe', appearances: 24, confidence: 83.2 }
  ];
  
  let processingHistory = [
    { date: '2024-01-15', videos: 1, faces: 127, accuracy: 82.3 },
    { date: '2024-01-14', videos: 1, faces: 89, accuracy: 76.8 },
    { date: '2024-01-13', videos: 1, faces: 126, accuracy: 79.4 }
  ];
  
  function formatTime(seconds: number): string {
    const hours = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    
    if (hours > 0) {
      return `${hours}h ${mins}m ${secs}s`;
    }
    return `${mins}m ${secs}s`;
  }
  
  function formatDate(dateString: string): string {
    return new Date(dateString).toLocaleDateString();
  }
  
  onMount(() => {
    // Simulate real-time updates
    const interval = setInterval(() => {
      analyticsData = {
        ...analyticsData,
        accuracy: Math.max(70, Math.min(95, analyticsData.accuracy + (Math.random() - 0.5) * 2))
      };
    }, 5000);
    
    return () => clearInterval(interval);
  });
</script>

<svelte:head>
  <title>Analytics - Face Recognition Dashboard</title>
</svelte:head>

<div class="analytics-container">
  <div class="analytics-header">
    <h1>Analytics Dashboard</h1>
    <div class="refresh-info">
      <span class="refresh-indicator">🔄</span>
      <span>Auto-refresh: 5s</span>
    </div>
  </div>

  <!-- Key Metrics -->
  <div class="metrics-grid">
    <div class="metric-card">
      <div class="metric-icon">🎬</div>
      <div class="metric-content">
        <div class="metric-value">{analyticsData.totalVideos}</div>
        <div class="metric-label">Videos Processed</div>
      </div>
    </div>
    
    <div class="metric-card">
      <div class="metric-icon">👥</div>
      <div class="metric-content">
        <div class="metric-value">{analyticsData.totalFacesDetected.toLocaleString()}</div>
        <div class="metric-label">Faces Detected</div>
      </div>
    </div>
    
    <div class="metric-card">
      <div class="metric-icon">✅</div>
      <div class="metric-content">
        <div class="metric-value">{analyticsData.totalFacesRecognized.toLocaleString()}</div>
        <div class="metric-label">Faces Recognized</div>
      </div>
    </div>
    
    <div class="metric-card">
      <div class="metric-icon">⏱️</div>
      <div class="metric-content">
        <div class="metric-value">{formatTime(analyticsData.processingTime)}</div>
        <div class="metric-label">Total Processing Time</div>
      </div>
    </div>
  </div>

  <div class="analytics-main">
    <!-- Recognition Accuracy -->
    <div class="accuracy-panel">
      <h3>Recognition Accuracy</h3>
      
      <div class="accuracy-display">
        <div class="accuracy-circle">
          <div class="accuracy-value">{analyticsData.accuracy.toFixed(1)}%</div>
          <div class="accuracy-label">Overall Accuracy</div>
        </div>
        
        <div class="accuracy-breakdown">
          <div class="breakdown-item">
            <span class="breakdown-label">High Confidence (&gt;80%):</span>
            <span class="breakdown-value">67%</span>
          </div>
          <div class="breakdown-item">
            <span class="breakdown-label">Medium Confidence (60-80%):</span>
            <span class="breakdown-value">23%</span>
          </div>
          <div class="breakdown-item">
            <span class="breakdown-label">Low Confidence (&lt;60%):</span>
            <span class="breakdown-value">10%</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Top Contestants -->
    <div class="contestants-panel">
      <h3>Top Recognized Contestants</h3>
      
      <div class="contestants-list">
        {#each topContestants as contestant, index}
          <div class="contestant-item">
            <div class="contestant-rank">#{index + 1}</div>
            <div class="contestant-info">
              <div class="contestant-name">{contestant.name}</div>
              <div class="contestant-stats">
                <span class="stat">
                  <span class="stat-icon">👁️</span>
                  {contestant.appearances} appearances
                </span>
                <span class="stat">
                  <span class="stat-icon">🎯</span>
                  {contestant.confidence}% avg confidence
                </span>
              </div>
            </div>
            <div class="contestant-confidence">
              <div class="confidence-bar">
                <div 
                  class="confidence-fill" 
                  style="width: {contestant.confidence}%"
                ></div>
              </div>
            </div>
          </div>
        {/each}
      </div>
    </div>
  </div>

  <!-- Processing History -->
  <div class="history-panel">
    <h3>Processing History</h3>
    
    <div class="history-table">
      <div class="table-header">
        <div class="header-cell">Date</div>
        <div class="header-cell">Videos</div>
        <div class="header-cell">Faces Detected</div>
        <div class="header-cell">Accuracy</div>
      </div>
      
      {#each processingHistory as record}
        <div class="table-row">
          <div class="table-cell">{formatDate(record.date)}</div>
          <div class="table-cell">{record.videos}</div>
          <div class="table-cell">{record.faces}</div>
          <div class="table-cell">
            <span class="accuracy-badge">{record.accuracy}%</span>
          </div>
        </div>
      {/each}
    </div>
  </div>

  <!-- Export Options -->
  <div class="export-panel">
    <h3>Export Data</h3>
    
    <div class="export-options">
      <button class="export-btn">
        📊 Export CSV
      </button>
      <button class="export-btn">
        📈 Export JSON
      </button>
      <button class="export-btn">
        📋 Generate Report
      </button>
    </div>
  </div>
</div>

<style>
  .analytics-container {
    height: 100%;
    display: flex;
    flex-direction: column;
    padding: 20px;
    background-color: #1a1a1a;
    color: #ffffff;
    gap: 20px;
    overflow-y: auto;
  }

  .analytics-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: 15px;
    border-bottom: 1px solid #444;
  }

  .analytics-header h1 {
    font-size: 24px;
    font-weight: 600;
    margin: 0;
  }

  .refresh-info {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 14px;
    color: #9ca3af;
  }

  .refresh-indicator {
    animation: spin 2s linear infinite;
  }

  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }

  .metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 20px;
  }

  .metric-card {
    background-color: #1e293b;
    border-radius: 8px;
    padding: 20px;
    display: flex;
    align-items: center;
    gap: 15px;
    border: 1px solid #334155;
    transition: all 0.2s;
  }

  .metric-card:hover {
    border-color: #3b82f6;
    transform: translateY(-2px);
  }

  .metric-icon {
    font-size: 32px;
    width: 50px;
    text-align: center;
  }

  .metric-content {
    flex: 1;
  }

  .metric-value {
    font-size: 28px;
    font-weight: 700;
    color: #ffffff;
    line-height: 1;
  }

  .metric-label {
    font-size: 14px;
    color: #9ca3af;
    margin-top: 4px;
  }

  .analytics-main {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
  }

  .accuracy-panel {
    background-color: #1e293b;
    border-radius: 8px;
    padding: 20px;
  }

  .accuracy-panel h3 {
    font-size: 18px;
    font-weight: 600;
    margin-bottom: 20px;
    color: #ffffff;
  }

  .accuracy-display {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 20px;
  }

  .accuracy-circle {
    width: 150px;
    height: 150px;
    border-radius: 50%;
    background: conic-gradient(#22c55e 0deg, #22c55e calc(var(--accuracy, 78.1) * 3.6deg), #374151 calc(var(--accuracy, 78.1) * 3.6deg), #374151 360deg);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    position: relative;
  }

  .accuracy-circle::before {
    content: '';
    position: absolute;
    width: 120px;
    height: 120px;
    background-color: #1e293b;
    border-radius: 50%;
  }

  .accuracy-value {
    font-size: 24px;
    font-weight: 700;
    color: #ffffff;
    z-index: 1;
  }

  .accuracy-label {
    font-size: 12px;
    color: #9ca3af;
    z-index: 1;
  }

  .accuracy-breakdown {
    width: 100%;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .breakdown-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 0;
    border-bottom: 1px solid #334155;
  }

  .breakdown-item:last-child {
    border-bottom: none;
  }

  .breakdown-label {
    color: #9ca3af;
    font-size: 14px;
  }

  .breakdown-value {
    color: #ffffff;
    font-weight: 600;
  }

  .contestants-panel {
    background-color: #1e293b;
    border-radius: 8px;
    padding: 20px;
  }

  .contestants-panel h3 {
    font-size: 18px;
    font-weight: 600;
    margin-bottom: 20px;
    color: #ffffff;
  }

  .contestants-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .contestant-item {
    display: flex;
    align-items: center;
    gap: 15px;
    padding: 12px;
    background-color: #2d3748;
    border-radius: 6px;
    transition: all 0.2s;
  }

  .contestant-item:hover {
    background-color: #374151;
  }

  .contestant-rank {
    width: 30px;
    height: 30px;
    background-color: #3b82f6;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 600;
    font-size: 14px;
    color: #ffffff;
  }

  .contestant-info {
    flex: 1;
  }

  .contestant-name {
    font-weight: 600;
    margin-bottom: 4px;
    color: #ffffff;
  }

  .contestant-stats {
    display: flex;
    gap: 15px;
    font-size: 12px;
    color: #9ca3af;
  }

  .stat {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .stat-icon {
    font-size: 10px;
  }

  .contestant-confidence {
    width: 100px;
  }

  .confidence-bar {
    height: 6px;
    background-color: #374151;
    border-radius: 3px;
    overflow: hidden;
  }

  .confidence-fill {
    height: 100%;
    background-color: #22c55e;
    border-radius: 3px;
    transition: width 0.3s ease;
  }

  .history-panel {
    background-color: #1e293b;
    border-radius: 8px;
    padding: 20px;
    grid-column: 1 / -1;
  }

  .history-panel h3 {
    font-size: 18px;
    font-weight: 600;
    margin-bottom: 20px;
    color: #ffffff;
  }

  .history-table {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .table-header {
    display: grid;
    grid-template-columns: 1fr 80px 120px 100px;
    gap: 15px;
    padding: 10px 15px;
    background-color: #374151;
    border-radius: 6px;
    font-weight: 600;
    color: #ffffff;
  }

  .table-row {
    display: grid;
    grid-template-columns: 1fr 80px 120px 100px;
    gap: 15px;
    padding: 10px 15px;
    background-color: #2d3748;
    border-radius: 6px;
    transition: background-color 0.2s;
  }

  .table-row:hover {
    background-color: #374151;
  }

  .header-cell {
    font-size: 14px;
  }

  .table-cell {
    font-size: 14px;
    color: #e2e8f0;
    display: flex;
    align-items: center;
  }

  .accuracy-badge {
    background-color: #22c55e;
    color: #000;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 600;
  }

  .export-panel {
    background-color: #1e293b;
    border-radius: 8px;
    padding: 20px;
  }

  .export-panel h3 {
    font-size: 18px;
    font-weight: 600;
    margin-bottom: 20px;
    color: #ffffff;
  }

  .export-options {
    display: flex;
    gap: 15px;
  }

  .export-btn {
    padding: 10px 20px;
    background-color: #3b82f6;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
    font-size: 14px;
  }

  .export-btn:hover {
    background-color: #2563eb;
    transform: translateY(-1px);
  }

  /* Mobile Responsive */
  @media (max-width: 768px) {
    .analytics-header {
      flex-direction: column;
      align-items: flex-start;
      gap: 15px;
    }
    
    .metrics-grid {
      grid-template-columns: 1fr;
    }
    
    .analytics-main {
      grid-template-columns: 1fr;
    }
    
    .table-header,
    .table-row {
      grid-template-columns: 1fr 60px 80px 80px;
      gap: 10px;
      padding: 8px 10px;
    }
    
    .export-options {
      flex-direction: column;
    }
  }
</style>