import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
	apiRequest,
	getContestants,
	getVideos,
	getVideoMetadata,
	getRecognitionResults,
	getSystemStatus,
	getAnalytics,
	formatDuration,
	formatTimestamp,
	getConfidenceColor,
	debounce,
	WebSocketManager
} from '../../../lib/utils/api';
import { createMockFetch, createMockWebSocket } from '../../mocks/api';

describe('API Utils', () => {
	let mockFetch: ReturnType<typeof createMockFetch>;

	beforeEach(() => {
		mockFetch = createMockFetch();
		global.fetch = mockFetch;
	});

	afterEach(() => {
		vi.restoreAllMocks();
	});

	describe('apiRequest', () => {
		it('should make successful API request', async () => {
			const mockData = { test: 'data' };
			mockFetch.mockResolvedValueOnce({
				ok: true,
				json: () => Promise.resolve(mockData),
				status: 200
			});

			const result = await apiRequest('/test');

			expect(result.data).toEqual(mockData);
			expect(result.status).toBe(200);
			expect(result.error).toBeUndefined();
		});

		it('should handle API errors', async () => {
			mockFetch.mockResolvedValueOnce({
				ok: false,
				json: () => Promise.resolve({ error: 'Not found' }),
				status: 404
			});

			const result = await apiRequest('/test');

			expect(result.data).toBeUndefined();
			expect(result.status).toBe(404);
			expect(result.error).toBe('Not found');
		});

		it('should handle network errors', async () => {
			mockFetch.mockRejectedValueOnce(new Error('Network error'));

			const result = await apiRequest('/test');

			expect(result.data).toBeUndefined();
			expect(result.status).toBe(0);
			expect(result.error).toBe('Network error');
		});

		it('should include custom headers', async () => {
			await apiRequest('/test', {
				headers: { 'Custom-Header': 'value' }
			});

			expect(mockFetch).toHaveBeenCalledWith('/api/test', {
				headers: {
					'Content-Type': 'application/json',
					'Custom-Header': 'value'
				}
			});
		});
	});

	describe('API endpoint functions', () => {
		it('should get contestants', async () => {
			await getContestants();
			expect(mockFetch).toHaveBeenCalledWith('/api/contestants', expect.any(Object));
		});

		it('should get videos', async () => {
			await getVideos();
			expect(mockFetch).toHaveBeenCalledWith('/api/videos', expect.any(Object));
		});

		it('should get video metadata', async () => {
			await getVideoMetadata('123');
			expect(mockFetch).toHaveBeenCalledWith('/api/videos/123/metadata', expect.any(Object));
		});

		it('should get recognition results with parameters', async () => {
			await getRecognitionResults({
				video_id: '123',
				min_confidence: 0.8,
				page: 1,
				limit: 50
			});

			expect(mockFetch).toHaveBeenCalledWith(
				'/api/recognition/results?video_id=123&min_confidence=0.8&page=1&limit=50',
				expect.any(Object)
			);
		});

		it('should get recognition results without parameters', async () => {
			await getRecognitionResults();
			expect(mockFetch).toHaveBeenCalledWith('/api/recognition/results', expect.any(Object));
		});

		it('should get system status', async () => {
			await getSystemStatus();
			expect(mockFetch).toHaveBeenCalledWith('/api/system/status', expect.any(Object));
		});

		it('should get analytics', async () => {
			await getAnalytics();
			expect(mockFetch).toHaveBeenCalledWith('/api/analytics/overview', expect.any(Object));
		});
	});

	describe('Utility functions', () => {
		describe('formatDuration', () => {
			it('should format seconds to MM:SS', () => {
				expect(formatDuration(0)).toBe('0:00');
				expect(formatDuration(30)).toBe('0:30');
				expect(formatDuration(60)).toBe('1:00');
				expect(formatDuration(90)).toBe('1:30');
				expect(formatDuration(3661)).toBe('61:01');
			});
		});

		describe('formatTimestamp', () => {
			it('should format ISO timestamp to readable format', () => {
				const timestamp = '2024-07-01T12:30:45Z';
				const result = formatTimestamp(timestamp);
				
				expect(result).toMatch(/2024/);
				expect(result).toMatch(/12:30/);
			});
		});

		describe('getConfidenceColor', () => {
			it('should return green for high confidence', () => {
				expect(getConfidenceColor(0.9)).toBe('#10b981');
				expect(getConfidenceColor(0.8)).toBe('#10b981');
			});

			it('should return yellow for medium confidence', () => {
				expect(getConfidenceColor(0.7)).toBe('#f59e0b');
				expect(getConfidenceColor(0.6)).toBe('#f59e0b');
			});

			it('should return red for low confidence', () => {
				expect(getConfidenceColor(0.5)).toBe('#ef4444');
				expect(getConfidenceColor(0.1)).toBe('#ef4444');
			});
		});

		describe('debounce', () => {
			it('should debounce function calls', async () => {
				const mockFn = vi.fn();
				const debouncedFn = debounce(mockFn, 100);

				debouncedFn('test1');
				debouncedFn('test2');
				debouncedFn('test3');

				expect(mockFn).not.toHaveBeenCalled();

				await new Promise(resolve => setTimeout(resolve, 150));

				expect(mockFn).toHaveBeenCalledTimes(1);
				expect(mockFn).toHaveBeenCalledWith('test3');
			});
		});
	});

	describe('WebSocketManager', () => {
		let manager: WebSocketManager;
		let mockWS: any;

		beforeEach(() => {
			mockWS = createMockWebSocket();
			global.WebSocket = vi.fn(() => mockWS);
			manager = new WebSocketManager('ws://test');
		});

		it('should create WebSocket connection', () => {
			const onMessage = vi.fn();
			const onError = vi.fn();

			manager.connect(onMessage, onError);

			expect(global.WebSocket).toHaveBeenCalledWith('ws://test');
		});

		it('should handle incoming messages', () => {
			const onMessage = vi.fn();
			manager.connect(onMessage);

			const testData = { type: 'test', data: 'message' };
			mockWS.onmessage({ data: JSON.stringify(testData) });

			expect(onMessage).toHaveBeenCalledWith(testData);
		});

		it('should handle connection errors', () => {
			const onError = vi.fn();
			manager.connect(undefined, onError);

			const errorEvent = new Event('error');
			mockWS.onerror(errorEvent);

			expect(onError).toHaveBeenCalledWith(errorEvent);
		});

		it('should send messages when connected', () => {
			manager.connect();
			mockWS.readyState = 1; // WebSocket.OPEN

			const testData = { type: 'test' };
			manager.send(testData);

			expect(mockWS.send).toHaveBeenCalledWith(JSON.stringify(testData));
		});

		it('should not send messages when disconnected', () => {
			manager.connect();
			mockWS.readyState = 3; // WebSocket.CLOSED

			const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
			
			manager.send({ type: 'test' });

			expect(mockWS.send).not.toHaveBeenCalled();
			expect(consoleSpy).toHaveBeenCalledWith('WebSocket is not connected');
			
			consoleSpy.mockRestore();
		});

		it('should disconnect WebSocket', () => {
			manager.connect();
			manager.disconnect();

			expect(mockWS.close).toHaveBeenCalled();
		});
	});
});