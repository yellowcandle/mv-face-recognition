<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { initializeVideoPlayer, currentVideo, isLoading, error, videoPlayerActions } from '$lib/stores/videoPlayer';
	import VideoPlayer from './VideoPlayer.svelte';
	import VideoSelector from './VideoSelector.svelte';
	import FaceGallery from './FaceGallery.svelte';
	import VideoTimeline from './VideoTimeline.svelte';
	import FaceDetailsPanel from './FaceDetailsPanel.svelte';

	// Initialize video player on mount
	onMount(() => {
		initializeVideoPlayer();
	});

	// Clear error when component unmounts
	onDestroy(() => {
		videoPlayerActions.clearError();
	});
</script>

<svelte:head>
	<title>Video Player - MV Face Recognition</title>
</svelte:head>

<div class="video-player-page">
	<!-- Header Section -->
	<div class="page-header">
		<h1>Video Player</h1>
		<p class="page-description">
			Watch processed videos with real-time face recognition and contestant identification
		</p>
	</div>

	<!-- Video Selection -->
	<div class="video-selection">
		<VideoSelector />
	</div>

	<!-- Main Content -->
	{#if $currentVideo}
		<div class="main-content">
			<!-- Video Player Section -->
			<div class="video-section">
				<VideoPlayer />
				
				<!-- Timeline -->
				<div class="timeline-section">
					<VideoTimeline />
				</div>
			</div>

			<!-- Sidebar Section -->
			<div class="sidebar-section">
				<!-- Face Gallery -->
				<div class="gallery-container">
					<FaceGallery />
				</div>

				<!-- Face Details Panel -->
				<div class="details-container">
					<FaceDetailsPanel />
				</div>
			</div>
		</div>
	{:else}
		<div class="empty-state">
			{#if $isLoading}
				<div class="loading">
					<div class="loading-spinner"></div>
					<p>Loading videos...</p>
				</div>
			{:else}
				<div class="no-video">
					<div class="no-video-icon">🎬</div>
					<h3>Select a Video</h3>
					<p>Choose a processed video from the dropdown above to start watching with face recognition.</p>
				</div>
			{/if}
		</div>
	{/if}

	<!-- Error Display -->
	{#if $error}
		<div class="error-banner">
			<div class="error-content">
				<span class="error-icon">⚠️</span>
				<span class="error-message">{$error}</span>
				<button class="error-close" on:click={videoPlayerActions.clearError}>✕</button>
			</div>
		</div>
	{/if}
</div>

<style>
	.video-player-page {
		max-width: 1400px;
		margin: 0 auto;
		padding: 24px;
		min-height: calc(100vh - 120px);
	}

	.page-header {
		margin-bottom: 32px;
		text-align: center;
	}

	.page-header h1 {
		font-size: 2.5rem;
		font-weight: 300;
		margin: 0 0 12px 0;
		color: var(--text-primary);
	}

	.page-description {
		font-size: 1.1rem;
		color: var(--text-secondary);
		margin: 0;
		max-width: 600px;
		margin: 0 auto;
	}

	.video-selection {
		margin-bottom: 32px;
	}

	.main-content {
		display: grid;
		grid-template-columns: 1fr 450px;
		gap: 32px;
		align-items: start;
	}

	.video-section {
		display: flex;
		flex-direction: column;
		gap: 16px;
	}

	.timeline-section {
		background-color: var(--surface-color);
		border-radius: 8px;
		padding: 16px;
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
	}

	.sidebar-section {
		position: sticky;
		top: 24px;
		max-height: calc(100vh - 120px);
		display: flex;
		flex-direction: column;
		gap: 24px;
		overflow-y: auto;
	}

	.gallery-container {
		flex-shrink: 0;
	}

	.details-container {
		flex-shrink: 0;
	}

	.empty-state {
		display: flex;
		justify-content: center;
		align-items: center;
		min-height: 400px;
		background-color: var(--surface-color);
		border-radius: 12px;
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
	}

	.loading {
		text-align: center;
	}

	.loading-spinner {
		width: 48px;
		height: 48px;
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

	.no-video {
		text-align: center;
		padding: 48px;
		color: var(--text-secondary);
	}

	.no-video-icon {
		font-size: 4rem;
		margin-bottom: 24px;
	}

	.no-video h3 {
		font-size: 1.5rem;
		margin: 0 0 12px 0;
		color: var(--text-primary);
	}

	.no-video p {
		font-size: 1rem;
		margin: 0;
		max-width: 400px;
		margin: 0 auto;
	}

	.error-banner {
		position: fixed;
		top: 80px;
		left: 50%;
		transform: translateX(-50%);
		background-color: #d32f2f;
		color: white;
		padding: 16px 24px;
		border-radius: 8px;
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
		z-index: 1000;
		max-width: 500px;
		min-width: 300px;
	}

	.error-content {
		display: flex;
		align-items: center;
		gap: 12px;
	}

	.error-icon {
		font-size: 1.25rem;
	}

	.error-message {
		flex: 1;
		font-size: 0.95rem;
	}

	.error-close {
		background: none;
		border: none;
		color: white;
		font-size: 1.25rem;
		cursor: pointer;
		padding: 4px;
		border-radius: 4px;
		line-height: 1;
	}

	.error-close:hover {
		background-color: rgba(255, 255, 255, 0.1);
	}

	/* Enhanced Responsive Design */
	@media (max-width: 1400px) {
		.main-content {
			grid-template-columns: 1fr 420px;
		}
	}

	@media (max-width: 1200px) {
		.main-content {
			grid-template-columns: 1fr 380px;
		}

		.sidebar-section {
			gap: 16px;
		}
	}

	@media (max-width: 1024px) {
		.main-content {
			grid-template-columns: 1fr;
			gap: 24px;
		}

		.sidebar-section {
			position: static;
			max-height: none;
			order: -1;
			flex-direction: row;
			overflow-x: auto;
			gap: 20px;
		}

		.gallery-container,
		.details-container {
			min-width: 350px;
			flex-shrink: 0;
		}
	}

	@media (max-width: 768px) {
		.video-player-page {
			padding: 16px;
		}

		.page-header h1 {
			font-size: 2rem;
		}

		.page-description {
			font-size: 1rem;
		}

		.main-content {
			gap: 16px;
		}

		.sidebar-section {
			flex-direction: column;
			overflow-x: visible;
			gap: 16px;
		}

		.gallery-container,
		.details-container {
			min-width: auto;
		}

		.error-banner {
			left: 16px;
			right: 16px;
			transform: none;
			max-width: none;
		}
	}

	@media (max-width: 480px) {
		.video-player-page {
			padding: 12px;
		}

		.page-header {
			margin-bottom: 20px;
		}

		.page-header h1 {
			font-size: 1.75rem;
		}

		.page-description {
			font-size: 0.95rem;
		}

		.video-selection {
			margin-bottom: 20px;
		}

		.main-content {
			gap: 12px;
		}

		.sidebar-section {
			gap: 12px;
		}

		.timeline-section {
			padding: 12px;
		}
	}

	/* Landscape mobile optimization */
	@media (max-width: 768px) and (orientation: landscape) {
		.sidebar-section {
			flex-direction: row;
			overflow-x: auto;
			gap: 16px;
			max-height: 60vh;
		}

		.gallery-container,
		.details-container {
			min-width: 300px;
			max-height: 50vh;
			overflow-y: auto;
		}
	}

	/* Ultra-wide screen optimization */
	@media (min-width: 1600px) {
		.main-content {
			grid-template-columns: 1fr 500px;
		}

		.video-player-page {
			max-width: 1600px;
		}
	}
</style>