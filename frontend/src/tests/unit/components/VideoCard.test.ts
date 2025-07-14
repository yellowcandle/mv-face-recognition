import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/svelte';
import VideoCard from '../../../lib/components/VideoCard.svelte';

describe('VideoCard', () => {
	const mockVideo = {
		id: '1',
		name: 'Test Video Name',
		filename: 'test-video.mp4',
		duration: 125.5, // 2:05
		uploadedAt: '2024-07-01T12:30:00Z',
		status: 'completed',
		thumbnail: '/test-thumbnail.jpg'
	};

	it('should render video information correctly', () => {
		render(VideoCard, { video: mockVideo });

		expect(screen.getByTestId('video-title')).toHaveTextContent('Test Video Name');
		expect(screen.getByTestId('video-filename')).toHaveTextContent('test-video.mp4');
		expect(screen.getByTestId('video-date')).toHaveTextContent('2024');
		
		// Check duration formatting
		expect(screen.getByText('2:05')).toBeInTheDocument();
		
		// Check status
		expect(screen.getByText('completed')).toBeInTheDocument();
	});

	it('should display thumbnail with correct alt text', () => {
		render(VideoCard, { video: mockVideo });

		const thumbnail = screen.getByAltText('Video thumbnail for Test Video Name');
		expect(thumbnail).toBeInTheDocument();
		expect(thumbnail).toHaveAttribute('src', '/test-thumbnail.jpg');
	});

	it('should handle click events', async () => {
		const onClick = vi.fn();
		render(VideoCard, { video: mockVideo, onClick });

		const card = screen.getByTestId('video-card');
		await fireEvent.click(card);

		expect(onClick).toHaveBeenCalledWith('1');
	});

	it('should handle keyboard navigation', async () => {
		const onClick = vi.fn();
		render(VideoCard, { video: mockVideo, onClick });

		const card = screen.getByTestId('video-card');
		await fireEvent.keyDown(card, { key: 'Enter' });

		expect(onClick).toHaveBeenCalledWith('1');
	});

	it('should not trigger click on other keys', async () => {
		const onClick = vi.fn();
		render(VideoCard, { video: mockVideo, onClick });

		const card = screen.getByTestId('video-card');
		await fireEvent.keyDown(card, { key: 'Space' });

		expect(onClick).not.toHaveBeenCalled();
	});

	it('should display correct status colors', () => {
		const { rerender } = render(VideoCard, { 
			video: { ...mockVideo, status: 'completed' } 
		});
		
		expect(screen.getByText('completed')).toHaveClass('text-green-600');

		rerender({ video: { ...mockVideo, status: 'processing' } });
		expect(screen.getByText('processing')).toHaveClass('text-yellow-600');

		rerender({ video: { ...mockVideo, status: 'failed' } });
		expect(screen.getByText('failed')).toHaveClass('text-red-600');
	});

	it('should be accessible', () => {
		render(VideoCard, { video: mockVideo });

		const card = screen.getByTestId('video-card');
		expect(card).toHaveAttribute('role', 'button');
		expect(card).toHaveAttribute('tabindex', '0');
	});

	it('should format duration correctly for different values', () => {
		const { rerender } = render(VideoCard, { 
			video: { ...mockVideo, duration: 60 } 
		});
		expect(screen.getByText('1:00')).toBeInTheDocument();

		rerender({ video: { ...mockVideo, duration: 3661 } });
		expect(screen.getByText('61:01')).toBeInTheDocument();

		rerender({ video: { ...mockVideo, duration: 0 } });
		expect(screen.getByText('0:00')).toBeInTheDocument();
	});
});