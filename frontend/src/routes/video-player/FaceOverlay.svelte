<script lang="ts">
	import { 
		currentMetadata, 
		currentTime,
		activeContestants,
		allContestants 
	} from '$lib/stores/videoPlayer';
	import type { ContestantAppearance } from '$lib/stores/videoPlayer';

	export let videoElement: HTMLVideoElement | null = null;
	export let containerWidth: number = 0;
	export let containerHeight: number = 0;

	let overlayElement: HTMLDivElement;
	let faceBoxes: Array<{
		contestant: string;
		confidence: number;
		bbox: [number, number, number, number];
		displayName: string;
		photo_url: string | null;
	}> = [];

	// Get contestant display name and photo
	function getContestantInfo(contestantName: string) {
		const contestant = $allContestants.find(c => c.nickname === contestantName);
		return {
			displayName: contestant?.nickname || contestantName,
			photo_url: contestant?.photo_url || null
		};
	}

	// Calculate face positions based on current time
	$: if ($currentMetadata && $currentTime !== undefined) {
		updateFaceBoxes();
	}

	function updateFaceBoxes() {
		if (!$currentMetadata?.contestant_timeline) {
			faceBoxes = [];
			return;
		}

		const boxes: typeof faceBoxes = [];
		const tolerance = 1.0; // 1 second tolerance

		Object.entries($currentMetadata.contestant_timeline).forEach(([name, timeline]) => {
			// Use frame_appearances if available, otherwise fall back to detailed_timeline
			const appearances = timeline.frame_appearances || timeline.detailed_timeline || [];
			
			// Find appearances close to current time
			const relevantAppearances = appearances.filter(
				appearance => Math.abs(appearance.timestamp - $currentTime) <= tolerance
			);

			if (relevantAppearances.length > 0) {
				// Use the appearance with highest confidence
				const bestAppearance = relevantAppearances.reduce((best, current) => 
					current.confidence > best.confidence ? current : best
				);

				const { displayName, photo_url } = getContestantInfo(name);

				boxes.push({
					contestant: name,
					confidence: bestAppearance.confidence,
					bbox: bestAppearance.bbox,
					displayName,
					photo_url
				});
			}
		});

		faceBoxes = boxes.sort((a, b) => b.confidence - a.confidence);
	}

	// Convert normalized coordinates to pixel coordinates
	function getBboxStyle(bbox: [number, number, number, number]) {
		if (!videoElement || containerWidth === 0 || containerHeight === 0) {
			return '';
		}

		const [x, y, width, height] = bbox;
		
		// Get video dimensions and calculate scale
		const videoWidth = videoElement.videoWidth || 1920;
		const videoHeight = videoElement.videoHeight || 1080;
		const videoAspectRatio = videoWidth / videoHeight;
		const containerAspectRatio = containerWidth / containerHeight;

		let scaleX, scaleY, offsetX = 0, offsetY = 0;

		if (containerAspectRatio > videoAspectRatio) {
			// Container is wider - video is letterboxed horizontally
			scaleY = containerHeight / videoHeight;
			scaleX = scaleY;
			offsetX = (containerWidth - videoWidth * scaleX) / 2;
		} else {
			// Container is taller - video is letterboxed vertically
			scaleX = containerWidth / videoWidth;
			scaleY = scaleX;
			offsetY = (containerHeight - videoHeight * scaleY) / 2;
		}

		const pixelX = x * scaleX + offsetX;
		const pixelY = y * scaleY + offsetY;
		const pixelWidth = width * scaleX;
		const pixelHeight = height * scaleY;

		return `
			left: ${pixelX}px;
			top: ${pixelY}px;
			width: ${pixelWidth}px;
			height: ${pixelHeight}px;
		`;
	}

	// Get confidence color
	function getConfidenceColor(confidence: number): string {
		if (confidence >= 0.8) return '#4CAF50'; // Green
		if (confidence >= 0.6) return '#FF9800'; // Orange
		return '#F44336'; // Red
	}

	// Format confidence percentage
	function formatConfidence(confidence: number): string {
		return `${(confidence * 100).toFixed(0)}%`;
	}
</script>

