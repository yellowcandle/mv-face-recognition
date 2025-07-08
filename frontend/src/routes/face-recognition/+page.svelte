<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { videoProcessingStore } from '$lib/stores/videoProcessing';
	import { contestantsStore } from '$lib/stores/contestants';
	import type { RecognitionResult } from '$lib/types/api';
	
	let selectedVideoId: string | null = null;
	let selectedContestantId: string | null = null;
	let filterConfidence = 0.5;
	
	// Reactive statements
	$: recognitionResults = $videoProcessingStore.recognitionResults;
	$: contestants = $contestantsStore.contestants;
	$: processingJobs = $videoProcessingStore.processingJobs;
	$: isLoading = $videoProcessingStore.isLoading;
	$: error = $videoProcessingStore.error;
	
	// Get video ID from URL params
	$: {
		const videoParam = $page.url.searchParams.get('video');
		if (videoParam && videoParam !== selectedVideoId) {
			selectedVideoId = videoParam;
			loadResults();
		}
	}
	
	// Filter results based on confidence threshold
	$: filteredResults = recognitionResults.filter(result => 
		result.confidence >= filterConfidence &&
		(!selectedVideoId || result.video_id === selectedVideoId) &&
		(!selectedContestantId || result.contestant_id === selectedContestantId)
	);
	
	// Group results by video
	$: resultsByVideo = filteredResults.reduce((acc, result) => {
		if (!acc[result.video_id]) {
			acc[result.video_id] = [];
		}
		acc[result.video_id].push(result);
		return acc;
	}, {} as Record<string, RecognitionResult[]>);
	
	// Group results by contestant
	$: resultsByContestant = filteredResults.reduce((acc, result) => {
		if (!acc[result.contestant_id]) {
			acc[result.contestant_id] = [];
		}
		acc[result.contestant_id].push(result);
		return acc;
	}, {} as Record<string, RecognitionResult[]>);
	
	function getContestantName(contestantId: string): string {
		const contestant = $contestantsStore.contestants.find(c => c.id === contestantId);
		return contestant?.name || `Contestant ${contestantId}`;
	}
	
	function formatTimestamp(timestamp: number): string {
		const minutes = Math.floor(timestamp / 60);
		const seconds = Math.floor(timestamp % 60);
		return `${minutes}:${seconds.toString().padStart(2, '0')}`;
	}
	
	function formatConfidence(confidence: number): string {
		return (confidence * 100).toFixed(1) + '%';
	}
	
	async function loadResults() {
		try {
			await videoProcessingStore.getRecognitionResults(selectedVideoId || undefined, selectedContestantId || undefined);
		} catch (err) {
			console.error('Failed to load recognition results:', err);
		}
	}
	
	function clearFilters() {
		selectedVideoId = null;
		selectedContestantId = null;
		filterConfidence = 0.5;
		loadResults();
	}
	
	onMount(async () => {
		await Promise.all([
			contestantsStore.loadContestants(),
			videoProcessingStore.getProcessingJobs(),
			loadResults()
		]);
	});
</script>

<svelte:head>
	<title>Face Recognition Results - MV Face Recognition</title>
</svelte:head>

