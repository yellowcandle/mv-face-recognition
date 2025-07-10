<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { 
		dashboardStats, 
		fetchSystemStatus, 
		isLoading, 
		isSystemHealthy,
		offlineMode 
	} from '$lib/stores/main';
	import { contestantsStore } from '$lib/stores/contestants';
	import { videoProcessingStore } from '$lib/stores/videoProcessing';
	
	// Auto-refresh interval
	let refreshInterval: number | null = null;
	
	// Reactive statements for computed values
	$: recentActivity = $videoProcessingStore.processingJobs
		.slice(0, 5) // Latest 5 jobs
		.map(job => ({
			id: job.job_id,
			videoName: `Video ${job.video_id}`,
			status: job.status,
			timestamp: job.created_at
		}));
	
	// Methods
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
			default: return 'ℹ️';
		}
	}
	
	function formatTime(timestamp: string): string {
		return new Date(timestamp).toLocaleString();
	}
	
	async function refreshDashboard() {
		// Skip refresh if in offline mode
		if ($offlineMode) {
			return;
		}
		
		try {
			await Promise.all([
				fetchSystemStatus(),
				contestantsStore.loadContestants(),
				videoProcessingStore.loadVideos(),
				videoProcessingStore.getProcessingJobs()
			]);
		} catch (error) {
			console.error('Failed to refresh dashboard:', error);
		}
	}
	
	onMount(async () => {
		// Load initial data
		await refreshDashboard();
		
		// Set up auto-refresh every 30 seconds
		refreshInterval = setInterval(refreshDashboard, 30000);
	});
	
	onDestroy(() => {
		if (refreshInterval) {
			clearInterval(refreshInterval);
		}
	});
</script>

<svelte:head>
	<title>Dashboard - MV Face Recognition</title>
</svelte:head>

