<script lang="ts">
	import { 
		currentMetadata, 
		currentTime,
		activeContestants,
		allContestants,
		selectedContestant,
		videoPlayerActions 
	} from '$lib/stores/videoPlayer';
	import type { ContestantInfo } from '$lib/stores/videoPlayer';

	let selectedFaceIndex = 0;
	let showPanel = true;

	// Get detailed face data for current timestamp
	$: faceDetails = getFaceDetails($currentMetadata, $currentTime, $activeContestants);

	function getFaceDetails(metadata: any, currentTime: number, activeContestants: any[]) {
		if (!metadata?.contestant_timeline || !activeContestants.length) {
			return [];
		}

		const tolerance = 1.0; // 1 second tolerance
		const details: Array<{
			contestant: string;
			confidence: number;
			bbox: [number, number, number, number];
			displayName: string;
			fullName: string;
			age: number;
			photo_url: string | null;
			timeline: any;
			timestamps: number[];
		}> = [];

		Object.entries(metadata.contestant_timeline).forEach(([name, timeline]: [string, any]) => {
			const appearances = timeline.frame_appearances || timeline.detailed_timeline || [];
			const relevantAppearances = (appearances || []).filter(
				(appearance: any) => Math.abs(appearance.timestamp - currentTime) <= tolerance
			);

			if (relevantAppearances.length > 0) {
				const bestAppearance = relevantAppearances.reduce((best: any, current: any) => 
					current.confidence > best.confidence ? current : best
				);

				const contestant = $allContestants.find(c => c.nickname === name);
				const timestamps = (appearances || []).map((a: any) => a.timestamp).slice(0, 5);

				details.push({
					contestant: name,
					confidence: bestAppearance.confidence,
					bbox: bestAppearance.bbox,
					displayName: contestant?.nickname || name,
					fullName: contestant?.name || '',
					age: contestant?.age || 0,
					photo_url: contestant?.photo_url || null,
					timeline,
					timestamps
				});
			}
		});

		return details.sort((a, b) => b.confidence - a.confidence);
	}

	// Navigate between faces
	function selectFace(index: number) {
		selectedFaceIndex = Math.max(0, Math.min(index, faceDetails.length - 1));
	}

	function nextFace() {
		selectFace(selectedFaceIndex + 1);
	}

	function prevFace() {
		selectFace(selectedFaceIndex - 1);
	}

	// Jump to specific timestamp
	function jumpToTimestamp(timestamp: number) {
		videoPlayerActions.updateCurrentTime(timestamp);
	}

	// Format confidence percentage
	function formatConfidence(confidence: number): string {
		return `${(confidence * 100).toFixed(1)}%`;
	}

	// Format time
	function formatTime(seconds: number): string {
		const mins = Math.floor(seconds / 60);
		const secs = Math.floor(seconds % 60);
		return `${mins}:${secs.toString().padStart(2, '0')}`;
	}

	// Get confidence color
	function getConfidenceColor(confidence: number): string {
		if (confidence >= 0.8) return '#4CAF50'; // Green
		if (confidence >= 0.6) return '#FF9800'; // Orange
		return '#F44336'; // Red
	}

	// Get confidence level text
	function getConfidenceLevel(confidence: number): string {
		if (confidence >= 0.9) return 'Excellent';
		if (confidence >= 0.8) return 'Very Good';
		if (confidence >= 0.7) return 'Good';
		if (confidence >= 0.6) return 'Fair';
		return 'Low';
	}

	// Reactive: update selected face when active contestants change
	$: if (faceDetails.length > 0 && selectedFaceIndex >= faceDetails.length) {
		selectedFaceIndex = 0;
	}

	$: selectedFace = faceDetails[selectedFaceIndex] || null;
</script>

