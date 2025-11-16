/**
 * API utility for environment-aware URL generation
 * Handles development vs production API endpoint routing
 */
import { logger } from './logger';

const PRODUCTION_API_BASE = 'https://mv-face-recognition-api.herballemon.workers.dev';

/**
 * Get the appropriate API URL based on environment
 * @param endpoint - The API endpoint path (e.g., '/api/videos/processed/list')
 * @returns Complete URL for the API call
 */
export function getApiUrl(endpoint: string): string {
  // In development, use relative URLs so Vite proxy can handle routing
  if (import.meta.env.DEV) {
    return endpoint;
  }
  
  // In production, use absolute URLs to the Worker API
  return `${PRODUCTION_API_BASE}${endpoint}`;
}

/**
 * Enhanced fetch wrapper with better error handling for HTML responses
 * @param endpoint - The API endpoint path
 * @param options - Fetch options
 * @returns Promise with parsed JSON response
 */
export async function apiFetch(endpoint: string, options?: RequestInit): Promise<any> {
  const url = getApiUrl(endpoint);
  
  try {
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
      ...options,
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const contentType = response.headers.get('content-type');
    if (!contentType || !contentType.includes('application/json')) {
      const text = await response.text();
      if (text.includes('<!DOCTYPE')) {
        throw new Error(`API returned HTML instead of JSON. This usually means the API endpoint is not available or there's a routing issue. URL: ${url}`);
      }
      throw new Error(`API returned non-JSON response: ${contentType}`);
    }

    return await response.json();
  } catch (error) {
    logger.error('API call failed', { url, error: error.message });
    throw error;
  }
}