import { writable, derived, get } from 'svelte/store';
import { apiFetch } from '$lib/utils/api';
import { offlineMode } from './main.js';
import { loadVideoList, loadVideoMetadata, isMetadataAvailable, loadContestantInfo } from '$lib/services/metadataService';

// Store states
export const availableVideos = writable([]);
export const allContestants = writable([]);
export const currentVideo = writable(null);
export const currentMetadata = writable(null);
export const isLoading = writable(false);
export const error = writable(null);

// Player state
export const currentTime = writable(0);
export const duration = writable(0);
export const isPlaying = writable(false);
export const volume = writable(1);
export const isMuted = writable(false);

// UI state
export const selectedContestant = writable(null);
export const showTimeline = writable(true);
export const timelineHeight = writable(100);

// Derived stores
export const activeContestants = derived(
	[currentMetadata, currentTime],
	([$metadata, $currentTime]) => {
		if (!$metadata?.contestant_timeline) return [];
		
		const active = [];
		
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
		
		const markers = [];
		
		// Create markers for face detection events
		const timeMap = new Map();
		
		Object.entries($metadata.contestant_timeline).forEach(([name, timeline]) => {
			// Use frame_appearances if available, otherwise fall back to detailed_timeline
			const appearances = timeline.frame_appearances || timeline.detailed_timeline || [];
			appearances.forEach(appearance => {
				const time = Math.round(appearance.timestamp);
				if (!timeMap.has(time)) {
					timeMap.set(time, []);
				}
				timeMap.get(time).push(name);
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
			// Try to load from local metadata first
			const metadataAvailable = await isMetadataAvailable();
			
			if (metadataAvailable) {
				console.log('Loading videos from local metadata...');
				const videos = await loadVideoList();
				availableVideos.set(videos);
				return;
			}
			
			// Fallback to live API
			console.log('Loading videos from API...');
			const videos = await apiFetch('/api/videos/processed/list');
			availableVideos.set(videos);
		} catch (err) {
			console.warn('Failed to load videos, checking offline mode:', err);
			if (get(offlineMode)) {
				// Use mock videos
				const mockVideos = [
					{
						id: '1',
						name: 'Video 1: Zenkoku Zosei IV - Prologue MV 1',
						filename: 'video-1.mp4',
						size: 257949696,
						created_at: Date.now() / 1000,
						has_metadata: true,
						stream_url: 'https://mv.herballemon.dev/videos/video-1.mp4',
						duration_seconds: 240,
						fps: 30,
						width: 1920,
						height: 1080,
						face_count: 156,
						unique_contestants: 8
					},
					{
						id: '2',
						name: 'Video 2: Zenkoku Zosei IV - Prologue MV 2',
						filename: 'video-2.mp4',
						size: 300944896,
						created_at: Date.now() / 1000 - 3600,
						has_metadata: true,
						stream_url: 'https://mv.herballemon.dev/videos/video-2.mp4',
						duration_seconds: 180,
						fps: 30,
						width: 1920,
						height: 1080,
						face_count: 89,
						unique_contestants: 5
					}
				];
				availableVideos.set(mockVideos);
			} else {
				error.set(err instanceof Error ? err.message : 'Failed to load videos');
			}
		} finally {
			isLoading.set(false);
		}
	},

	async loadContestants() {
		isLoading.set(true);
		error.set(null);
		
		try {
			// Try to load from local metadata first
			const metadataAvailable = await isMetadataAvailable();
			
			if (metadataAvailable) {
				console.log('Loading contestants from local metadata...');
				const contestants = await loadContestantInfo();
				allContestants.set(contestants);
				return;
			}
			
			// Fallback to live API
			console.log('Loading contestants from API...');
			const contestants = await apiFetch('/api/contestants/');
			// Add photo URLs if available
			const contestantsWithPhotos = contestants.map((contestant) => ({
				...contestant,
				photo_url: contestant.has_photos ? `/photos/${contestant.number}-1.jpg` : null
			}));
			allContestants.set(contestantsWithPhotos);
		} catch (err) {
			console.warn('Failed to load contestants, checking offline mode:', err);
			if (get(offlineMode)) {
				// Use mock contestants
				const mockContestants = [
					{
						id: '1',
						number: 1,
						name: '蘇雅琳',
						nickname: 'Ivy So',
						age: 20,
						has_photos: true,
						has_embedding: true,
						photo_url: '/photos/1-1.jpg'
					},
					{
						id: '2',
						number: 2,
						name: '黃雅慧',
						nickname: '咖喱',
						age: 27,
						has_photos: true,
						has_embedding: true,
						photo_url: '/photos/2-1.jpg'
					}
				];
				allContestants.set(mockContestants);
			} else {
				error.set(err instanceof Error ? err.message : 'Failed to load contestants');
			}
		} finally {
			isLoading.set(false);
		}
	},

	    async selectVideo(video) {
        if (!video || !video.id) {
            currentVideo.set(null);
            currentMetadata.set(null);
            return;
        }

        isLoading.set(true);
        error.set(null);

        try {
            // First, fetch the metadata for the selected video
            const metadata = await (async () => {
                const metadataAvailable = await isMetadataAvailable();
                if (metadataAvailable) {
                    console.log(`Loading metadata for video ${video.id} from local files...`);
                    return await loadVideoMetadata(video.id, false);
                }
                console.log(`Loading metadata for video ${video.id} from API...`);
                return await apiFetch(`/api/videos/metadata/${video.id}`);
            })();

            // Once metadata is successfully fetched, update all related stores
            currentMetadata.set(metadata);
            currentVideo.set({
                ...video,
                // Ensure stream_url is present, fallback to a default if needed
                stream_url: video.stream_url || '', 
            });
            currentTime.set(0);
            duration.set(video.duration_seconds || 0);
            isPlaying.set(false);

        } catch (err) {
            console.error('Failed to load video metadata:', err);
            error.set('Failed to load video data. Please try again.');
            // Clear video selection on error to prevent broken state
            currentVideo.set(null);
            currentMetadata.set(null);
        } finally {
            isLoading.set(false);
        }
    },

	updateCurrentTime(time) {
		currentTime.set(time);
	},

	updateDuration(dur) {
		duration.set(dur);
	},

	setPlaying(playing) {
		isPlaying.set(playing);
	},

	setVolume(vol) {
		volume.set(Math.max(0, Math.min(1, vol)));
	},

	toggleMute() {
		isMuted.update(muted => !muted);
	},

	selectContestant(contestant) {
		selectedContestant.set(contestant);
	},

	seekToContestant(contestantName) {
		const metadata = get(currentMetadata);
		if (metadata?.contestant_timeline[contestantName]) {
			const firstAppearance = metadata.contestant_timeline[contestantName].first_appearance_time;
			currentTime.set(firstAppearance);
			// Trigger video seek - this will be handled by the video component
			return firstAppearance;
		}
		return null;
	},

	getContestantAppearances(contestantName) {
		const metadata = get(currentMetadata);
		return metadata?.contestant_timeline[contestantName] || null;
	},

	clearError() {
		error.set(null);
	},

	async loadFaceData(videoId, timestamp) {
		try {
			// Try to load from local metadata first
			const metadataAvailable = await isMetadataAvailable();
			
			if (metadataAvailable) {
				console.log(`Loading dense face data for video ${videoId} from local files...`);
				const faceData = await loadVideoMetadata(videoId, true);
				
				// If timestamp is provided, filter the data for that timestamp
				if (timestamp !== undefined && faceData.frame_data) {
					// Find frames near the timestamp (within 1 second tolerance)
					const filteredFrames = faceData.frame_data.filter(frame => 
						Math.abs(frame.timestamp - timestamp) <= 1.0
					);
					return { ...faceData, frame_data: filteredFrames };
				}
				
				return faceData;
			} else {
				console.log(`Loading dense face data for video ${videoId} from API...`);
				const url = timestamp !== undefined 
					? `/api/videos/metadata/dense/${videoId}?timestamp=${timestamp}`
					: `/api/videos/metadata/dense/${videoId}`;
				
				const faceData = await apiFetch(url);
				return faceData;
			}
		} catch (err) {
			console.error('Failed to load face data:', err);
			throw err;
		}
	},

	async getContestantTimeline(videoId, contestantName) {
		try {
			// Try to load from local metadata first
			const metadataAvailable = await isMetadataAvailable();
			let metadata;
			
			if (metadataAvailable) {
				console.log(`Loading contestant timeline for video ${videoId} from local files...`);
				metadata = await loadVideoMetadata(videoId, false);
			} else {
				console.log(`Loading contestant timeline for video ${videoId} from API...`);
				metadata = await apiFetch(`/api/videos/metadata/${videoId}`);
			}
			
			// Extract the specific contestant's timeline from the metadata
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