<script lang="ts">
  import { onMount } from 'svelte';
  
  let loading = true;
  let error = '';
  let systemMetrics: any = {};
  let processingStats: any = {};
  let recognitionStats: any = {};
  let performanceData: any[] = [];
  let topContestants: any[] = [];
  let timeRange = '7d';
  
  onMount(async () => {
    try {
      await loadAnalytics();
    } catch (err) {
      error = 'Failed to load analytics data';
      console.error('Analytics error:', err);
    } finally {
      loading = false;
    }
  });
  
  async function loadAnalytics() {
    // Since we don't have real analytics endpoints yet, we'll generate mock data
    generateMockData();
  }
  
  function generateMockData() {
    // System Metrics
    systemMetrics = {
      totalVideos: 15,
      totalRecognitions: 1247,
      totalContestants: 95,
      averageConfidence: 0.847,
      processingTime: 142.5,
      storageUsed: 2.4,
      apiCalls: 8932
    };
    
    // Processing Stats
    processingStats = {
      videosProcessed: 12,
      videosInQueue: 3,
      averageProcessingTime: 95.2,
      successRate: 94.7,
      failureRate: 5.3,
      totalFramesProcessed: 45823
    };
    
    // Recognition Stats
    recognitionStats = {
      highConfidence: 756, // >= 80%
      mediumConfidence: 342, // 60-80%
      lowConfidence: 149, // < 60%
      uniqueFacesDetected: 1247,
      averageConfidenceScore: 0.847,
      mostActiveVideo: 'Video 1'
    };
    
    // Performance Data (last 7 days)
    performanceData = [
      { date: '2024-07-08', recognitions: 145, avgConfidence: 0.85, processingTime: 89 },
      { date: '2024-07-09', recognitions: 167, avgConfidence: 0.82, processingTime: 92 },
      { date: '2024-07-10', recognitions: 198, avgConfidence: 0.88, processingTime: 85 },
      { date: '2024-07-11', recognitions: 156, avgConfidence: 0.84, processingTime: 91 },
      { date: '2024-07-12', recognitions: 203, avgConfidence: 0.86, processingTime: 87 },
      { date: '2024-07-13', recognitions: 189, avgConfidence: 0.83, processingTime: 94 },
      { date: '2024-07-14', recognitions: 189, avgConfidence: 0.85, processingTime: 88 }
    ];
    
    // Top Contestants by Recognition Count
    topContestants = [
      { name: '張三', nickname: '小張', recognitions: 89, avgConfidence: 0.92 },
      { name: '李四', nickname: '小李', recognitions: 76, avgConfidence: 0.88 },
      { name: '王五', nickname: '小王', recognitions: 65, avgConfidence: 0.85 },
      { name: '趙六', nickname: '小趙', recognitions: 58, avgConfidence: 0.90 },
      { name: '錢七', nickname: '小錢', recognitions: 52, avgConfidence: 0.87 },
      { name: '陳八', nickname: '小陳', recognitions: 47, avgConfidence: 0.83 },
      { name: '周九', nickname: '小周', recognitions: 41, avgConfidence: 0.89 },
      { name: '吳十', nickname: '小吳', recognitions: 38, avgConfidence: 0.86 }
    ];
  }
  
  function formatNumber(num: number) {
    if (num >= 1000000) {
      return (num / 1000000).toFixed(1) + 'M';
    } else if (num >= 1000) {
      return (num / 1000).toFixed(1) + 'K';
    }
    return num.toString();
  }
  
  function formatPercentage(num: number) {
    return (num * 100).toFixed(1) + '%';
  }
  
  function formatDuration(seconds: number) {
    if (seconds >= 60) {
      return `${Math.floor(seconds / 60)}m ${Math.floor(seconds % 60)}s`;
    }
    return `${Math.floor(seconds)}s`;
  }
  
  function getConfidenceColor(confidence: number) {
    if (confidence >= 0.8) return '#10b981';
    if (confidence >= 0.6) return '#f59e0b';
    return '#ef4444';
  }
  
  function getConfidenceLabel(confidence: number) {
    if (confidence >= 0.8) return 'High';
    if (confidence >= 0.6) return 'Medium';
    return 'Low';
  }
  
  $: {
    if (timeRange && !loading) {
      // In a real app, this would trigger a new data fetch
      console.log('Time range changed to:', timeRange);
    }
  }
