import '@testing-library/jest-dom';
import { vi } from 'vitest';

// Mock browser APIs
Object.defineProperty(window, 'matchMedia', {
	writable: true,
	value: vi.fn().mockImplementation(query => ({
		matches: false,
		media: query,
		onchange: null,
		addListener: vi.fn(),
		removeListener: vi.fn(),
		addEventListener: vi.fn(),
		removeEventListener: vi.fn(),
		dispatchEvent: vi.fn(),
	})),
});

// Mock IntersectionObserver
global.IntersectionObserver = vi.fn().mockImplementation(() => ({
	observe: vi.fn(),
	unobserve: vi.fn(),
	disconnect: vi.fn(),
}));

// Mock ResizeObserver
global.ResizeObserver = vi.fn().mockImplementation(() => ({
	observe: vi.fn(),
	unobserve: vi.fn(),
	disconnect: vi.fn(),
}));

// Mock Canvas API for video player tests
HTMLCanvasElement.prototype.getContext = vi.fn().mockReturnValue({
	fillRect: vi.fn(),
	clearRect: vi.fn(),
	getImageData: vi.fn(),
	putImageData: vi.fn(),
	createImageData: vi.fn(),
	setTransform: vi.fn(),
	drawImage: vi.fn(),
	save: vi.fn(),
	fillText: vi.fn(),
	restore: vi.fn(),
	beginPath: vi.fn(),
	moveTo: vi.fn(),
	lineTo: vi.fn(),
	closePath: vi.fn(),
	stroke: vi.fn(),
	translate: vi.fn(),
	scale: vi.fn(),
	rotate: vi.fn(),
	arc: vi.fn(),
	fill: vi.fn(),
	measureText: vi.fn().mockReturnValue({ width: 0 }),
	transform: vi.fn(),
	rect: vi.fn(),
	clip: vi.fn(),
});

// Mock WebSocket for real-time features
global.WebSocket = vi.fn().mockImplementation(() => ({
	send: vi.fn(),
	close: vi.fn(),
	readyState: 1,
	CONNECTING: 0,
	OPEN: 1,
	CLOSING: 2,
	CLOSED: 3,
}));

// Mock fetch API
global.fetch = vi.fn();

// Mock video element
Object.defineProperty(HTMLVideoElement.prototype, 'load', {
	writable: true,
	value: vi.fn(),
});

Object.defineProperty(HTMLVideoElement.prototype, 'play', {
	writable: true,
	value: vi.fn().mockResolvedValue(undefined),
});

Object.defineProperty(HTMLVideoElement.prototype, 'pause', {
	writable: true,
	value: vi.fn(),
});

// Global test utilities
export const mockApiResponse = (data: any, ok = true) => {
	return Promise.resolve({
		ok,
		json: () => Promise.resolve(data),
		text: () => Promise.resolve(JSON.stringify(data)),
		status: ok ? 200 : 400,
		statusText: ok ? 'OK' : 'Bad Request',
	});
};

export const mockVideoElement = () => ({
	currentTime: 0,
	duration: 100,
	paused: true,
	volume: 1,
	muted: false,
	playbackRate: 1,
	readyState: 4,
	videoWidth: 1920,
	videoHeight: 1080,
	load: vi.fn(),
	play: vi.fn().mockResolvedValue(undefined),
	pause: vi.fn(),
	addEventListener: vi.fn(),
	removeEventListener: vi.fn(),
});