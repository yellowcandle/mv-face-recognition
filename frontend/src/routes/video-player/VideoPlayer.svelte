<script lang="ts">
	import { onMount, onDestroy, afterUpdate } from 'svelte';
	import { 
		currentVideo, 
		currentTime, 
		duration, 
		isPlaying, 
		volume, 
		isMuted,
		videoPlayerActions 
	} from '$lib/stores/videoPlayer';
	import FaceOverlay from './FaceOverlay.svelte';

	let videoElement: HTMLVideoElement;
	let videoContainer: HTMLDivElement;
	let isVideoLoaded = false;
	let isBuffering = false;
	let showControls = true;
	let controlsTimeout: ReturnType<typeof setTimeout>;
	let containerWidth = 0;
	let containerHeight = 0;

	// Format time for display (MM:SS or HH:MM:SS)
	function formatTime(seconds: number): string {
		const hrs = Math.floor(seconds / 3600);
		const mins = Math.floor((seconds % 3600) / 60);
		const secs = Math.floor(seconds % 60);
		
		if (hrs > 0) {
			return `${hrs}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
		}
		return `${mins}:${secs.toString().padStart(2, '0')}`;
	}

	// Handle video events
	function onLoadedData() {
		isVideoLoaded = true;
		videoPlayerActions.updateDuration(videoElement.duration);
	}

	function onTimeUpdate() {
		if (videoElement && !isNaN(videoElement.currentTime)) {
			videoPlayerActions.updateCurrentTime(videoElement.currentTime);
		}
	}

	function onPlay() {
		videoPlayerActions.setPlaying(true);
	}

	function onPause() {
		videoPlayerActions.setPlaying(false);
	}

	function onWaiting() {
		isBuffering = true;
	}

	function onCanPlay() {
		isBuffering = false;
	}

	function onVolumeChange() {
		if (videoElement) {
			videoPlayerActions.setVolume(videoElement.volume);
		}
	}

	// Control functions
	function togglePlayPause() {
		if (!videoElement || !isVideoLoaded) return;
		
		if ($isPlaying) {
			videoElement.pause();
		} else {
			videoElement.play();
		}
	}

	function seek(event: Event) {
		if (!videoElement || !isVideoLoaded) return;
		
		const target = event.target as HTMLInputElement;
		const time = parseFloat(target.value);
		videoElement.currentTime = time;
		videoPlayerActions.updateCurrentTime(time);
	}

	function changeVolume(event: Event) {
		if (!videoElement) return;
		
		const target = event.target as HTMLInputElement;
		const vol = parseFloat(target.value);
		videoElement.volume = vol;
		videoPlayerActions.setVolume(vol);
	}

	function toggleMute() {
		if (!videoElement) return;
		
		videoElement.muted = !videoElement.muted;
		videoPlayerActions.toggleMute();
	}

	function toggleFullscreen() {
		if (!videoElement) return;
		
		if (document.fullscreenElement) {
			document.exitFullscreen();
		} else {
			videoElement.requestFullscreen();
		}
	}

	// Keyboard controls
	function handleKeydown(event: KeyboardEvent) {
		if (!videoElement || !isVideoLoaded) return;
		
		switch (event.code) {
			case 'Space':
				event.preventDefault();
				togglePlayPause();
				break;
			case 'ArrowLeft':
				event.preventDefault();
				videoElement.currentTime = Math.max(0, videoElement.currentTime - 10);
				break;
			case 'ArrowRight':
				event.preventDefault();
				videoElement.currentTime = Math.min($duration, videoElement.currentTime + 10);
				break;
			case 'ArrowUp':
				event.preventDefault();
				videoElement.volume = Math.min(1, videoElement.volume + 0.1);
				break;
			case 'ArrowDown':
				event.preventDefault();
				videoElement.volume = Math.max(0, videoElement.volume - 0.1);
				break;
			case 'KeyM':
				event.preventDefault();
				toggleMute();
				break;
			case 'KeyF':
				event.preventDefault();
				toggleFullscreen();
				break;
		}
	}

	// Show/hide controls
	function showControlsTemporarily() {
		showControls = true;
		clearTimeout(controlsTimeout);
		controlsTimeout = setTimeout(() => {
			if ($isPlaying) {
				showControls = false;
			}
		}, 3000);
	}

	function onMouseMove() {
		showControlsTemporarily();
	}

	function onMouseLeave() {
		if ($isPlaying) {
			showControls = false;
		}
	}

	// Reactive statements
	$: if (videoElement && $volume !== undefined) {
		videoElement.volume = $volume;
	}

	$: if (videoElement && $isMuted !== undefined) {
		videoElement.muted = $isMuted;
	}

	// Listen for external seek requests (from face gallery)
	$: if (videoElement && $currentTime !== undefined && isVideoLoaded) {
		const timeDiff = Math.abs(videoElement.currentTime - $currentTime);
		if (timeDiff > 1) { // Only seek if difference is significant
			videoElement.currentTime = $currentTime;
		}
	}

	// Track container dimensions for overlay positioning
	let resizeObserver: ResizeObserver;

	function setupResizeObserver() {
		// Check if videoContainer exists and observer hasn't been set up yet
		if (typeof videoContainer !== 'undefined' && videoContainer && !resizeObserver) {
			resizeObserver = new ResizeObserver(entries => {
				for (const entry of entries) {
					containerWidth = entry.contentRect.width;
					containerHeight = entry.contentRect.height;
				}
			});
			resizeObserver.observe(videoContainer);
		}
	}

	afterUpdate(() => {
		setupResizeObserver();
	});

	onMount(() => {
		document.addEventListener('keydown', handleKeydown);

		return () => {
			document.removeEventListener('keydown', handleKeydown);
			clearTimeout(controlsTimeout);
			if (resizeObserver) {
				resizeObserver.disconnect();
			}
		};
	});

	onDestroy(() => {
		clearTimeout(controlsTimeout);
		if (resizeObserver) {
			resizeObserver.disconnect();
		}
	});
</script>

<div class="video-player" 
	 on:mousemove={onMouseMove} 
	 on:mouseleave={onMouseLeave}
	 role="application"
	 tabindex="0"
>
	{#if $currentVideo}
		<div class="video-container" bind:this={videoContainer}>
			<!-- Video Element -->
			<video
				bind:this={videoElement}
				class="video-element"
				src={$currentVideo.stream_url}
				on:loadeddata={onLoadedData}
				on:timeupdate={onTimeUpdate}
				on:play={onPlay}
				on:pause={onPause}
				on:waiting={onWaiting}
				on:canplay={onCanPlay}
				on:volumechange={onVolumeChange}
				preload="metadata"
			>
				<track kind="captions" />
				Your browser does not support the video tag.
			</video>

			<!-- Face Detection Overlay -->
			<FaceOverlay 
				{videoElement}
				{containerWidth}
				{containerHeight}
			/>

			<!-- Loading/Buffering Overlay -->
			{#if isBuffering || !isVideoLoaded}
				<div class="loading-overlay">
					<div class="loading-spinner"></div>
					<p>{isVideoLoaded ? 'Buffering...' : 'Loading video...'}</p>
				</div>
			{/if}

			<!-- Controls Overlay -->
			<div class="controls-overlay" class:visible={showControls || !$isPlaying}>
				<!-- Play/Pause Button Overlay -->
				<div class="play-overlay">
					<button 
						class="play-button-large" 
						on:click={togglePlayPause}
						disabled={!isVideoLoaded}
					>
						<span class="play-icon">
							{$isPlaying ? '⏸️' : '▶️'}
						</span>
					</button>
				</div>

				<!-- Bottom Controls -->
				<div class="controls-bar">
					<!-- Progress Bar -->
					<div class="progress-container">
						<input
							type="range"
							class="progress-bar"
							min="0"
							max={$duration || 0}
							value={$currentTime || 0}
							on:input={seek}
							disabled={!isVideoLoaded}
						/>
					</div>

					<!-- Control Buttons -->
					<div class="controls-row">
						<!-- Left Controls -->
						<div class="controls-left">
							<button 
								class="control-button" 
								on:click={togglePlayPause}
								disabled={!isVideoLoaded}
								title="Play/Pause (Space)"
							>
								{$isPlaying ? '⏸️' : '▶️'}
							</button>

							<div class="volume-controls">
								<button 
									class="control-button" 
									on:click={toggleMute}
									disabled={!isVideoLoaded}
									title="Mute/Unmute (M)"
								>
									{$isMuted || $volume === 0 ? '🔇' : $volume < 0.5 ? '🔉' : '🔊'}
								</button>
								
								<input
									type="range"
									class="volume-slider"
									min="0"
									max="1"
									step="0.1"
									value={$isMuted ? 0 : $volume}
									on:input={changeVolume}
									disabled={!isVideoLoaded}
								/>
							</div>

							<div class="time-display">
								<span class="current-time">{formatTime($currentTime || 0)}</span>
								<span class="time-separator">/</span>
								<span class="total-time">{formatTime($duration || 0)}</span>
							</div>
						</div>

						<!-- Right Controls -->
						<div class="controls-right">
							<button 
								class="control-button" 
								on:click={toggleFullscreen}
								disabled={!isVideoLoaded}
								title="Fullscreen (F)"
							>
								🔳
							</button>
						</div>
					</div>
				</div>
			</div>
		</div>
	{:else}
		<div class="no-video">
			<div class="no-video-content">
				<div class="no-video-icon">📺</div>
				<h3>No Video Selected</h3>
				<p>Select a video from the dropdown above to start watching.</p>
			</div>
		</div>
	{/if}
</div>

<style>
	.video-player {
		background-color: var(--surface-color);
		border-radius: 12px;
		overflow: hidden;
		box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
		position: relative;
		outline: none;
	}

	.video-container {
		position: relative;
		width: 100%;
		aspect-ratio: 16/9;
		background-color: #000;
		border-radius: 12px;
		overflow: hidden;
	}

	.video-element {
		width: 100%;
		height: 100%;
		object-fit: contain;
		background-color: #000;
	}

	.loading-overlay {
		position: absolute;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		background-color: rgba(0, 0, 0, 0.8);
		display: flex;
		flex-direction: column;
		justify-content: center;
		align-items: center;
		color: white;
		z-index: 10;
	}

	.loading-spinner {
		width: 48px;
		height: 48px;
		border: 4px solid rgba(255, 255, 255, 0.3);
		border-top: 4px solid white;
		border-radius: 50%;
		animation: spin 1s linear infinite;
		margin-bottom: 16px;
	}

	@keyframes spin {
		0% { transform: rotate(0deg); }
		100% { transform: rotate(360deg); }
	}

	.controls-overlay {
		position: absolute;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		background: linear-gradient(transparent 70%, rgba(0, 0, 0, 0.5));
		opacity: 0;
		transition: opacity 0.3s ease;
		z-index: 5;
	}

	.controls-overlay.visible {
		opacity: 1;
	}

	.play-overlay {
		display: flex;
		justify-content: center;
		align-items: center;
		height: 100%;
	}

	.play-button-large {
		background: rgba(0, 0, 0, 0.7);
		border: none;
		border-radius: 50%;
		width: 80px;
		height: 80px;
		cursor: pointer;
		transition: all 0.2s ease;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.play-button-large:hover:not(:disabled) {
		background: rgba(0, 0, 0, 0.9);
		transform: scale(1.1);
	}

	.play-button-large:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.play-icon {
		font-size: 2rem;
	}

	.controls-bar {
		position: absolute;
		bottom: 0;
		left: 0;
		right: 0;
		padding: 16px;
		color: white;
	}

	.progress-container {
		margin-bottom: 12px;
	}

	.progress-bar {
		width: 100%;
		height: 8px;
		background: rgba(255, 255, 255, 0.3);
		border-radius: 4px;
		appearance: none;
		cursor: pointer;
	}

	.progress-bar::-webkit-slider-thumb {
		appearance: none;
		width: 16px;
		height: 16px;
		border-radius: 50%;
		background: var(--primary-color);
		cursor: pointer;
	}

	.progress-bar::-moz-range-thumb {
		width: 16px;
		height: 16px;
		border-radius: 50%;
		background: var(--primary-color);
		cursor: pointer;
		border: none;
	}

	.controls-row {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.controls-left,
	.controls-right {
		display: flex;
		align-items: center;
		gap: 12px;
	}

	.control-button {
		background: none;
		border: none;
		color: white;
		font-size: 1.25rem;
		cursor: pointer;
		padding: 8px;
		border-radius: 4px;
		transition: background-color 0.2s ease;
	}

	.control-button:hover:not(:disabled) {
		background: rgba(255, 255, 255, 0.2);
	}

	.control-button:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.volume-controls {
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.volume-slider {
		width: 80px;
		height: 4px;
		background: rgba(255, 255, 255, 0.3);
		border-radius: 2px;
		appearance: none;
		cursor: pointer;
	}

	.volume-slider::-webkit-slider-thumb {
		appearance: none;
		width: 12px;
		height: 12px;
		border-radius: 50%;
		background: white;
		cursor: pointer;
	}

	.volume-slider::-moz-range-thumb {
		width: 12px;
		height: 12px;
		border-radius: 50%;
		background: white;
		cursor: pointer;
		border: none;
	}

	.time-display {
		font-size: 0.9rem;
		font-family: 'Courier New', monospace;
		color: rgba(255, 255, 255, 0.9);
	}

	.time-separator {
		margin: 0 4px;
	}

	.no-video {
		aspect-ratio: 16/9;
		display: flex;
		justify-content: center;
		align-items: center;
		background: linear-gradient(135deg, var(--surface-color) 0%, rgba(var(--primary-color), 0.1) 100%);
	}

	.no-video-content {
		text-align: center;
		color: var(--text-secondary);
	}

	.no-video-icon {
		font-size: 4rem;
		margin-bottom: 16px;
	}

	.no-video h3 {
		font-size: 1.5rem;
		margin: 0 0 8px 0;
		color: var(--text-primary);
	}

	.no-video p {
		margin: 0;
		font-size: 1rem;
	}

	/* Mobile Responsive */
	@media (max-width: 768px) {
		.controls-bar {
			padding: 12px;
		}

		.controls-left {
			gap: 8px;
		}

		.volume-controls {
			display: none; /* Hide volume controls on mobile */
		}

		.play-button-large {
			width: 60px;
			height: 60px;
		}

		.play-icon {
			font-size: 1.5rem;
		}

		.control-button {
			font-size: 1rem;
			padding: 6px;
		}

		.time-display {
			font-size: 0.8rem;
		}
	}
</style>