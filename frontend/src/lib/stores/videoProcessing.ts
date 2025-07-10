import { writable, derived } from 'svelte/store';
import { offlineMode } from './main';
import { apiFetch } from '$lib/utils/api';

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
export const loading = writable(false);
export const error = writable<string | null>(null);

// Derived stores
export const videoCount = derived(videos, ($videos) => $videos.length);

export const activeJobs = derived(
	processingJobs,
	($jobs) => $jobs.filter(job => job.status === 'processing')
);

export const completedJobs = derived(
	processingJobs,
	($jobs) => $jobs.filter(job => job.status === 'completed')
);

export const failedJobs = derived(
	processingJobs,
	($jobs) => $jobs.filter(job => job.status === 'failed')
);

// Store instance for backward compatibility
export const videoProcessingStore = {
	subscribe: videos.subscribe,
	set: videos.set,
	update: videos.update,
	processingJobs,
	
	async loadVideos() {
		loading.set(true);
		error.set(null);
		
		try {
			// Try to load from live API first
			const response = await apiFetch('/api/videos');
			if (!response.ok) throw new Error('Failed to load videos from API');
			
			const data = await response.json();
			// If API returns wrapped data with videos property, extract it
			const videoList = data.videos || data;
			videos.set(videoList);
		} catch (err) {
			console.warn('Failed to load videos from API, checking offline mode:', err);
			
			// Check if in offline mode as fallback
			if (offlineMode.get()) {
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

	clearError() {
		error.set(null);
	}
};