import { vi } from 'vitest';

export const mockContestants = [
	{
		id: 1,
		name: "張三",
		nickname: "Ace",
		age: 22,
		status: "active"
	},
	{
		id: 2,
		name: "李四",
		nickname: "Ling",
		age: 20,
		status: "active"
	},
	{
		id: 3,
		name: "王五",
		nickname: "Alice",
		age: 24,
		status: "active"
	}
];

export const mockVideos = [
	{
		id: "1",
		name: "《全民造星IV》主題曲 《前傳》MV",
		filename: "video-1.mp4",
		duration: 240.5,
		uploadedAt: "2024-07-01T00:00:00Z",
		status: "completed",
		thumbnail: "/api/videos/1/thumbnail",
		width: 1920,
		height: 1080,
		fps: 30
	},
	{
		id: "2",
		name: "女團の駅 Performance",
		filename: "video-2.mp4",
		duration: 180.2,
		uploadedAt: "2024-07-02T00:00:00Z",
		status: "completed",
		thumbnail: "/api/videos/2/thumbnail",
		width: 1920,
		height: 1080,
		fps: 30
	}
];

export const mockRecognitionResults = [
	{
		id: "1",
		video_id: "1",
		contestant_id: 1,
		contestant_name: "張三",
		contestant_nickname: "Ace",
		timestamp: 10.5,
		confidence: 0.95,
		bounding_box: { x: 100, y: 100, width: 150, height: 200 }
	},
	{
		id: "2",
		video_id: "1",
		contestant_id: 2,
		contestant_name: "李四",
		contestant_nickname: "Ling",
		timestamp: 15.2,
		confidence: 0.88,
		bounding_box: { x: 300, y: 120, width: 140, height: 180 }
	}
];

export const mockMetadata = {
	video_info: {
		filename: "video-1.mp4",
		duration: 240.5,
		width: 1920,
		height: 1080,
		fps: 30
	},
	processing_summary: {
		total_frames: 7215,
		frames_processed: 1443,
		total_faces_detected: 256,
		total_recognitions: 142,
		unique_contestants: 8,
		processing_time: 127.3,
		recognition_rate: 0.55
	},
	contestant_timeline: [
		{
			contestant_id: 1,
			contestant_name: "張三",
			first_appearance: 5.2,
			last_appearance: 235.8,
			total_appearances: 45,
			avg_confidence: 0.91
		}
	],
	timeline: [
		{
			frame_number: 0,
			timestamp: 0.0,
			contestants: [
				{
					id: 1,
					name: "張三",
					nickname: "Ace",
					bbox: [100, 100, 200, 200],
					confidence: 0.95,
					interpolated: false
				}
			]
		}
	]
};

export const mockSystemStatus = {
	status: "healthy",
	version: "1.0.0",
	uptime: 86400,
	features: {
		video_streaming: true,
		face_recognition: true,
		metadata_storage: true,
		websocket: true
	},
	stats: {
		total_videos: 5,
		total_contestants: 95,
		total_recognitions: 1247,
		processing_queue: 0
	}
};

export const mockAnalytics = {
	overview: {
		total_videos: 5,
		total_recognitions: 1247,
		avg_confidence: 0.87,
		processing_speed: 5.3
	},
	performance: {
		api_response_time: 145,
		video_load_time: 2.3,
		recognition_accuracy: 0.91
	},
	top_performers: [
		{ name: "張三", nickname: "Ace", appearances: 145, avg_confidence: 0.94 },
		{ name: "李四", nickname: "Ling", appearances: 132, avg_confidence: 0.91 }
	]
};

// Mock fetch function
export const createMockFetch = () => {
	return vi.fn().mockImplementation((url: string, options?: RequestInit) => {
		// Parse URL to determine response
		const urlObj = new URL(url, 'http://localhost');
		const path = urlObj.pathname;

		if (path === '/api/contestants') {
			return Promise.resolve({
				ok: true,
				json: () => Promise.resolve(mockContestants),
				status: 200
			});
		}

		if (path === '/api/videos') {
			return Promise.resolve({
				ok: true,
				json: () => Promise.resolve(mockVideos),
				status: 200
			});
		}

		if (path.startsWith('/api/videos/') && path.endsWith('/metadata')) {
			return Promise.resolve({
				ok: true,
				json: () => Promise.resolve(mockMetadata),
				status: 200
			});
		}

		if (path === '/api/recognition/results') {
			return Promise.resolve({
				ok: true,
				json: () => Promise.resolve({
					results: mockRecognitionResults,
					total: mockRecognitionResults.length,
					page: 1,
					limit: 50
				}),
				status: 200
			});
		}

		if (path === '/api/system/status') {
			return Promise.resolve({
				ok: true,
				json: () => Promise.resolve(mockSystemStatus),
				status: 200
			});
		}

		if (path === '/api/analytics/overview') {
			return Promise.resolve({
				ok: true,
				json: () => Promise.resolve(mockAnalytics),
				status: 200
			});
		}

		// Default 404 response
		return Promise.resolve({
			ok: false,
			json: () => Promise.resolve({ error: 'Not found' }),
			status: 404
		});
	});
};

// Mock WebSocket
export const createMockWebSocket = () => {
	const listeners: { [key: string]: Function[] } = {};
	
	return {
		send: vi.fn(),
		close: vi.fn(),
		readyState: 1,
		addEventListener: vi.fn((event: string, handler: Function) => {
			if (!listeners[event]) listeners[event] = [];
			listeners[event].push(handler);
		}),
		removeEventListener: vi.fn(),
		dispatchEvent: vi.fn(),
		triggerEvent: (event: string, data: any) => {
			if (listeners[event]) {
				listeners[event].forEach(handler => handler(data));
			}
		}
	};
};