{#if faceBoxes.length > 0}
	<div 
		class="face-overlay" 
		bind:this={overlayElement}
		style="width: {containerWidth}px; height: {containerHeight}px;"
	>
		{#each faceBoxes as face (face.contestant)}
			{@const confidenceColor = getConfidenceColor(face.confidence)}
			<div 
				class="face-box"
				style="{getBboxStyle(face.bbox)} border-color: {confidenceColor};"
			>
				<!-- Bounding box border -->
				<div class="face-border"></div>
				
				<!-- Contestant label -->
				<div class="face-label" style="background-color: {confidenceColor};">
					{#if face.photo_url}
						<img 
							src={face.photo_url} 
							alt={face.displayName}
							class="face-photo"
						/>
					{/if}
					<div class="face-info">
						<span class="face-name">{face.displayName}</span>
						<span class="face-confidence">{formatConfidence(face.confidence)}</span>
					</div>
				</div>

				<!-- Confidence indicator -->
				<div class="confidence-bar">
					<div 
						class="confidence-fill"
						style="width: {face.confidence * 100}%; background-color: {confidenceColor};"
					></div>
				</div>

				<!-- Corner markers -->
				<div class="corner-markers">
					<div class="corner top-left"></div>
					<div class="corner top-right"></div>
					<div class="corner bottom-left"></div>
					<div class="corner bottom-right"></div>
				</div>
			</div>
		{/each}

		<!-- Face detection count -->
		<div class="detection-summary">
			<div class="detection-count">
				<span class="count-icon">👁️</span>
				<span class="count-text">{faceBoxes.length} face{faceBoxes.length !== 1 ? 's' : ''} detected</span>
			</div>
		</div>
	</div>
{/if}

<style>
	.face-overlay {
		position: absolute;
		top: 0;
		left: 0;
		pointer-events: none;
		z-index: 10;
		overflow: hidden;
	}

	.face-box {
		position: absolute;
		border: 2px solid;
		border-radius: 4px;
		transition: all 0.2s ease;
		animation: fadeIn 0.3s ease;
	}

	@keyframes fadeIn {
		from {
			opacity: 0;
			transform: scale(0.8);
		}
		to {
			opacity: 1;
			transform: scale(1);
		}
	}

	.face-border {
		position: absolute;
		top: -2px;
		left: -2px;
		right: -2px;
		bottom: -2px;
		border: 1px solid rgba(255, 255, 255, 0.5);
		border-radius: 4px;
		box-shadow: 0 0 10px rgba(0, 0, 0, 0.3);
	}

	.face-label {
		position: absolute;
		bottom: -40px;
		left: 0;
		display: flex;
		align-items: center;
		gap: 6px;
		padding: 4px 8px;
		border-radius: 4px;
		color: white;
		font-size: 12px;
		font-weight: 500;
		white-space: nowrap;
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
		max-width: 200px;
		z-index: 2;
	}

	.face-photo {
		width: 24px;
		height: 24px;
		border-radius: 50%;
		object-fit: cover;
		border: 1px solid rgba(255, 255, 255, 0.5);
	}

	.face-info {
		display: flex;
		flex-direction: column;
		gap: 1px;
	}

	.face-name {
		font-weight: 600;
		line-height: 1;
	}

	.face-confidence {
		font-size: 10px;
		opacity: 0.9;
		line-height: 1;
	}

	.confidence-bar {
		position: absolute;
		top: -6px;
		left: 0;
		right: 0;
		height: 3px;
		background-color: rgba(255, 255, 255, 0.3);
		border-radius: 2px;
		overflow: hidden;
	}

	.confidence-fill {
		height: 100%;
		transition: width 0.3s ease;
		border-radius: 2px;
	}

	.corner-markers {
		position: absolute;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		pointer-events: none;
	}

	.corner {
		position: absolute;
		width: 8px;
		height: 8px;
		border: 2px solid rgba(255, 255, 255, 0.8);
	}

	.corner.top-left {
		top: -4px;
		left: -4px;
		border-right: none;
		border-bottom: none;
	}

	.corner.top-right {
		top: -4px;
		right: -4px;
		border-left: none;
		border-bottom: none;
	}

	.corner.bottom-left {
		bottom: -4px;
		left: -4px;
		border-right: none;
		border-top: none;
	}

	.corner.bottom-right {
		bottom: -4px;
		right: -4px;
		border-left: none;
		border-top: none;
	}

	.detection-summary {
		position: absolute;
		top: 12px;
		right: 12px;
		z-index: 5;
	}

	.detection-count {
		display: flex;
		align-items: center;
		gap: 6px;
		background: rgba(0, 0, 0, 0.7);
		color: white;
		padding: 6px 12px;
		border-radius: 20px;
		font-size: 12px;
		font-weight: 500;
		backdrop-filter: blur(4px);
		border: 1px solid rgba(255, 255, 255, 0.2);
	}

	.count-icon {
		font-size: 14px;
	}

	/* Animation for confidence changes */
	.face-box:hover {
		transform: scale(1.02);
		z-index: 15;
	}

	.face-box:hover .face-label {
		transform: scale(1.05);
	}

	/* Responsive adjustments */
	@media (max-width: 768px) {
		.face-label {
			font-size: 10px;
			padding: 3px 6px;
			gap: 4px;
		}

		.face-photo {
			width: 20px;
			height: 20px;
		}

		.face-confidence {
			font-size: 8px;
		}

		.detection-count {
			font-size: 10px;
			padding: 4px 8px;
		}

		.corner {
			width: 6px;
			height: 6px;
		}
	}
</style> 