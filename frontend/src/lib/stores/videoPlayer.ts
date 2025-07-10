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
	duration_seconds?: number;
	fps?: number;
	width?: number;
	height?: number;
	face_count?: number;
	unique_contestants?: number;
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
	processing_timestamp?: string;
	total_frames?: number;
	frames_with_faces?: number;
	total_face_detections?: number;
	unique_contestants?: number;
	recognition_summary: {
		unique_contestants: number;
		faces_detected: number;
		faces_recognized: number;
		recognition_rate: number;
		processing_time_seconds?: number;
		frames_processed?: number;
	};
	contestant_timeline: Record<string, ContestantAppearance>;
	frame_data?: Array<{
		timestamp: number;
		frame_number: number;
		faces: Array<{
			contestant: string;
			confidence: number;
			bbox: [number, number, number, number];
			landmarks?: number[][];
		}>;
	}>;
}

export interface ContestantAppearance {
	total_appearances: number;
	avg_confidence: number;
	max_confidence: number;
	first_appearance_time: number;
	last_appearance_time: number;
	frame_appearances?: Array<{
		timestamp: number;
		confidence: number;
		bbox: [number, number, number, number];
		landmarks?: number[][];
	}>;
	detailed_timeline?: Array<{
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
			// Use frame_appearances if available, otherwise fall back to detailed_timeline
			const appearances = timeline.frame_appearances || timeline.detailed_timeline || [];
			const relevantAppearances = appearances.filter(
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
			// Use frame_appearances if available, otherwise fall back to detailed_timeline
			const appearances = timeline.frame_appearances || timeline.detailed_timeline || [];
			appearances.forEach(appearance => {
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
			const videos = await apiFetch('/api/videos/processed/list');
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
			const contestants = await apiFetch('/api/contestants/');
			// Add photo URLs if available
			const contestantsWithPhotos = contestants.map((contestant: ContestantInfo) => ({
				...contestant,
				photo_url: contestant.has_photos ? `/photos/${contestant.number}-1.jpg` : null
			}));
			allContestants.set(contestantsWithPhotos);
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
		duration.set(video.duration_seconds || 0);
		isPlaying.set(false);
		
		// Load metadata for the selected video
		if (video.has_metadata) {
			try {
				const metadata = await apiFetch(`/api/videos/metadata/${video.id}`);
				currentMetadata.set(metadata);
				
				// Update duration from metadata if available
				if (metadata && video.duration_seconds) {
					duration.set(video.duration_seconds);
				}
			} catch (err) {
				console.error('Failed to load video metadata:', err);
				error.set('Failed to load face recognition data');
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

			async loadFaceData(videoId: string, timestamp?: number) {
		try {
			const url = timestamp !== undefined 
				? `/api/videos/metadata/dense/${videoId}?timestamp=${timestamp}`
				: `/api/videos/metadata/dense/${videoId}`;
			
			const faceData = await apiFetch(url);
			return faceData;
		} catch (err) {
			console.error('Failed to load face data:', err);
			throw err;
		}
	},

	async getContestantTimeline(videoId: string, contestantName: string) {
		try {
			const timeline = await apiFetch(`/api/videos/metadata/${videoId}`);
			// Extract the specific contestant's timeline from the metadata
			const metadata = timeline;
			return metadata?.contestant_timeline?.[contestantName] || null;
		} catch (err) {
			console.error('Failed to load contestant timeline:', err);
			throw err;
		}
	}
};

// Initialize stores
export function initializeVideoPlayer() {
	videoPlayerActions.loadVideos();
	videoPlayerActions.loadContestants();
}