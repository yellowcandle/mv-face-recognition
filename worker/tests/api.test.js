import { describe, it, expect, beforeEach, vi } from 'vitest';

// Mock the worker environment
const mockEnv = {
	METADATA_KV: {
		get: vi.fn(),
		put: vi.fn(),
		list: vi.fn()
	},
	VIDEOS_BUCKET: {
		get: vi.fn(),
		put: vi.fn(),
		list: vi.fn(),
		head: vi.fn()
	}
};

// Mock Request and Response
global.Request = class MockRequest {
	constructor(url, options = {}) {
		this.url = url;
		this.method = options.method || 'GET';
		this.headers = new Map(Object.entries(options.headers || {}));
	}
	
	header(name) {
		return this.headers.get(name.toLowerCase());
	}
};

global.Response = class MockResponse {
	constructor(body, options = {}) {
		this.body = body;
		this.status = options.status || 200;
		this.statusText = options.statusText || 'OK';
		this.headers = new Map(Object.entries(options.headers || {}));
	}
	
	static json(data, options = {}) {
		return new MockResponse(JSON.stringify(data), {
			...options,
			headers: {
				'Content-Type': 'application/json',
				...options.headers
			}
		});
	}
};

describe('Worker API', () => {
	let worker;

	beforeEach(async () => {
		// Reset mocks
		vi.clearAllMocks();
		
		// Import worker after mocking globals
		worker = await import('../index.js');
	});

	describe('System Status API', () => {
		it('should return healthy status', async () => {
			const request = new Request('https://worker.dev/api/system/status');
			const response = await worker.default.fetch(request, mockEnv);
			
			expect(response.status).toBe(200);
			const data = JSON.parse(response.body);
			expect(data.status).toBe('healthy');
			expect(data.features).toBeDefined();
			expect(data.stats).toBeDefined();
		});

		it('should include feature flags', async () => {
			const request = new Request('https://worker.dev/api/system/status');
			const response = await worker.default.fetch(request, mockEnv);
			
			const data = JSON.parse(response.body);
			expect(data.features.video_streaming).toBe(true);
			expect(data.features.face_recognition).toBe(true);
			expect(data.features.metadata_storage).toBe(true);
			expect(data.features.websocket).toBe(true);
		});
	});

	describe('Videos API', () => {
		it('should return list of videos', async () => {
			const request = new Request('https://worker.dev/api/videos');
			const response = await worker.default.fetch(request, mockEnv);
			
			expect(response.status).toBe(200);
			const data = JSON.parse(response.body);
			expect(Array.isArray(data.videos)).toBe(true);
		});

		it('should handle video streaming with range requests', async () => {
			const request = new Request('https://worker.dev/videos/test-video.mp4', {
				headers: { 'Range': 'bytes=0-1023' }
			});

			// Mock R2 response
			mockEnv.VIDEOS_BUCKET.get.mockResolvedValue({
				body: new ArrayBuffer(1024),
				httpMetadata: {
					contentType: 'video/mp4',
					contentLength: 1048576
				}
			});

			const response = await worker.default.fetch(request, mockEnv);
			
			expect(response.status).toBe(206); // Partial Content
			expect(mockEnv.VIDEOS_BUCKET.get).toHaveBeenCalledWith(
				'test-video.mp4',
				expect.objectContaining({
					range: { offset: 0, length: 1024 }
				})
			);
		});

		it('should handle video metadata requests', async () => {
			const mockMetadata = {
				video_info: { duration: 120, width: 1920, height: 1080 },
				processing_summary: { total_recognitions: 45 }
			};

			mockEnv.METADATA_KV.get.mockResolvedValue(JSON.stringify(mockMetadata));

			const request = new Request('https://worker.dev/api/videos/test-video/metadata');
			const response = await worker.default.fetch(request, mockEnv);
			
			expect(response.status).toBe(200);
			const data = JSON.parse(response.body);
			expect(data.video_info.duration).toBe(120);
		});

		it('should return 404 for non-existent video metadata', async () => {
			mockEnv.METADATA_KV.get.mockResolvedValue(null);

			const request = new Request('https://worker.dev/api/videos/non-existent/metadata');
			const response = await worker.default.fetch(request, mockEnv);
			
			expect(response.status).toBe(404);
		});
	});

	describe('Contestants API', () => {
		it('should return contestants list', async () => {
			const mockContestants = [
				{ id: 1, name: '張三', nickname: 'Ace' },
				{ id: 2, name: '李四', nickname: 'Ling' }
			];

			mockEnv.METADATA_KV.get.mockResolvedValue(JSON.stringify({
				contestants: mockContestants
			}));

			const request = new Request('https://worker.dev/api/contestants');
			const response = await worker.default.fetch(request, mockEnv);
			
			expect(response.status).toBe(200);
			const data = JSON.parse(response.body);
			expect(data.contestants).toHaveLength(2);
			expect(data.contestants[0].name).toBe('張三');
		});

		it('should handle missing contestants data', async () => {
			mockEnv.METADATA_KV.get.mockResolvedValue(null);

			const request = new Request('https://worker.dev/api/contestants');
			const response = await worker.default.fetch(request, mockEnv);
			
			expect(response.status).toBe(200);
			const data = JSON.parse(response.body);
			expect(data.contestants).toEqual([]);
		});
	});

	describe('Recognition Results API', () => {
		it('should return recognition results with pagination', async () => {
			const mockResults = [
				{ id: '1', video_id: 'video1', contestant_name: '張三', confidence: 0.95 },
				{ id: '2', video_id: 'video1', contestant_name: '李四', confidence: 0.88 }
			];

			const request = new Request('https://worker.dev/api/recognition/results?page=1&limit=10');
			const response = await worker.default.fetch(request, mockEnv);
			
			expect(response.status).toBe(200);
			const data = JSON.parse(response.body);
			expect(data.results).toBeDefined();
			expect(data.pagination).toBeDefined();
			expect(data.pagination.page).toBe(1);
			expect(data.pagination.limit).toBe(10);
		});

		it('should filter results by confidence', async () => {
			const request = new Request('https://worker.dev/api/recognition/results?min_confidence=0.8');
			const response = await worker.default.fetch(request, mockEnv);
			
			expect(response.status).toBe(200);
			const data = JSON.parse(response.body);
			// All results should have confidence >= 0.8
			data.results.forEach(result => {
				expect(result.confidence).toBeGreaterThanOrEqual(0.8);
			});
		});

		it('should filter results by video ID', async () => {
			const request = new Request('https://worker.dev/api/recognition/results?video_id=video1');
			const response = await worker.default.fetch(request, mockEnv);
			
			expect(response.status).toBe(200);
			const data = JSON.parse(response.body);
			data.results.forEach(result => {
				expect(result.video_id).toBe('video1');
			});
		});
	});

	describe('Static Assets', () => {
		it('should serve embedded frontend assets', async () => {
			const request = new Request('https://worker.dev/');
			const response = await worker.default.fetch(request, mockEnv);
			
			expect(response.status).toBe(200);
			expect(response.headers.get('Content-Type')).toContain('text/html');
		});

		it('should serve CSS assets', async () => {
			const request = new Request('https://worker.dev/_app/immutable/assets/app.css');
			const response = await worker.default.fetch(request, mockEnv);
			
			expect(response.status).toBe(200);
			expect(response.headers.get('Content-Type')).toContain('text/css');
		});

		it('should serve JavaScript assets', async () => {
			const request = new Request('https://worker.dev/_app/immutable/chunks/app.js');
			const response = await worker.default.fetch(request, mockEnv);
			
			expect(response.status).toBe(200);
			expect(response.headers.get('Content-Type')).toContain('application/javascript');
		});

		it('should return 404 for non-existent assets', async () => {
			const request = new Request('https://worker.dev/non-existent-file.js');
			const response = await worker.default.fetch(request, mockEnv);
			
			expect(response.status).toBe(404);
		});
	});

	describe('CORS Headers', () => {
		it('should include CORS headers in API responses', async () => {
			const request = new Request('https://worker.dev/api/system/status');
			const response = await worker.default.fetch(request, mockEnv);
			
			expect(response.headers.get('Access-Control-Allow-Origin')).toBe('*');
			expect(response.headers.get('Access-Control-Allow-Methods')).toContain('GET');
		});

		it('should handle OPTIONS preflight requests', async () => {
			const request = new Request('https://worker.dev/api/videos', {
				method: 'OPTIONS'
			});
			const response = await worker.default.fetch(request, mockEnv);
			
			expect(response.status).toBe(200);
			expect(response.headers.get('Access-Control-Allow-Origin')).toBe('*');
		});
	});

	describe('Error Handling', () => {
		it('should handle KV storage errors gracefully', async () => {
			mockEnv.METADATA_KV.get.mockRejectedValue(new Error('KV Error'));

			const request = new Request('https://worker.dev/api/contestants');
			const response = await worker.default.fetch(request, mockEnv);
			
			expect(response.status).toBe(500);
			const data = JSON.parse(response.body);
			expect(data.error).toBeDefined();
		});

		it('should handle R2 storage errors gracefully', async () => {
			mockEnv.VIDEOS_BUCKET.get.mockRejectedValue(new Error('R2 Error'));

			const request = new Request('https://worker.dev/videos/test-video.mp4');
			const response = await worker.default.fetch(request, mockEnv);
			
			expect(response.status).toBe(500);
		});

		it('should validate request parameters', async () => {
			const request = new Request('https://worker.dev/api/recognition/results?page=invalid');
			const response = await worker.default.fetch(request, mockEnv);
			
			// Should handle invalid parameters gracefully
			expect(response.status).toBe(200); // Uses default values
		});
	});

	describe('Performance', () => {
		it('should cache static assets', async () => {
			const request = new Request('https://worker.dev/_app/immutable/assets/app.css');
			const response = await worker.default.fetch(request, mockEnv);
			
			expect(response.headers.get('Cache-Control')).toContain('max-age');
		});

		it('should set appropriate cache headers for API responses', async () => {
			const request = new Request('https://worker.dev/api/system/status');
			const response = await worker.default.fetch(request, mockEnv);
			
			// API responses should have cache control
			expect(response.headers.get('Cache-Control')).toBeDefined();
		});
	});

	describe('Analytics API', () => {
		it('should return analytics overview', async () => {
			const request = new Request('https://worker.dev/api/analytics/overview');
			const response = await worker.default.fetch(request, mockEnv);
			
			expect(response.status).toBe(200);
			const data = JSON.parse(response.body);
			expect(data.overview).toBeDefined();
			expect(data.performance).toBeDefined();
		});
	});

	describe('Settings API', () => {
		it('should return current settings', async () => {
			const request = new Request('https://worker.dev/api/settings');
			const response = await worker.default.fetch(request, mockEnv);
			
			expect(response.status).toBe(200);
			const data = JSON.parse(response.body);
			expect(data.processing).toBeDefined();
			expect(data.display).toBeDefined();
		});

		it('should handle settings updates', async () => {
			const request = new Request('https://worker.dev/api/settings', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					processing: { confidence_threshold: 0.8 }
				})
			});
			
			const response = await worker.default.fetch(request, mockEnv);
			
			expect(response.status).toBe(200);
			expect(mockEnv.METADATA_KV.put).toHaveBeenCalled();
		});
	});
});