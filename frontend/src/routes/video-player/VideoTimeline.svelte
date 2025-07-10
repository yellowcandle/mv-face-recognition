<script lang="ts">
	import { 
		currentTime, 
		duration, 
		timelineMarkers, 
		currentMetadata,
		showTimeline,
		videoPlayerActions 
	} from '$lib/stores/videoPlayer';

	let timelineElement: HTMLDivElement;
	let isDragging = false;

	// Format time for display
	function formatTime(seconds: number): string {
		const mins = Math.floor(seconds / 60);
		const secs = Math.floor(seconds % 60);
		return `${mins}:${secs.toString().padStart(2, '0')}`;
	}

	// Handle timeline click
	function handleTimelineClick(event: MouseEvent) {
		if (!timelineElement || $duration === 0) return;
		
		const rect = timelineElement.getBoundingClientRect();
		const clickX = event.clientX - rect.left;
		const percentage = clickX / rect.width;
		const newTime = percentage * $duration;
		
		videoPlayerActions.updateCurrentTime(Math.max(0, Math.min($duration, newTime)));
	}

	// Handle timeline drag
	function handleMouseDown(event: MouseEvent) {
		isDragging = true;
		handleTimelineClick(event);
		
		function handleMouseMove(e: MouseEvent) {
			if (isDragging) {
				handleTimelineClick(e);
			}
		}
		
		function handleMouseUp() {
			isDragging = false;
			document.removeEventListener('mousemove', handleMouseMove);
			document.removeEventListener('mouseup', handleMouseUp);
		}
		
		document.addEventListener('mousemove', handleMouseMove);
		document.addEventListener('mouseup', handleMouseUp);
	}

	// Calculate progress percentage
	$: progressPercentage = $duration > 0 ? ($currentTime / $duration) * 100 : 0;

	// Get unique contestants for color coding
	$: uniqueContestants = $currentMetadata ? 
		Object.keys($currentMetadata.contestant_timeline) : [];

	// Generate color for contestant with better distribution
	function getContestantColor(contestant: string, index: number): string {
		const colors = [
			'#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7',
			'#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9',
			'#F8C471', '#82E0AA', '#F1948A', '#85C1E9', '#D7BDE2',
			'#FF8A80', '#80CBC4', '#81C784', '#FFB74D', '#CE93D8'
		];
		return colors[index % colors.length];
	}

	// Get confidence heat map data
	$: confidenceHeatMap = getConfidenceHeatMap($currentMetadata, $duration);

	function getConfidenceHeatMap(metadata: any, duration: number) {
		if (!metadata?.contestant_timeline || duration === 0) {
			return [];
		}

		const heatMapData: Array<{
			time: number;
			percentage: number;
			confidence: number;
			contestants: number;
		}> = [];

		// Create heat map points every 5 seconds
		const interval = 5; // seconds
		const totalPoints = Math.ceil(duration / interval);

		for (let i = 0; i <= totalPoints; i++) {
			const time = i * interval;
			const tolerance = 2.5; // 2.5 second tolerance for each point

			let totalConfidence = 0;
			let contestantCount = 0;

			Object.entries(metadata.contestant_timeline).forEach(([name, timeline]: [string, any]) => {
				const appearances = timeline.frame_appearances || timeline.detailed_timeline || [];
				const relevantAppearances = appearances.filter(
					(appearance: any) => Math.abs(appearance.timestamp - time) <= tolerance
				);

				if (relevantAppearances.length > 0) {
					const maxConfidence = Math.max(...relevantAppearances.map((a: any) => a.confidence));
					totalConfidence += maxConfidence;
					contestantCount++;
				}
			});

			if (contestantCount > 0) {
				heatMapData.push({
					time,
					percentage: (time / duration) * 100,
					confidence: totalConfidence / contestantCount,
					contestants: contestantCount
				});
			}
		}

		return heatMapData;
	}

	// Get contestant tracks for the enhanced timeline
	$: contestantTracks = getContestantTracks($currentMetadata, $duration);

	function getContestantTracks(metadata: any, duration: number) {
		if (!metadata?.contestant_timeline || duration === 0) {
			return [];
		}

		return Object.entries(metadata.contestant_timeline).map(([name, timeline]: [string, any], index) => {
			const appearances = timeline.frame_appearances || timeline.detailed_timeline || [];
			const segments: Array<{
				start: number;
				end: number;
				confidence: number;
				startPercentage: number;
				widthPercentage: number;
			}> = [];

			// Group continuous appearances into segments
			appearances.sort((a: any, b: any) => a.timestamp - b.timestamp);

			let currentSegment: any = null;
			const segmentGap = 5; // seconds

			appearances.forEach((appearance: any) => {
				if (!currentSegment || (appearance.timestamp - currentSegment.end) > segmentGap) {
					// Start new segment
					if (currentSegment) {
						segments.push({
							start: currentSegment.start,
							end: currentSegment.end,
							confidence: currentSegment.totalConfidence / currentSegment.count,
							startPercentage: (currentSegment.start / duration) * 100,
							widthPercentage: ((currentSegment.end - currentSegment.start) / duration) * 100
						});
					}
					currentSegment = {
						start: appearance.timestamp,
						end: appearance.timestamp,
						totalConfidence: appearance.confidence,
						count: 1
					};
				} else {
					// Extend current segment
					currentSegment.end = appearance.timestamp;
					currentSegment.totalConfidence += appearance.confidence;
					currentSegment.count++;
				}
			});

			// Add final segment
			if (currentSegment) {
				segments.push({
					start: currentSegment.start,
					end: currentSegment.end,
					confidence: currentSegment.totalConfidence / currentSegment.count,
					startPercentage: (currentSegment.start / duration) * 100,
					widthPercentage: ((currentSegment.end - currentSegment.start) / duration) * 100
				});
			}

			return {
				contestant: name,
				color: getContestantColor(name, index),
				segments,
				totalAppearances: timeline.total_appearances,
				avgConfidence: timeline.avg_confidence
			};
		});
	}

	// Toggle timeline visibility
	function toggleTimeline() {
		showTimeline.update(show => !show);
	}
