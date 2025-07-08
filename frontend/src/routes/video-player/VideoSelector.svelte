<script lang="ts">
	import { availableVideos, currentVideo, videoPlayerActions, isLoading } from '$lib/stores/videoPlayer';
	import type { VideoInfo } from '$lib/stores/videoPlayer';

	// Format file size for display
	function formatFileSize(bytes: number): string {
		const units = ['B', 'KB', 'MB', 'GB'];
		let size = bytes;
		let unitIndex = 0;
		
		while (size >= 1024 && unitIndex < units.length - 1) {
			size /= 1024;
			unitIndex++;
		}
		
		return `${size.toFixed(1)} ${units[unitIndex]}`;
	}

	// Format date for display
	function formatDate(timestamp: number): string {
		return new Date(timestamp * 1000).toLocaleDateString();
	}

	// Handle video selection
	function onVideoSelect(event: Event) {
		const target = event.target as HTMLSelectElement;
		const selectedId = target.value;
		
		if (selectedId) {
			const video = $availableVideos.find(v => v.id === selectedId);
			if (video) {
				videoPlayerActions.selectVideo(video);
			}
		}
	}

	// Refresh video list
	function refreshVideos() {
		videoPlayerActions.loadVideos();
	}
</script>

<div class="video-selector">
	<div class="selector-header">
		<label for="video-select" class="selector-label">
			<span class="label-text">Select Video</span>
			<span class="label-count">
				{$availableVideos.length} video{$availableVideos.length !== 1 ? 's' : ''} available
			</span>
		</label>
		
		<button 
			class="refresh-button" 
			on:click={refreshVideos}
			disabled={$isLoading}
			title="Refresh video list"
		>
			<span class="refresh-icon" class:spinning={$isLoading}>🔄</span>
			Refresh
		</button>
	</div>

	<div class="selector-wrapper">
		<select 
			id="video-select"
			class="video-select"
			on:change={onVideoSelect}
			value={$currentVideo?.id || ''}
			disabled={$isLoading}
		>
			<option value="">Choose a video to watch...</option>
			{#each $availableVideos as video (video.id)}
				<option value={video.id}>
					{video.name}
				</option>
			{/each}
		</select>
		
		<div class="select-icon">▼</div>
	</div>

	<!-- Video Info Display -->
	{#if $currentVideo}
		<div class="video-info">
			<div class="video-info-content">
				<div class="video-info-main">
					<h3 class="video-title">{$currentVideo.name}</h3>
					<div class="video-details">
						<span class="detail-item">
							<span class="detail-icon">📁</span>
							{formatFileSize($currentVideo.size)}
						</span>
						<span class="detail-item">
							<span class="detail-icon">📅</span>
							{formatDate($currentVideo.created_at)}
						</span>
						<span class="detail-item">
							<span class="detail-icon">{$currentVideo.has_metadata ? '✅' : '❌'}</span>
							{$currentVideo.has_metadata ? 'Face data available' : 'No face data'}
						</span>
					</div>
				</div>
				
				<div class="video-actions">
					<button 
						class="action-button primary"
						on:click={() => videoPlayerActions.selectVideo($currentVideo)}
						title="Reload video"
					>
						<span class="action-icon">🔄</span>
						Reload
					</button>
				</div>
			</div>
		</div>
	{/if}
</div>

<style>
	.video-selector {
		background-color: var(--surface-color);
		border-radius: 12px;
		padding: 24px;
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
	}

	.selector-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-end;
		margin-bottom: 16px;
	}

	.selector-label {
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.label-text {
		font-size: 1.1rem;
		font-weight: 500;
		color: var(--text-primary);
	}

	.label-count {
		font-size: 0.9rem;
		color: var(--text-secondary);
	}

	.refresh-button {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 8px 16px;
		background-color: transparent;
		border: 2px solid var(--primary-color);
		color: var(--primary-color);
		border-radius: 6px;
		cursor: pointer;
		font-size: 0.9rem;
		transition: all 0.2s ease;
	}

	.refresh-button:hover:not(:disabled) {
		background-color: var(--primary-color);
		color: white;
	}

	.refresh-button:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.refresh-icon {
		font-size: 1rem;
		transition: transform 0.5s ease;
	}

	.refresh-icon.spinning {
		animation: spin 1s linear infinite;
	}

	@keyframes spin {
		from { transform: rotate(0deg); }
		to { transform: rotate(360deg); }
	}

	.selector-wrapper {
		position: relative;
		margin-bottom: 24px;
	}

	.video-select {
		width: 100%;
		padding: 16px 48px 16px 16px;
		font-size: 1rem;
		border: 2px solid rgba(var(--text-primary), 0.2);
		border-radius: 8px;
		background-color: var(--background-color);
		color: var(--text-primary);
		cursor: pointer;
		transition: all 0.2s ease;
		appearance: none;
	}

	.video-select:focus {
		outline: none;
		border-color: var(--primary-color);
		box-shadow: 0 0 0 3px rgba(var(--primary-color), 0.1);
	}

	.video-select:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.select-icon {
		position: absolute;
		right: 16px;
		top: 50%;
		transform: translateY(-50%);
		color: var(--text-secondary);
		pointer-events: none;
		font-size: 0.8rem;
	}

	.video-info {
		border-top: 1px solid rgba(var(--text-primary), 0.1);
		padding-top: 24px;
	}

	.video-info-content {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 24px;
	}

	.video-info-main {
		flex: 1;
	}

	.video-title {
		font-size: 1.3rem;
		font-weight: 500;
		margin: 0 0 12px 0;
		color: var(--text-primary);
		line-height: 1.4;
	}

	.video-details {
		display: flex;
		flex-wrap: wrap;
		gap: 16px;
	}

	.detail-item {
		display: flex;
		align-items: center;
		gap: 6px;
		font-size: 0.9rem;
		color: var(--text-secondary);
	}

	.detail-icon {
		font-size: 1rem;
	}

	.video-actions {
		display: flex;
		gap: 12px;
	}

	.action-button {
		display: flex;
		align-items: center;
		gap: 6px;
		padding: 10px 16px;
		border: none;
		border-radius: 6px;
		cursor: pointer;
		font-size: 0.9rem;
		transition: all 0.2s ease;
		white-space: nowrap;
	}

	.action-button.primary {
		background-color: var(--primary-color);
		color: white;
	}

	.action-button.primary:hover {
		background-color: rgba(var(--primary-color), 0.9);
		transform: translateY(-1px);
	}

	.action-icon {
		font-size: 1rem;
	}

	/* Mobile Responsive */
	@media (max-width: 768px) {
		.video-selector {
			padding: 16px;
		}

		.selector-header {
			flex-direction: column;
			align-items: flex-start;
			gap: 12px;
		}

		.video-info-content {
			flex-direction: column;
			gap: 16px;
		}

		.video-details {
			flex-direction: column;
			gap: 8px;
		}

		.video-actions {
			align-self: stretch;
		}

		.action-button {
			flex: 1;
			justify-content: center;
		}
	}
</style>