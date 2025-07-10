import { writable, derived } from 'svelte/store';
import { apiFetch } from '$lib/utils/api';

// Types
export interface DashboardStats {
	contestants: number;
	videos: number;
	processingJobs: number;
	results: number;
}

export interface SystemStatus {
	chromadb_connected: boolean;
	model_loaded: boolean;
	services_running: boolean;
}

// Stores
export const isLoading = writable(false);
export const error = writable<string | null>(null);
export const dashboardStats = writable<DashboardStats>({
	contestants: 0,
	videos: 0,
	processingJobs: 0,
	results: 0
});
export const systemStatus = writable<SystemStatus>({
	chromadb_connected: false,
	model_loaded: false,
	services_running: false
});

// API connection status
export const apiConnected = writable(false);
export const offlineMode = writable(false);

// Settings interface
export interface AppSettings {
	theme: 'light' | 'dark' | 'auto';
	notifications: boolean;
	autoRefresh: boolean;
	refreshInterval: number;
	maxConcurrentJobs: number;
	videoQuality: 'low' | 'medium' | 'high';
	faceDetectionThreshold: number;
}

// Settings store
export const settings = writable<AppSettings>({
	theme: 'auto',
	notifications: true,
	autoRefresh: true,
	refreshInterval: 30,
	maxConcurrentJobs: 3,
	videoQuality: 'medium',
	faceDetectionThreshold: 0.8
});

// Derived stores
export const isSystemHealthy = derived(
	systemStatus,
	($status) => $status.chromadb_connected && $status.model_loaded && $status.services_running
);

// Health check interval
let healthCheckInterval: number | null = null;

// Mock data for offline mode
const mockSystemStatus = {
	chromadb_connected: true,
	model_loaded: true,
	services_running: true,
	contestant_count: 96,
	video_count: 5,
	processing_jobs: 3
};

// API calls now use environment-aware utility functions

// Actions
export async function initializeApp() {
	isLoading.set(true);
	error.set(null);
	
	try {
		// Try to initialize the application with live API
		await fetchSystemStatus();
		apiConnected.set(true);
		offlineMode.set(false);
	} catch (err) {
		console.warn('API not available, switching to offline mode:', err);
		// Set offline mode with mock data as fallback
		offlineMode.set(true);
		apiConnected.set(false);
		
		// Load mock data
		systemStatus.set({
			chromadb_connected: mockSystemStatus.chromadb_connected,
			model_loaded: mockSystemStatus.model_loaded,
			services_running: mockSystemStatus.services_running
		});
		
		dashboardStats.set({
			contestants: mockSystemStatus.contestant_count,
			videos: mockSystemStatus.video_count,
			processingJobs: mockSystemStatus.processing_jobs,
			results: 2
		});
		
		// Show warning but don't break the app
		error.set('Using offline mode - backend API unavailable');
	} finally {
		isLoading.set(false);
	}
}

export async function fetchSystemStatus() {
	try {
		const data = await apiFetch('/api/system/status');
		
		// Update system status
		systemStatus.set({
			chromadb_connected: data.chromadb_connected,
			model_loaded: data.model_loaded,
			services_running: data.services_running
		});
		
		// Update dashboard stats
		dashboardStats.set({
			contestants: data.contestant_count || 0,
			videos: data.video_count || 0,
			processingJobs: data.processing_jobs || 0,
			results: 0 // Will be updated by other stores
		});
		
		apiConnected.set(true);
	} catch (err) {
		console.error('Failed to fetch system status:', err);
		apiConnected.set(false);
		throw err;
	}
}

export function startHealthChecks(): () => void {
	// Clear any existing interval
	if (healthCheckInterval) {
		clearInterval(healthCheckInterval);
	}
	
	// Start health checks every 30 seconds, but only if not in offline mode
	healthCheckInterval = setInterval(async () => {
		// Skip health checks if in offline mode
		if (offlineMode.get()) {
			return;
		}
		
		try {
			await fetchSystemStatus();
		} catch (err) {
			console.error('Health check failed:', err);
			// Don't switch to offline mode on health check failure
			// Only on initial app load
		}
	}, 30000);
	
	// Return cleanup function
	return () => {
		if (healthCheckInterval) {
			clearInterval(healthCheckInterval);
			healthCheckInterval = null;
		}
	};
}

export function clearError() {
	error.set(null);
}

// Settings functions
export async function loadSettings() {
	try {
		const data = await apiFetch('/api/settings');
		settings.set(data);
	} catch (err) {
		console.error('Failed to load settings:', err);
		// Use default settings if loading fails
		settings.set({
			theme: 'auto',
			notifications: true,
			autoRefresh: true,
			refreshInterval: 30,
			maxConcurrentJobs: 3,
			videoQuality: 'medium',
			faceDetectionThreshold: 0.8
		});
	}
}

export async function updateSettings(newSettings: AppSettings) {
	try {
		const data = await apiFetch('/api/settings', {
			method: 'PUT',
			headers: {
				'Content-Type': 'application/json',
			},
			body: JSON.stringify(newSettings),
		});
		
		settings.set(data);
	} catch (err) {
		console.error('Failed to update settings:', err);
		throw err;
	}
}