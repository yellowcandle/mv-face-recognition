<script lang="ts">
	import { 
		allContestants, 
		currentMetadata, 
		activeContestants, 
		selectedContestant,
		videoPlayerActions 
	} from '$lib/stores/videoPlayer';
	import type { ContestantInfo } from '$lib/stores/videoPlayer';

	// Check if contestant is currently active
	function isContestantActive(contestant: ContestantInfo): boolean {
		return $activeContestants.some(active => active.contestant === contestant.nickname);
	}

	// Get contestant's confidence at current time
	function getCurrentConfidence(contestant: ContestantInfo): number {
		const active = $activeContestants.find(a => a.contestant === contestant.nickname);
		return active?.confidence || 0;
	}

	// Handle contestant selection
	function selectContestant(contestant: ContestantInfo) {
		if ($selectedContestant?.id === contestant.id) {
			videoPlayerActions.selectContestant(null);
		} else {
			videoPlayerActions.selectContestant(contestant);
		}
	}

	// Format confidence percentage
	function formatConfidence(confidence: number): string {
		return `${(confidence * 100).toFixed(0)}%`;
	}

	// Get confidence color
	function getConfidenceColor(confidence: number): string {
		if (confidence >= 0.8) return '#4CAF50'; // Green
		if (confidence >= 0.6) return '#FF9800'; // Orange
		return '#F44336'; // Red
	}

	// Filter contestants that appear in this video
	$: videoContestants = ($allContestants || []).filter(contestant => {
		return $currentMetadata?.contestant_timeline[contestant.nickname];
	});
</script>

