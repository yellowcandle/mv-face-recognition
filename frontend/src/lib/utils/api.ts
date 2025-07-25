/**
 * API utility functions for the MV Face Recognition frontend
 */

const API_BASE = '/api';

export interface ApiResponse<T> {
	data?: T;
	error?: string;
	status: number;
}

// TypeScript interfaces for API responses
export interface Video {
	id: string;
	name: string;
	filename: string;
	duration: number;
	uploadedAt: string;
	status: string;
	thumbnail: string;
	width?: number;
	height?: number;
	fps?: number;
	qualities?: {
		[key: string]: {
			filename: string;
			bitrate: number;
			size: number;
		};
	};
}

export interface Contestant {
	id: number;
	name: string;
	nickname: string;
	age: number;
	status: string;
}

export interface BoundingBox {
	x: number;
	y: number;
	width: number;
	height: number;
}

export interface RecognitionResult {
	id: string;
	video_id: string;
	contestant_id: number;
	contestant_name: string;
	contestant_nickname?: string;
	timestamp: number;
	confidence: number;
	bounding_box: BoundingBox;
}

export interface VideoMetadata {
	video_id: string;
	video_name: string;
	duration: number;
	video_info?: {
		filename: string;
		duration: number;
		width?: number;
		height?: number;
		fps?: number;
	};
	processing_info?: {
		processing_interval: number;
		interpolation_enabled: boolean;
		total_processed_frames: number;
		total_interpolated_frames: number;
	};
	contestant_timeline?: Array<{
		contestant_id: number;
		contestant_name: string;
		first_appearance: number;
		last_appearance: number;
		total_appearances: number;
		avg_confidence: number;
	}>;
	timeline?: Array<{
		frame_number: number;
		timestamp: number;
		contestants: Array<{
			id: string;
			contestant_id: number;
			contestant_name: string;
			contestant_nickname?: string;
			confidence: number;
			bounding_box: BoundingBox;
			timestamp: number;
			interpolated?: boolean;
		}>;
	}>;
	total_faces?: number;
	total_contestants?: number;
	confidence_stats?: {
		average: number;
		min: number;
		max: number;
	};
}

export interface SystemStatus {
	status: string;
	version: string;
	uptime: number;
	features: {
		video_streaming: boolean;
		face_recognition: boolean;
		metadata_storage: boolean;
		websocket: boolean;
	};
	stats: {
		total_videos: number;
		total_contestants: number;
		total_recognitions: number;
		processing_queue: number;
	};
}

export interface Analytics {
	overview: {
		total_videos: number;
		total_recognitions: number;
		avg_confidence: number;
		processing_speed: number;
	};
	performance: {
		api_response_time: number;
		video_load_time: number;
		recognition_accuracy: number;
	};
	top_performers: Array<{
		name: string;
		nickname: string;
		appearances: number;
		avg_confidence: number;
	}>;
}

/**
 * Generic API request handler
 */
export async function apiRequest<T>(
	endpoint: string, 
	options: RequestInit = {}
): Promise<ApiResponse<T>> {
	try {
		const response = await fetch(`${API_BASE}${endpoint}`, {
			headers: {
				'Content-Type': 'application/json',
				...options.headers,
			},
			...options,
		});

		const data = await response.json();

		if (!response.ok) {
			return {
				error: data.error || `HTTP ${response.status}`,
				status: response.status
			};
		}

		return {
			data,
			status: response.status
		};
	} catch (error) {
		return {
			error: error instanceof Error ? error.message : 'Network error',
			status: 0
		};
	}
}

/**
 * Get all contestants
 */
export async function getContestants(): Promise<ApiResponse<Contestant[]>> {
	return apiRequest<Contestant[]>('/contestants');
}

/**
 * Get all videos
 */
export async function getVideos(): Promise<ApiResponse<{ videos: Video[] }>> {
	return apiRequest<{ videos: Video[] }>('/videos');
}

/**
 * Get video metadata with correct endpoint pattern
 */
export async function getVideoMetadata(videoId: string): Promise<ApiResponse<VideoMetadata>> {
	return apiRequest<VideoMetadata>(`/videos/${videoId}/metadata`);
}

/**
 * Get recognition results with improved error handling
 */
export async function getRecognitionResults(params: {
	video_id?: string;
	contestant_id?: number;
	min_confidence?: number;
	page?: number;
	limit?: number;
} = {}): Promise<ApiResponse<{
	results: RecognitionResult[];
	total: number;
	page: number;
	limit: number;
}>> {
	const searchParams = new URLSearchParams();
	
	Object.entries(params).forEach(([key, value]) => {
		if (value !== undefined) {
			searchParams.append(key, value.toString());
		}
	});

	const query = searchParams.toString();
	const endpoint = `/recognition/results${query ? `?${query}` : ''}`;
	
	return apiRequest<{
		results: RecognitionResult[];
		total: number;
		page: number;
		limit: number;
	}>(endpoint);
}

/**
 * Get system status
 */
export async function getSystemStatus(): Promise<ApiResponse<SystemStatus>> {
	return apiRequest<SystemStatus>('/system/status');
}

/**
 * Get analytics data
 */
export async function getAnalytics(): Promise<ApiResponse<Analytics>> {
	return apiRequest<Analytics>('/analytics/overview');
}

/**
 * Settings interface for type safety
 */
