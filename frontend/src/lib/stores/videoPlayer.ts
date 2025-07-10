import { writable, derived, get } from 'svelte/store';
import { apiFetch } from '$lib/utils/api';

// API calls now use environment-aware utility functions

// Types
export interface VideoInfo {
	id: string;
	name: string;
	filename: string;
	size: number;
	created_at: number;
	has_metadata: boolean;
	stream_url: string;
}

export interface ContestantInfo {
	id: string;
	number: number;
	name: string;
	nickname: string;
	age: number;
	has_photos: boolean;
	has_embedding: boolean;
	photo_url: string | null;
}

export interface VideoMetadata {
	video_id: string;
	video_info: {
		filename: string;
		fps: number;
		duration_seconds: number;
		frame_count: number;
	};
	processing_info?: {
		frame_interval: number;
		interpolation_enabled: boolean;
		similarity_threshold: number;
	};
	recognition_summary: {
		unique_contestants: number;
		total_faces_detected: number;
		total_faces_recognized: number;
	};
	contestant_timeline: Record<string, ContestantAppearance>;
}

export interface ContestantAppearance {
	total_appearances: number;
	avg_confidence: number;
	max_confidence: number;
	first_appearance_time: number;
	last_appearance_time: number;
	detailed_timeline: Array<{
		frame: number;
		timestamp: number;
		confidence: number;
		bbox: [number, number, number, number];
		interpolated?: boolean;
	}>;
}

// Store states
export const availableVideos = writable<VideoInfo[]>([]);
export const allContestants = writable<ContestantInfo[]>([]);
export const currentVideo = writable<VideoInfo | null>(null);
export const currentMetadata = writable<VideoMetadata | null>(null);
export const isLoading = writable(false);
export const error = writable<string | null>(null);

// Player state
export const currentTime = writable(0);
export const duration = writable(0);
export const isPlaying = writable(false);
export const volume = writable(1);
export const isMuted = writable(false);

// UI state
export const selectedContestant = writable<ContestantInfo | null>(null);
export const showTimeline = writable(true);
export const timelineHeight = writable(100);

// Derived stores
export const activeContestants = derived(
	[currentMetadata, currentTime],
	([$metadata, $currentTime]) => {
		if (!$metadata?.contestant_timeline) return [];
		
		const active: { contestant: string; confidence: number }[] = [];
		
		// Check which contestants are visible at current time (with 1 second tolerance)
		Object.entries($metadata.contestant_timeline).forEach(([name, timeline]) => {
			const relevantAppearances = timeline.detailed_timeline.filter(
				appearance => Math.abs(appearance.timestamp - $currentTime) <= 1.0
			);
			
			if (relevantAppearances.length > 0) {
				const maxConfidence = Math.max(...relevantAppearances.map(a => a.confidence));
				active.push({ contestant: name, confidence: maxConfidence });
			}
		});
		
		return active.sort((a, b) => b.confidence - a.confidence);
	}
);

export const timelineMarkers = derived(
	[currentMetadata, duration],
	([$metadata, $duration]) => {
		if (!$metadata?.contestant_timeline || $duration === 0) return [];
		
		const markers: Array<{
			time: number;
			contestants: string[];
			percentage: number;
		}> = [];
		
		// Create markers for face detection events
		const timeMap = new Map<number, string[]>();
		
		Object.entries($metadata.contestant_timeline).forEach(([name, timeline]) => {
			timeline.detailed_timeline.forEach(appearance => {
				const time = Math.round(appearance.timestamp);
				if (!timeMap.has(time)) {
					timeMap.set(time, []);
				}
				timeMap.get(time)!.push(name);
			});
		});
		
		timeMap.forEach((contestants, time) => {
			markers.push({
				time,
				contestants,
				percentage: (time / $duration) * 100
			});
		});
		
		return markers.sort((a, b) => a.time - b.time);
	}
);

// Actions
export const videoPlayerActions = {
	async loadVideos() {
		isLoading.set(true);
		error.set(null);
		
		try {
			const response = await apiFetch('/api/videos/processed/list');
			if (!response.ok) throw new Error('Failed to load videos');
			
			const videos = await response.json();
			availableVideos.set(videos);
		} catch (err) {
			error.set(err instanceof Error ? err.message : 'Failed to load videos');
		} finally {
			isLoading.set(false);
		}
	},

	async loadContestants() {
		isLoading.set(true);
		error.set(null);
		
		try {
			const response = await apiFetch('/api/videos/contestants');
			if (!response.ok) throw new Error('Failed to load contestants');
			
			const contestants = await response.json();
			allContestants.set(contestants);
		} catch (err) {
			error.set(err instanceof Error ? err.message : 'Failed to load contestants');
		} finally {
			isLoading.set(false);
		}
	},

	async selectVideo(video: VideoInfo) {
		currentVideo.set(video);
		currentMetadata.set(null);
		currentTime.set(0);
		duration.set(0);
		isPlaying.set(false);
		
		// Load metadata for the selected video
		if (video.has_metadata) {
			try {
				// Try to load dense metadata first
				let response = await apiFetch(`/api/videos/metadata/dense/${video.id}`);
				if (response.ok) {
					const metadata = await response.json();
					currentMetadata.set(metadata);
					duration.set(metadata.video_info.duration_seconds);
				} else {
					// Fallback to regular metadata
					response = await apiFetch(`/api/videos/metadata/${video.id}`);
					if (response.ok) {
						const metadata = await response.json();
						currentMetadata.set(metadata);
						duration.set(metadata.video_info.duration_seconds);
					}
				}
			} catch (err) {
				console.error('Failed to load video metadata:', err);
			}
		}
	},

	updateCurrentTime(time: number) {
		currentTime.set(time);
	},

	updateDuration(dur: number) {
		duration.set(dur);
	},

	setPlaying(playing: boolean) {
		isPlaying.set(playing);
	},

	setVolume(vol: number) {
		volume.set(Math.max(0, Math.min(1, vol)));
	},

	toggleMute() {
		isMuted.update(muted => !muted);
	},

	selectContestant(contestant: ContestantInfo | null) {
		selectedContestant.set(contestant);
	},

	seekToContestant(contestantName: string) {
		const metadata = get(currentMetadata);
		if (metadata?.contestant_timeline[contestantName]) {
			const firstAppearance = metadata.contestant_timeline[contestantName].first_appearance_time;
			currentTime.set(firstAppearance);
			// Trigger video seek - this will be handled by the video component
			return firstAppearance;
		}
		return null;
	},

	getContestantAppearances(contestantName: string) {
		const metadata = get(currentMetadata);
		return metadata?.contestant_timeline[contestantName] || null;
	},

	clearError() {
		error.set(null);
	},

	async generateDenseMetadata(videoId: string) {
		isLoading.set(true);
		error.set(null);
		
		try {
			const response = await apiFetch(`/api/videos/metadata/dense/${videoId}/generate`, {
				method: 'POST'
			});
			
			if (!response.ok) {
				throw new Error('Failed to generate dense metadata');
			}
			
			const result = await response.json();
			console.log('Dense metadata generated:', result);
			
			// Reload the video to get the new dense metadata
			const video = get(currentVideo);
			if (video && video.id === videoId) {
				await this.selectVideo(video);
			}
			
			return result;
			
		} catch (err) {
			error.set(err instanceof Error ? err.message : 'Failed to generate dense metadata');
			throw err;
		} finally {
			isLoading.set(false);
		}
	}
};

// Initialize stores
export function initializeVideoPlayer() {
	videoPlayerActions.loadVideos();
	videoPlayerActions.loadContestants();
}