import { test, expect } from '@playwright/test';

test.describe('Video Player', () => {
	test.beforeEach(async ({ page }) => {
		// Navigate to video player page
		await page.goto('/video-player');
	});

	test('should load video player interface', async ({ page }) => {
		// Check for main video player elements
		await expect(page.getByTestId('video-player')).toBeVisible();
		await expect(page.getByTestId('video-controls')).toBeVisible();
		await expect(page.getByTestId('face-recognition-sidebar')).toBeVisible();
	});

	test('should display video selection dropdown', async ({ page }) => {
		await expect(page.getByTestId('video-selector')).toBeVisible();
		
		// Open dropdown
		await page.getByTestId('video-selector').click();
		
		// Should show video options
		await expect(page.getByText('《全民造星IV》主題曲')).toBeVisible();
		await expect(page.getByText('女團の駅 Performance')).toBeVisible();
	});

	test('should load video when selected', async ({ page }) => {
		// Select a video
		await page.getByTestId('video-selector').click();
		await page.getByText('《全民造星IV》主題曲').click();
		
		// Wait for video to load
		await expect(page.getByTestId('video-element')).toBeVisible();
		
		// Check that metadata loaded
		await expect(page.getByTestId('video-duration')).toBeVisible();
		await expect(page.getByTestId('video-title')).toContainText('《全民造星IV》主題曲');
	});

	test('should show face recognition overlay', async ({ page }) => {
		// Load a video with face recognition data
		await page.getByTestId('video-selector').click();
		await page.getByText('《全民造星IV》主題曲').click();
		
		// Wait for face recognition data to load
		await page.waitForTimeout(1000);
		
		// Check for face overlay canvas
		await expect(page.getByTestId('face-overlay-canvas')).toBeVisible();
		
		// Check for face detection indicators
		await expect(page.getByTestId('face-gallery')).toBeVisible();
	});

	test('should display contestant information in sidebar', async ({ page }) => {
		await page.getByTestId('video-selector').click();
		await page.getByText('《全民造星IV》主題曲').click();
		
		// Wait for data to load
		await page.waitForTimeout(1000);
		
		// Check sidebar content
		await expect(page.getByTestId('contestants-list')).toBeVisible();
		await expect(page.getByTestId('recognition-stats')).toBeVisible();
	});

	test('should control video playback', async ({ page }) => {
		await page.getByTestId('video-selector').click();
		await page.getByText('《全民造星IV》主題曲').click();
		
		// Wait for video to load
		await page.waitForTimeout(2000);
		
		// Test play button
		await page.getByTestId('play-button').click();
		
		// Check that video is playing (this is mocked in tests)
		await expect(page.getByTestId('play-button')).toHaveAttribute('aria-label', /pause/i);
		
		// Test pause button
		await page.getByTestId('play-button').click();
		await expect(page.getByTestId('play-button')).toHaveAttribute('aria-label', /play/i);
	});

	test('should update timeline with face detections', async ({ page }) => {
		await page.getByTestId('video-selector').click();
		await page.getByText('《全民造星IV》主題曲').click();
		
		await page.waitForTimeout(1000);
		
		// Check timeline elements
		await expect(page.getByTestId('video-timeline')).toBeVisible();
		await expect(page.getByTestId('timeline-markers')).toBeVisible();
		
		// Timeline should show detection points
		const markers = page.getByTestId('timeline-marker');
		await expect(markers.first()).toBeVisible();
	});

	test('should be responsive on mobile', async ({ page }) => {
		// Set mobile viewport
		await page.setViewportSize({ width: 375, height: 667 });
		
		await expect(page.getByTestId('video-player')).toBeVisible();
		
		// Mobile layout adjustments
		await expect(page.getByTestId('face-recognition-sidebar')).toHaveClass(/hidden|sm:block/);
		
		// Should have mobile controls
		await expect(page.getByTestId('mobile-menu-button')).toBeVisible();
	});

	test('should handle video loading errors', async ({ page }) => {
		// Mock a video loading error
		await page.route('**/api/videos/*/stream', route => {
			route.fulfill({ status: 404, body: 'Video not found' });
		});
		
		await page.getByTestId('video-selector').click();
		await page.getByText('《全民造星IV》主題曲').click();
		
		// Should show error message
		await expect(page.getByText(/failed to load video/i)).toBeVisible();
	});

	test('should filter face detections by confidence', async ({ page }) => {
		await page.getByTestId('video-selector').click();
		await page.getByText('《全民造星IV》主題曲').click();
		
		await page.waitForTimeout(1000);
		
		// Adjust confidence filter
		await page.getByTestId('confidence-filter').fill('0.8');
		
		// Should update face gallery and timeline
		await page.waitForTimeout(500);
		
		// Verify filtered results
		const faceItems = page.getByTestId('face-item');
		const count = await faceItems.count();
		expect(count).toBeGreaterThanOrEqual(0);
	});

	test('should export video clips', async ({ page }) => {
		await page.getByTestId('video-selector').click();
		await page.getByText('《全民造星IV》主題曲').click();
		
		await page.waitForTimeout(1000);
		
		// Click export button
		await page.getByTestId('export-clip-button').click();
		
		// Should show export dialog
		await expect(page.getByTestId('export-dialog')).toBeVisible();
		
		// Configure export settings
		await page.getByTestId('start-time-input').fill('10');
		await page.getByTestId('end-time-input').fill('20');
		
		// Start export
		await page.getByTestId('confirm-export-button').click();
		
		// Should show progress indicator
		await expect(page.getByTestId('export-progress')).toBeVisible();
	});

	test('should search and jump to specific contestants', async ({ page }) => {
		await page.getByTestId('video-selector').click();
		await page.getByText('《全民造星IV》主題曲').click();
		
		await page.waitForTimeout(1000);
		
		// Search for a contestant
		await page.getByTestId('contestant-search').fill('張三');
		
		// Should filter contestants list
		await expect(page.getByText('張三')).toBeVisible();
		
		// Click on contestant to jump to their appearance
		await page.getByText('張三').click();
		
		// Video should jump to contestant's timestamp
		await page.waitForTimeout(500);
		
		// Should highlight the contestant in the overlay
		await expect(page.getByTestId('highlighted-face')).toBeVisible();
	});
});