export interface Settings {
	theme: string;
	language: string;
	processing: {
		confidence_threshold: number;
		max_faces_per_frame: number;
		enable_tracking: boolean;
		processing_interval: number;
		enable_interpolation: boolean;
		smoothing_window: number;
	};
	display: {
		show_confidence: boolean;
		show_bounding_boxes: boolean;
		overlay_opacity: number;
		auto_play_videos: boolean;
		video_quality: string;
	};
	notifications: {
		processing_complete: boolean;
		recognition_alerts: boolean;
		system_updates: boolean;
		email_notifications: boolean;
	};
	privacy: {
		store_analytics: boolean;
		share_usage_data: boolean;
		log_retention_days: number;
	};
	performance: {
		cache_videos: boolean;
		preload_metadata: boolean;
		batch_size: number;
		parallel_processing: boolean;
	};
}

/**
 * Get current settings
 */
export async function getSettings(): Promise<ApiResponse<Settings>> {
	return apiRequest<Settings>('/settings');
}

/**
 * Update settings
 */
export async function updateSettings(settings: Settings): Promise<ApiResponse<{ success: boolean }>> {
	return apiRequest<{ success: boolean }>('/settings', {
		method: 'POST',
		body: JSON.stringify(settings)
	});
}

/**
 * Upload video file with improved type safety
 */
export async function uploadVideo(
	file: File, 
	onProgress?: (progress: number) => void
): Promise<{ success: boolean; videoId?: string; error?: string }> {
	return new Promise((resolve, reject) => {
		const formData = new FormData();
		formData.append('video', file);

		const xhr = new XMLHttpRequest();

		xhr.upload.addEventListener('progress', (event) => {
			if (event.lengthComputable && onProgress) {
				const progress = (event.loaded / event.total) * 100;
				onProgress(progress);
			}
		});

		xhr.addEventListener('load', () => {
			try {
				const response = JSON.parse(xhr.responseText);
				if (xhr.status >= 200 && xhr.status < 300) {
					resolve(response);
				} else {
					resolve({ 
						success: false, 
						error: response.error || `Upload failed with status ${xhr.status}` 
					});
				}
			} catch (error) {
				resolve({ 
					success: false, 
					error: 'Failed to parse server response' 
				});
			}
		});

		xhr.addEventListener('error', () => {
			resolve({ 
				success: false, 
				error: 'Network error during upload' 
			});
		});

		xhr.addEventListener('timeout', () => {
			resolve({ 
				success: false, 
				error: 'Upload timed out' 
			});
		});

		xhr.timeout = 300000; // 5 minute timeout
		xhr.open('POST', `${API_BASE}/videos/upload`);
		xhr.send(formData);
	});
}

/**
 * Format duration in seconds to human readable format
 */
export function formatDuration(seconds: number): string {
	const minutes = Math.floor(seconds / 60);
	const remainingSeconds = Math.floor(seconds % 60);
	return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
}

/**
 * Format timestamp for display
 */
export function formatTimestamp(timestamp: string): string {
	return new Date(timestamp).toLocaleDateString('zh-TW', {
		year: 'numeric',
		month: 'short',
		day: 'numeric',
		hour: '2-digit',
		minute: '2-digit'
	});
}

/**
 * Get confidence color based on score
 */
export function getConfidenceColor(confidence: number): string {
	if (confidence >= 0.8) return '#10b981'; // Green
	if (confidence >= 0.6) return '#f59e0b'; // Yellow
	return '#ef4444'; // Red
}

/**
 * Debounce function for search inputs
 */
export function debounce<T extends (...args: any[]) => any>(
	func: T,
	wait: number
): (...args: Parameters<T>) => void {
	let timeout: NodeJS.Timeout;
	
	return (...args: Parameters<T>) => {
		clearTimeout(timeout);
		timeout = setTimeout(() => func(...args), wait);
	};
}

/**
 * WebSocket connection manager
 */
export class WebSocketManager {
	private ws: WebSocket | null = null;
	private reconnectAttempts = 0;
	private maxReconnectAttempts = 5;
	private reconnectDelay = 1000;

	constructor(private url: string) {}

	connect(onMessage?: (data: any) => void, onError?: (error: Event) => void) {
		try {
			this.ws = new WebSocket(this.url);

			this.ws.onopen = () => {
				this.reconnectAttempts = 0;
				console.log('WebSocket connected');
			};

			this.ws.onmessage = (event) => {
				if (onMessage) {
					try {
						const data = JSON.parse(event.data);
						onMessage(data);
					} catch (error) {
						console.error('Failed to parse WebSocket message:', error);
					}
				}
			};

			this.ws.onclose = () => {
				console.log('WebSocket disconnected');
				this.attemptReconnect(onMessage, onError);
			};

			this.ws.onerror = (error) => {
				console.error('WebSocket error:', error);
				if (onError) onError(error);
			};

		} catch (error) {
			console.error('Failed to create WebSocket:', error);
			if (onError) onError(error as Event);
		}
	}

	private attemptReconnect(onMessage?: (data: any) => void, onError?: (error: Event) => void) {
		if (this.reconnectAttempts < this.maxReconnectAttempts) {
			this.reconnectAttempts++;
			const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
			
			setTimeout(() => {
				console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);
				this.connect(onMessage, onError);
			}, delay);
		}
	}

	send(data: any) {
		if (this.ws && this.ws.readyState === WebSocket.OPEN) {
			this.ws.send(JSON.stringify(data));
		} else {
			console.warn('WebSocket is not connected');
		}
	}

	disconnect() {
		if (this.ws) {
			this.ws.close();
			this.ws = null;
		}
	}
}