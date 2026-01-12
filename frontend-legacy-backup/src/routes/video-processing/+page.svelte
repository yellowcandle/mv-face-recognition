<script lang="ts">
	import { onMount } from 'svelte';
	import { videoProcessingStore, processingJobs, loading, error, type ProcessingJob } from '$lib/stores/videoProcessing';
	import { contestantsStore, contestants } from '$lib/stores/contestants';
	import { logger } from '$lib/utils/logger';
	
	let fileInput: HTMLInputElement;
	let selectedFile: File | null = null;
	let selectedContestants: string[] = [];
	let processingQuality: 'low' | 'medium' | 'high' = 'medium';
	let faceDetectionThreshold = 0.8;
	let uploadProgress = 0;
	
	// Initialize local variables with safe defaults
	let isUploading = false;
	let jobsList: ProcessingJob[] = [];
	let contestantsList: any[] = [];
	let errorMessage: string | null = null;
	let isPageLoading = true;
	let initializationError: string | null = null;
	
	// Reactive statements with comprehensive error handling
	$: {
		try {
			isUploading = $loading || false;
		} catch (e) {
			console.warn('Error accessing loading state:', e);
			isUploading = false;
		}
	}
	
	$: {
		try {
			const jobs = $processingJobs;
			jobsList = Array.isArray(jobs) ? jobs : [];
		} catch (e) {
			console.warn('Error accessing processing jobs:', e);
			jobsList = [];
		}
	}
	
	$: {
		try {
			const contestantsData = $contestants;
			contestantsList = Array.isArray(contestantsData) ? contestantsData : [];
		} catch (e) {
			console.warn('Error accessing contestants:', e);
			contestantsList = [];
		}
	}
	
	$: {
		try {
			errorMessage = $error;
		} catch (e) {
			console.warn('Error accessing error state:', e);
			errorMessage = null;
		}
	}
	
	function handleFileSelect(event: Event) {
		const target = event.target as HTMLInputElement;
		selectedFile = target.files?.[0] || null;
	}
	
	function toggleContestant(contestantId: string) {
		if (selectedContestants.includes(contestantId)) {
			selectedContestants = selectedContestants.filter(id => id !== contestantId);
		} else {
			selectedContestants = [...selectedContestants, contestantId];
		}
	}
	
	async function handleUploadAndProcess() {
		if (!selectedFile) return;
		
		try {
			// Simulate upload progress
			uploadProgress = 0;
			const progressInterval = setInterval(() => {
				uploadProgress += 10;
				if (uploadProgress >= 100) {
					clearInterval(progressInterval);
					uploadProgress = 0;
				}
			}, 200);
			
			// Mock processing - in real implementation, this would call the API
			
			// Reset form
			selectedFile = null;
			selectedContestants = [];
			if (fileInput) fileInput.value = '';
			
		} catch (err) {
			console.error('Failed to process video:', err);
		}
	}
	
	function getStatusColor(status: string): string {
		switch (status) {
			case 'completed': return 'var(--success-color)';
			case 'processing': return 'var(--warning-color)';
			case 'failed': return 'var(--error-color)';
			default: return 'var(--info-color)';
		}
	}
	
	function getStatusIcon(status: string): string {
		switch (status) {
			case 'completed': return '✅';
			case 'processing': return '⏳';
			case 'failed': return '❌';
			default: return '⏸️';
		}
	}
	
	function formatTime(timestamp: string): string {
		return new Date(timestamp).toLocaleString();
	}
	
	async function cancelJob(jobId: string) {
		try {
			// Mock cancel job - in real implementation, this would call the API
		} catch (err) {
			console.error('Failed to cancel job:', err);
		}
	}
	
	onMount(async () => {
		logger.info('Video Processing page initializing');

		// Set loading state
		isPageLoading = true;
		initializationError = null;

		try {
			// Initialize stores with empty arrays to prevent undefined errors
			logger.debug('Setting initial store values');
			processingJobs.set([]);
			contestants.set([]);

			logger.debug('Loading data from stores');
			await Promise.all([
				videoProcessingStore.getProcessingJobs().catch((err) => {
					logger.warn('Failed to load processing jobs', { error: err.message });
					return [];
				}),
				contestantsStore.loadContestants().catch((err) => {
					logger.warn('Failed to load contestants', { error: err.message });
					return [];
				})
			]);

			logger.info('Video Processing page initialized successfully');
		} catch (err) {
			console.error('Failed to initialize video processing page:', err);
			initializationError = 'Failed to load page data. Please try refreshing the page.';
		} finally {
			isPageLoading = false;
		}
	});
</script>

<svelte:head>
	<title>Video Processing - MV Face Recognition</title>
</svelte:head>

