<script lang="ts">
	import { 
		allContestants, 
		currentMetadata, 
		activeContestants, 
		selectedContestant,
		currentTime,
		videoPlayerActions 
	} from '$lib/stores/videoPlayer';
	import type { ContestantInfo } from '$lib/stores/videoPlayer';

	let searchQuery = '';
	let showOnlyActive = false;
	let sortBy: 'name' | 'appearances' | 'confidence' = 'name';

	// Filter and sort contestants
	$: filteredContestants = $allContestants
		.filter(contestant => {
			// Search filter
			if (searchQuery) {
				const query = searchQuery.toLowerCase();
				if (!contestant.name.toLowerCase().includes(query) && 
					!contestant.nickname.toLowerCase().includes(query)) {
					return false;
				}
			}
			
			// Active filter
			if (showOnlyActive && $currentMetadata) {
				return Object.keys($currentMetadata.contestant_timeline).includes(contestant.nickname);
			}
			
			return true;
		})
		.sort((a, b) => {
			switch (sortBy) {
				case 'name':
					return a.nickname.localeCompare(b.nickname);
				case 'appearances':
					const aAppearances = $currentMetadata?.contestant_timeline[a.nickname]?.total_appearances || 0;
					const bAppearances = $currentMetadata?.contestant_timeline[b.nickname]?.total_appearances || 0;
					return bAppearances - aAppearances;
				case 'confidence':
					const aConfidence = $currentMetadata?.contestant_timeline[a.nickname]?.max_confidence || 0;
					const bConfidence = $currentMetadata?.contestant_timeline[b.nickname]?.max_confidence || 0;
					return bConfidence - aConfidence;
				default:
					return 0;
			}
		});

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
			// Deselect if already selected
			videoPlayerActions.selectContestant(null);
		} else {
			videoPlayerActions.selectContestant(contestant);
		}
	}

	// Jump to contestant's first appearance
	function jumpToContestant(contestant: ContestantInfo, event: Event) {
		event.stopPropagation();
		const seekTime = videoPlayerActions.seekToContestant(contestant.nickname);
		if (seekTime !== null) {
			// Also select the contestant
			videoPlayerActions.selectContestant(contestant);
		}
	}

	// Get contestant timeline info
	function getTimelineInfo(contestant: ContestantInfo) {
		const timeline = $currentMetadata?.contestant_timeline[contestant.nickname];
		return timeline || null;
	}

	// Get total appearances for sorting
	function getTotalAppearances(contestant: ContestantInfo): number {
		const timeline = getTimelineInfo(contestant);
		return timeline?.total_appearances || 0;
	}

	// Get max confidence for sorting
	function getMaxConfidence(contestant: ContestantInfo): number {
		const timeline = getTimelineInfo(contestant);
		return timeline?.max_confidence || 0;
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
</script>

<div class="face-gallery">
	<div class="gallery-header">
		<h2 class="gallery-title">
			<span class="title-icon">👥</span>
			Contestants
		</h2>
		
		<div class="gallery-stats">
			{#if $currentMetadata}
				<span class="stat">
					{$currentMetadata.recognition_summary.unique_contestants} detected
				</span>
				{#if $currentMetadata.recognition_summary.faces_detected}
					<span class="stat">
						{$currentMetadata.recognition_summary.faces_detected} faces
					</span>
				{/if}
				{#if $currentMetadata.recognition_summary.recognition_rate}
					<span class="stat">
						{Math.round($currentMetadata.recognition_summary.recognition_rate * 100)}% recognized
					</span>
				{/if}
			{/if}
			<span class="stat">
				{filteredContestants.length} shown
			</span>
		</div>
	</div>

	<!-- Search and Filters -->
	<div class="gallery-controls">
		<div class="search-container">
			<input
				type="text"
				class="search-input"
				placeholder="Search contestants..."
				bind:value={searchQuery}
			/>
			<span class="search-icon">🔍</span>
		</div>

		<div class="filter-controls">
			<label class="filter-checkbox">
				<input
					type="checkbox"
					bind:checked={showOnlyActive}
				/>
				<span class="checkbox-label">In this video</span>
			</label>

			<select class="sort-select" bind:value={sortBy}>
				<option value="name">Sort by Name</option>
				<option value="appearances">Sort by Appearances</option>
				<option value="confidence">Sort by Confidence</option>
			</select>
		</div>
	</div>

	<!-- Enhanced Active Contestants Display -->
	{#if $activeContestants.length > 0}
		<div class="active-faces-panel">
			<div class="active-faces-header">
				<div class="header-left">
					<div class="detection-indicator">
						<div class="pulse-ring"></div>
						<div class="pulse-dot"></div>
					</div>
					<div class="header-text">
						<h3>Live Detection</h3>
						<p>{$activeContestants.length} face{$activeContestants.length !== 1 ? 's' : ''} recognized</p>
					</div>
				</div>
				<div class="timestamp">
					{formatTime($currentTime)}
				</div>
			</div>

			<div class="active-faces-grid">
				{#each $activeContestants as active}
					{@const contestant = $allContestants.find(c => c.nickname === active.contestant)}
					{@const confidenceColor = getConfidenceColor(active.confidence)}
					<div 
						class="active-face-card"
						on:click={() => contestant && selectContestant(contestant)}
						on:keydown={(e) => e.key === 'Enter' && contestant && selectContestant(contestant)}
						role="button"
						tabindex="0"
						style="border-color: {confidenceColor};"
					>
						<div class="face-photo-container">
							{#if contestant?.photo_url}
								<img 
									src={contestant.photo_url} 
									alt={contestant.name}
									class="active-face-photo"
								/>
							{:else}
								<div class="active-face-placeholder">
									<span class="placeholder-icon">👤</span>
								</div>
							{/if}
							
							<!-- Confidence ring -->
							<div class="confidence-ring">
								<svg class="confidence-circle" width="80" height="80">
									<circle
										cx="40"
										cy="40"
										r="35"
										stroke="rgba(255,255,255,0.2)"
										stroke-width="3"
										fill="none"
									/>
									<circle
										cx="40"
										cy="40"
										r="35"
										stroke={confidenceColor}
										stroke-width="3"
										fill="none"
										stroke-dasharray={2 * Math.PI * 35}
										stroke-dashoffset={2 * Math.PI * 35 * (1 - active.confidence)}
										class="confidence-progress"
									/>
								</svg>
								<div class="confidence-percentage" style="color: {confidenceColor};">
									{formatConfidence(active.confidence)}
								</div>
							</div>
						</div>

						<div class="active-face-info">
							<h4 class="active-face-name">{contestant?.nickname || active.contestant}</h4>
							<p class="active-face-fullname">{contestant?.name || ''}</p>
							<div class="confidence-bar-horizontal">
								<div class="confidence-track">
									<div 
										class="confidence-fill-horizontal"
										style="width: {active.confidence * 100}%; background-color: {confidenceColor};"
									></div>
								</div>
								<span class="confidence-text" style="color: {confidenceColor};">
									{formatConfidence(active.confidence)}
								</span>
							</div>
						</div>
					</div>
				{/each}
			</div>
		</div>
	{:else}
		<!-- No Active Faces State -->
		<div class="no-active-faces">
			<div class="no-faces-icon">👤</div>
			<h4>No Faces Detected</h4>
			<p>No contestants are currently visible at this timestamp</p>
		</div>
	{/if}

	<!-- Contestants Grid -->
	<div class="contestants-grid">
		{#each filteredContestants as contestant (contestant.id)}
			{@const isActive = isContestantActive(contestant)}
			{@const isSelected = $selectedContestant?.id === contestant.id}
			{@const timeline = getTimelineInfo(contestant)}
			{@const currentConfidence = getCurrentConfidence(contestant)}
			
			<div 
				class="contestant-card"
				class:active={isActive}
				class:selected={isSelected}
				class:has-timeline={timeline !== null}
				on:click={() => selectContestant(contestant)}
				on:keydown={(e) => e.key === 'Enter' && selectContestant(contestant)}
				role="button"
				tabindex="0"
			>
				<!-- Photo -->
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
					
					<!-- Active indicator -->
					{#if isActive}
						<div class="active-indicator">
							<span class="active-dot"></span>
							<span class="confidence-badge">
								{formatConfidence(currentConfidence)}
							</span>
						</div>
					{/if}
				</div>

				<!-- Info -->
				<div class="contestant-info">
					<div class="contestant-names">
						<h3 class="contestant-nickname">{contestant.nickname}</h3>
						<p class="contestant-name">{contestant.name}</p>
					</div>
					
					<div class="contestant-details">
						<span class="detail-age">Age {contestant.age}</span>
						{#if timeline}
							<span class="detail-appearances">
								{timeline.total_appearances} appearance{timeline.total_appearances !== 1 ? 's' : ''}
							</span>
						{/if}
					</div>

					<!-- Timeline Info -->
					{#if timeline}
						<div class="timeline-info">
							<div class="timeline-times">
								<span class="time-range">
									{formatTime(timeline.first_appearance_time)} - {formatTime(timeline.last_appearance_time)}
								</span>
								<span class="max-confidence">
									Max: {formatConfidence(timeline.max_confidence)}
								</span>
							</div>
							
							<button 
								class="jump-button"
								on:click={(e) => jumpToContestant(contestant, e)}
								title="Jump to first appearance"
							>
								<span class="jump-icon">⏭️</span>
								Jump to
							</button>
						</div>
					{/if}
				</div>
			</div>
		{/each}
	</div>

	<!-- Empty State -->
	{#if filteredContestants.length === 0}
		<div class="empty-state">
			<div class="empty-icon">🔍</div>
			<h3>No Contestants Found</h3>
			<p>
				{#if searchQuery}
					No contestants match your search for "{searchQuery}".
				{:else if showOnlyActive}
					No contestants detected in this video.
				{:else}
					No contestants available.
				{/if}
			</p>
			{#if searchQuery}
				<button class="clear-search" on:click={() => searchQuery = ''}>
					Clear Search
				</button>
			{/if}
		</div>
	{/if}
</div>

<style>
	.face-gallery {
		background-color: var(--surface-color);
		border-radius: 12px;
		padding: 24px;
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
		height: fit-content;
	}

	.gallery-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 20px;
		padding-bottom: 16px;
		border-bottom: 1px solid rgba(var(--text-primary), 0.1);
	}

	.gallery-title {
		font-size: 1.5rem;
		font-weight: 500;
		margin: 0;
		color: var(--text-primary);
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.title-icon {
		font-size: 1.25rem;
	}

	.gallery-stats {
		display: flex;
		flex-direction: column;
		gap: 4px;
		text-align: right;
	}

	.stat {
		font-size: 0.85rem;
		color: var(--text-secondary);
	}

	.gallery-controls {
		margin-bottom: 20px;
		display: flex;
		flex-direction: column;
		gap: 12px;
	}

	.search-container {
		position: relative;
	}

	.search-input {
		width: 100%;
		padding: 12px 40px 12px 12px;
		border: 1px solid rgba(var(--text-primary), 0.3);
		border-radius: 8px;
		background-color: var(--background-color);
		color: var(--text-primary);
		font-size: 0.9rem;
	}

	.search-input:focus {
		outline: none;
		border-color: var(--primary-color);
		box-shadow: 0 0 0 2px rgba(var(--primary-color), 0.2);
	}

	.search-icon {
		position: absolute;
		right: 12px;
		top: 50%;
		transform: translateY(-50%);
		color: var(--text-secondary);
		font-size: 1rem;
	}

	.filter-controls {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 12px;
	}

	.filter-checkbox {
		display: flex;
		align-items: center;
		gap: 6px;
		cursor: pointer;
		font-size: 0.9rem;
		color: var(--text-primary);
	}

	.filter-checkbox input[type="checkbox"] {
		margin: 0;
	}

	.sort-select {
		padding: 6px 8px;
		border: 1px solid rgba(var(--text-primary), 0.3);
		border-radius: 6px;
		background-color: var(--background-color);
		color: var(--text-primary);
		font-size: 0.85rem;
	}

	.active-faces-panel {
		background: linear-gradient(135deg, rgba(var(--primary-color), 0.15) 0%, rgba(var(--primary-color), 0.05) 100%);
		border: 2px solid rgba(var(--primary-color), 0.3);
		border-radius: 12px;
		padding: 20px;
		margin-bottom: 24px;
		box-shadow: 0 4px 16px rgba(var(--primary-color), 0.1);
	}

	.active-faces-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 16px;
	}

	.header-left {
		display: flex;
		align-items: center;
		gap: 12px;
	}

	.detection-indicator {
		position: relative;
		width: 24px;
		height: 24px;
	}

	.pulse-ring {
		position: absolute;
		top: 0;
		left: 0;
		width: 24px;
		height: 24px;
		border: 2px solid var(--primary-color);
		border-radius: 50%;
		animation: pulse-ring 1.5s infinite;
	}

	.pulse-dot {
		position: absolute;
		top: 6px;
		left: 6px;
		width: 12px;
		height: 12px;
		background-color: var(--primary-color);
		border-radius: 50%;
		animation: pulse-dot 1.5s infinite;
	}

	@keyframes pulse-ring {
		0% {
			transform: scale(0.8);
			opacity: 1;
		}
		100% {
			transform: scale(1.5);
			opacity: 0;
		}
	}

	@keyframes pulse-dot {
		0%, 100% {
			opacity: 1;
		}
		50% {
			opacity: 0.5;
		}
	}

	.header-text h3 {
		margin: 0;
		font-size: 1.1rem;
		font-weight: 600;
		color: var(--text-primary);
	}

	.header-text p {
		margin: 2px 0 0 0;
		font-size: 0.85rem;
		color: var(--text-secondary);
	}

	.timestamp {
		font-family: 'Courier New', monospace;
		font-size: 0.9rem;
		font-weight: 600;
		color: var(--primary-color);
		background: rgba(var(--primary-color), 0.1);
		padding: 4px 8px;
		border-radius: 6px;
	}

	.active-faces-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
		gap: 16px;
	}

	.active-face-card {
		background: rgba(255, 255, 255, 0.9);
		border: 2px solid;
		border-radius: 12px;
		padding: 16px;
		cursor: pointer;
		transition: all 0.3s ease;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 12px;
		position: relative;
		overflow: hidden;
	}

	.active-face-card:hover {
		transform: translateY(-2px);
		box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
	}

	.active-face-card::before {
		content: '';
		position: absolute;
		top: 0;
		left: 0;
		right: 0;
		height: 3px;
		background: linear-gradient(90deg, transparent, var(--primary-color), transparent);
		animation: shimmer 2s infinite;
	}

	@keyframes shimmer {
		0% { transform: translateX(-100%); }
		100% { transform: translateX(100%); }
	}

	.face-photo-container {
		position: relative;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.active-face-photo {
		width: 80px;
		height: 80px;
		border-radius: 50%;
		object-fit: cover;
		border: 3px solid white;
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
	}

	.active-face-placeholder {
		width: 80px;
		height: 80px;
		border-radius: 50%;
		background: linear-gradient(135deg, #f0f0f0, #e0e0e0);
		display: flex;
		align-items: center;
		justify-content: center;
		border: 3px solid white;
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
	}

	.active-face-placeholder .placeholder-icon {
		font-size: 2rem;
		color: #999;
	}

	.confidence-ring {
		position: absolute;
		top: 0;
		left: 0;
	}

	.confidence-circle {
		transform: rotate(-90deg);
	}

	.confidence-progress {
		transition: stroke-dashoffset 0.5s ease;
	}

	.confidence-percentage {
		position: absolute;
		top: 50%;
		left: 50%;
		transform: translate(-50%, -50%);
		font-size: 0.75rem;
		font-weight: 700;
		text-shadow: 0 1px 2px rgba(0, 0, 0, 0.5);
	}

	.active-face-info {
		text-align: center;
		width: 100%;
	}

	.active-face-name {
		margin: 0 0 4px 0;
		font-size: 1rem;
		font-weight: 600;
		color: var(--text-primary);
	}

	.active-face-fullname {
		margin: 0 0 8px 0;
		font-size: 0.8rem;
		color: var(--text-secondary);
	}

	.confidence-bar-horizontal {
		display: flex;
		align-items: center;
		gap: 8px;
		width: 100%;
	}

	.confidence-track {
		flex: 1;
		height: 6px;
		background: rgba(0, 0, 0, 0.1);
		border-radius: 3px;
		overflow: hidden;
	}

	.confidence-fill-horizontal {
		height: 100%;
		transition: width 0.5s ease;
		border-radius: 3px;
	}

	.confidence-text {
		font-size: 0.75rem;
		font-weight: 600;
		min-width: 35px;
		text-align: right;
	}

	.no-active-faces {
		background: rgba(var(--text-primary), 0.05);
		border: 2px dashed rgba(var(--text-primary), 0.2);
		border-radius: 12px;
		padding: 32px 20px;
		text-align: center;
		margin-bottom: 24px;
		color: var(--text-secondary);
	}

	.no-faces-icon {
		font-size: 3rem;
		margin-bottom: 12px;
		opacity: 0.5;
	}

	.no-active-faces h4 {
		margin: 0 0 8px 0;
		font-size: 1.1rem;
		color: var(--text-primary);
	}

	.no-active-faces p {
		margin: 0;
		font-size: 0.9rem;
	}

	.contestants-grid {
		display: flex;
		flex-direction: column;
		gap: 12px;
		max-height: 600px;
		overflow-y: auto;
	}

	.contestant-card {
		display: flex;
		gap: 12px;
		padding: 12px;
		border: 2px solid transparent;
		border-radius: 8px;
		cursor: pointer;
		transition: all 0.2s ease;
		background-color: var(--background-color);
	}

	.contestant-card:hover {
		border-color: rgba(var(--primary-color), 0.3);
		transform: translateY(-1px);
	}

	.contestant-card.active {
		border-color: var(--primary-color);
		background: linear-gradient(135deg, rgba(var(--primary-color), 0.1) 0%, rgba(var(--primary-color), 0.05) 100%);
	}

	.contestant-card.selected {
		border-color: var(--primary-color);
		background-color: rgba(var(--primary-color), 0.1);
	}

	.contestant-card.has-timeline {
		border-left: 4px solid rgba(var(--primary-color), 0.5);
	}

	.contestant-photo {
		position: relative;
		width: 60px;
		height: 60px;
		border-radius: 8px;
		overflow: hidden;
		flex-shrink: 0;
	}

	.photo-image {
		width: 100%;
		height: 100%;
		object-fit: cover;
	}

	.photo-placeholder {
		width: 100%;
		height: 100%;
		background-color: rgba(var(--text-primary), 0.1);
		display: flex;
		align-items: center;
		justify-content: center;
		color: var(--text-secondary);
	}

	.placeholder-icon {
		font-size: 1.5rem;
	}

	.active-indicator {
		position: absolute;
		top: 4px;
		right: 4px;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 2px;
	}

	.active-dot {
		width: 8px;
		height: 8px;
		background-color: #4caf50;
		border-radius: 50%;
		animation: pulse 1.5s infinite;
	}

	@keyframes pulse {
		0%, 100% { opacity: 1; }
		50% { opacity: 0.5; }
	}

	.confidence-badge {
		background-color: rgba(0, 0, 0, 0.8);
		color: white;
		font-size: 0.7rem;
		padding: 2px 4px;
		border-radius: 4px;
		font-weight: 500;
	}

	.contestant-info {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.contestant-names {
		margin-bottom: 4px;
	}

	.contestant-nickname {
		font-size: 1rem;
		font-weight: 500;
		margin: 0 0 2px 0;
		color: var(--text-primary);
	}

	.contestant-name {
		font-size: 0.85rem;
		margin: 0;
		color: var(--text-secondary);
	}

	.contestant-details {
		display: flex;
		gap: 8px;
		flex-wrap: wrap;
		margin-bottom: 4px;
	}

	.detail-age,
	.detail-appearances {
		font-size: 0.8rem;
		color: var(--text-secondary);
		background-color: rgba(var(--text-primary), 0.1);
		padding: 2px 6px;
		border-radius: 4px;
	}

	.timeline-info {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 8px;
	}

	.timeline-times {
		display: flex;
		flex-direction: column;
		gap: 2px;
	}

	.time-range,
	.max-confidence {
		font-size: 0.75rem;
		color: var(--text-secondary);
	}

	.jump-button {
		display: flex;
		align-items: center;
		gap: 4px;
		padding: 4px 8px;
		background-color: var(--primary-color);
		color: white;
		border: none;
		border-radius: 4px;
		cursor: pointer;
		font-size: 0.75rem;
		transition: background-color 0.2s ease;
	}

	.jump-button:hover {
		background-color: rgba(var(--primary-color), 0.8);
	}

	.jump-icon {
		font-size: 0.8rem;
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

	.empty-state h3 {
		font-size: 1.25rem;
		margin: 0 0 8px 0;
		color: var(--text-primary);
	}

	.empty-state p {
		margin: 0 0 16px 0;
		font-size: 0.9rem;
	}

	.clear-search {
		background-color: var(--primary-color);
		color: white;
		border: none;
		padding: 8px 16px;
		border-radius: 6px;
		cursor: pointer;
		font-size: 0.9rem;
	}

	.clear-search:hover {
		background-color: rgba(var(--primary-color), 0.8);
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

		.gallery-stats {
			text-align: center;
		}

		.filter-controls {
			flex-direction: column;
			gap: 8px;
		}

		.contestants-grid {
			max-height: 400px;
		}

		.contestant-card {
			flex-direction: column;
			text-align: center;
		}

		.contestant-photo {
			align-self: center;
		}

		.timeline-info {
			flex-direction: column;
			gap: 6px;
		}
	}
</style>