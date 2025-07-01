<script lang="ts">
	import { onMount } from 'svelte';
	import { videoProcessingStore } from '$lib/stores/videoProcessing';
	import { contestantsStore } from '$lib/stores/contestants';
	import { dashboardStats } from '$lib/stores/main';
	
	// Reactive statements
	$: processingJobs = $videoProcessingStore.processingJobs;
	$: contestants = $contestantsStore.contestants;
	$: recognitionResults = $videoProcessingStore.recognitionResults;
	$: stats = $dashboardStats;
	
	// Computed analytics
	$: totalJobs = processingJobs.length;
	$: completedJobs = processingJobs.filter(job => job.status === 'completed').length;
	$: failedJobs = processingJobs.filter(job => job.status === 'failed').length;
	$: successRate = totalJobs > 0 ? (completedJobs / totalJobs * 100).toFixed(1) : '0';
	
	$: jobsByStatus = processingJobs.reduce((acc, job) => {
		acc[job.status] = (acc[job.status] || 0) + 1;
		return acc;
	}, {} as Record<string, number>);
	
	$: averageConfidence = recognitionResults.length > 0 
		? (recognitionResults.reduce((sum, r) => sum + r.confidence, 0) / recognitionResults.length * 100).toFixed(1)
		: '0';
	
	onMount(async () => {
		await Promise.all([
			videoProcessingStore.getProcessingJobs(),
			videoProcessingStore.getRecognitionResults(),
			contestantsStore.loadContestants()
		]);
	});
</script>

<svelte:head>
	<title>Analytics - MV Face Recognition</title>
</svelte:head>