{#if showPanel && faceDetails.length > 0}
	<div class="face-details-panel">
		<!-- Panel Header -->
		<div class="panel-header">
			<div class="header-left">
				<h3 class="panel-title">
					<span class="title-icon">🔍</span>
					Face Analysis
				</h3>
				<div class="face-counter">
					{selectedFaceIndex + 1} of {faceDetails.length}
				</div>
			</div>
			
			<div class="header-controls">
				{#if faceDetails.length > 1}
					<button class="nav-button" on:click={prevFace} disabled={selectedFaceIndex === 0}>
						←
					</button>
					<button class="nav-button" on:click={nextFace} disabled={selectedFaceIndex === faceDetails.length - 1}>
						→
					</button>
				{/if}
				<button class="close-button" on:click={() => showPanel = false}>
					✕
				</button>
			</div>
		</div>

		{#if selectedFace}
			<div class="face-content">
				<!-- Face Photo Section -->
				<div class="face-photo-section">
					<div class="photo-container">
						{#if selectedFace.photo_url}
							<img 
								src={selectedFace.photo_url} 
								alt={selectedFace.fullName}
								class="main-photo"
							/>
						{:else}
							<div class="photo-placeholder">
								<span class="placeholder-icon">👤</span>
							</div>
						{/if}
						
						<!-- Confidence overlay -->
						<div class="confidence-overlay">
							<div 
								class="confidence-ring"
								style="--confidence: {selectedFace.confidence}; --color: {getConfidenceColor(selectedFace.confidence)};"
							>
								<div class="confidence-value">
									{formatConfidence(selectedFace.confidence)}
								</div>
							</div>
						</div>
					</div>

					<!-- Confidence Details -->
					<div class="confidence-details">
						<div class="confidence-label">
							Recognition Confidence
						</div>
						<div 
							class="confidence-level"
							style="color: {getConfidenceColor(selectedFace.confidence)}"
						>
							{getConfidenceLevel(selectedFace.confidence)}
						</div>
						<div class="confidence-bar">
							<div 
								class="confidence-fill"
								style="width: {selectedFace.confidence * 100}%; background-color: {getConfidenceColor(selectedFace.confidence)};"
							></div>
						</div>
					</div>
				</div>

				<!-- Face Information -->
				<div class="face-info-section">
					<div class="contestant-info">
						<h4 class="contestant-name">{selectedFace.displayName}</h4>
						<p class="contestant-fullname">{selectedFace.fullName}</p>
						{#if selectedFace.age > 0}
							<p class="contestant-age">Age {selectedFace.age}</p>
						{/if}
					</div>

					<!-- Timeline Stats -->
					<div class="timeline-stats">
						<h5>Appearance Statistics</h5>
						<div class="stats-grid">
							<div class="stat-item">
								<span class="stat-label">Total Appearances</span>
								<span class="stat-value">{selectedFace.timeline.total_appearances}</span>
							</div>
							<div class="stat-item">
								<span class="stat-label">Average Confidence</span>
								<span class="stat-value">{formatConfidence(selectedFace.timeline.avg_confidence)}</span>
							</div>
							<div class="stat-item">
								<span class="stat-label">Max Confidence</span>
								<span class="stat-value">{formatConfidence(selectedFace.timeline.max_confidence)}</span>
							</div>
							<div class="stat-item">
								<span class="stat-label">Duration</span>
								<span class="stat-value">
									{formatTime(selectedFace.timeline.last_appearance_time - selectedFace.timeline.first_appearance_time)}
								</span>
							</div>
						</div>
					</div>

					<!-- Recent Timestamps -->
					<div class="recent-timestamps">
						<h5>Recent Appearances</h5>
						<div class="timestamps-list">
							{#each selectedFace.timestamps as timestamp}
								<button 
									class="timestamp-button"
									class:current={Math.abs(timestamp - $currentTime) < 1}
									on:click={() => jumpToTimestamp(timestamp)}
								>
									{formatTime(timestamp)}
								</button>
							{/each}
						</div>
					</div>

					<!-- Actions -->
					<div class="face-actions">
						<button 
							class="action-button primary"
							on:click={() => {
								const contestant = $allContestants.find(c => c.nickname === selectedFace.contestant);
								if (contestant) videoPlayerActions.selectContestant(contestant);
							}}
						>
							<span class="action-icon">👤</span>
							Select in Gallery
						</button>
						
						<button 
							class="action-button secondary"
							on:click={() => jumpToTimestamp(selectedFace.timeline.first_appearance_time)}
						>
							<span class="action-icon">⏭️</span>
							First Appearance
						</button>
					</div>
				</div>
			</div>
		{/if}
	</div>
{:else if !showPanel}
	<!-- Show Panel Button -->
	<button class="show-panel-button" on:click={() => showPanel = true}>
		<span class="button-icon">🔍</span>
		<span class="button-text">Face Details</span>
	</button>
{/if}

<style>
	.face-details-panel {
		background: rgba(255, 255, 255, 0.95);
		backdrop-filter: blur(10px);
		border: 1px solid rgba(0, 0, 0, 0.1);
		border-radius: 16px;
		box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
		padding: 20px;
		max-width: 400px;
		max-height: 80vh;
		overflow-y: auto;
		position: relative;
	}

	.panel-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 20px;
		padding-bottom: 16px;
		border-bottom: 1px solid rgba(0, 0, 0, 0.1);
	}

	.header-left {
		display: flex;
		align-items: center;
		gap: 12px;
	}

	.panel-title {
		margin: 0;
		font-size: 1.2rem;
		font-weight: 600;
		color: var(--text-primary);
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.title-icon {
		font-size: 1.1rem;
	}

	.face-counter {
		background: rgba(var(--primary-color), 0.1);
		color: var(--primary-color);
		padding: 4px 8px;
		border-radius: 12px;
		font-size: 0.8rem;
		font-weight: 500;
	}

	.header-controls {
		display: flex;
		align-items: center;
		gap: 6px;
	}

	.nav-button, .close-button {
		background: none;
		border: 1px solid rgba(0, 0, 0, 0.2);
		border-radius: 6px;
		width: 32px;
		height: 32px;
		display: flex;
		align-items: center;
		justify-content: center;
		cursor: pointer;
		font-size: 0.9rem;
		transition: all 0.2s ease;
	}

	.nav-button:hover:not(:disabled), .close-button:hover {
		background: rgba(0, 0, 0, 0.1);
	}

	.nav-button:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.face-content {
		display: flex;
		flex-direction: column;
		gap: 20px;
	}

	.face-photo-section {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 16px;
	}

	.photo-container {
		position: relative;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.main-photo {
		width: 120px;
		height: 120px;
		border-radius: 50%;
		object-fit: cover;
		border: 4px solid white;
		box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
	}

	.photo-placeholder {
		width: 120px;
		height: 120px;
		border-radius: 50%;
		background: linear-gradient(135deg, #f0f0f0, #e0e0e0);
		display: flex;
		align-items: center;
		justify-content: center;
		border: 4px solid white;
		box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
	}

	.placeholder-icon {
		font-size: 3rem;
		color: #999;
	}

	.confidence-overlay {
		position: absolute;
		top: -10px;
		right: -10px;
	}

	.confidence-ring {
		width: 50px;
		height: 50px;
		border-radius: 50%;
		background: conic-gradient(var(--color) calc(var(--confidence) * 360deg), rgba(0,0,0,0.1) 0deg);
		display: flex;
		align-items: center;
		justify-content: center;
		position: relative;
	}

	.confidence-ring::before {
		content: '';
		position: absolute;
		top: 4px;
		left: 4px;
		right: 4px;
		bottom: 4px;
		background: white;
		border-radius: 50%;
	}

	.confidence-value {
		position: relative;
		z-index: 1;
		font-size: 0.7rem;
		font-weight: 700;
		color: var(--color);
	}

	.confidence-details {
		text-align: center;
		width: 100%;
	}

	.confidence-label {
		font-size: 0.9rem;
		color: var(--text-secondary);
		margin-bottom: 4px;
	}

	.confidence-level {
		font-size: 1.1rem;
		font-weight: 600;
		margin-bottom: 8px;
	}

	.confidence-bar {
		width: 100%;
		height: 8px;
		background: rgba(0, 0, 0, 0.1);
		border-radius: 4px;
		overflow: hidden;
	}

	.confidence-fill {
		height: 100%;
		transition: width 0.5s ease;
		border-radius: 4px;
	}

	.face-info-section {
		display: flex;
		flex-direction: column;
		gap: 16px;
	}

	.contestant-info {
		text-align: center;
		padding: 16px;
		background: rgba(var(--primary-color), 0.05);
		border-radius: 12px;
	}

	.contestant-name {
		margin: 0 0 8px 0;
		font-size: 1.3rem;
		font-weight: 600;
		color: var(--text-primary);
	}

	.contestant-fullname {
		margin: 0 0 4px 0;
		font-size: 1rem;
		color: var(--text-secondary);
	}

	.contestant-age {
		margin: 0;
		font-size: 0.9rem;
		color: var(--text-secondary);
	}

	.timeline-stats h5, .recent-timestamps h5 {
		margin: 0 0 12px 0;
		font-size: 1rem;
		font-weight: 600;
		color: var(--text-primary);
	}

	.stats-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 12px;
	}

	.stat-item {
		background: rgba(0, 0, 0, 0.05);
		padding: 12px;
		border-radius: 8px;
		text-align: center;
	}

	.stat-label {
		display: block;
		font-size: 0.8rem;
		color: var(--text-secondary);
		margin-bottom: 4px;
	}

	.stat-value {
		display: block;
		font-size: 1.1rem;
		font-weight: 600;
		color: var(--text-primary);
	}

	.timestamps-list {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
	}

	.timestamp-button {
		background: rgba(var(--primary-color), 0.1);
		border: 1px solid rgba(var(--primary-color), 0.3);
		color: var(--primary-color);
		padding: 6px 10px;
		border-radius: 16px;
		font-size: 0.8rem;
		cursor: pointer;
		transition: all 0.2s ease;
	}

	.timestamp-button:hover {
		background: rgba(var(--primary-color), 0.2);
	}

	.timestamp-button.current {
		background: var(--primary-color);
		color: white;
		border-color: var(--primary-color);
	}

	.face-actions {
		display: flex;
		gap: 8px;
	}

	.action-button {
		flex: 1;
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 6px;
		padding: 12px;
		border: none;
		border-radius: 8px;
		font-size: 0.9rem;
		font-weight: 500;
		cursor: pointer;
		transition: all 0.2s ease;
	}

	.action-button.primary {
		background: var(--primary-color);
		color: white;
	}

	.action-button.primary:hover {
		background: color-mix(in srgb, var(--primary-color) 80%, black);
	}

	.action-button.secondary {
		background: rgba(0, 0, 0, 0.1);
		color: var(--text-primary);
	}

	.action-button.secondary:hover {
		background: rgba(0, 0, 0, 0.2);
	}

	.action-icon {
		font-size: 1rem;
	}

	.show-panel-button {
		display: flex;
		align-items: center;
		gap: 8px;
		background: rgba(var(--primary-color), 0.9);
		color: white;
		border: none;
		padding: 12px 16px;
		border-radius: 24px;
		font-size: 0.9rem;
		font-weight: 500;
		cursor: pointer;
		box-shadow: 0 4px 16px rgba(var(--primary-color), 0.3);
		transition: all 0.2s ease;
		backdrop-filter: blur(10px);
	}

	.show-panel-button:hover {
		transform: translateY(-2px);
		box-shadow: 0 6px 20px rgba(var(--primary-color), 0.4);
	}

	.button-icon {
		font-size: 1.1rem;
	}

	/* Mobile responsive */
	@media (max-width: 768px) {
		.face-details-panel {
			max-width: 100%;
			max-height: 70vh;
		}

		.main-photo, .photo-placeholder {
			width: 100px;
			height: 100px;
		}

		.stats-grid {
			grid-template-columns: 1fr;
		}

		.face-actions {
			flex-direction: column;
		}
	}
</style> 