</script>

<div class="video-timeline">
	<!-- Timeline Header -->
	<div class="timeline-header">
		<div class="timeline-title">
			<h3>
				<span class="timeline-icon">📊</span>
				Face Detection Timeline
			</h3>
			<button 
				class="toggle-button" 
				on:click={toggleTimeline}
				title={$showTimeline ? 'Hide timeline' : 'Show timeline'}
			>
				{$showTimeline ? '▲' : '▼'}
			</button>
		</div>
		
		{#if $currentMetadata && $showTimeline}
			<div class="timeline-stats">
				<span class="stat">
					{$currentMetadata.recognition_summary.faces_detected} faces detected
				</span>
				<span class="stat">
					{$currentMetadata.recognition_summary.faces_recognized} recognized
				</span>
				<span class="stat">
					{$currentMetadata.recognition_summary.unique_contestants} contestants
				</span>
			</div>
		{/if}
	</div>

	{#if $showTimeline}
		<!-- Timeline Content -->
		<div class="timeline-content">
			{#if $currentMetadata && $duration > 0}
				<!-- Enhanced Timeline Track -->
				<div class="enhanced-timeline-container">
					<!-- Confidence Heat Map -->
					<div class="confidence-heatmap">
						{#each confidenceHeatMap as point}
							<div 
								class="heatmap-point"
								style="
									left: {point.percentage}%; 
									background-color: rgba(255, 165, 0, {point.confidence * 0.8});
									height: {Math.max(2, point.contestants * 3)}px;
								"
								title="Time: {formatTime(point.time)}, Confidence: {(point.confidence * 100).toFixed(0)}%, Contestants: {point.contestants}"
							></div>
						{/each}
					</div>

					<!-- Contestant Tracks -->
					<div class="contestant-tracks">
						{#each contestantTracks as track, trackIndex}
							<div class="track-row" style="--track-color: {track.color};">
								<div class="track-label">
									<span class="track-name">{track.contestant}</span>
									<span class="track-stats">{track.totalAppearances} appearances</span>
								</div>
								<div class="track-line">
									{#each track.segments as segment}
										<div 
											class="track-segment"
											style="
												left: {segment.startPercentage}%; 
												width: {Math.max(0.5, segment.widthPercentage)}%;
												background-color: {track.color};
												opacity: {0.4 + (segment.confidence * 0.6)};
											"
											title="Confidence: {(segment.confidence * 100).toFixed(0)}%"
										></div>
									{/each}
								</div>
							</div>
						{/each}
					</div>

					<!-- Main Timeline Track -->
					<div 
						class="timeline-track"
						bind:this={timelineElement}
						on:mousedown={handleMouseDown}
						role="slider"
						tabindex="0"
						aria-label="Video timeline"
						aria-valuemin="0"
						aria-valuemax={$duration}
						aria-valuenow={$currentTime}
					>
						<!-- Background -->
						<div class="timeline-background"></div>
						
						<!-- Face Detection Markers -->
						{#each $timelineMarkers as marker (marker.time)}
							<div 
								class="detection-marker"
								style="left: {marker.percentage}%"
								title="{formatTime(marker.time)}: {marker.contestants.join(', ')}"
							>
								<div class="marker-line"></div>
								<div class="marker-tooltip">
									<div class="tooltip-time">{formatTime(marker.time)}</div>
									<div class="tooltip-contestants">
										{#each marker.contestants as contestant, i}
											<span 
												class="tooltip-contestant"
												style="color: {getContestantColor(contestant, uniqueContestants.indexOf(contestant))}"
											>
												{contestant}
											</span>
											{#if i < marker.contestants.length - 1}, {/if}
										{/each}
									</div>
								</div>
							</div>
						{/each}
						
						<!-- Progress Bar -->
						<div 
							class="timeline-progress"
							style="width: {progressPercentage}%"
						></div>
						
						<!-- Current Time Indicator -->
						<div 
							class="time-indicator"
							style="left: {progressPercentage}%"
						>
							<div class="indicator-line"></div>
							<div class="indicator-handle"></div>
							<div class="indicator-tooltip">
								{formatTime($currentTime)}
							</div>
						</div>
					</div>
				</div>

				<!-- Time Labels -->
				<div class="time-labels">
					<span class="time-label start">0:00</span>
					<span class="time-label current">{formatTime($currentTime)}</span>
					<span class="time-label end">{formatTime($duration)}</span>
				</div>

				<!-- Contestant Legend -->
				{#if uniqueContestants.length > 0}
					<div class="contestant-legend">
						<h4 class="legend-title">Contestants in this video:</h4>
						<div class="legend-items">
							{#each uniqueContestants as contestant, index}
								{@const timeline = $currentMetadata.contestant_timeline[contestant]}
								<div 
									class="legend-item"
									on:click={() => videoPlayerActions.seekToContestant(contestant)}
									on:keydown={(e) => e.key === 'Enter' && videoPlayerActions.seekToContestant(contestant)}
									role="button"
									tabindex="0"
									title="Click to jump to first appearance"
								>
									<div 
										class="legend-color"
										style="background-color: {getContestantColor(contestant, index)}"
									></div>
									<span class="legend-name">{contestant}</span>
									<span class="legend-stats">
										{timeline.total_appearances} appearance{timeline.total_appearances !== 1 ? 's' : ''}
									</span>
								</div>
							{/each}
						</div>
					</div>
				{/if}
			{:else}
				<!-- No Timeline Data -->
				<div class="no-timeline">
					<div class="no-timeline-icon">📊</div>
					<h4>No Timeline Data</h4>
					<p>
						{#if !$currentMetadata}
							No face detection data available for this video.
						{:else if $duration === 0}
							Video not loaded yet.
						{:else}
							Timeline data is loading...
						{/if}
					</p>
				</div>
			{/if}
		</div>
	{/if}
</div>

<style>
	.video-timeline {
		background-color: var(--background-color);
		border-radius: 8px;
		overflow: hidden;
	}

	.timeline-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 16px;
		border-bottom: 1px solid rgba(var(--text-primary), 0.1);
	}

	.timeline-title {
		display: flex;
		align-items: center;
		gap: 12px;
	}

	.timeline-title h3 {
		font-size: 1.1rem;
		font-weight: 500;
		margin: 0;
		color: var(--text-primary);
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.timeline-icon {
		font-size: 1rem;
	}

	.toggle-button {
		background: none;
		border: none;
		color: var(--text-secondary);
		font-size: 1rem;
		cursor: pointer;
		padding: 4px;
		border-radius: 4px;
		transition: all 0.2s ease;
	}

	.toggle-button:hover {
		background-color: rgba(var(--text-primary), 0.1);
		color: var(--text-primary);
	}

	.timeline-stats {
		display: flex;
		gap: 16px;
		flex-wrap: wrap;
	}

	.stat {
		font-size: 0.85rem;
		color: var(--text-secondary);
		background-color: rgba(var(--text-primary), 0.1);
		padding: 4px 8px;
		border-radius: 4px;
	}

	.timeline-content {
		padding: 20px;
	}

	.enhanced-timeline-container {
		display: flex;
		flex-direction: column;
		gap: 12px;
		margin: 20px 0;
	}

	/* Confidence Heat Map */
	.confidence-heatmap {
		position: relative;
		height: 20px;
		background: linear-gradient(90deg, rgba(0,0,0,0.05) 0%, rgba(0,0,0,0.02) 100%);
		border-radius: 4px;
		margin-bottom: 8px;
	}

	.heatmap-point {
		position: absolute;
		bottom: 0;
		width: 3px;
		border-radius: 2px 2px 0 0;
		transition: all 0.2s ease;
	}

	.heatmap-point:hover {
		transform: scaleY(1.2);
		z-index: 10;
	}

	/* Contestant Tracks */
	.contestant-tracks {
		display: flex;
		flex-direction: column;
		gap: 4px;
		margin-bottom: 12px;
	}

	.track-row {
		display: flex;
		align-items: center;
		gap: 12px;
		min-height: 24px;
	}

	.track-label {
		min-width: 120px;
		display: flex;
		flex-direction: column;
		gap: 1px;
	}

	.track-name {
		font-size: 0.8rem;
		font-weight: 500;
		color: var(--track-color);
	}

	.track-stats {
		font-size: 0.7rem;
		color: var(--text-secondary);
	}

	.track-line {
		flex: 1;
		position: relative;
		height: 8px;
		background: rgba(var(--text-primary), 0.05);
		border-radius: 4px;
		overflow: hidden;
	}

	.track-segment {
		position: absolute;
		top: 0;
		height: 100%;
		border-radius: 2px;
		transition: all 0.2s ease;
		cursor: pointer;
	}

	.track-segment:hover {
		transform: scaleY(1.3);
		z-index: 5;
		opacity: 1 !important;
	}

	.timeline-track {
		position: relative;
		height: 40px;
		margin: 20px 0;
		cursor: pointer;
		border-radius: 6px;
		overflow: visible;
	}

	.timeline-background {
		position: absolute;
		top: 50%;
		left: 0;
		right: 0;
		height: 8px;
		background-color: rgba(var(--text-primary), 0.2);
		border-radius: 4px;
		transform: translateY(-50%);
	}

	.timeline-progress {
		position: absolute;
		top: 50%;
		left: 0;
		height: 8px;
		background-color: var(--primary-color);
		border-radius: 4px;
		transform: translateY(-50%);
		transition: width 0.1s ease;
	}

	.detection-marker {
		position: absolute;
		top: 0;
		bottom: 0;
		width: 2px;
		z-index: 2;
	}

	.marker-line {
		width: 100%;
		height: 100%;
		background-color: rgba(255, 215, 0, 0.8);
		border-radius: 1px;
	}

	.marker-tooltip {
		position: absolute;
		bottom: 100%;
		left: 50%;
		transform: translateX(-50%);
		background-color: rgba(0, 0, 0, 0.9);
		color: white;
		padding: 6px 8px;
		border-radius: 4px;
		font-size: 0.75rem;
		white-space: nowrap;
		opacity: 0;
		pointer-events: none;
		transition: opacity 0.2s ease;
		z-index: 10;
	}

	.detection-marker:hover .marker-tooltip {
		opacity: 1;
	}

	.tooltip-time {
		font-weight: 500;
		margin-bottom: 2px;
	}

	.tooltip-contestants {
		display: flex;
		flex-wrap: wrap;
		gap: 4px;
	}

	.tooltip-contestant {
		font-weight: 500;
	}

	.time-indicator {
		position: absolute;
		top: 0;
		bottom: 0;
		width: 2px;
		z-index: 3;
		pointer-events: none;
	}

	.indicator-line {
		width: 100%;
		height: 100%;
		background-color: var(--primary-color);
		border-radius: 1px;
	}

	.indicator-handle {
		position: absolute;
		top: 50%;
		left: 50%;
		transform: translate(-50%, -50%);
		width: 12px;
		height: 12px;
		background-color: var(--primary-color);
		border: 2px solid white;
		border-radius: 50%;
		box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
	}

	.indicator-tooltip {
		position: absolute;
		top: -30px;
		left: 50%;
		transform: translateX(-50%);
		background-color: var(--primary-color);
		color: white;
		padding: 4px 6px;
		border-radius: 4px;
		font-size: 0.75rem;
		font-weight: 500;
		white-space: nowrap;
	}

	.time-labels {
		display: flex;
		justify-content: space-between;
		margin-top: 8px;
		font-size: 0.8rem;
		color: var(--text-secondary);
	}

	.time-label.current {
		color: var(--primary-color);
		font-weight: 500;
	}

	.contestant-legend {
		margin-top: 24px;
		padding-top: 16px;
		border-top: 1px solid rgba(var(--text-primary), 0.1);
	}

	.legend-title {
		font-size: 0.9rem;
		font-weight: 500;
		margin: 0 0 12px 0;
		color: var(--text-primary);
	}

	.legend-items {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
	}

	.legend-item {
		display: flex;
		align-items: center;
		gap: 6px;
		padding: 6px 10px;
		background-color: var(--surface-color);
		border-radius: 6px;
		cursor: pointer;
		transition: all 0.2s ease;
		border: 1px solid transparent;
	}

	.legend-item:hover {
		border-color: var(--primary-color);
		transform: translateY(-1px);
	}

	.legend-color {
		width: 12px;
		height: 12px;
		border-radius: 50%;
		flex-shrink: 0;
	}

	.legend-name {
		font-size: 0.85rem;
		font-weight: 500;
		color: var(--text-primary);
	}

	.legend-stats {
		font-size: 0.75rem;
		color: var(--text-secondary);
	}

	.no-timeline {
		text-align: center;
		padding: 40px 20px;
		color: var(--text-secondary);
	}

	.no-timeline-icon {
		font-size: 2.5rem;
		margin-bottom: 12px;
	}

	.no-timeline h4 {
		font-size: 1.1rem;
		margin: 0 0 8px 0;
		color: var(--text-primary);
	}

	.no-timeline p {
		margin: 0;
		font-size: 0.9rem;
	}

	/* Mobile Responsive */
	@media (max-width: 768px) {
		.timeline-header {
			flex-direction: column;
			gap: 12px;
			align-items: flex-start;
		}

		.timeline-stats {
			gap: 8px;
		}

		.timeline-content {
			padding: 16px;
		}

		.timeline-track {
			height: 50px;
		}

		.legend-items {
			flex-direction: column;
			gap: 6px;
		}

		.legend-item {
			justify-content: flex-start;
		}

		.marker-tooltip,
		.indicator-tooltip {
			font-size: 0.7rem;
		}
	}
</style>