<div class="analytics">
	<div class="page-header">
		<h1>Analytics Dashboard</h1>
		<p>Performance metrics and insights for the face recognition system</p>
	</div>

	<!-- Key Metrics -->
	<div class="metrics-grid">
		<div class="metric-card">
			<div class="metric-icon">🎯</div>
			<div class="metric-info">
				<div class="metric-value">{totalJobs}</div>
				<div class="metric-label">Total Processing Jobs</div>
			</div>
		</div>

		<div class="metric-card">
			<div class="metric-icon">✅</div>
			<div class="metric-info">
				<div class="metric-value">{successRate}%</div>
				<div class="metric-label">Success Rate</div>
			</div>
		</div>

		<div class="metric-card">
			<div class="metric-icon">🔍</div>
			<div class="metric-info">
				<div class="metric-value">{recognitionResults.length}</div>
				<div class="metric-label">Total Detections</div>
			</div>
		</div>

		<div class="metric-card">
			<div class="metric-icon">📊</div>
			<div class="metric-info">
				<div class="metric-value">{averageConfidence}%</div>
				<div class="metric-label">Avg Confidence</div>
			</div>
		</div>
	</div>

	<!-- Charts Section -->
	<div class="charts-grid">
		<!-- Job Status Distribution -->
		<div class="chart-card">
			<div class="card-header">
				<h2>Job Status Distribution</h2>
			</div>
			<div class="card-content">
				<div class="status-chart">
					{#each Object.entries(jobsByStatus) as [status, count]}
						<div class="status-item">
							<div class="status-label">{status}</div>
							<div class="status-bar">
								<div 
									class="status-fill {status}" 
									style="width: {totalJobs > 0 ? (count / totalJobs * 100) : 0}%"
								></div>
							</div>
							<div class="status-count">{count}</div>
						</div>
					{/each}
				</div>
			</div>
		</div>

		<!-- System Overview -->
		<div class="chart-card">
			<div class="card-header">
				<h2>System Overview</h2>
			</div>
			<div class="card-content">
				<div class="overview-stats">
					<div class="overview-item">
						<div class="overview-label">Contestants</div>
						<div class="overview-value">{stats.contestants}</div>
					</div>
					<div class="overview-item">
						<div class="overview-label">Videos Processed</div>
						<div class="overview-value">{stats.videos}</div>
					</div>
					<div class="overview-item">
						<div class="overview-label">Active Jobs</div>
						<div class="overview-value">{stats.processingJobs}</div>
					</div>
					<div class="overview-item">
						<div class="overview-label">System Health</div>
						<div class="overview-value {stats.systemHealthy ? 'healthy' : 'unhealthy'}">
							{stats.systemHealthy ? 'Healthy' : 'Issues'}
						</div>
					</div>
				</div>
			</div>
		</div>
	</div>

	<!-- Recent Activity -->
	<div class="activity-card">
		<div class="card-header">
			<h2>Recent Processing Activity</h2>
		</div>
		<div class="card-content">
			{#if processingJobs.length > 0}
				<div class="activity-timeline">
					{#each processingJobs.slice(0, 10) as job}
						<div class="timeline-item">
							<div class="timeline-marker {job.status}"></div>
							<div class="timeline-content">
								<div class="timeline-header">
									<span class="job-id">Job {job.job_id.slice(0, 8)}</span>
									<span class="job-time">{new Date(job.created_at).toLocaleString()}</span>
								</div>
								<div class="timeline-details">
									<span class="job-status {job.status}">{job.status}</span>
									{#if job.progress > 0}
										<span class="job-progress">{job.progress}% complete</span>
									{/if}
								</div>
							</div>
						</div>
					{/each}
				</div>
			{:else}
				<div class="empty-state">
					<div class="empty-icon">📈</div>
					<p>No processing activity yet</p>
				</div>
			{/if}
		</div>
	</div>
</div>

<style>
	.analytics {
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

	.metrics-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
		gap: 24px;
		margin-bottom: 32px;
	}

	.metric-card {
		background-color: var(--surface-color);
		border-radius: 12px;
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
		padding: 24px;
		display: flex;
		align-items: center;
		gap: 16px;
	}

	.metric-icon {
		font-size: 2.5rem;
	}

	.metric-value {
		font-size: 2rem;
		font-weight: 500;
		color: var(--text-primary);
	}

	.metric-label {
		color: var(--text-secondary);
		font-size: 0.875rem;
	}

	.charts-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
		gap: 24px;
		margin-bottom: 32px;
	}

	.chart-card,
	.activity-card {
		background-color: var(--surface-color);
		border-radius: 12px;
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
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

	.status-chart {
		display: flex;
		flex-direction: column;
		gap: 16px;
	}

	.status-item {
		display: grid;
		grid-template-columns: 100px 1fr auto;
		align-items: center;
		gap: 16px;
	}

	.status-label {
		font-weight: 500;
		color: var(--text-primary);
		text-transform: capitalize;
	}

	.status-bar {
		height: 20px;
		background-color: #f0f0f0;
		border-radius: 10px;
		overflow: hidden;
	}

	.status-fill {
		height: 100%;
		border-radius: 10px;
		transition: width 0.3s ease;
	}

	.status-fill.completed {
		background-color: var(--success-color);
	}

	.status-fill.processing {
		background-color: var(--warning-color);
	}

	.status-fill.failed {
		background-color: var(--error-color);
	}

	.status-fill.pending {
		background-color: var(--info-color);
	}

	.status-count {
		font-weight: 500;
		color: var(--text-primary);
		min-width: 30px;
		text-align: right;
	}

	.overview-stats {
		display: grid;
		grid-template-columns: repeat(2, 1fr);
		gap: 24px;
	}

	.overview-item {
		text-align: center;
		padding: 16px;
		border-radius: 8px;
		background-color: var(--background-color);
	}

	.overview-label {
		color: var(--text-secondary);
		font-size: 0.875rem;
		margin-bottom: 8px;
	}

	.overview-value {
		font-size: 1.5rem;
		font-weight: 500;
		color: var(--text-primary);
	}

	.overview-value.healthy {
		color: var(--success-color);
	}

	.overview-value.unhealthy {
		color: var(--error-color);
	}

	.activity-timeline {
		display: flex;
		flex-direction: column;
		gap: 16px;
	}

	.timeline-item {
		display: flex;
		align-items: flex-start;
		gap: 16px;
	}

	.timeline-marker {
		width: 12px;
		height: 12px;
		border-radius: 50%;
		margin-top: 6px;
		flex-shrink: 0;
	}

	.timeline-marker.completed {
		background-color: var(--success-color);
	}

	.timeline-marker.processing {
		background-color: var(--warning-color);
	}

	.timeline-marker.failed {
		background-color: var(--error-color);
	}

	.timeline-marker.pending {
		background-color: var(--info-color);
	}

	.timeline-content {
		flex: 1;
	}

	.timeline-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 4px;
	}

	.job-id {
		font-weight: 500;
		color: var(--text-primary);
	}

	.job-time {
		color: var(--text-secondary);
		font-size: 0.875rem;
	}

	.timeline-details {
		display: flex;
		gap: 16px;
		font-size: 0.875rem;
	}

	.job-status {
		font-weight: 500;
		text-transform: capitalize;
	}

	.job-status.completed {
		color: var(--success-color);
	}

	.job-status.processing {
		color: var(--warning-color);
	}

	.job-status.failed {
		color: var(--error-color);
	}

	.job-status.pending {
		color: var(--info-color);
	}

	.job-progress {
		color: var(--text-secondary);
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

	@media (max-width: 768px) {
		.analytics {
			padding: 16px;
		}

		.metrics-grid {
			grid-template-columns: repeat(2, 1fr);
		}

		.charts-grid {
			grid-template-columns: 1fr;
		}

		.overview-stats {
			grid-template-columns: 1fr;
		}

		.timeline-header {
			flex-direction: column;
			align-items: flex-start;
			gap: 4px;
		}
	}
</style>