<div class="dashboard">
	<div class="dashboard-header">
		<h1>Dashboard</h1>
		{#if $offlineMode}
			<div class="offline-notice">
				<div class="offline-icon">🔌</div>
				<div class="offline-text">
					<strong>Offline Mode</strong> - Showing demo data. Backend API is not available.
				</div>
			</div>
		{/if}
	</div></div>

	<!-- System Status Cards -->
	<div class="stats-grid">
		<div class="stat-card">
			<div class="stat-content">
				<div class="stat-icon" style="color: var(--primary-color);">👥</div>
				<div class="stat-info">
					<div class="stat-label">Contestants</div>
					<div class="stat-value">{$dashboardStats.contestants}</div>
				</div>
			</div>
		</div>

		<div class="stat-card">
			<div class="stat-content">
				<div class="stat-icon" style="color: var(--success-color);">🎥</div>
				<div class="stat-info">
					<div class="stat-label">Videos</div>
					<div class="stat-value">{$dashboardStats.videos}</div>
				</div>
			</div>
		</div>

		<div class="stat-card">
			<div class="stat-content">
				<div class="stat-icon" style="color: var(--warning-color);">⚙️</div>
				<div class="stat-info">
					<div class="stat-label">Processing</div>
					<div class="stat-value">{$dashboardStats.processingJobs}</div>
				</div>
			</div>
		</div>

		<div class="stat-card">
			<div class="stat-content">
				<div class="stat-icon" style="color: var(--info-color);">📊</div>
				<div class="stat-info">
					<div class="stat-label">Results</div>
					<div class="stat-value">
						{$videoProcessingStore.processingJobs.filter(job => job.status === 'completed').length}
					</div>
				</div>
			</div>
		</div>
	</div>

	<!-- Content Grid -->
	<div class="content-grid">
		<!-- Recent Activity -->
		<div class="content-card activity-card">
			<div class="card-header">
				<h2>Recent Processing Activity</h2>
			</div>
			<div class="card-content">
				{#if recentActivity.length > 0}
					<div class="activity-list">
						{#each recentActivity as activity}
							<div class="activity-item">
								<div class="activity-icon" style="color: {getStatusColor(activity.status)};">
									{getStatusIcon(activity.status)}
								</div>
								<div class="activity-info">
									<div class="activity-title">{activity.videoName}</div>
									<div class="activity-subtitle">
										{activity.status} • {formatTime(activity.timestamp)}
									</div>
								</div>
							</div>
						{/each}
					</div>
				{:else}
					<div class="empty-state">
						<div class="empty-icon">📝</div>
						<p>No recent activity</p>
					</div>
				{/if}
			</div>
		</div>

		<!-- System Status -->
		<div class="content-card status-card">
			<div class="card-header">
				<h2>System Status</h2>
			</div>
			<div class="card-content">
				<div class="status-list">
					<div class="status-item">
						<div class="status-icon" style="color: var(--success-color);">✅</div>
						<span>ChromaDB Connected</span>
					</div>
					<div class="status-item">
						<div class="status-icon" style="color: var(--success-color);">✅</div>
						<span>Face Detection Model Loaded</span>
					</div>
					<div class="status-item">
						<div class="status-icon" style="color: {$isSystemHealthy ? 'var(--success-color)' : 'var(--error-color)'};">
							{$isSystemHealthy ? '✅' : '❌'}
						</div>
						<span>All Services Running</span>
					</div>
				</div>
			</div>
		</div>
	</div>

	<!-- Quick Actions -->
	<div class="content-card actions-card">
		<div class="card-header">
			<h2>Quick Actions</h2>
		</div>
		<div class="card-content">
			<div class="actions-grid">
				<a href="/video-processing" class="action-button primary">
					<div class="action-icon">🎥</div>
					<span>Process Video</span>
				</a>
				<a href="/face-recognition" class="action-button secondary">
					<div class="action-icon">👤</div>
					<span>View Results</span>
				</a>
				<a href="/analytics" class="action-button success">
					<div class="action-icon">📊</div>
					<span>Analytics</span>
				</a>
				<a href="/settings" class="action-button warning">
					<div class="action-icon">⚙️</div>
					<span>Settings</span>
				</a>
			</div>
		</div>
	</div>
</div>

<style>
	.dashboard {
		max-width: 1200px;
		margin: 0 auto;
		padding: 24px;
	}

	.dashboard-header {
		margin-bottom: 32px;
	}

	.dashboard-header h1 {
		font-size: 2.5rem;
		font-weight: 300;
		margin: 0;
		color: var(--text-primary);
	}

	.stats-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
		gap: 24px;
		margin-bottom: 32px;
	}

	.stat-card {
		background-color: var(--surface-color);
		border-radius: 8px;
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
		overflow: hidden;
	}

	.stat-content {
		display: flex;
		align-items: center;
		padding: 24px;
	}

	.stat-icon {
		font-size: 2.5rem;
		margin-right: 16px;
	}

	.stat-info {
		flex: 1;
	}

	.stat-label {
		font-size: 1rem;
		color: var(--text-secondary);
		margin-bottom: 4px;
	}

	.stat-value {
		font-size: 2rem;
		font-weight: 500;
		color: var(--text-primary);
	}

	.content-grid {
		display: grid;
		grid-template-columns: 2fr 1fr;
		gap: 24px;
		margin-bottom: 32px;
	}

	.content-card {
		background-color: var(--surface-color);
		border-radius: 8px;
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

	.activity-list {
		display: flex;
		flex-direction: column;
		gap: 16px;
	}

	.activity-item {
		display: flex;
		align-items: center;
		padding: 12px 0;
		border-bottom: 1px solid rgba(var(--text-primary), 0.1);
	}

	.activity-item:last-child {
		border-bottom: none;
	}

	.activity-icon {
		font-size: 1.5rem;
		margin-right: 16px;
	}

	.activity-info {
		flex: 1;
	}

	.activity-title {
		font-weight: 500;
		color: var(--text-primary);
		margin-bottom: 4px;
	}

	.activity-subtitle {
		font-size: 0.875rem;
		color: var(--text-secondary);
	}

	.status-list {
		display: flex;
		flex-direction: column;
		gap: 16px;
	}

	.status-item {
		display: flex;
		align-items: center;
	}

	.status-icon {
		font-size: 1.25rem;
		margin-right: 12px;
	}

	.empty-state {
		text-align: center;
		padding: 48px 24px;
		color: var(--text-secondary);
	}

	.empty-icon {
		font-size: 3rem;
		margin-bottom: 16px;
	}

	.actions-card {
		grid-column: 1 / -1;
	}

	.actions-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
		gap: 16px;
	}

	.action-button {
		display: flex;
		flex-direction: column;
		align-items: center;
		padding: 24px;
		border-radius: 8px;
		text-decoration: none;
		transition: all 0.2s ease;
		border: 2px solid transparent;
	}

	.action-button:hover {
		transform: translateY(-2px);
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
	}

	.action-button.primary {
		background-color: var(--primary-color);
		color: white;
	}

	.action-button.secondary {
		background-color: var(--secondary-color);
		color: white;
	}

	.action-button.success {
		background-color: var(--success-color);
		color: white;
	}

	.action-button.warning {
		background-color: var(--warning-color);
		color: white;
	}

	.action-icon {
		font-size: 2rem;
		margin-bottom: 8px;
	}

	.offline-notice {
		display: flex;
		align-items: center;
		background-color: rgba(255, 170, 0, 0.1);
		border: 1px solid rgba(255, 170, 0, 0.3);
		border-radius: 8px;
		padding: 12px 16px;
		margin-top: 16px;
	}

	.offline-icon {
		font-size: 1.5rem;
		margin-right: 12px;
		color: #ffaa00;
	}

	.offline-text {
		color: var(--text-primary);
		font-size: 0.9rem;
	}

	@media (max-width: 768px) {
		.dashboard {
			padding: 16px;
		}

		.dashboard-header h1 {
			font-size: 2rem;
		}

		.stats-grid {
			grid-template-columns: 1fr;
			gap: 16px;
		}

		.content-grid {
			grid-template-columns: 1fr;
			gap: 16px;
		}

		.actions-grid {
			grid-template-columns: repeat(2, 1fr);
		}
	}
</style>