</script>

<svelte:head>
  <title>Analytics - MV Face Recognition</title>
  <meta name="description" content="Analytics dashboard with system metrics and performance insights" />
</svelte:head>

<div class="analytics-page">
  <header class="page-header">
    <div class="header-content">
      <div>
        <h1>Analytics Dashboard</h1>
        <p>System metrics, performance insights, and recognition statistics</p>
      </div>
      
      <div class="time-range-selector">
        <label for="time-range">Time Range:</label>
        <select id="time-range" bind:value={timeRange}>
          <option value="24h">Last 24 Hours</option>
          <option value="7d">Last 7 Days</option>
          <option value="30d">Last 30 Days</option>
          <option value="90d">Last 90 Days</option>
        </select>
      </div>
    </div>
  </header>
  
  {#if loading}
    <div class="loading">
      <div class="spinner"></div>
      <p>Loading analytics...</p>
    </div>
  {:else if error}
    <div class="error">
      <p>{error}</p>
      <button on:click={() => window.location.reload()}>Retry</button>
    </div>
  {:else}
    <!-- System Overview -->
    <section class="metrics-section">
      <h2>System Overview</h2>
      <div class="metrics-grid">
        <div class="metric-card">
          <div class="metric-icon">🎬</div>
          <div class="metric-content">
            <div class="metric-value">{systemMetrics.totalVideos}</div>
            <div class="metric-label">Total Videos</div>
          </div>
        </div>
        
        <div class="metric-card">
          <div class="metric-icon">🎯</div>
          <div class="metric-content">
            <div class="metric-value">{formatNumber(systemMetrics.totalRecognitions)}</div>
            <div class="metric-label">Total Recognitions</div>
          </div>
        </div>
        
        <div class="metric-card">
          <div class="metric-icon">👥</div>
          <div class="metric-content">
            <div class="metric-value">{systemMetrics.totalContestants}</div>
            <div class="metric-label">Contestants</div>
          </div>
        </div>
        
        <div class="metric-card">
          <div class="metric-icon">📊</div>
          <div class="metric-content">
            <div class="metric-value">{formatPercentage(systemMetrics.averageConfidence)}</div>
            <div class="metric-label">Avg Confidence</div>
          </div>
        </div>
        
        <div class="metric-card">
          <div class="metric-icon">⚡</div>
          <div class="metric-content">
            <div class="metric-value">{formatDuration(systemMetrics.processingTime)}</div>
            <div class="metric-label">Avg Processing Time</div>
          </div>
        </div>
        
        <div class="metric-card">
          <div class="metric-icon">💾</div>
          <div class="metric-content">
            <div class="metric-value">{systemMetrics.storageUsed}GB</div>
            <div class="metric-label">Storage Used</div>
          </div>
        </div>
      </div>
    </section>
    
    <!-- Processing Statistics -->
    <section class="stats-section">
      <div class="stats-grid">
        <div class="stat-panel">
          <h3>Processing Status</h3>
          <div class="stat-items">
            <div class="stat-item">
              <span class="stat-label">Videos Processed</span>
              <span class="stat-value">{processingStats.videosProcessed}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">Videos in Queue</span>
              <span class="stat-value">{processingStats.videosInQueue}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">Success Rate</span>
              <span class="stat-value" style="color: var(--success-color)">
                {processingStats.successRate}%
              </span>
            </div>
            <div class="stat-item">
              <span class="stat-label">Failure Rate</span>
              <span class="stat-value" style="color: var(--error-color)">
                {processingStats.failureRate}%
              </span>
            </div>
          </div>
        </div>
        
        <div class="stat-panel">
          <h3>Recognition Quality</h3>
          <div class="confidence-breakdown">
            <div class="confidence-item">
              <div class="confidence-bar high" style="width: {(recognitionStats.highConfidence / systemMetrics.totalRecognitions) * 100}%"></div>
              <div class="confidence-details">
                <span class="confidence-label">High Confidence (≥80%)</span>
                <span class="confidence-count">{recognitionStats.highConfidence}</span>
              </div>
            </div>
            
            <div class="confidence-item">
              <div class="confidence-bar medium" style="width: {(recognitionStats.mediumConfidence / systemMetrics.totalRecognitions) * 100}%"></div>
              <div class="confidence-details">
                <span class="confidence-label">Medium Confidence (60-80%)</span>
                <span class="confidence-count">{recognitionStats.mediumConfidence}</span>
              </div>
            </div>
            
            <div class="confidence-item">
              <div class="confidence-bar low" style="width: {(recognitionStats.lowConfidence / systemMetrics.totalRecognitions) * 100}%"></div>
              <div class="confidence-details">
                <span class="confidence-label">Low Confidence (<60%)</span>
                <span class="confidence-count">{recognitionStats.lowConfidence}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
    
    <!-- Performance Trends -->
    <section class="trends-section">
      <h2>Performance Trends</h2>
      <div class="chart-container">
        <div class="chart-header">
          <h3>Daily Recognition Activity</h3>
          <span class="chart-subtitle">Recognition count and average confidence over time</span>
        </div>
        
        <div class="simple-chart">
          <div class="chart-grid">
            {#each performanceData as dataPoint, i}
              <div class="chart-day">
                <div class="chart-bars">
                  <div 
                    class="chart-bar recognitions"
                    style="height: {(dataPoint.recognitions / 250) * 100}%"
                    title="Recognitions: {dataPoint.recognitions}"
                  ></div>
                  <div 
                    class="chart-bar confidence"
                    style="height: {dataPoint.avgConfidence * 100}%; background-color: {getConfidenceColor(dataPoint.avgConfidence)}"
                    title="Avg Confidence: {formatPercentage(dataPoint.avgConfidence)}"
                  ></div>
                </div>
                <div class="chart-label">
                  {new Date(dataPoint.date).toLocaleDateString('en-US', { weekday: 'short' })}
                </div>
              </div>
            {/each}
          </div>
          
          <div class="chart-legend">
            <div class="legend-item">
              <div class="legend-color recognitions"></div>
              <span>Recognition Count</span>
            </div>
            <div class="legend-item">
              <div class="legend-color confidence"></div>
              <span>Average Confidence</span>
            </div>
          </div>
        </div>
      </div>
    </section>
    
    <!-- Top Performers -->
    <section class="top-performers-section">
      <h2>Top Recognized Contestants</h2>
      <div class="performers-grid">
        {#each topContestants as contestant, index}
          <div class="performer-card" class:top-performer={index < 3}>
            <div class="performer-rank">
              {#if index === 0}
                🥇
              {:else if index === 1}
                🥈
              {:else if index === 2}
                🥉
              {:else}
                #{index + 1}
              {/if}
            </div>
            
            <div class="performer-avatar">
              <span>{contestant.name.charAt(0)}</span>
            </div>
            
            <div class="performer-info">
              <h4>{contestant.name}</h4>
              <p>{contestant.nickname}</p>
              
              <div class="performer-stats">
                <div class="stat">
                  <span class="stat-number">{contestant.recognitions}</span>
                  <span class="stat-text">recognitions</span>
                </div>
                <div class="stat">
                  <span class="stat-number" style="color: {getConfidenceColor(contestant.avgConfidence)}">
                    {formatPercentage(contestant.avgConfidence)}
                  </span>
                  <span class="stat-text">avg confidence</span>
                </div>
              </div>
            </div>
          </div>
        {/each}
      </div>
    </section>
    
    <!-- System Health -->
    <section class="health-section">
      <h2>System Health</h2>
      <div class="health-grid">
        <div class="health-card">
          <div class="health-header">
            <h3>API Performance</h3>
            <div class="health-status healthy">
              <span class="status-dot"></span>
              Healthy
            </div>
          </div>
          <div class="health-metrics">
            <div class="health-metric">
              <span class="metric-label">Total API Calls</span>
              <span class="metric-value">{formatNumber(systemMetrics.apiCalls)}</span>
            </div>
            <div class="health-metric">
              <span class="metric-label">Average Response Time</span>
              <span class="metric-value">145ms</span>
            </div>
            <div class="health-metric">
              <span class="metric-label">Success Rate</span>
              <span class="metric-value" style="color: var(--success-color)">99.7%</span>
            </div>
          </div>
        </div>
        
        <div class="health-card">
          <div class="health-header">
            <h3>Processing Pipeline</h3>
            <div class="health-status healthy">
              <span class="status-dot"></span>
              Operational
            </div>
          </div>
          <div class="health-metrics">
            <div class="health-metric">
              <span class="metric-label">Queue Length</span>
              <span class="metric-value">{processingStats.videosInQueue}</span>
            </div>
            <div class="health-metric">
              <span class="metric-label">Processing Rate</span>
              <span class="metric-value">5.3 FPS</span>
            </div>
            <div class="health-metric">
              <span class="metric-label">Uptime</span>
              <span class="metric-value" style="color: var(--success-color)">99.9%</span>
            </div>
          </div>
        </div>
        
        <div class="health-card">
          <div class="health-header">
            <h3>Recognition Engine</h3>
            <div class="health-status healthy">
              <span class="status-dot"></span>
              Active
            </div>
          </div>
          <div class="health-metrics">
            <div class="health-metric">
              <span class="metric-label">Model Accuracy</span>
              <span class="metric-value" style="color: var(--success-color)">94.7%</span>
            </div>
            <div class="health-metric">
              <span class="metric-label">Detection Speed</span>
              <span class="metric-value">12ms/frame</span>
            </div>
            <div class="health-metric">
              <span class="metric-label">False Positive Rate</span>
              <span class="metric-value" style="color: var(--warning-color)">2.1%</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  {/if}
</div>

<style>
  .analytics-page {
    max-width: 100%;
  }
  
  .page-header {
    margin-bottom: 2rem;
  }
  
  .header-content {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 2rem;
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
  
  .time-range-selector {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-shrink: 0;
  }
  
  .time-range-selector label {
    font-weight: 600;
    color: var(--text-color);
  }
  
  .time-range-selector select {
    padding: 0.5rem 1rem;
    border: 1px solid var(--border-color);
    border-radius: 0.375rem;
    background-color: var(--surface-color);
    color: var(--text-color);
    font-size: 0.9rem;
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
  
  /* Section Styles */
  section {
    margin-bottom: 3rem;
  }
  
  section h2 {
    font-size: 1.75rem;
    font-weight: 600;
    margin-bottom: 1.5rem;
    color: var(--text-color);
  }
  
  /* Metrics Grid */
  .metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 1.5rem;
  }
  
  .metric-card {
    background-color: var(--surface-color);
    border: 1px solid var(--border-color);
    border-radius: 0.75rem;
    padding: 1.5rem;
    display: flex;
    align-items: center;
    gap: 1rem;
    box-shadow: var(--shadow);
    transition: transform 0.2s;
  }
  
  .metric-card:hover {
    transform: translateY(-2px);
  }
  
  .metric-icon {
    font-size: 2.5rem;
    flex-shrink: 0;
  }
  
  .metric-content {
    flex: 1;
  }
  
  .metric-value {
    font-size: 2rem;
    font-weight: 700;
    color: var(--primary-color);
    line-height: 1;
    margin-bottom: 0.25rem;
  }
  
  .metric-label {
    font-size: 0.9rem;
    color: var(--text-secondary);
    font-weight: 500;
  }
  
  /* Stats Grid */
  .stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
    gap: 2rem;
  }
  
  .stat-panel {
    background-color: var(--surface-color);
    border: 1px solid var(--border-color);
    border-radius: 0.75rem;
    padding: 1.5rem;
    box-shadow: var(--shadow);
  }
  
  .stat-panel h3 {
    margin: 0 0 1.5rem 0;
    font-size: 1.25rem;
    font-weight: 600;
    color: var(--text-color);
  }
  
  .stat-items {
    display: grid;
    gap: 1rem;
  }
  
  .stat-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.75rem 0;
    border-bottom: 1px solid var(--border-color);
  }
  
  .stat-item:last-child {
    border-bottom: none;
  }
  
  .stat-label {
    font-size: 0.9rem;
    color: var(--text-secondary);
  }
  
  .stat-value {
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--text-color);
  }
  
  /* Confidence Breakdown */
  .confidence-breakdown {
    display: grid;
    gap: 1rem;
  }
  
  .confidence-item {
    position: relative;
  }
  
  .confidence-bar {
    height: 1.5rem;
    border-radius: 0.75rem;
    margin-bottom: 0.5rem;
    transition: width 0.3s ease;
  }
  
  .confidence-bar.high {
    background-color: var(--success-color);
  }
  
  .confidence-bar.medium {
    background-color: var(--warning-color);
  }
  
  .confidence-bar.low {
    background-color: var(--error-color);
  }
  
  .confidence-details {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  
  .confidence-label {
    font-size: 0.9rem;
    color: var(--text-secondary);
  }
  
  .confidence-count {
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--text-color);
  }
  
  /* Chart Styles */
  .chart-container {
    background-color: var(--surface-color);
    border: 1px solid var(--border-color);
    border-radius: 0.75rem;
    padding: 1.5rem;
    box-shadow: var(--shadow);
  }
  
  .chart-header {
    margin-bottom: 2rem;
  }
  
  .chart-header h3 {
    margin: 0 0 0.25rem 0;
    font-size: 1.25rem;
    font-weight: 600;
  }
  
  .chart-subtitle {
    font-size: 0.9rem;
    color: var(--text-secondary);
  }
  
  .simple-chart {
    width: 100%;
  }
  
  .chart-grid {
    display: flex;
    align-items: flex-end;
    gap: 1rem;
    height: 200px;
    margin-bottom: 1rem;
    padding: 1rem 0;
    border-bottom: 1px solid var(--border-color);
  }
  
  .chart-day {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.5rem;
  }
  
  .chart-bars {
    display: flex;
    align-items: flex-end;
    gap: 0.25rem;
    height: 150px;
    width: 100%;
    justify-content: center;
  }
  
  .chart-bar {
    width: 1rem;
    min-height: 4px;
    border-radius: 0.125rem 0.125rem 0 0;
    transition: height 0.3s ease;
  }
  
  .chart-bar.recognitions {
    background-color: var(--primary-color);
  }
  
  .chart-bar.confidence {
    opacity: 0.8;
  }
  
  .chart-label {
    font-size: 0.75rem;
    color: var(--text-secondary);
    text-align: center;
  }
  
  .chart-legend {
    display: flex;
    justify-content: center;
    gap: 2rem;
    margin-top: 1rem;
  }
  
  .legend-item {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.9rem;
    color: var(--text-secondary);
  }
  
  .legend-color {
    width: 1rem;
    height: 0.75rem;
    border-radius: 0.125rem;
  }
  
  .legend-color.recognitions {
    background-color: var(--primary-color);
  }
  
  .legend-color.confidence {
    background: linear-gradient(90deg, var(--error-color), var(--warning-color), var(--success-color));
  }
  
  /* Top Performers */
  .performers-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
    gap: 1.5rem;
  }
  
  .performer-card {
    background-color: var(--surface-color);
    border: 1px solid var(--border-color);
    border-radius: 0.75rem;
    padding: 1.5rem;
    text-align: center;
    box-shadow: var(--shadow);
    transition: transform 0.2s, box-shadow 0.2s;
  }
  
  .performer-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px 0 rgb(0 0 0 / 0.15);
  }
  
  .performer-card.top-performer {
    border-color: var(--primary-color);
    background: linear-gradient(135deg, var(--surface-color), rgba(37, 99, 235, 0.05));
  }
  
  .performer-rank {
    font-size: 1.5rem;
    margin-bottom: 1rem;
  }
  
  .performer-avatar {
    width: 4rem;
    height: 4rem;
    border-radius: 50%;
    background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-weight: 600;
    font-size: 1.5rem;
    margin: 0 auto 1rem auto;
  }
  
  .performer-info h4 {
    margin: 0 0 0.25rem 0;
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--text-color);
  }
  
  .performer-info p {
    margin: 0 0 1rem 0;
    font-size: 0.9rem;
    color: var(--text-secondary);
  }
  
  .performer-stats {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
  }
  
  .stat {
    text-align: center;
  }
  
  .stat-number {
    display: block;
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--text-color);
    margin-bottom: 0.25rem;
  }
  
  .stat-text {
    font-size: 0.8rem;
    color: var(--text-secondary);
  }
  
  /* Health Section */
  .health-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 1.5rem;
  }
  
  .health-card {
    background-color: var(--surface-color);
    border: 1px solid var(--border-color);
    border-radius: 0.75rem;
    padding: 1.5rem;
    box-shadow: var(--shadow);
  }
  
  .health-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1.5rem;
  }
  
  .health-header h3 {
    margin: 0;
    font-size: 1.1rem;
    font-weight: 600;
  }
  
  .health-status {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.9rem;
    font-weight: 500;
  }
  
  .health-status.healthy {
    color: var(--success-color);
  }
  
  .status-dot {
    width: 0.5rem;
    height: 0.5rem;
    border-radius: 50%;
    background-color: currentColor;
  }
  
  .health-metrics {
    display: grid;
    gap: 1rem;
  }
  
  .health-metric {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  
  .health-metric .metric-label {
    font-size: 0.9rem;
    color: var(--text-secondary);
  }
  
  .health-metric .metric-value {
    font-size: 0.95rem;
    font-weight: 600;
    color: var(--text-color);
  }
  
  /* Mobile Responsiveness */
  @media (max-width: 768px) {
    .page-header h1 {
      font-size: 2rem;
    }
    
    .header-content {
      flex-direction: column;
      gap: 1rem;
    }
    
    .time-range-selector {
      align-self: stretch;
    }
    
    .time-range-selector select {
      flex: 1;
    }
    
    .metrics-grid {
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 1rem;
    }
    
    .metric-card {
      flex-direction: column;
      text-align: center;
      gap: 0.5rem;
    }
    
    .metric-icon {
      font-size: 2rem;
    }
    
    .metric-value {
      font-size: 1.5rem;
    }
    
    .stats-grid {
      grid-template-columns: 1fr;
      gap: 1rem;
    }
    
    .chart-grid {
      gap: 0.5rem;
      height: 150px;
    }
    
    .chart-bars {
      height: 100px;
    }
    
    .chart-bar {
      width: 0.75rem;
    }
    
    .performers-grid {
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 1rem;
    }
    
    .health-grid {
      grid-template-columns: 1fr;
      gap: 1rem;
    }
  }
  
  @media (max-width: 480px) {
    .page-header h1 {
      font-size: 1.75rem;
    }
    
    .metrics-grid {
      grid-template-columns: 1fr;
    }
    
    .chart-container {
      padding: 1rem;
    }
    
    .chart-legend {
      flex-direction: column;
      align-items: center;
      gap: 0.5rem;
    }
    
    .performers-grid {
      grid-template-columns: 1fr;
    }
    
    .performer-stats {
      grid-template-columns: 1fr;
    }
  }
  
  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }
</style>