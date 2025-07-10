// API Configuration utility for environment-aware base URL handling

/**
 * Get the appropriate API base URL based on the current environment
 * In development: Use relative URLs to leverage Vite proxy
 * In production: Use the full Worker API URL
 */
export function getApiBaseUrl(): string {
	// Check if we're in development mode
	const isDevelopment = import.meta.env.DEV;
	
	if (isDevelopment) {
		// Use relative URLs in development to leverage Vite proxy
		// This will proxy to http://127.0.0.1:8000 as configured in vite.config.js
		return '';
	} else {
		// Use full Worker API URL in production
		return 'https://mv-face-recognition-api.herballemon.workers.dev';
	}
}

/**
 * Create a full API URL for the given endpoint
 */
export function apiUrl(endpoint: string): string {
	const baseUrl = getApiBaseUrl();
	const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
	return `${baseUrl}${cleanEndpoint}`;
}

/**
 * Enhanced fetch with error handling and fallback logic
 */
export async function apiFetch(endpoint: string, options?: RequestInit): Promise<Response> {
	const url = apiUrl(endpoint);
	
	try {
		const response = await fetch(url, options);
		
		// Check if we got HTML instead of JSON (common error case)
		const contentType = response.headers.get('content-type');
		if (contentType && contentType.includes('text/html') && response.status === 200) {
			throw new Error('Received HTML instead of JSON - API endpoint may be incorrect');
		}
		
		return response;
	} catch (error) {
		console.error(`API call failed for ${url}:`, error);
		throw error;
	}
}