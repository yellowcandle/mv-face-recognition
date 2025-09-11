import { writable, derived, get } from 'svelte/store';
import { offlineMode } from './main';
import { apiFetch } from '$lib/utils/api';
import type { RecognitionResult } from '$lib/types/api';

// API calls now use environment-aware utility functions

// Types
export interface ProcessingJob {
	job_id: string;
	video_id: string;
	status: 'pending' | 'processing' | 'completed' | 'failed';
	created_at: string;
	completed_at?: string;
	progress?: number;
	error_message?: string;
}

export interface Video {
	id: string;
	name: string;
	filename: string;
	path: string;
	size: number;
	duration_seconds: number;
	fps: number;
	width: number;
	height: number;
	frame_count: number;
	created_at: string;
}

// Stores
export const videos = writable<Video[]>([]);
export const processingJobs = writable<ProcessingJob[]>([]);
export const recognitionResults = writable<RecognitionResult[]>([]);
export const loading = writable(false);
export const error = writable<string | null>(null);

// Derived stores
export const videoCount = derived(videos, ($videos) => $videos ? $videos.length : 0);

export const activeJobs = derived(
	processingJobs,
	($jobs) => $jobs ? $jobs.filter(job => job.status === 'processing') : []
);

export const completedJobs = derived(
	processingJobs,
	($jobs) => $jobs ? $jobs.filter(job => job.status === 'completed') : []
);

export const failedJobs = derived(
	processingJobs,
	($jobs) => $jobs ? $jobs.filter(job => job.status === 'failed') : []
);

// Store instance for backward compatibility
export const videoProcessingStore = {
	subscribe: videos.subscribe,
	set: videos.set,
	update: videos.update,
	
	// Expose stores as properties for component compatibility
	processingJobs,
	recognitionResults,
	isLoading: loading,
	error,
	
	async loadVideos() {
		loading.set(true);
		error.set(null);
		
		try {
			// Try to load from live API first
			const data = await apiFetch('/api/videos');
			// If API returns wrapped data with videos property, extract it
			const videoList = data.videos || data;
			videos.set(videoList);
		} catch (err) {
			console.warn('Failed to load videos from API, checking offline mode:', err);
			
			// Check if in offline mode as fallback
			if (get(offlineMode)) {
				// Return mock videos data
				const mockVideos: Video[] = [
					{
						id: '1',
						name: '《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅',
						filename: '1-《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅.mp4',
						path: '/source/videos/1-《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅.mp4',
						size: 234567890,
						duration_seconds: 240,
						fps: 30,
						width: 1920,
						height: 1080,
						frame_count: 7200,
						created_at: new Date().toISOString()
					},
					{
						id: '2',
						name: '《全民造星IV》主題曲 《前傳》MV 2021夏の次部曲：始発の駅',
						filename: '2-《全民造星IV》主題曲 《前傳》MV 2021夏の次部曲：始発の駅.mp4',
						path: '/source/videos/2-《全民造星IV》主題曲 《前傳》MV 2021夏の次部曲：始発の駅.mp4',
						size: 345678901,
						duration_seconds: 180,
						fps: 30,
						width: 1920,
						height: 1080,
						frame_count: 5400,
						created_at: new Date().toISOString()
					}
				];
				videos.set(mockVideos);
			} else {
				error.set(err instanceof Error ? err.message : 'Failed to load videos');
			}
		} finally {
			loading.set(false);
		}
	},

	async getProcessingJobs() {
		try {
			// Mock processing jobs for demo
			const mockJobs: ProcessingJob[] = [
				{
					job_id: '1',
					video_id: '1',
					status: 'completed',
					created_at: new Date(Date.now() - 1000 * 60 * 30).toISOString(), // 30 minutes ago
					completed_at: new Date(Date.now() - 1000 * 60 * 10).toISOString() // 10 minutes ago
				},
				{
					job_id: '2',
					video_id: '2',
					status: 'completed',
					created_at: new Date(Date.now() - 1000 * 60 * 60).toISOString(), // 1 hour ago
					completed_at: new Date(Date.now() - 1000 * 60 * 45).toISOString() // 45 minutes ago
				},
				{
					job_id: '3',
					video_id: '3',
					status: 'processing',
					created_at: new Date(Date.now() - 1000 * 60 * 5).toISOString(), // 5 minutes ago
					progress: 75
				}
			];
			processingJobs.set(mockJobs);
		} catch (err) {
			console.error('Failed to load processing jobs:', err);
		}
	},

	async getRecognitionResults(videoId?: string, contestantId?: string) {
		try {
			loading.set(true);
			
			// Build query parameters
			const params = new URLSearchParams();
			if (videoId) params.append('video_id', videoId);
			if (contestantId) params.append('contestant_id', contestantId);
			
			const queryString = params.toString();
			const endpoint = `/api/recognition/results${queryString ? `?${queryString}` : ''}`;
			
			try {
				const data = await apiFetch(endpoint);
				// Handle the new API response format: { results: [], total: number, filters: {} }
				const results = data.results || data;
				recognitionResults.set(Array.isArray(results) ? results : []);
			} catch (err) {
				console.warn('Failed to load recognition results from API, using mock data:', err);
				
				// Provide mock recognition results
				const mockResults: RecognitionResult[] = [
					{
						confidence: 0.85,
						video_id: '1',
						contestant_id: '1',
						timestamp: 45.2,
						bounding_box: { x: 100, y: 50, width: 150, height: 200 }
					},
					{
						confidence: 0.92,
						video_id: '1',
						contestant_id: '2',
						timestamp: 67.8,
						bounding_box: { x: 300, y: 75, width: 140, height: 180 }
					},
					{
						confidence: 0.78,
						video_id: '2',
						contestant_id: '1',
						timestamp: 23.5,
						bounding_box: { x: 200, y: 100, width: 160, height: 210 }
					}
				];
				
				// Apply filters if provided
				let filteredResults = mockResults;
				if (videoId) {
					filteredResults = filteredResults.filter(r => r.video_id === videoId);
				}
				if (contestantId) {
					filteredResults = filteredResults.filter(r => r.contestant_id === contestantId);
				}
				
				recognitionResults.set(filteredResults);
			}
		} catch (err) {
			console.error('Failed to load recognition results:', err);
			error.set(err instanceof Error ? err.message : 'Failed to load recognition results');
		} finally {
			loading.set(false);
		}
	},

	clearError() {
		error.set(null);
	}
};
