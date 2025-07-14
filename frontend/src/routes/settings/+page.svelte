<script lang="ts">
  import { onMount } from 'svelte';
  
  let loading = true;
  let error = '';
  let saving = false;
  let saveSuccess = false;
  
  // Settings state
  let settings = {
    theme: 'auto',
    language: 'zh-TW',
    processing: {
      confidence_threshold: 0.7,
      max_faces_per_frame: 10,
      enable_tracking: true,
      processing_interval: 5,
      enable_interpolation: true,
      smoothing_window: 5
    },
    display: {
      show_confidence: true,
      show_bounding_boxes: true,
      overlay_opacity: 0.8,
      auto_play_videos: false,
      video_quality: 'auto'
    },
    notifications: {
      processing_complete: true,
      recognition_alerts: false,
      system_updates: true,
      email_notifications: false
    },
    privacy: {
      store_analytics: true,
      share_usage_data: false,
      log_retention_days: 30
    },
    performance: {
      cache_videos: true,
      preload_metadata: true,
      batch_size: 32,
      parallel_processing: true
    }
  };
  
  onMount(async () => {
    await loadSettings();
    loading = false;
  });
  
  async function loadSettings() {
    try {
      const response = await fetch('/api/settings');
      if (response.ok) {
        const data = await response.json();
        settings = { ...settings, ...data };
      }
    } catch (err) {
      console.error('Failed to load settings:', err);
      // Use default settings
    }
  }
  
  async function saveSettings() {
    saving = true;
    saveSuccess = false;
    
    try {
      const response = await fetch('/api/settings', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(settings)
      });
      
      if (response.ok) {
        saveSuccess = true;
        setTimeout(() => saveSuccess = false, 3000);
      } else {
        throw new Error('Failed to save settings');
      }
    } catch (err) {
      console.error('Failed to save settings:', err);
      error = 'Failed to save settings. Please try again.';
      setTimeout(() => error = '', 5000);
    } finally {
      saving = false;
    }
  }
  
  function resetToDefaults() {
    if (confirm('Are you sure you want to reset all settings to their default values?')) {
      settings = {
        theme: 'auto',
        language: 'zh-TW',
        processing: {
          confidence_threshold: 0.7,
          max_faces_per_frame: 10,
          enable_tracking: true,
          processing_interval: 5,
          enable_interpolation: true,
          smoothing_window: 5
        },
        display: {
          show_confidence: true,
          show_bounding_boxes: true,
          overlay_opacity: 0.8,
          auto_play_videos: false,
          video_quality: 'auto'
        },
        notifications: {
          processing_complete: true,
          recognition_alerts: false,
          system_updates: true,
          email_notifications: false
        },
        privacy: {
          store_analytics: true,
          share_usage_data: false,
          log_retention_days: 30
        },
        performance: {
          cache_videos: true,
          preload_metadata: true,
          batch_size: 32,
          parallel_processing: true
        }
      };
    }
  }
  
  function exportSettings() {
    const dataStr = JSON.stringify(settings, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(dataBlob);
    
    const link = document.createElement('a');
    link.href = url;
    link.download = 'mv-face-recognition-settings.json';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    URL.revokeObjectURL(url);
  }
  
  function importSettings(event: Event) {
    const target = event.target as HTMLInputElement;
    const file = target.files?.[0];
    
    if (file) {
      const reader = new FileReader();
      reader.onload = (e) => {
        try {
          const imported = JSON.parse(e.target?.result as string);
          settings = { ...settings, ...imported };
        } catch (err) {
          error = 'Invalid settings file format';
          setTimeout(() => error = '', 5000);
        }
      };
      reader.readAsText(file);
    }
  }
</script>

<svelte:head>
  <title>Settings - MV Face Recognition</title>
  <meta name="description" content="Configure system settings and preferences" />
</svelte:head>

<div class="settings-page">
  <header class="page-header">
    <h1>Settings</h1>
    <p>Configure system preferences and processing parameters</p>
  </header>
  
  {#if loading}
    <div class="loading">
      <div class="spinner"></div>
      <p>Loading settings...</p>
    </div>
  {:else}
    <div class="settings-container">
      <!-- Theme & Appearance -->
      <section class="settings-section">
        <div class="section-header">
          <h2>🎨 Theme & Appearance</h2>
          <p>Customize the look and feel of the application</p>
        </div>
        
        <div class="setting-groups">
          <div class="setting-group">
            <label for="theme">Theme</label>
            <select id="theme" bind:value={settings.theme}>
              <option value="light">Light</option>
              <option value="dark">Dark</option>
              <option value="auto">System Preference</option>
            </select>
            <span class="setting-description">Choose your preferred color scheme</span>
          </div>
          
          <div class="setting-group">
            <label for="language">Language</label>
            <select id="language" bind:value={settings.language}>
              <option value="en-US">English (US)</option>
              <option value="zh-TW">繁體中文 (Traditional Chinese)</option>
              <option value="zh-CN">简体中文 (Simplified Chinese)</option>
            </select>
            <span class="setting-description">Select your preferred language</span>
          </div>
        </div>
      </section>
      
      <!-- Processing Settings -->
      <section class="settings-section">
        <div class="section-header">
          <h2>⚙️ Processing Settings</h2>
          <p>Configure face recognition and video processing parameters</p>
        </div>
        
        <div class="setting-groups">
          <div class="setting-group">
            <label for="confidence-threshold">
              Confidence Threshold: {Math.round(settings.processing.confidence_threshold * 100)}%
            </label>
            <input
              id="confidence-threshold"
              type="range"
              min="0.3"
              max="0.95"
              step="0.05"
              bind:value={settings.processing.confidence_threshold}
            />
            <span class="setting-description">
              Minimum confidence score for face recognition results
            </span>
          </div>
          
          <div class="setting-group">
            <label for="max-faces">
              Max Faces per Frame: {settings.processing.max_faces_per_frame}
            </label>
            <input
              id="max-faces"
              type="range"
              min="1"
              max="20"
              step="1"
              bind:value={settings.processing.max_faces_per_frame}
            />
            <span class="setting-description">
              Maximum number of faces to detect in a single frame
            </span>
          </div>
          
          <div class="setting-group">
            <label for="processing-interval">
              Processing Interval: {settings.processing.processing_interval} frames
            </label>
            <input
              id="processing-interval"
              type="range"
              min="1"
              max="30"
              step="1"
              bind:value={settings.processing.processing_interval}
            />
            <span class="setting-description">
              Process every Nth frame (lower = more accurate, higher = faster)
            </span>
          </div>
          
          <div class="setting-group">
            <label for="smoothing-window">
              Smoothing Window: {settings.processing.smoothing_window} frames
            </label>
            <input
              id="smoothing-window"
              type="range"
              min="1"
              max="15"
              step="1"
              bind:value={settings.processing.smoothing_window}
            />
            <span class="setting-description">
              Number of frames to average for temporal smoothing
            </span>
          </div>
          
          <div class="setting-group checkbox-group">
            <label class="checkbox-label">
              <input
                type="checkbox"
                bind:checked={settings.processing.enable_tracking}
              />
              <span class="checkbox-custom"></span>
              Enable Face Tracking
            </label>
            <span class="setting-description">
              Track faces across frames for improved consistency
            </span>
          </div>
          
          <div class="setting-group checkbox-group">
            <label class="checkbox-label">
              <input
                type="checkbox"
                bind:checked={settings.processing.enable_interpolation}
              />
              <span class="checkbox-custom"></span>
              Enable Interpolation
            </label>
            <span class="setting-description">
              Interpolate face positions between detected frames
            </span>
          </div>
        </div>
      </section>
      
      <!-- Display Settings -->
      <section class="settings-section">
        <div class="section-header">
          <h2>📺 Display Settings</h2>
          <p>Control how videos and overlays are displayed</p>
        </div>
        
        <div class="setting-groups">
          <div class="setting-group">
            <label for="overlay-opacity">
              Overlay Opacity: {Math.round(settings.display.overlay_opacity * 100)}%
            </label>
            <input
              id="overlay-opacity"
              type="range"
              min="0.1"
              max="1"
              step="0.1"
              bind:value={settings.display.overlay_opacity}
            />
            <span class="setting-description">
              Transparency level for face recognition overlays
            </span>
          </div>
          
          <div class="setting-group">
            <label for="video-quality">Video Quality</label>
            <select id="video-quality" bind:value={settings.display.video_quality}>
              <option value="auto">Auto</option>
              <option value="720p">720p</option>
              <option value="1080p">1080p</option>
              <option value="4k">4K</option>
            </select>
            <span class="setting-description">
              Default video playback quality
            </span>
          </div>
          
          <div class="setting-group checkbox-group">
            <label class="checkbox-label">
              <input
                type="checkbox"
                bind:checked={settings.display.show_confidence}
              />
              <span class="checkbox-custom"></span>
              Show Confidence Scores
            </label>
            <span class="setting-description">
              Display confidence percentages on face overlays
            </span>
          </div>
          
          <div class="setting-group checkbox-group">
            <label class="checkbox-label">
              <input
                type="checkbox"
                bind:checked={settings.display.show_bounding_boxes}
              />
              <span class="checkbox-custom"></span>
              Show Bounding Boxes
            </label>
            <span class="setting-description">
              Draw bounding boxes around detected faces
            </span>
          </div>
          
          <div class="setting-group checkbox-group">
            <label class="checkbox-label">
              <input
                type="checkbox"
                bind:checked={settings.display.auto_play_videos}
              />
              <span class="checkbox-custom"></span>
              Auto-play Videos
            </label>
            <span class="setting-description">
              Automatically start video playback when loaded
            </span>
          </div>
        </div>
      </section>
      
      <!-- Notifications -->
      <section class="settings-section">
        <div class="section-header">
          <h2>🔔 Notifications</h2>
          <p>Manage notification preferences and alerts</p>
        </div>
        
        <div class="setting-groups">
          <div class="setting-group checkbox-group">
            <label class="checkbox-label">
              <input
                type="checkbox"
                bind:checked={settings.notifications.processing_complete}
              />
              <span class="checkbox-custom"></span>
              Processing Complete
            </label>
            <span class="setting-description">
              Notify when video processing is finished
            </span>
          </div>
          
          <div class="setting-group checkbox-group">
            <label class="checkbox-label">
              <input
                type="checkbox"
                bind:checked={settings.notifications.recognition_alerts}
              />
              <span class="checkbox-custom"></span>
              Recognition Alerts
            </label>
            <span class="setting-description">
              Alert when new faces are recognized
            </span>
          </div>
          
          <div class="setting-group checkbox-group">
            <label class="checkbox-label">
              <input
                type="checkbox"
                bind:checked={settings.notifications.system_updates}
              />
              <span class="checkbox-custom"></span>
              System Updates
            </label>
            <span class="setting-description">
              Notify about system updates and maintenance
            </span>
          </div>
          
          <div class="setting-group checkbox-group">
            <label class="checkbox-label">
              <input
                type="checkbox"
                bind:checked={settings.notifications.email_notifications}
              />
              <span class="checkbox-custom"></span>
              Email Notifications
            </label>
            <span class="setting-description">
              Send notifications via email
            </span>
          </div>
        </div>
      </section>
      
      <!-- Privacy Settings -->
      <section class="settings-section">
        <div class="section-header">
          <h2>🔒 Privacy & Security</h2>
          <p>Control data collection and retention policies</p>
        </div>
        
        <div class="setting-groups">
          <div class="setting-group">
            <label for="log-retention">
              Log Retention: {settings.privacy.log_retention_days} days
            </label>
            <input
              id="log-retention"
              type="range"
              min="7"
              max="365"
              step="7"
              bind:value={settings.privacy.log_retention_days}
            />
            <span class="setting-description">
              How long to keep system logs and analytics data
            </span>
          </div>
          
          <div class="setting-group checkbox-group">
            <label class="checkbox-label">
              <input
                type="checkbox"
                bind:checked={settings.privacy.store_analytics}
              />
              <span class="checkbox-custom"></span>
              Store Analytics Data
            </label>
            <span class="setting-description">
              Collect usage statistics for system improvement
            </span>
          </div>
          
          <div class="setting-group checkbox-group">
            <label class="checkbox-label">
              <input
                type="checkbox"
                bind:checked={settings.privacy.share_usage_data}
              />
              <span class="checkbox-custom"></span>
              Share Usage Data
            </label>
            <span class="setting-description">
              Share anonymized usage data for research purposes
            </span>
          </div>
        </div>
      </section>
      
      <!-- Performance Settings -->
      <section class="settings-section">
        <div class="section-header">
          <h2>⚡ Performance</h2>
          <p>Optimize system performance and resource usage</p>
        </div>
        
        <div class="setting-groups">
          <div class="setting-group">
            <label for="batch-size">
              Batch Size: {settings.performance.batch_size}
            </label>
            <input
              id="batch-size"
              type="range"
              min="8"
              max="128"
              step="8"
              bind:value={settings.performance.batch_size}
            />
            <span class="setting-description">
              Number of frames to process in each batch
            </span>
          </div>
          
          <div class="setting-group checkbox-group">
            <label class="checkbox-label">
              <input
                type="checkbox"
                bind:checked={settings.performance.cache_videos}
              />
              <span class="checkbox-custom"></span>
              Cache Videos
            </label>
            <span class="setting-description">
              Cache video files locally for faster playback
            </span>
          </div>
          
          <div class="setting-group checkbox-group">
            <label class="checkbox-label">
              <input
                type="checkbox"
                bind:checked={settings.performance.preload_metadata}
              />
              <span class="checkbox-custom"></span>
              Preload Metadata
            </label>
            <span class="setting-description">
              Load recognition metadata in advance
            </span>
          </div>
          
          <div class="setting-group checkbox-group">
            <label class="checkbox-label">
              <input
                type="checkbox"
                bind:checked={settings.performance.parallel_processing}
              />
              <span class="checkbox-custom"></span>
              Parallel Processing
            </label>
            <span class="setting-description">
              Use multiple CPU cores for processing
            </span>
          </div>
        </div>
      </section>
      
      <!-- Actions -->
      <section class="settings-actions">
        <div class="action-buttons">
          <button class="primary-btn" on:click={saveSettings} disabled={saving}>
            {#if saving}
              <span class="spinner-small"></span>
              Saving...
            {:else}
              💾 Save Settings
            {/if}
          </button>
          
          <button class="secondary-btn" on:click={resetToDefaults}>
            🔄 Reset to Defaults
          </button>
          
          <button class="secondary-btn" on:click={exportSettings}>
            📤 Export Settings
          </button>
          
          <label class="import-btn">
            📥 Import Settings
            <input
              type="file"
              accept=".json"
              on:change={importSettings}
              style="display: none;"
            />
          </label>
        </div>
        
        {#if saveSuccess}
          <div class="success-message">
            ✅ Settings saved successfully!
          </div>
        {/if}
        
        {#if error}
          <div class="error-message">
            ❌ {error}
          </div>
        {/if}
      </section>
    </div>
  {/if}
</div>

<style>
  .settings-page {
    max-width: 800px;
    margin: 0 auto;
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
  
  .loading {
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
  
  .settings-container {
    display: flex;
    flex-direction: column;
    gap: 2rem;
  }
  
  /* Settings Section */
  .settings-section {
    background-color: var(--surface-color);
    border: 1px solid var(--border-color);
    border-radius: 0.75rem;
    overflow: hidden;
    box-shadow: var(--shadow);
  }
  
  .section-header {
    padding: 1.5rem;
    background-color: var(--background-color);
    border-bottom: 1px solid var(--border-color);
  }
  
  .section-header h2 {
    margin: 0 0 0.5rem 0;
    font-size: 1.25rem;
    font-weight: 600;
    color: var(--text-color);
  }
  
  .section-header p {
    margin: 0;
    font-size: 0.9rem;
    color: var(--text-secondary);
  }
  
  .setting-groups {
    padding: 1.5rem;
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
  }
  
  /* Setting Groups */
  .setting-group {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  
  .setting-group label {
    font-size: 0.95rem;
    font-weight: 600;
    color: var(--text-color);
  }
  
  .setting-group input[type="range"],
  .setting-group select {
    padding: 0.5rem;
    border: 1px solid var(--border-color);
    border-radius: 0.375rem;
    background-color: var(--background-color);
    color: var(--text-color);
    font-size: 0.9rem;
  }
  
  .setting-group input[type="range"] {
    padding: 0;
    height: 0.5rem;
    background: var(--border-color);
    cursor: pointer;
  }
  
  .setting-group input[type="range"]::-webkit-slider-thumb {
    width: 1.25rem;
    height: 1.25rem;
    border-radius: 50%;
    background: var(--primary-color);
    cursor: pointer;
    border: none;
    box-shadow: var(--shadow);
  }
  
  .setting-group input[type="range"]::-moz-range-thumb {
    width: 1.25rem;
    height: 1.25rem;
    border-radius: 50%;
    background: var(--primary-color);
    cursor: pointer;
    border: none;
    box-shadow: var(--shadow);
  }
  
  .setting-description {
    font-size: 0.8rem;
    color: var(--text-secondary);
    line-height: 1.4;
  }
  
  /* Checkbox Groups */
  .checkbox-group {
    flex-direction: row;
    align-items: center;
    gap: 1rem;
  }
  
  .checkbox-label {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    cursor: pointer;
    font-size: 0.95rem;
    font-weight: 600;
    color: var(--text-color);
  }
  
  .checkbox-label input[type="checkbox"] {
    display: none;
  }
  
  .checkbox-custom {
    width: 1.25rem;
    height: 1.25rem;
    border: 2px solid var(--border-color);
    border-radius: 0.25rem;
    background-color: var(--background-color);
    position: relative;
    transition: all 0.2s;
    flex-shrink: 0;
  }
  
  .checkbox-label input[type="checkbox"]:checked + .checkbox-custom {
    background-color: var(--primary-color);
    border-color: var(--primary-color);
  }
  
  .checkbox-label input[type="checkbox"]:checked + .checkbox-custom::after {
    content: '✓';
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    color: white;
    font-size: 0.8rem;
    font-weight: bold;
  }
  
  .checkbox-group .setting-description {
    margin-left: auto;
    flex: 1;
  }
  
  /* Actions Section */
  .settings-actions {
    background-color: var(--surface-color);
    border: 1px solid var(--border-color);
    border-radius: 0.75rem;
    padding: 1.5rem;
    box-shadow: var(--shadow);
  }
  
  .action-buttons {
    display: flex;
    flex-wrap: wrap;
    gap: 1rem;
    margin-bottom: 1rem;
  }
  
  .primary-btn,
  .secondary-btn,
  .import-btn {
    padding: 0.75rem 1.5rem;
    border-radius: 0.5rem;
    font-size: 0.95rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    border: none;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    text-decoration: none;
  }
  
  .primary-btn {
    background-color: var(--primary-color);
    color: white;
  }
  
  .primary-btn:hover:not(:disabled) {
    background-color: var(--primary-hover);
    transform: translateY(-1px);
  }
  
  .primary-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
    transform: none;
  }
  
  .secondary-btn,
  .import-btn {
    background-color: var(--background-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
  }
  
  .secondary-btn:hover,
  .import-btn:hover {
    background-color: var(--border-color);
    transform: translateY(-1px);
  }
  
  .spinner-small {
    width: 1rem;
    height: 1rem;
    border: 2px solid rgba(255, 255, 255, 0.3);
    border-top: 2px solid white;
    border-radius: 50%;
    animation: spin 1s linear infinite;
  }
  
  .success-message {
    padding: 0.75rem 1rem;
    background-color: rgba(16, 185, 129, 0.1);
    border: 1px solid var(--success-color);
    border-radius: 0.5rem;
    color: var(--success-color);
    font-size: 0.9rem;
    font-weight: 500;
  }
  
  .error-message {
    padding: 0.75rem 1rem;
    background-color: rgba(239, 68, 68, 0.1);
    border: 1px solid var(--error-color);
    border-radius: 0.5rem;
    color: var(--error-color);
    font-size: 0.9rem;
    font-weight: 500;
  }
  
  /* Mobile Responsiveness */
  @media (max-width: 768px) {
    .settings-page {
      max-width: 100%;
    }
    
    .page-header h1 {
      font-size: 2rem;
    }
    
    .section-header {
      padding: 1rem;
    }
    
    .setting-groups {
      padding: 1rem;
      gap: 1rem;
    }
    
    .checkbox-group {
      flex-direction: column;
      align-items: flex-start;
      gap: 0.5rem;
    }
    
    .checkbox-group .setting-description {
      margin-left: 0;
    }
    
    .action-buttons {
      flex-direction: column;
    }
    
    .primary-btn,
    .secondary-btn,
    .import-btn {
      justify-content: center;
    }
  }
  
  @media (max-width: 480px) {
    .page-header h1 {
      font-size: 1.75rem;
    }
    
    .section-header h2 {
      font-size: 1.1rem;
    }
    
    .settings-actions {
      padding: 1rem;
    }
  }
  
  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }
</style>