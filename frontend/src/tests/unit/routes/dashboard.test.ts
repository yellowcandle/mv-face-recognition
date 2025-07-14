import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/svelte';
import { createMockFetch, mockSystemStatus, mockVideos, mockContestants } from '../../mocks/api';
import Dashboard from '../../../routes/+page.svelte';

describe('Dashboard', () => {
	let mockFetch: ReturnType<typeof createMockFetch>;

	beforeEach(() => {
		mockFetch = createMockFetch();
		global.fetch = mockFetch;
	});

	it('should render loading state initially', () => {
		render(Dashboard);
		expect(screen.getByText(/loading/i)).toBeInTheDocument();
	});

	it('should load and display system status', async () => {
		mockFetch.mockImplementation((url) => {
			if (url.includes('/api/system/status')) {
				return Promise.resolve({
					ok: true,
					json: () => Promise.resolve(mockSystemStatus)
				});
			}
			return Promise.resolve({
				ok: true,
				json: () => Promise.resolve([])
			});
		});

		render(Dashboard);

		await waitFor(() => {
			expect(screen.getByText('healthy')).toBeInTheDocument();
		});

		expect(screen.getByText('5')).toBeInTheDocument(); // total videos
		expect(screen.getByText('95')).toBeInTheDocument(); // total contestants
	});

	it('should load and display videos', async () => {
		mockFetch.mockImplementation((url) => {
			if (url.includes('/api/videos')) {
				return Promise.resolve({
					ok: true,
					json: () => Promise.resolve({ videos: mockVideos })
				});
			}
			return Promise.resolve({
				ok: true,
				json: () => Promise.resolve([])
			});
		});

		render(Dashboard);

		await waitFor(() => {
			expect(screen.getByText('《全民造星IV》主題曲 《前傳》MV')).toBeInTheDocument();
		});

		expect(screen.getByText('女團の駅 Performance')).toBeInTheDocument();
	});

	it('should handle loading errors gracefully', async () => {
		mockFetch.mockRejectedValue(new Error('Network error'));

		render(Dashboard);

		await waitFor(() => {
			expect(screen.getByText(/failed to load dashboard data/i)).toBeInTheDocument();
		});
	});

	it('should handle API errors', async () => {
		mockFetch.mockResolvedValue({
			ok: false,
			status: 500,
			json: () => Promise.resolve({ error: 'Server error' })
		});

		render(Dashboard);

		await waitFor(() => {
			expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
		});
	});

	it('should display quick actions', async () => {
		render(Dashboard);

		await waitFor(() => {
			expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
		});

		expect(screen.getByText(/upload new video/i)).toBeInTheDocument();
		expect(screen.getByText(/view analytics/i)).toBeInTheDocument();
		expect(screen.getByText(/system settings/i)).toBeInTheDocument();
	});

	it('should show system health indicators', async () => {
		mockFetch.mockImplementation((url) => {
			if (url.includes('/api/system/status')) {
				return Promise.resolve({
					ok: true,
					json: () => Promise.resolve({
						...mockSystemStatus,
						features: {
							video_streaming: true,
							face_recognition: false,
							metadata_storage: true,
							websocket: true
						}
					})
				});
			}
			return Promise.resolve({
				ok: true,
				json: () => Promise.resolve([])
			});
		});

		render(Dashboard);

		await waitFor(() => {
			expect(screen.getByText('Video Streaming')).toBeInTheDocument();
		});

		// Should show enabled features
		const enabledFeatures = screen.getAllByText('✅');
		expect(enabledFeatures.length).toBeGreaterThan(0);

		// Should show disabled features
		const disabledFeatures = screen.getAllByText('❌');
		expect(disabledFeatures.length).toBeGreaterThan(0);
	});
});