<div class="face-gallery">
	<div class="gallery-header">
		<h2 class="gallery-title">
			<span class="title-icon">👥</span>
			Face Recognition
		</h2>
		
		<div class="detection-count">
			{#if $activeContestants.length > 0}
				<span class="count-active">{$activeContestants.length} detected</span>
			{:else}
				<span class="count-none">No faces</span>
			{/if}
		</div>
	</div>

	<!-- Currently Detected Faces -->
	{#if $activeContestants.length > 0}
		<div class="active-faces-panel">
			<h3 class="panel-title">Currently Detected</h3>
			
			<div class="active-faces-grid">
				{#each $activeContestants as active}
					{@const contestant = $allContestants.find(c => c.nickname === active.contestant)}
					{@const confidenceColor = getConfidenceColor(active.confidence)}
					{#if contestant}
						<div 
							class="active-face-card"
							on:click={() => selectContestant(contestant)}
							on:keydown={(e) => e.key === 'Enter' && selectContestant(contestant)}
							role="button"
							tabindex="0"
							style="border-color: {confidenceColor};"
						>
							<div class="face-photo">
								{#if contestant.photo_url}
									<img 
										src={contestant.photo_url} 
										alt={contestant.name}
										class="photo-image"
									/>
								{:else}
									<div class="photo-placeholder">
										<span class="placeholder-icon">👤</span>
									</div>
								{/if}
								
								<div class="confidence-badge" style="background-color: {confidenceColor};">
									{formatConfidence(active.confidence)}
								</div>
							</div>

							<div class="face-info">
								<h4 class="face-name">{contestant.nickname}</h4>
								<p class="face-fullname">{contestant.name}</p>
							</div>
						</div>
					{/if}
				{/each}
			</div>
		</div>
	{:else}
		<!-- No Active Faces State -->
		<div class="no-active-faces">
			<div class="no-faces-icon">👤</div>
			<p>No faces detected at current time</p>
		</div>
	{/if}

	<!-- All Contestants in Video -->
	{#if videoContestants.length > 0}
		<div class="contestants-panel">
			<h3 class="panel-title">All Contestants ({videoContestants.length})</h3>
			
			<div class="contestants-list">
				{#each videoContestants as contestant}
					{@const isActive = isContestantActive(contestant)}
					{@const isSelected = $selectedContestant?.id === contestant.id}
					{@const currentConfidence = getCurrentConfidence(contestant)}
					
					<div 
						class="contestant-card"
						class:active={isActive}
						class:selected={isSelected}
						on:click={() => selectContestant(contestant)}
						on:keydown={(e) => e.key === 'Enter' && selectContestant(contestant)}
						role="button"
						tabindex="0"
					>
						<div class="contestant-photo">
							{#if contestant.photo_url}
								<img 
									src={contestant.photo_url} 
									alt={contestant.name}
									class="photo-image"
									loading="lazy"
								/>
							{:else}
								<div class="photo-placeholder">
									<span class="placeholder-icon">👤</span>
								</div>
							{/if}
							
							{#if isActive}
								<div class="active-indicator">
									<span class="active-dot"></span>
								</div>
							{/if}
						</div>

						<div class="contestant-info">
							<h4 class="contestant-name">{contestant.nickname}</h4>
							<p class="contestant-fullname">{contestant.name}</p>
							{#if isActive}
								<span class="confidence-text" style="color: {getConfidenceColor(currentConfidence)};">
									{formatConfidence(currentConfidence)}
								</span>
							{/if}
						</div>
					</div>
				{/each}
			</div>
		</div>
	{/if}
</div>

<style>
	.face-gallery {
		background-color: #ffffff;
		border-radius: 12px;
		padding: 20px;
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
		height: fit-content;
	}

	.gallery-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 20px;
		padding-bottom: 16px;
		border-bottom: 1px solid #e0e0e0;
	}

	.gallery-title {
		font-size: 1.25rem;
		font-weight: 600;
		margin: 0;
		color: #333;
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.title-icon {
		font-size: 1.1rem;
	}

	.detection-count {
		font-size: 0.9rem;
		font-weight: 500;
	}

	.count-active {
		color: #4CAF50;
	}

	.count-none {
		color: #666;
	}

	.active-faces-panel {
		background: linear-gradient(135deg, rgba(76, 175, 80, 0.1) 0%, rgba(76, 175, 80, 0.05) 100%);
		border: 2px solid rgba(76, 175, 80, 0.3);
		border-radius: 12px;
		padding: 16px;
		margin-bottom: 20px;
	}

	.panel-title {
		font-size: 1rem;
		font-weight: 600;
		margin: 0 0 12px 0;
		color: #333;
	}

	.active-faces-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
		gap: 12px;
	}

	.active-face-card {
		background: rgba(255, 255, 255, 0.9);
		border: 2px solid;
		border-radius: 8px;
		padding: 12px;
		cursor: pointer;
		transition: all 0.3s ease;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 8px;
	}

	.active-face-card:hover {
		transform: translateY(-2px);
		box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
	}

	.face-photo {
		position: relative;
		width: 60px;
		height: 60px;
		border-radius: 8px;
		overflow: hidden;
	}

	.photo-image {
		width: 100%;
		height: 100%;
		object-fit: cover;
	}

	.photo-placeholder {
		width: 100%;
		height: 100%;
		background-color: #f5f5f5;
		display: flex;
		align-items: center;
		justify-content: center;
		color: #999;
	}

	.placeholder-icon {
		font-size: 1.5rem;
	}

	.confidence-badge {
		position: absolute;
		top: 4px;
		right: 4px;
		color: white;
		font-size: 0.7rem;
		padding: 2px 4px;
		border-radius: 4px;
		font-weight: 600;
	}

	.face-info {
		text-align: center;
		width: 100%;
	}

	.face-name {
		margin: 0 0 4px 0;
		font-size: 0.9rem;
		font-weight: 600;
		color: #333;
	}

	.face-fullname {
		margin: 0;
		font-size: 0.75rem;
		color: #666;
	}

	.no-active-faces {
		background: #f8f9fa;
		border: 2px dashed #dee2e6;
		border-radius: 8px;
		padding: 24px;
		text-align: center;
		margin-bottom: 20px;
		color: #666;
	}

	.no-faces-icon {
		font-size: 2rem;
		margin-bottom: 8px;
		opacity: 0.5;
	}

	.contestants-panel {
		margin-top: 20px;
	}

	.contestants-list {
		display: flex;
		flex-direction: column;
		gap: 8px;
		max-height: 400px;
		overflow-y: auto;
	}

	.contestant-card {
		display: flex;
		gap: 12px;
		padding: 8px;
		border: 2px solid transparent;
		border-radius: 8px;
		cursor: pointer;
		transition: all 0.2s ease;
		background-color: #f8f9fa;
	}

	.contestant-card:hover {
		border-color: rgba(76, 175, 80, 0.3);
		transform: translateY(-1px);
	}

	.contestant-card.active {
		border-color: #4CAF50;
		background: linear-gradient(135deg, rgba(76, 175, 80, 0.1) 0%, rgba(76, 175, 80, 0.05) 100%);
	}

	.contestant-card.selected {
		border-color: #2196F3;
		background-color: rgba(33, 150, 243, 0.1);
	}

	.contestant-photo {
		position: relative;
		width: 50px;
		height: 50px;
		border-radius: 6px;
		overflow: hidden;
		flex-shrink: 0;
	}

	.active-indicator {
		position: absolute;
		top: 2px;
		right: 2px;
	}

	.active-dot {
		width: 8px;
		height: 8px;
		background-color: #4CAF50;
		border-radius: 50%;
		animation: pulse 1.5s infinite;
	}

	@keyframes pulse {
		0%, 100% { opacity: 1; }
		50% { opacity: 0.5; }
	}

	.contestant-info {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 2px;
	}

	.contestant-name {
		font-size: 0.9rem;
		font-weight: 600;
		margin: 0;
		color: #333;
	}

	.contestant-fullname {
		font-size: 0.8rem;
		margin: 0;
		color: #666;
	}

	.confidence-text {
		font-size: 0.75rem;
		font-weight: 500;
		margin-top: 2px;
	}

	/* Mobile Responsive */
	@media (max-width: 768px) {
		.face-gallery {
			padding: 16px;
		}

		.gallery-header {
			flex-direction: column;
			gap: 8px;
			text-align: center;
		}

		.active-faces-grid {
			grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
		}

		.contestants-list {
			max-height: 300px;
		}

		.contestant-card {
			padding: 6px;
		}

		.contestant-photo {
			width: 40px;
			height: 40px;
		}
	}
</style>
