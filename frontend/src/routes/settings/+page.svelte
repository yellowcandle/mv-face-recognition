<script lang="ts">
	import { onMount } from 'svelte';
	import { settings, updateSettings, loadSettings } from '$lib/stores/main';
	import type { AppSettings } from '$lib/types/api';
	
	let localSettings: AppSettings = {
		theme: 'auto',
		notifications: true,
		autoRefresh: true,
		refreshInterval: 30,
		maxConcurrentJobs: 3,
		videoQuality: 'medium',
		faceDetectionThreshold: 0.8
	};
	
	let isLoading = false;
	let isSaving = false;
	let saveMessage = '';
	
	// Reactive statement to sync with store
	$: if ($settings) {
		localSettings = { ...$settings };
	}
	
	async function handleSave() {
		try {
			isSaving = true;
			await updateSettings(localSettings);
			saveMessage = 'Settings saved successfully!';
			setTimeout(() => {
				saveMessage = '';
			}, 3000);
		} catch (error) {
			console.error('Failed to save settings:', error);
			saveMessage = 'Failed to save settings. Please try again.';
			setTimeout(() => {
				saveMessage = '';
			}, 3000);
		} finally {
			isSaving = false;
		}
	}
	
	function resetToDefaults() {
		localSettings = {
			theme: 'auto',
			notifications: true,
			autoRefresh: true,
			refreshInterval: 30,
			maxConcurrentJobs: 3,
			videoQuality: 'medium',
			faceDetectionThreshold: 0.8
		};
	}
	
	onMount(async () => {
		isLoading = true;
		try {
			await loadSettings();
		} catch (error) {
			console.error('Failed to load settings:', error);
		} finally {
			isLoading = false;
		}
	});
</script>

<svelte:head>
	<title>Settings - MV Face Recognition</title>
</svelte:head>

