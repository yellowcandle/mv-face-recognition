/**
 * Metadata Service
 * Handles local metadata files from @/metadata/ directory
 * Provides structured access to contestant info and video metadata
 */

import { apiFetch } from '$lib/utils/api';

// Cache for metadata
const metadataCache = new Map();

/**
 * Parse CSV content into array of objects
 * @param {string} csvContent - Raw CSV content
 * @returns {Array<Object>} Array of contestant objects
 */
function parseContestantCSV(csvContent) {
	const lines = csvContent.trim().split('\n');
	const headers = lines[0].split(',');
	
	return lines.slice(1).map(line => {
		const values = line.split(',');
		/** @type {{ id?: string, number?: number, name?: string, nickname?: string, age?: number, has_photos?: boolean, has_embedding?: boolean, photo_url?: string, [key: string]: any }} */
		const contestant = {
			has_photos: true,
			has_embedding: true,
			photo_url: ''
		};
		
		headers.forEach((header, index) => {
			const key = header.trim();
			const value = values[index]?.trim() || '';
			
			// Map CSV headers to frontend structure
			switch (key) {
				case '編號':
					contestant.id = value;
					contestant.number = parseInt(value);
					break;
				case '姓名':
					contestant.name = value;
					break;
				case '暱稱':
					contestant.nickname = value;
					break;
				case '年齡':
					contestant.age = parseInt(value);
					break;
				default:
					contestant[key] = value;
			}
		});
		
		// Add additional metadata
		contestant.has_photos = true; // Assume all contestants have photos
		contestant.has_embedding = true; // Assume all contestants have embeddings
		if (contestant.number) {
			contestant.photo_url = `https://pub-271379da2b2840d6936c13ca830fab0d.r2.dev/contestants/${contestant.number}/${contestant.number}-1.jpg`;
		}
		
		return contestant;
	});
}

/**
 * Load contestant information from metadata/contestant_info.csv
 * @returns {Promise<Array<Object>>} Array of contestant objects
 */
export async function loadContestantInfo() {
	const cacheKey = 'contestant_info';
	
	if (metadataCache.has(cacheKey)) {
		return metadataCache.get(cacheKey);
	}
	
	try {
		// Try to load from metadata API endpoint first
		const csvContent = await fetch('/metadata/contestant_info.csv').then(r => r.text());
		const contestants = parseContestantCSV(csvContent);
		
		metadataCache.set(cacheKey, contestants);
		return contestants;
	} catch (error) {
		console.error('Failed to load contestant info from metadata:', error);
		// Fallback to API if metadata file is not accessible
		throw error;
	}
}

/**
 * Load optimized video list metadata
 * @returns {Promise<Object>} Video list with metadata
 */
export async function loadVideoList() {
	const cacheKey = 'videos_list_optimized';
	
	if (metadataCache.has(cacheKey)) {
		return metadataCache.get(cacheKey);
	}
	
	try {
		const videoList = await fetch('/metadata/optimized/videos_list_optimized.json').then(r => r.json());
		
		// Transform to match expected frontend format
		const transformedVideos = Object.entries(videoList.videos || {}).map(([title, data]) => ({
			id: extractVideoId(data.video_info.filename),
			name: title,
			filename: data.video_info.filename,
			size: data.video_info.file_size_mb * 1024 * 1024, // Convert MB to bytes
			created_at: new Date(data.processing_date).getTime() / 1000,
			has_metadata: data.has_detailed_metadata,
			stream_url: `https://pub-271379da2b2840d6936c13ca830fab0d.r2.dev/${data.video_info.filename}`,
			duration_seconds: data.video_info.duration_seconds,
			fps: data.video_info.fps,
			width: data.video_info.width,
			height: data.video_info.height,
			face_count: data.recognition_summary.total_faces_detected,
			unique_contestants: data.recognition_summary.unique_contestants,
			metadata_endpoints: data.metadata_endpoints
		}));
		
		metadataCache.set(cacheKey, transformedVideos);
		return transformedVideos;
	} catch (error) {
		console.error('Failed to load video list from metadata:', error);
		throw error;
	}
}

/**
 * Extract video ID from filename (assumes pattern: "ID-Title.mp4")
 * @param {string} filename 
 * @returns {string} Video ID
 */
function extractVideoId(filename) {
	// New format: "video-1.mp4", "video-2.mp4", etc.
	const newMatch = filename.match(/^video-(\d+)\.mp4$/);
	if (newMatch) {
		return newMatch[1];
	}
	
	// Fallback for old format: "1-Title.mp4"
	const oldMatch = filename.match(/^(\d+)-/);
	if (oldMatch) {
		return oldMatch[1];
	}
	
	// Generic fallback
	return filename.replace('.mp4', '');
}

/**
 * Load optimized metadata for a specific video
 * @param {string} videoId - Video ID
 * @param {boolean} dense - Whether to load dense metadata
 * @returns {Promise<Object>} Video metadata
 */
export async function loadVideoMetadata(videoId, dense = false) {
	const cacheKey = `video_metadata_${videoId}_${dense ? 'dense' : 'basic'}`;
	
	if (metadataCache.has(cacheKey)) {
		return metadataCache.get(cacheKey);
	}
	
	try {
		const filename = dense ? `metadata_dense_${videoId}.json` : `metadata_${videoId}.json`;
		const metadata = await fetch(`/metadata/optimized/${filename}`).then(r => r.json());
		
		metadataCache.set(cacheKey, metadata);
		return metadata;
	} catch (error) {
		console.error(`Failed to load video metadata for ${videoId}:`, error);
		throw error;
	}
}

/**
 * Get contestant by ID or nickname
 * @param {string|number} identifier - Contestant ID, number, or nickname
 * @returns {Promise<Object|null>} Contestant object or null
 */
export async function getContestant(identifier) {
	try {
		const contestants = await loadContestantInfo();
		
		return contestants.find(c => 
			c.id === String(identifier) ||
			c.number === Number(identifier) ||
			c.nickname === identifier ||
			c.name === identifier
		) || null;
	} catch (error) {
		console.error('Failed to get contestant:', error);
		return null;
	}
}

/**
 * Search contestants by query
 * @param {string} query - Search query
 * @returns {Promise<Array>} Filtered contestants
 */
export async function searchContestants(query) {
	try {
		const contestants = await loadContestantInfo();
		
		if (!query) return contestants;
		
		const normalizedQuery = query.toLowerCase();
		return contestants.filter(c =>
			c.name.toLowerCase().includes(normalizedQuery) ||
			c.nickname.toLowerCase().includes(normalizedQuery)
		);
	} catch (error) {
		console.error('Failed to search contestants:', error);
		return [];
	}
}

/**
 * Clear metadata cache
 */
export function clearMetadataCache() {
	metadataCache.clear();
}

/**
 * Check if metadata files are available
 * @returns {Promise<boolean>} Whether metadata is accessible
 */
export async function isMetadataAvailable() {
	try {
		await fetch('/metadata/contestant_info.csv', { method: 'HEAD' });
		await fetch('/metadata/optimized/videos_list_optimized.json', { method: 'HEAD' });
		return true;
	} catch (error) {
		return false;
	}
}