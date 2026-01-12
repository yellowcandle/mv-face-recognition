<script>
  import { onMount } from 'svelte';
  import { resultsStore } from '../stores/processing.js';
  import { processingUpdates } from '../stores/websocket.js';

  let currentFrameResults = [];
  let contestantAppearances = {};
  let allResults = [];
  let selectedTab = 'current';

  // Subscribe to stores
  resultsStore.subscribe(state => {
    currentFrameResults = state.currentFrameResults;
    contestantAppearances = state.contestantAppearances;
    allResults = state.allResults;
  });

  function getTopContestants(limit = 5) {
    return Object.entries(contestantAppearances || {})
      .sort(([,a], [,b]) => b.totalAppearances - a.totalAppearances)
      .slice(0, limit);
  }

  function getRecentResults(limit = 10) {
    return (allResults || []).slice(-limit).reverse();
  }

  function formatConfidence(confidence) {
    return (confidence * 100).toFixed(1) + '%';
  }

  function getBboxCenter(bbox) {
    if (!bbox || bbox.length !== 4) return { x: 0, y: 0 };
    const [x1, y1, x2, y2] = bbox;
    return {
      x: (x1 + x2) / 2,
      y: (y1 + y2) / 2
    };
  }

  function getBboxSize(bbox) {
    if (!bbox || bbox.length !== 4) return { width: 0, height: 0 };
    const [x1, y1, x2, y2] = bbox;
    return {
      width: x2 - x1,
      height: y2 - y1
    };
  }

  function exportResults() {
    if (allResults.length === 0) {
      alert('No results to export');
      return;
    }

    // Convert results to CSV format
    const csvHeader = 'Frame,Timestamp,Face_Count,Contestant_Name,Bbox_X1,Bbox_Y1,Bbox_X2,Bbox_Y2,Detection_Confidence,Recognition_Confidence,Matched\n';
    
    const csvRows = allResults.flatMap(frameResult => {
      if (frameResult.faces.length === 0) {
        return [`${frameResult.frameNumber},${frameResult.timestamp},0,,,,,,,false`];
      }
      
      return frameResult.faces.map(face => {
        const bbox = face.b || face.bbox || [];
        const name = face.n || face.contestant_name || '';
        const detectionConf = face.c || face.detection_confidence || 0;
        const recognitionConf = face.r || face.recognition_confidence || 0;
        const matched = face.m || face.matched || false;
        
        return [
          frameResult.frameNumber,
          frameResult.timestamp.toFixed(2),
          frameResult.faces.length,
          name,
          bbox[0] || '',
          bbox[1] || '',
          bbox[2] || '',
          bbox[3] || '',
          detectionConf.toFixed(3),
          recognitionConf.toFixed(3),
          matched
        ].join(',');
      });
    });

    const csvContent = csvHeader + csvRows.join('\n');
    
    // Download CSV file
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `face_recognition_results_${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  }
</script>

<div class="results-panel">
  <div class="results-header">
    <h3>📋 Results</h3>
    
    <div class="tab-buttons">
      <button 
        class="tab-button"
        class:active={selectedTab === 'current'}
        on:click={() => selectedTab = 'current'}
      >
        Current Frame
      </button>
      <button 
        class="tab-button"
        class:active={selectedTab === 'contestants'}
        on:click={() => selectedTab = 'contestants'}
      >
        Contestants
      </button>
      <button 
        class="tab-button"
        class:active={selectedTab === 'history'}
        on:click={() => selectedTab = 'history'}
      >
        History
      </button>
    </div>
  </div>

  <div class="results-content">
    {#if selectedTab === 'current'}
      <!-- Current Frame Results -->
      <div class="current-frame">
        {#if currentFrameResults.length > 0}
          <div class="face-grid">
            {#each currentFrameResults as face, index}
              <div class="face-card" class:matched={face.m || face.matched}>
                <div class="face-header">
                  <span class="face-id">Face #{index + 1}</span>
                  <span class="face-status" class:recognized={face.m || face.matched}>
                    {face.m || face.matched ? '✅' : '❓'}
                  </span>
                </div>
                
                <div class="face-details">
                  <div class="detail-row">
                    <span class="label">Name:</span>
                    <span class="value">
                      {face.n || face.contestant_name || 'Unknown'}
                    </span>
                  </div>
                  
                  <div class="detail-row">
                    <span class="label">Detection:</span>
                    <span class="value">
                      {formatConfidence(face.c || face.detection_confidence || 0)}
                    </span>
                  </div>
                  
                  {#if face.m || face.matched}
                    <div class="detail-row">
                      <span class="label">Recognition:</span>
                      <span class="value">
                        {formatConfidence(face.r || face.recognition_confidence || 0)}
                      </span>
                    </div>
                  {/if}
                  
                  <div class="detail-row">
                    <span class="label">Position:</span>
                    <span class="value">
                      {getBboxCenter(face.b || face.bbox).x.toFixed(0)}, {getBboxCenter(face.b || face.bbox).y.toFixed(0)}
                    </span>
                  </div>
                </div>
              </div>
            {/each}
          </div>
        {:else}
          <div class="no-results">
            <p>No faces detected in current frame</p>
          </div>
        {/if}
      </div>

    {:else if selectedTab === 'contestants'}
      <!-- Contestant Statistics -->
      <div class="contestants-list">
        {#if Object.keys(contestantAppearances).length > 0}
          <div class="export-button-container">
            <button class="export-button" on:click={exportResults}>
              📥 Export Results
            </button>
          </div>
          
          {#each getTopContestants(10) as [name, stats]}
            <div class="contestant-card">
              <div class="contestant-header">
                <h4>{name}</h4>
                <span class="appearance-count">{stats.totalAppearances} appearances</span>
              </div>
              
              <div class="contestant-stats">
                <div class="stat-row">
                  <span class="stat-label">Avg Confidence:</span>
                  <span class="stat-value">{formatConfidence(stats.avgConfidence)}</span>
                </div>
                
                <div class="stat-row">
                  <span class="stat-label">Max Confidence:</span>
                  <span class="stat-value">{formatConfidence(stats.maxConfidence)}</span>
                </div>
                
                <div class="confidence-bar">
                  <div 
                    class="confidence-fill" 
                    style="width: {stats.avgConfidence * 100}%"
                  ></div>
                </div>
              </div>
            </div>
          {/each}
        {:else}
          <div class="no-results">
            <p>No contestants detected yet</p>
          </div>
        {/if}
      </div>

    {:else if selectedTab === 'history'}
      <!-- Recent Results History -->
      <div class="results-history">
        {#if allResults.length > 0}
          <div class="history-stats">
            <span>Total frames processed: {allResults.length}</span>
          </div>
          
          <div class="history-list">
            {#each getRecentResults(20) as result}
              <div class="history-item">
                <div class="history-header">
                  <span class="frame-info">Frame {result.frameNumber}</span>
                  <span class="timestamp">{result.timestamp.toFixed(1)}s</span>
                  <span class="face-count">{result.faces.length} faces</span>
                </div>
                
                {#if result.faces.length > 0}
                  <div class="history-faces">
                    {#each result.faces as face}
                      <span 
                        class="history-face" 
                        class:recognized={face.m || face.matched}
                      >
                        {face.n || face.contestant_name || 'Unknown'}
                      </span>
                    {/each}
                  </div>
                {/if}
              </div>
            {/each}
          </div>
        {:else}
          <div class="no-results">
            <p>No processing history available</p>
          </div>
        {/if}
      </div>
    {/if}
  </div>
</div>

<style>
  .results-panel {
    height: 100%;
    display: flex;
    flex-direction: column;
  }

  .results-header {
    margin-bottom: 16px;
  }

  .results-header h3 {
    margin: 0 0 12px 0;
    color: #ffffff;
    font-size: 1.2rem;
    border-bottom: 2px solid #e17055;
    padding-bottom: 8px;
  }

  .tab-buttons {
    display: flex;
    gap: 4px;
  }

  .tab-button {
    padding: 8px 12px;
    background: rgba(255, 255, 255, 0.1);
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 4px;
    color: #b2bec3;
    font-size: 0.8rem;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .tab-button:hover {
    background: rgba(255, 255, 255, 0.2);
  }

  .tab-button.active {
    background: #e17055;
    color: #ffffff;
    border-color: #e17055;
  }

  .results-content {
    flex: 1;
    overflow-y: auto;
  }

  .face-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 12px;
  }

  .face-card {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 6px;
    padding: 12px;
    transition: border-color 0.3s ease;
  }

  .face-card.matched {
    border-color: #00b894;
    background: rgba(0, 184, 148, 0.1);
  }

  .face-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
  }

  .face-id {
    font-weight: 600;
    color: #ffffff;
    font-size: 0.9rem;
  }

  .face-status {
    font-size: 1.2rem;
  }

  .face-details {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .detail-row {
    display: flex;
    justify-content: space-between;
    font-size: 0.8rem;
  }

  .label {
    color: #636e72;
  }

  .value {
    color: #b2bec3;
    font-family: monospace;
  }

  .contestants-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .export-button-container {
    display: flex;
    justify-content: flex-end;
    margin-bottom: 8px;
  }

  .export-button {
    padding: 8px 16px;
    background: #74b9ff;
    border: none;
    border-radius: 4px;
    color: #ffffff;
    font-size: 0.8rem;
    cursor: pointer;
    transition: background 0.2s ease;
  }

  .export-button:hover {
    background: #0984e3;
  }

  .contestant-card {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 6px;
    padding: 12px;
  }

  .contestant-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
  }

  .contestant-header h4 {
    margin: 0;
    color: #ffffff;
    font-size: 0.9rem;
  }

  .appearance-count {
    color: #74b9ff;
    font-size: 0.8rem;
    font-weight: 600;
  }

  .contestant-stats {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .stat-row {
    display: flex;
    justify-content: space-between;
    font-size: 0.8rem;
  }

  .stat-label {
    color: #636e72;
  }

  .stat-value {
    color: #b2bec3;
    font-family: monospace;
  }

  .confidence-bar {
    height: 4px;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 2px;
    margin-top: 4px;
    overflow: hidden;
  }

  .confidence-fill {
    height: 100%;
    background: linear-gradient(90deg, #00b894 0%, #55efc4 100%);
    border-radius: 2px;
    transition: width 0.3s ease;
  }

  .results-history {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .history-stats {
    color: #b2bec3;
    font-size: 0.8rem;
    padding: 8px;
    background: rgba(255, 255, 255, 0.05);
    border-radius: 4px;
  }

  .history-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .history-item {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 4px;
    padding: 8px;
  }

  .history-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 4px;
    font-size: 0.8rem;
  }

  .frame-info {
    color: #ffffff;
    font-weight: 600;
  }

  .timestamp {
    color: #636e72;
    font-family: monospace;
  }

  .face-count {
    color: #74b9ff;
  }

  .history-faces {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }

  .history-face {
    padding: 2px 6px;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 3px;
    font-size: 0.7rem;
    color: #b2bec3;
  }

  .history-face.recognized {
    background: rgba(0, 184, 148, 0.3);
    color: #00b894;
  }

  .no-results {
    text-align: center;
    color: #636e72;
    padding: 24px;
    font-style: italic;
  }

  /* Responsive design */
  @media (max-width: 768px) {
    .tab-buttons {
      flex-direction: column;
    }

    .face-grid {
      gap: 8px;
    }

    .contestant-header {
      flex-direction: column;
      align-items: flex-start;
      gap: 4px;
    }

    .history-header {
      flex-direction: column;
      align-items: flex-start;
      gap: 2px;
    }
  }
</style>