<div class="video-processing">
	<div class="page-header">
		<h1>Video Processing</h1>
		<p>Upload and process videos for face recognition</p>
	</div>

	{#if isPageLoading}
		<div class="loading-state">
			<div class="loading-spinner"></div>
			<p>Loading video processing interface...</p>
		</div>
	{:else if initializationError}
		<div class="error-banner">
			<span class="error-icon">⚠️</span>
			<span>{initializationError}</span>
			<button on:click={() => location.reload()}>Refresh Page</button>
		</div>
	{:else}
		{#if errorMessage}
			<div class="error-banner">
				<span class="error-icon">⚠️</span>
				<span>{errorMessage}</span>
				<button on:click={videoProcessingStore.clearError}>✕</button>
			</div>
		{/if}

	<!-- Upload Section -->
	<div class="upload-card">
		<div class="card-header">
			<h2>Upload Video</h2>
		</div>
		<div class="card-content">
			<div class="upload-area" class:has-file={selectedFile}>
				<input
					bind:this={fileInput}
					type="file"
					accept="video/*"
					on:change={handleFileSelect}
					class="file-input"
					id="video-upload"
				/>
				<label for="video-upload" class="upload-label">
					{#if selectedFile}
						<div class="file-info">
							<div class="file-icon">🎥</div>
							<div class="file-details">
								<div class="file-name">{selectedFile.name}</div>
								<div class="file-size">{(selectedFile.size / 1024 / 1024).toFixed(2)} MB</div>
							</div>
						</div>
					{:else}
						<div class="upload-placeholder">
							<div class="upload-icon">📁</div>
							<div class="upload-text">Click to select video file</div>
							<div class="upload-hint">Supports MP4, AVI, MOV formats</div>
						</div>
					{/if}
				</label>
			</div>

			{#if uploadProgress > 0 && uploadProgress < 100}
				<div class="progress-bar">
					<div class="progress-fill" style="width: {uploadProgress}%"></div>
				</div>
				<div class="progress-text">{uploadProgress}% uploaded</div>
			{/if}

			<!-- Processing Options -->
			{#if selectedFile}
				<div class="processing-options">
					<h3>Processing Options</h3>
					
					<div class="option-group">
						<label for="quality">Video Quality:</label>
						<select bind:value={processingQuality} id="quality">
							<option value="low">Low</option>
							<option value="medium">Medium</option>
							<option value="high">High</option>
						</select>
					</div>

					<div class="option-group">
						<label for="threshold">Face Detection Threshold:</label>
						<input
							type="range"
							min="0.1"
							max="1.0"
							step="0.1"
							bind:value={faceDetectionThreshold}
							id="threshold"
						/>
						<span class="threshold-value">{faceDetectionThreshold}</span>
					</div>

					{#if contestantsList && contestantsList.length > 0}
						<div class="option-group">
							<label>Target Contestants (optional):</label>
							<div class="contestants-grid">
								{#each contestantsList as contestant}
									<label class="contestant-checkbox">
										<input
											type="checkbox"
											checked={selectedContestants.includes(contestant.id)}
											on:change={() => toggleContestant(contestant.id)}
										/>
										<span>{contestant.name}</span>
									</label>
								{/each}
							</div>
						</div>
					{/if}

					<button
						class="process-button"
						on:click={handleUploadAndProcess}
						disabled={isUploading}
					>
						{isUploading ? 'Processing...' : 'Upload & Process Video'}
					</button>
				</div>
			{/if}
		</div>
	</div>

	<!-- Processing Jobs -->
	<div class="jobs-card">
		<div class="card-header">
			<h2>Processing Jobs</h2>
		</div>
		<div class="card-content">
			{#if jobsList && jobsList.length > 0}
				<div class="jobs-list">
					{#each jobsList as job}
						<div class="job-item">
							<div class="job-info">
								<div class="job-header">
									<div class="job-id">Job {job.job_id ? job.job_id.slice(0, 8) : 'Unknown'}</div>
									<div class="job-status" style="color: {getStatusColor(job.status)};">
										{getStatusIcon(job.status)} {job.status}
									</div>
								</div>
								<div class="job-details">
									<div>Video: {job.video_id}</div>
									<div>Created: {formatTime(job.created_at)}</div>
									{#if job.progress && job.progress > 0}
										<div>Progress: {job.progress}%</div>
									{/if}
									{#if job.error_message}
										<div class="error-message">Error: {job.error_message}</div>
									{/if}
								</div>
							</div>
							<div class="job-actions">
								{#if job.status === 'processing' || job.status === 'pending'}
									<button class="cancel-button" on:click={() => cancelJob(job.job_id)}>
										Cancel
									</button>
								{/if}
								{#if job.status === 'completed'}
									<a href="/face-recognition?video={job.video_id}" class="view-results-button">
										View Results
									</a>
								{/if}
							</div>
						</div>
					{/each}
				</div>
			{:else}
				<div class="empty-state">
					<div class="empty-icon">📹</div>
					<p>No processing jobs yet</p>
					<p class="empty-hint">Upload a video to get started</p>
				</div>
			{/if}
		</div>
	</div>
	{/if}
</div>

<style>
	.video-processing {
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

	.loading-state {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		padding: 64px 24px;
		color: var(--text-secondary);
	}

	.loading-spinner {
		width: 40px;
		height: 40px;
		border: 3px solid rgba(var(--primary-color), 0.3);
		border-top: 3px solid var(--primary-color);
		border-radius: 50%;
		animation: spin 1s linear infinite;
		margin-bottom: 16px;
	}

	@keyframes spin {
		0% { transform: rotate(0deg); }
		100% { transform: rotate(360deg); }
	}

	.upload-card,
	.jobs-card {
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

	.upload-area {
		border: 2px dashed #ccc;
		border-radius: 8px;
		padding: 40px;
		text-align: center;
		transition: all 0.2s ease;
		cursor: pointer;
	}

	.upload-area:hover {
		border-color: var(--primary-color);
		background-color: rgba(var(--primary-color), 0.05);
	}

	.upload-area.has-file {
		border-color: var(--success-color);
		background-color: rgba(var(--success-color), 0.05);
	}

	.file-input {
		display: none;
	}

	.upload-label {
		cursor: pointer;
		display: block;
	}

	.file-info {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 16px;
	}

	.file-icon {
		font-size: 3rem;
	}

	.file-name {
		font-weight: 500;
		color: var(--text-primary);
	}

	.file-size {
		color: var(--text-secondary);
		font-size: 0.875rem;
	}

	.upload-placeholder {
		color: var(--text-secondary);
	}

	.upload-icon {
		font-size: 4rem;
		margin-bottom: 16px;
	}

	.upload-text {
		font-size: 1.25rem;
		margin-bottom: 8px;
		color: var(--text-primary);
	}

	.upload-hint {
		font-size: 0.875rem;
	}

	.progress-bar {
		width: 100%;
		height: 8px;
		background-color: #f0f0f0;
		border-radius: 4px;
		overflow: hidden;
		margin: 16px 0 8px;
	}

	.progress-fill {
		height: 100%;
		background-color: var(--primary-color);
		transition: width 0.2s ease;
	}

	.progress-text {
		text-align: center;
		color: var(--text-secondary);
		font-size: 0.875rem;
	}

	.processing-options {
		margin-top: 24px;
		padding-top: 24px;
		border-top: 1px solid rgba(var(--text-primary), 0.1);
	}

	.processing-options h3 {
		margin: 0 0 16px 0;
		color: var(--text-primary);
	}

	.option-group {
		margin-bottom: 16px;
	}

	.option-group label {
		display: block;
		margin-bottom: 8px;
		font-weight: 500;
		color: var(--text-primary);
	}

	.option-group select,
	.option-group input[type="range"] {
		width: 100%;
		padding: 8px;
		border: 1px solid #ddd;
		border-radius: 4px;
		background-color: var(--surface-color);
		color: var(--text-primary);
	}

	.threshold-value {
		margin-left: 8px;
		font-weight: 500;
		color: var(--text-primary);
	}

	.contestants-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
		gap: 8px;
		margin-top: 8px;
	}

	.contestant-checkbox {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 8px;
		border-radius: 4px;
		cursor: pointer;
	}

	.contestant-checkbox:hover {
		background-color: rgba(var(--primary-color), 0.1);
	}

	.process-button {
		background-color: var(--primary-color);
		color: white;
		border: none;
		padding: 12px 24px;
		border-radius: 6px;
		font-size: 1rem;
		cursor: pointer;
		margin-top: 16px;
		transition: background-color 0.2s ease;
	}

	.process-button:hover:not(:disabled) {
		background-color: #1565c0;
	}

	.process-button:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.jobs-list {
		display: flex;
		flex-direction: column;
		gap: 16px;
	}

	.job-item {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		padding: 16px;
		border: 1px solid rgba(var(--text-primary), 0.1);
		border-radius: 8px;
		background-color: var(--background-color);
	}

	.job-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 8px;
	}

	.job-id {
		font-weight: 500;
		color: var(--text-primary);
	}

	.job-status {
		font-weight: 500;
	}

	.job-details {
		font-size: 0.875rem;
		color: var(--text-secondary);
		line-height: 1.4;
	}

	.error-message {
		color: var(--error-color);
		font-weight: 500;
	}

	.job-actions {
		display: flex;
		gap: 8px;
	}

	.cancel-button {
		background-color: var(--error-color);
		color: white;
		border: none;
		padding: 6px 12px;
		border-radius: 4px;
		font-size: 0.875rem;
		cursor: pointer;
	}

	.view-results-button {
		background-color: var(--success-color);
		color: white;
		text-decoration: none;
		padding: 6px 12px;
		border-radius: 4px;
		font-size: 0.875rem;
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
		.video-processing {
			padding: 16px;
		}

		.job-item {
			flex-direction: column;
			gap: 16px;
		}

		.job-actions {
			align-self: stretch;
		}

		.contestants-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
