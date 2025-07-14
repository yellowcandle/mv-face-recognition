/**
 * API utility functions for the MV Face Recognition frontend
 */

const API_BASE = '/api';

export interface ApiResponse<T> {
	data?: T;
	error?: string;
	status: number;
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
export async function getContestants() {
	return apiRequest('/contestants');
}

/**
 * Get all videos
 */
export async function getVideos() {
	return apiRequest('/videos');
}

/**
 * Get video metadata
 */
export async function getVideoMetadata(videoId: string) {
	return apiRequest(`/videos/${videoId}/metadata`);
}

/**
 * Get recognition results
 */
export async function getRecognitionResults(params: {
	video_id?: string;
	contestant_id?: number;
	min_confidence?: number;
	page?: number;
	limit?: number;
} = {}) {
	const searchParams = new URLSearchParams();
	
	Object.entries(params).forEach(([key, value]) => {
		if (value !== undefined) {
			searchParams.append(key, value.toString());
		}
	});

	const query = searchParams.toString();
	const endpoint = `/recognition/results${query ? `?${query}` : ''}`;
	
	return apiRequest(endpoint);
}

/**
 * Get system status
 */
export async function getSystemStatus() {
	return apiRequest('/system/status');
}

/**
 * Get analytics data
 */
export async function getAnalytics() {
	return apiRequest('/analytics/overview');
}

/**
 * Upload video file
 */
export async function uploadVideo(file: File, onProgress?: (progress: number) => void) {
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
			if (xhr.status >= 200 && xhr.status < 300) {
				resolve(JSON.parse(xhr.responseText));
			} else {
				reject(new Error(`Upload failed: ${xhr.status}`));
			}
		});

		xhr.addEventListener('error', () => {
			reject(new Error('Upload failed'));
		});

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