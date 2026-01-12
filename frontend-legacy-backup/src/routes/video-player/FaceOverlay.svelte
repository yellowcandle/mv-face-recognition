<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { 
		currentMetadata, 
		currentTime,
		allContestants 
	} from '$lib/stores/videoPlayer';
	import { createOverlayRenderer } from '$lib/services/overlayRenderer.js';

	export let videoElement: HTMLVideoElement | null = null;
	export let containerWidth: number = 0;
	export let containerHeight: number = 0;

	let canvasElement: HTMLCanvasElement;
	let overlayRenderer: any = null;
	let previousFaceIds: Set<string> = new Set();
	let faceBoxes: Array<{
		contestant: string;
		confidence: number;
		bbox: [number, number, number, number];
		displayName: string;
	}> = [];

	// Get contestant display name
	function getContestantInfo(contestantName: string) {
		const contestant = $allContestants.find(c => c.nickname === contestantName);
		return {
			displayName: contestant?.nickname || contestantName
		};
	}

	// Initialize canvas renderer
	function initializeCanvasRenderer() {
		if (!canvasElement || !videoElement || overlayRenderer) return;

		try {
			overlayRenderer = createOverlayRenderer(canvasElement, videoElement);
			overlayRenderer.startRendering();
		} catch (error) {
			console.warn('Failed to initialize canvas renderer:', error);
		}
	}

	// Update canvas size when container changes
	function updateCanvasSize() {
		if (overlayRenderer && canvasElement) {
			overlayRenderer.updateCanvasSize();
		}
	}

	// Calculate face positions based on current time
	$: if ($currentMetadata && $currentTime !== undefined) {
		updateFaceBoxes();
	}

	// Update canvas size when container dimensions change
	$: if (containerWidth && containerHeight && overlayRenderer) {
		updateCanvasSize();
	}

	function updateFaceBoxes() {
		if (!$currentMetadata?.contestant_timeline) {
			faceBoxes = [];
			renderFaces([]);
			return;
		}

		const boxes: typeof faceBoxes = [];
		const tolerance = 1.0; // 1 second tolerance

		Object.entries($currentMetadata.contestant_timeline).forEach(([name, timeline]) => {
			// Use frame_appearances if available, otherwise fall back to detailed_timeline
			const appearances = timeline.frame_appearances || timeline.detailed_timeline || [];
			
			// Find appearances close to current time
			const relevantAppearances = (appearances || []).filter(
				appearance => Math.abs(appearance.timestamp - $currentTime) <= tolerance
			);

			if (relevantAppearances.length > 0) {
				// Use the appearance with highest confidence
				const bestAppearance = relevantAppearances.reduce((best, current) => 
					current.confidence > best.confidence ? current : best
				);

				const { displayName } = getContestantInfo(name);

				boxes.push({
					contestant: name,
					confidence: bestAppearance.confidence,
					bbox: bestAppearance.bbox,
					displayName
				});
			}
		});

		faceBoxes = boxes.sort((a, b) => b.confidence - a.confidence);
		renderFaces(faceBoxes);
	}

	// Render faces using canvas renderer
	function renderFaces(faces: typeof faceBoxes) {
		if (!overlayRenderer) return;

		// Detect face changes for animations
		const currentFaceIds = new Set(faces.map(f => f.contestant));
		const newFaceIds = Array.from(currentFaceIds).filter(id => !previousFaceIds.has(id));
		const removedFaceIds = Array.from(previousFaceIds).filter(id => !currentFaceIds.has(id));

		// Queue render with animation info
		overlayRenderer.queueRender(faces, newFaceIds, removedFaceIds);
		
		previousFaceIds = currentFaceIds;
	}

	// Lifecycle management
	onMount(() => {
		// Small delay to ensure elements are rendered
		setTimeout(() => {
			initializeCanvasRenderer();
		}, 100);
	});

	onDestroy(() => {
		if (overlayRenderer) {
			overlayRenderer.dispose();
			overlayRenderer = null;
		}
	});
</script>

<!-- Canvas-based overlay for face detection -->
<canvas 
	bind:this={canvasElement}
	class="face-overlay-canvas"
	style="width: {containerWidth}px; height: {containerHeight}px;"
/>

<!-- Face detection count -->
{#if faceBoxes.length > 0}
	<div class="detection-summary">
		<div class="detection-count">
			<span class="count-icon">👁️</span>
			<span class="count-text">{faceBoxes.length} face{faceBoxes.length !== 1 ? 's' : ''} detected</span>
		</div>
	</div>
{/if}

<style>
	.face-overlay-canvas {
		position: absolute;
		top: 0;
		left: 0;
		pointer-events: none;
		z-index: 10;
		overflow: hidden;
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

	/* Responsive adjustments */
	@media (max-width: 768px) {
		.detection-count {
			font-size: 10px;
			padding: 4px 8px;
		}
	}
</style>