<div class="face-recognition">
	<div class="page-header">
		<h1>Face Recognition Results</h1>
		<p>View and analyze face recognition results from processed videos</p>
	</div>

	{#if error}
		<div class="error-banner">
			<span class="error-icon">⚠️</span>
			<span>{error}</span>
			<button on:click={videoProcessingStore.clearError}>✕</button>
		</div>
	{/if}

	<!-- Filters -->
	<div class="filters-card">
		<div class="card-header">
			<h2>Filters</h2>
		</div>
		<div class="card-content">
			<div class="filters-grid">
				<div class="filter-group">
					<label for="video-filter">Video:</label>
					<select bind:value={selectedVideoId} id="video-filter" on:change={loadResults}>
						<option value={null}>All Videos</option>
						{#each processingJobs.filter(job => job.status === 'completed') as job}
							<option value={job.video_id}>Video {job.video_id}</option>
						{/each}
					</select>
				</div>

				<div class="filter-group">
					<label for="contestant-filter">Contestant:</label>
					<select bind:value={selectedContestantId} id="contestant-filter" on:change={loadResults}>
						<option value={null}>All Contestants</option>
						{#each contestants as contestant}
							<option value={contestant.id}>{contestant.name}</option>
						{/each}
					</select>
				</div>

				<div class="filter-group">
					<label for="confidence-filter">Minimum Confidence:</label>
					<div class="confidence-input">
						<input
							type="range"
							min="0"
							max="1"
							step="0.1"
							bind:value={filterConfidence}
							id="confidence-filter"
						/>
						<span class="confidence-value">{formatConfidence(filterConfidence)}</span>
					</div>
				</div>

				<div class="filter-actions">
					<button class="clear-filters-button" on:click={clearFilters}>
						Clear Filters
					</button>
					<button class="refresh-button" on:click={loadResults} disabled={isLoading}>
						{isLoading ? 'Loading...' : 'Refresh'}
					</button>
				</div>
			</div>
		</div>
	</div>

	<!-- Results Summary -->
	<div class="summary-cards">
		<div class="summary-card">
			<div class="summary-icon">🎯</div>
			<div class="summary-info">
				<div class="summary-value">{filteredResults.length}</div>
				<div class="summary-label">Total Detections</div>
			</div>
		</div>

		<div class="summary-card">
			<div class="summary-icon">👥</div>
			<div class="summary-info">
				<div class="summary-value">{Object.keys(resultsByContestant).length}</div>
				<div class="summary-label">Unique Contestants</div>
			</div>
		</div>

		<div class="summary-card">
			<div class="summary-icon">🎥</div>
			<div class="summary-info">
				<div class="summary-value">{Object.keys(resultsByVideo).length}</div>
				<div class="summary-label">Videos with Results</div>
			</div>
		</div>

		<div class="summary-card">
			<div class="summary-icon">📊</div>
			<div class="summary-info">
				<div class="summary-value">
					{filteredResults.length > 0 
						? formatConfidence(filteredResults.reduce((sum, r) => sum + r.confidence, 0) / filteredResults.length)
						: '0%'
					}
				</div>
				<div class="summary-label">Average Confidence</div>
			</div>
		</div>
	</div>

	<!-- Results List -->
	<div class="results-card">
		<div class="card-header">
			<h2>Recognition Results</h2>
		</div>
		<div class="card-content">
			{#if filteredResults.length > 0}
				<div class="results-list">
					{#each filteredResults as result}
						<div class="result-item">
							<div class="result-info">
								<div class="result-header">
									<div class="contestant-name">
										{getContestantName(result.contestant_id)}
									</div>
									<div class="confidence-badge" class:high-confidence={result.confidence >= 0.8}>
										{formatConfidence(result.confidence)}
									</div>
								</div>
								<div class="result-details">
									<div class="detail-item">
										<span class="detail-label">Video:</span>
										<span class="detail-value">{result.video_id}</span>
									</div>
									<div class="detail-item">
										<span class="detail-label">Timestamp:</span>
										<span class="detail-value">{formatTimestamp(result.timestamp)}</span>
									</div>
									<div class="detail-item">
										<span class="detail-label">Position:</span>
										<span class="detail-value">
											{result.bounding_box.x}, {result.bounding_box.y} 
											({result.bounding_box.width}×{result.bounding_box.height})
										</span>
									</div>
								</div>
							</div>
							<div class="result-actions">
								<button class="view-button">
									View Frame
								</button>
							</div>
						</div>
					{/each}
				</div>
			{:else}
				<div class="empty-state">
					<div class="empty-icon">🔍</div>
					<p>No recognition results found</p>
					<p class="empty-hint">
						{filteredResults.length === 0 && recognitionResults.length > 0 
							? 'Try adjusting your filters' 
							: 'Process some videos to see results here'
						}
					</p>
				</div>
			{/if}
		</div>
	</div>

	<!-- Results by Contestant -->
	{#if Object.keys(resultsByContestant).length > 0}
		<div class="breakdown-card">
			<div class="card-header">
				<h2>Results by Contestant</h2>
			</div>
			<div class="card-content">
				<div class="breakdown-list">
					{#each Object.entries(resultsByContestant) as [contestantId, results]}
						<div class="breakdown-item">
							<div class="breakdown-header">
								<div class="breakdown-name">{getContestantName(contestantId)}</div>
								<div class="breakdown-count">{results.length} detections</div>
							</div>
							<div class="breakdown-stats">
								<div class="stat-item">
									<span class="stat-label">Avg Confidence:</span>
									<span class="stat-value">
										{formatConfidence(results.reduce((sum, r) => sum + r.confidence, 0) / results.length)}
									</span>
								</div>
								<div class="stat-item">
									<span class="stat-label">Videos:</span>
									<span class="stat-value">
										{new Set(results.map(r => r.video_id)).size}
									</span>
								</div>
							</div>
						</div>
					{/each}
				</div>
			</div>
		</div>
	{/if}
</div>

<style>
	.face-recognition {
		max-width: 1200px;
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

	.error-banner {
		background-color: var(--error-color);
		color: white;
		padding: 16px;
		border-radius: 8px;
		margin-bottom: 24px;
		display: flex;
		align-items: center;
		gap: 12px;
	}

	.error-banner button {
		background: none;
		border: none;
		color: white;
		cursor: pointer;
		margin-left: auto;
	}

	.filters-card,
	.results-card,
	.breakdown-card {
		background-color: var(--surface-color);
		border-radius: 12px;
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
		margin-bottom: 24px;
		overflow: hidden;
	}

	.card-header {
		padding: 24px 24px 0;
	}

	.card-header h2 {
		font-size: 1.5rem;
		font-weight: 500;
		margin: 0;
		color: var(--text-primary);
	}

	.card-content {
		padding: 16px 24px 24px;
	}

	.filters-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
		gap: 16px;
		align-items: end;
	}

	.filter-group {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.filter-group label {
		font-weight: 500;
		color: var(--text-primary);
	}

	.filter-group select {
		padding: 8px 12px;
		border: 1px solid #ddd;
		border-radius: 6px;
		background-color: var(--surface-color);
		color: var(--text-primary);
	}

	.confidence-input {
		display: flex;
		align-items: center;
		gap: 12px;
	}

	.confidence-input input[type="range"] {
		flex: 1;
	}

	.confidence-value {
		font-weight: 500;
		color: var(--text-primary);
		min-width: 50px;
	}

	.filter-actions {
		display: flex;
		gap: 8px;
	}

	.clear-filters-button,
	.refresh-button {
		padding: 8px 16px;
		border: none;
		border-radius: 6px;
		cursor: pointer;
		font-size: 0.875rem;
	}

	.clear-filters-button {
		background-color: var(--secondary-color);
		color: white;
	}

	.refresh-button {
		background-color: var(--primary-color);
		color: white;
	}

	.refresh-button:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.summary-cards {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
		gap: 24px;
		margin-bottom: 32px;
	}

	.summary-card {
		background-color: var(--surface-color);
		border-radius: 12px;
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
		padding: 24px;
		display: flex;
		align-items: center;
		gap: 16px;
	}

	.summary-icon {
		font-size: 2.5rem;
	}

	.summary-value {
		font-size: 2rem;
		font-weight: 500;
		color: var(--text-primary);
	}

	.summary-label {
		color: var(--text-secondary);
		font-size: 0.875rem;
	}

	.results-list {
		display: flex;
		flex-direction: column;
		gap: 16px;
	}

	.result-item {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		padding: 16px;
		border: 1px solid rgba(var(--text-primary), 0.1);
		border-radius: 8px;
		background-color: var(--background-color);
	}

	.result-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 8px;
	}

	.contestant-name {
		font-weight: 500;
		color: var(--text-primary);
	}

	.confidence-badge {
		background-color: var(--warning-color);
		color: white;
		padding: 4px 8px;
		border-radius: 12px;
		font-size: 0.75rem;
		font-weight: 500;
	}

	.confidence-badge.high-confidence {
		background-color: var(--success-color);
	}

	.result-details {
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.detail-item {
		display: flex;
		gap: 8px;
		font-size: 0.875rem;
	}

	.detail-label {
		color: var(--text-secondary);
		min-width: 80px;
	}

	.detail-value {
		color: var(--text-primary);
	}

	.result-actions {
		display: flex;
		gap: 8px;
	}

	.view-button {
		background-color: var(--primary-color);
		color: white;
		border: none;
		padding: 6px 12px;
		border-radius: 4px;
		font-size: 0.875rem;
		cursor: pointer;
	}

	.breakdown-list {
		display: flex;
		flex-direction: column;
		gap: 16px;
	}

	.breakdown-item {
		padding: 16px;
		border: 1px solid rgba(var(--text-primary), 0.1);
		border-radius: 8px;
		background-color: var(--background-color);
	}

	.breakdown-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 8px;
	}

	.breakdown-name {
		font-weight: 500;
		color: var(--text-primary);
	}

	.breakdown-count {
		color: var(--text-secondary);
		font-size: 0.875rem;
	}

	.breakdown-stats {
		display: flex;
		gap: 24px;
	}

	.stat-item {
		display: flex;
		gap: 8px;
		font-size: 0.875rem;
	}

	.stat-label {
		color: var(--text-secondary);
	}

	.stat-value {
		color: var(--text-primary);
		font-weight: 500;
	}

	.empty-state {
		text-align: center;
		padding: 48px 24px;
		color: var(--text-secondary);
	}

	.empty-icon {
		font-size: 4rem;
		margin-bottom: 16px;
	}

	.empty-hint {
		font-size: 0.875rem;
		margin-top: 8px;
	}

	@media (max-width: 768px) {
		.face-recognition {
			padding: 16px;
		}

		.filters-grid {
			grid-template-columns: 1fr;
		}

		.summary-cards {
			grid-template-columns: repeat(2, 1fr);
		}

		.result-item {
			flex-direction: column;
			gap: 16px;
		}

		.result-actions {
			align-self: stretch;
		}

		.breakdown-stats {
			flex-direction: column;
			gap: 8px;
		}
	}
</style>