<div class="settings">
	<div class="page-header">
		<h1>Settings</h1>
		<p>Configure application preferences and system behavior</p>
	</div>

	{#if saveMessage}
		<div class="message-banner" class:success={saveMessage.includes('success')} class:error={saveMessage.includes('Failed')}>
			<span>{saveMessage}</span>
		</div>
	{/if}

	{#if isLoading}
		<div class="loading-state">
			<div class="loading-spinner"></div>
			<p>Loading settings...</p>
		</div>
	{:else}
		<div class="settings-grid">
			<!-- Appearance Settings -->
			<div class="settings-card">
				<div class="card-header">
					<h2>🎨 Appearance</h2>
				</div>
				<div class="card-content">
					<div class="setting-group">
						<label for="theme">Theme</label>
						<select bind:value={localSettings.theme} id="theme">
							<option value="light">Light</option>
							<option value="dark">Dark</option>
							<option value="auto">Auto (System)</option>
						</select>
						<div class="setting-description">
							Choose your preferred color theme. Auto will follow your system preference.
						</div>
					</div>
				</div>
			</div>

			<!-- Notification Settings -->
			<div class="settings-card">
				<div class="card-header">
					<h2>🔔 Notifications</h2>
				</div>
				<div class="card-content">
					<div class="setting-group">
						<label class="checkbox-label">
							<input type="checkbox" bind:checked={localSettings.notifications} />
							<span class="checkmark"></span>
							Enable notifications
						</label>
						<div class="setting-description">
							Receive notifications for processing job completions and system alerts.
						</div>
					</div>
				</div>
			</div>

			<!-- Auto-refresh Settings -->
			<div class="settings-card">
				<div class="card-header">
					<h2>🔄 Auto-refresh</h2>
				</div>
				<div class="card-content">
					<div class="setting-group">
						<label class="checkbox-label">
							<input type="checkbox" bind:checked={localSettings.autoRefresh} />
							<span class="checkmark"></span>
							Enable auto-refresh
						</label>
						<div class="setting-description">
							Automatically refresh data at regular intervals.
						</div>
					</div>

					{#if localSettings.autoRefresh}
						<div class="setting-group">
							<label for="refresh-interval">Refresh interval (seconds)</label>
							<div class="range-input">
								<input
									type="range"
									min="10"
									max="300"
									step="10"
									bind:value={localSettings.refreshInterval}
									id="refresh-interval"
								/>
								<span class="range-value">{localSettings.refreshInterval}s</span>
							</div>
							<div class="setting-description">
								How often to refresh data automatically.
							</div>
						</div>
					{/if}
				</div>
			</div>

			<!-- Processing Settings -->
			<div class="settings-card">
				<div class="card-header">
					<h2>⚙️ Processing</h2>
				</div>
				<div class="card-content">
					<div class="setting-group">
						<label for="max-jobs">Maximum concurrent jobs</label>
						<div class="range-input">
							<input
								type="range"
								min="1"
								max="10"
								step="1"
								bind:value={localSettings.maxConcurrentJobs}
								id="max-jobs"
							/>
							<span class="range-value">{localSettings.maxConcurrentJobs}</span>
						</div>
						<div class="setting-description">
							Maximum number of video processing jobs that can run simultaneously.
						</div>
					</div>

					<div class="setting-group">
						<label for="video-quality">Default video quality</label>
						<select bind:value={localSettings.videoQuality} id="video-quality">
							<option value="low">Low</option>
							<option value="medium">Medium</option>
							<option value="high">High</option>
						</select>
						<div class="setting-description">
							Default quality setting for video processing.
						</div>
					</div>

					<div class="setting-group">
						<label for="face-threshold">Face detection threshold</label>
						<div class="range-input">
							<input
								type="range"
								min="0.1"
								max="1.0"
								step="0.1"
								bind:value={localSettings.faceDetectionThreshold}
								id="face-threshold"
							/>
							<span class="range-value">{(localSettings.faceDetectionThreshold * 100).toFixed(0)}%</span>
						</div>
						<div class="setting-description">
							Minimum confidence threshold for face detection. Higher values mean more strict detection.
						</div>
					</div>
				</div>
			</div>

			<!-- System Information -->
			<div class="settings-card">
				<div class="card-header">
					<h2>ℹ️ System Information</h2>
				</div>
				<div class="card-content">
					<div class="info-grid">
						<div class="info-item">
							<div class="info-label">Frontend Version</div>
							<div class="info-value">1.0.0 (Svelte)</div>
						</div>
						<div class="info-item">
							<div class="info-label">Framework</div>
							<div class="info-value">SvelteKit</div>
						</div>
						<div class="info-item">
							<div class="info-label">Build Date</div>
							<div class="info-value">{new Date().toLocaleDateString()}</div>
						</div>
						<div class="info-item">
							<div class="info-label">Browser</div>
							<div class="info-value">{navigator.userAgent.split(' ')[0]}</div>
						</div>
					</div>
				</div>
			</div>
		</div>

		<!-- Action Buttons -->
		<div class="settings-actions">
			<button class="reset-button" on:click={resetToDefaults}>
				Reset to Defaults
			</button>
			<button class="save-button" on:click={handleSave} disabled={isSaving}>
				{isSaving ? 'Saving...' : 'Save Settings'}
			</button>
		</div>
	{/if}
</div>

<style>
	.settings {
		max-width: 1000px;
		margin: 0 auto;
		padding: 24px;
	}

	.page-header {
		margin-bottom: 32px;
	}

	.page-header h1 {
		font-size: 2.5rem;
		font-weight: 300;
		margin: 0 0 8px 0;
		color: var(--text-primary);
	}

	.page-header p {
		color: var(--text-secondary);
		margin: 0;
	}

	.message-banner {
		padding: 16px;
		border-radius: 8px;
		margin-bottom: 24px;
		text-align: center;
		font-weight: 500;
	}

	.message-banner.success {
		background-color: var(--success-color);
		color: white;
	}

	.message-banner.error {
		background-color: var(--error-color);
		color: white;
	}

	.loading-state {
		text-align: center;
		padding: 48px 24px;
		color: var(--text-secondary);
	}

	.loading-spinner {
		width: 40px;
		height: 40px;
		border: 4px solid rgba(var(--primary-color), 0.3);
		border-top: 4px solid var(--primary-color);
		border-radius: 50%;
		animation: spin 1s linear infinite;
		margin: 0 auto 16px;
	}

	@keyframes spin {
		0% { transform: rotate(0deg); }
		100% { transform: rotate(360deg); }
	}

	.settings-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
		gap: 24px;
		margin-bottom: 32px;
	}

	.settings-card {
		background-color: var(--surface-color);
		border-radius: 12px;
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
		overflow: hidden;
	}

	.card-header {
		padding: 24px 24px 0;
	}

	.card-header h2 {
		font-size: 1.25rem;
		font-weight: 500;
		margin: 0;
		color: var(--text-primary);
	}

	.card-content {
		padding: 16px 24px 24px;
	}

	.setting-group {
		margin-bottom: 24px;
	}

	.setting-group:last-child {
		margin-bottom: 0;
	}

	.setting-group label {
		display: block;
		font-weight: 500;
		color: var(--text-primary);
		margin-bottom: 8px;
	}

	.setting-group select {
		width: 100%;
		padding: 8px 12px;
		border: 1px solid #ddd;
		border-radius: 6px;
		background-color: var(--surface-color);
		color: var(--text-primary);
		font-size: 1rem;
	}

	.checkbox-label {
		display: flex !important;
		align-items: center;
		cursor: pointer;
		font-weight: 500 !important;
		margin-bottom: 8px !important;
	}

	.checkbox-label input[type="checkbox"] {
		display: none;
	}

	.checkmark {
		width: 20px;
		height: 20px;
		border: 2px solid #ddd;
		border-radius: 4px;
		margin-right: 12px;
		position: relative;
		transition: all 0.2s ease;
	}

	.checkbox-label input[type="checkbox"]:checked + .checkmark {
		background-color: var(--primary-color);
		border-color: var(--primary-color);
	}

	.checkbox-label input[type="checkbox"]:checked + .checkmark::after {
		content: '✓';
		position: absolute;
		top: 50%;
		left: 50%;
		transform: translate(-50%, -50%);
		color: white;
		font-size: 14px;
		font-weight: bold;
	}

	.range-input {
		display: flex;
		align-items: center;
		gap: 16px;
	}

	.range-input input[type="range"] {
		flex: 1;
		height: 6px;
		border-radius: 3px;
		background: #ddd;
		outline: none;
	}

	.range-value {
		font-weight: 500;
		color: var(--text-primary);
		min-width: 60px;
		text-align: right;
	}

	.setting-description {
		font-size: 0.875rem;
		color: var(--text-secondary);
		margin-top: 8px;
		line-height: 1.4;
	}

	.info-grid {
		display: grid;
		grid-template-columns: repeat(2, 1fr);
		gap: 16px;
	}

	.info-item {
		padding: 12px;
		background-color: var(--background-color);
		border-radius: 6px;
	}

	.info-label {
		font-size: 0.875rem;
		color: var(--text-secondary);
		margin-bottom: 4px;
	}

	.info-value {
		font-weight: 500;
		color: var(--text-primary);
	}

	.settings-actions {
		display: flex;
		justify-content: flex-end;
		gap: 16px;
		padding-top: 24px;
		border-top: 1px solid rgba(var(--text-primary), 0.1);
	}

	.reset-button,
	.save-button {
		padding: 12px 24px;
		border: none;
		border-radius: 6px;
		font-size: 1rem;
		cursor: pointer;
		transition: background-color 0.2s ease;
	}

	.reset-button {
		background-color: var(--secondary-color);
		color: white;
	}

	.reset-button:hover {
		background-color: #303030;
	}

	.save-button {
		background-color: var(--primary-color);
		color: white;
	}

	.save-button:hover:not(:disabled) {
		background-color: #1565c0;
	}

	.save-button:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	@media (max-width: 768px) {
		.settings {
			padding: 16px;
		}

		.settings-grid {
			grid-template-columns: 1fr;
		}

		.info-grid {
			grid-template-columns: 1fr;
		}

		.settings-actions {
			flex-direction: column;
		}

		.reset-button,
		.save-button {
			width: 100%;
		}
	}
</style>