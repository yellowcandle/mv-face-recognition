<script lang="ts">
	import { 
		allContestants, 
		currentMetadata, 
		activeContestants, 
		selectedContestant,
		videoPlayerActions,
		isLoading,
		error,
		currentVideo
	} from '$lib/stores/videoPlayer';
	import type { ContestantInfo } from '$lib/stores/videoPlayer';

	// Search and filter state
	let searchTerm = '';
	let showSelectedOnly = false;
	let sortBy: 'confidence' | 'name' = 'confidence';
	let sortOrder: 'asc' | 'desc' = 'desc';

	// Error handling state
	let retryCount = 0;
	const MAX_RETRIES = 3;

	// Retry mechanism for loading metadata
	async function retryLoadMetadata() {
		if (retryCount >= MAX_RETRIES) {
			return;
		}

		retryCount++;
		const video = $currentVideo;
		if (video && video.has_metadata) {
			try {
				await videoPlayerActions.selectVideo(video);
				retryCount = 0; // Reset on success
			} catch (err) {
				console.error(`Retry ${retryCount} failed:`, err);
			}
		}
	}

	// Clear error when successfully loading new data
	$: if ($currentMetadata && $error) {
		videoPlayerActions.clearError();
		retryCount = 0;
	}

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

	// Filter and sort contestants based on search term, selection filter, and sort options
	$: filteredContestants = videoContestants
		.filter(contestant => {
			// Search filter
			if (searchTerm.trim()) {
				const search = searchTerm.toLowerCase().trim();
				return contestant.name.toLowerCase().includes(search) || 
					   contestant.nickname.toLowerCase().includes(search);
			}
			return true;
		})
		.filter(contestant => {
			// Selected only filter
			if (showSelectedOnly) {
				return $selectedContestant?.id === contestant.id;
			}
			return true;
		})
		.sort((a, b) => {
			if (sortBy === 'confidence') {
				const aConfidence = getCurrentConfidence(a);
				const bConfidence = getCurrentConfidence(b);
				return sortOrder === 'desc' ? bConfidence - aConfidence : aConfidence - bConfidence;
			} else {
				// Sort by name
				const aName = a.name.toLowerCase();
				const bName = b.name.toLowerCase();
				const comparison = aName.localeCompare(bName);
				return sortOrder === 'desc' ? -comparison : comparison;
			}
		});

	// Clear search when no results
	$: if (searchTerm.trim() && filteredContestants.length === 0) {
		// Keep search term but show no results message
	}
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

	<!-- Loading State -->
	{#if $isLoading}
		<div class="loading-panel" data-testid="loading-spinner">
			<div class="loading-spinner"></div>
			<p>Loading face recognition data...</p>
		</div>
	{/if}

	<!-- Error State -->
	{#if $error && !$isLoading}
		<div class="error-panel" data-testid="error-message">
			<div class="error-icon">⚠️</div>
			<div class="error-content">
				<h4>Failed to Load Face Recognition Data</h4>
				<p class="error-text">{$error}</p>
				
				{#if retryCount < MAX_RETRIES}
					<div class="error-actions">
						<button 
							class="retry-btn"
							on:click={retryLoadMetadata}
							data-testid="retry-button"
						>
							Retry ({MAX_RETRIES - retryCount} attempts left)
						</button>
						<button 
							class="dismiss-btn"
							on:click={() => videoPlayerActions.clearError()}
							data-testid="dismiss-error-button"
						>
							Dismiss
						</button>
					</div>
				{:else}
					<div class="error-actions">
						<button 
							class="dismiss-btn"
							on:click={() => videoPlayerActions.clearError()}
							data-testid="dismiss-error-button"
						>
							Dismiss
						</button>
						<p class="max-retries-text">Maximum retry attempts reached</p>
					</div>
				{/if}
			</div>
		</div>
	{/if}

	<!-- Search and Filter Controls -->
	<div class="controls-panel">
		<div class="search-container">
			<input 
				type="text" 
				placeholder="Search contestants..." 
				bind:value={searchTerm}
				class="search-input"
				data-testid="contestant-search"
			/>
			<div class="search-icon">🔍</div>
		</div>
		
		<div class="filter-controls">
			<label class="filter-toggle">
				<input 
					type="checkbox" 
					bind:checked={showSelectedOnly}
					data-testid="selected-only-filter"
				/>
				<span class="toggle-text">Selected Only</span>
			</label>
			
			<div class="sort-controls">
				<select bind:value={sortBy} class="sort-select" data-testid="sort-by-select">
					<option value="confidence">Confidence</option>
					<option value="name">Name</option>
				</select>
				<button 
					class="sort-order-btn"
					class:desc={sortOrder === 'desc'}
					on:click={() => sortOrder = sortOrder === 'desc' ? 'asc' : 'desc'}
					data-testid="sort-order-button"
					title={sortOrder === 'desc' ? 'Sort Descending' : 'Sort Ascending'}
				>
					{sortOrder === 'desc' ? '↓' : '↑'}
				</button>
			</div>
		</div>
	</div>

	<!-- No Face Data Available State -->
	{#if $currentVideo && !$currentVideo.has_metadata && !$isLoading && !$error}
		<div class="no-face-data-panel" data-testid="no-face-data-message">
			<div class="no-data-icon">📹</div>
			<div class="no-data-content">
				<h4>No Face Data Available</h4>
				<p>Face recognition data is not available for this video.</p>
				<p class="note-text">Video playback will continue normally.</p>
			</div>
		</div>
	{:else if $currentVideo && $currentVideo.has_metadata && $currentMetadata}
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
			<h3 class="panel-title">
				All Contestants ({filteredContestants.length}
				{#if filteredContestants.length !== videoContestants.length}
					of {videoContestants.length}
				{/if})
			</h3>
			
			{#if filteredContestants.length > 0}
				<div class="contestants-list">
					{#each filteredContestants as contestant}
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
			{:else}
				<!-- No Results State -->
				<div class="no-results" data-testid="no-faces-message">
					<div class="no-results-icon">🔍</div>
					<p>
						{#if searchTerm.trim()}
							No contestants match "{searchTerm}"
						{:else if showSelectedOnly}
							No contestant selected
						{:else}
							No faces detected
						{/if}
					</p>
				</div>
			{/if}
		</div>
		{:else}
			<!-- No Contestants in Video -->
			<div class="contestants-panel">
				<div class="no-results" data-testid="no-faces-message">
					<div class="no-results-icon">👤</div>
					<p>No contestants appear in this video</p>
				</div>
			</div>
		{/if}
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

	/* Search and Filter Controls */
	.controls-panel {
		background: #f8f9fa;
		border-radius: 8px;
		padding: 16px;
		margin-bottom: 20px;
		display: flex;
		flex-direction: column;
		gap: 12px;
	}

	.search-container {
		position: relative;
		display: flex;
		align-items: center;
	}

	.search-input {
		width: 100%;
		padding: 8px 36px 8px 12px;
		border: 2px solid #e0e0e0;
		border-radius: 6px;
		font-size: 0.9rem;
		transition: border-color 0.2s ease;
		background: white;
	}

	.search-input:focus {
		outline: none;
		border-color: #4CAF50;
		box-shadow: 0 0 0 3px rgba(76, 175, 80, 0.1);
	}

	.search-icon {
		position: absolute;
		right: 12px;
		color: #666;
		pointer-events: none;
	}

	.filter-controls {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 12px;
	}

	.filter-toggle {
		display: flex;
		align-items: center;
		gap: 6px;
		cursor: pointer;
		font-size: 0.9rem;
		color: #333;
	}

	.filter-toggle input[type="checkbox"] {
		margin: 0;
		cursor: pointer;
	}

	.toggle-text {
		user-select: none;
	}

	.sort-controls {
		display: flex;
		align-items: center;
		gap: 6px;
	}

	.sort-select {
		padding: 4px 8px;
		border: 1px solid #e0e0e0;
		border-radius: 4px;
		font-size: 0.85rem;
		background: white;
		cursor: pointer;
	}

	.sort-select:focus {
		outline: none;
		border-color: #4CAF50;
	}

	.sort-order-btn {
		width: 28px;
		height: 28px;
		border: 1px solid #e0e0e0;
		border-radius: 4px;
		background: white;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		font-weight: bold;
		transition: all 0.2s ease;
	}

	.sort-order-btn:hover {
		border-color: #4CAF50;
		background-color: rgba(76, 175, 80, 0.1);
	}

	.sort-order-btn.desc {
		background-color: #4CAF50;
		color: white;
		border-color: #4CAF50;
	}

	/* Loading State */
	.loading-panel {
		background: #f8f9fa;
		border: 2px solid #e9ecef;
		border-radius: 8px;
		padding: 24px;
		text-align: center;
		margin-bottom: 20px;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 12px;
	}

	.loading-spinner {
		width: 32px;
		height: 32px;
		border: 3px solid #f3f3f3;
		border-top: 3px solid #4CAF50;
		border-radius: 50%;
		animation: spin 1s linear infinite;
	}

	@keyframes spin {
		0% { transform: rotate(0deg); }
		100% { transform: rotate(360deg); }
	}

	/* Error State */
	.error-panel {
		background: linear-gradient(135deg, rgba(244, 67, 54, 0.1) 0%, rgba(244, 67, 54, 0.05) 100%);
		border: 2px solid rgba(244, 67, 54, 0.3);
		border-radius: 8px;
		padding: 20px;
		margin-bottom: 20px;
		display: flex;
		gap: 12px;
		align-items: flex-start;
	}

	.error-icon {
		font-size: 1.5rem;
		flex-shrink: 0;
	}

	.error-content {
		flex: 1;
	}

	.error-content h4 {
		margin: 0 0 8px 0;
		font-size: 1rem;
		font-weight: 600;
		color: #d32f2f;
	}

	.error-text {
		margin: 0 0 12px 0;
		font-size: 0.9rem;
		color: #666;
	}

	.error-actions {
		display: flex;
		gap: 8px;
		align-items: center;
		flex-wrap: wrap;
	}

	.retry-btn {
		background-color: #4CAF50;
		color: white;
		border: none;
		border-radius: 4px;
		padding: 6px 12px;
		font-size: 0.85rem;
		cursor: pointer;
		transition: background-color 0.2s ease;
	}

	.retry-btn:hover {
		background-color: #45a049;
	}

	.dismiss-btn {
		background-color: transparent;
		color: #666;
		border: 1px solid #ddd;
		border-radius: 4px;
		padding: 6px 12px;
		font-size: 0.85rem;
		cursor: pointer;
		transition: all 0.2s ease;
	}

	.dismiss-btn:hover {
		border-color: #999;
		color: #333;
	}

	.max-retries-text {
		margin: 0;
		font-size: 0.8rem;
		color: #999;
		font-style: italic;
	}

	/* No Face Data State */
	.no-face-data-panel {
		background: linear-gradient(135deg, rgba(158, 158, 158, 0.1) 0%, rgba(158, 158, 158, 0.05) 100%);
		border: 2px solid rgba(158, 158, 158, 0.3);
		border-radius: 8px;
		padding: 24px;
		margin-bottom: 20px;
		text-align: center;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 12px;
	}

	.no-data-icon {
		font-size: 2.5rem;
		opacity: 0.7;
	}

	.no-data-content h4 {
		margin: 0 0 8px 0;
		font-size: 1.1rem;
		font-weight: 600;
		color: #555;
	}

	.no-data-content p {
		margin: 0 0 4px 0;
		font-size: 0.9rem;
		color: #666;
	}

	.note-text {
		font-style: italic;
		color: #888 !important;
		font-size: 0.85rem !important;
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

	/* No Results State */
	.no-results {
		background: #f8f9fa;
		border: 2px dashed #dee2e6;
		border-radius: 8px;
		padding: 24px;
		text-align: center;
		color: #666;
		margin-top: 12px;
	}

	.no-results-icon {
		font-size: 2rem;
		margin-bottom: 8px;
		opacity: 0.5;
	}

	.no-results p {
		margin: 0;
		font-size: 0.9rem;
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

		.controls-panel {
			padding: 12px;
		}

		.filter-controls {
			flex-direction: column;
			gap: 8px;
		}

		.sort-controls {
			justify-content: center;
		}

		.error-panel {
			padding: 16px;
			flex-direction: column;
			text-align: center;
		}

		.error-actions {
			justify-content: center;
		}

		.no-face-data-panel {
			padding: 20px;
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
