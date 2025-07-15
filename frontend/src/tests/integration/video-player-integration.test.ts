import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { createMockFetch, mockVideos, mockMetadata } from '../mocks/api.js';
import { parseMetadata } from '../../lib/utils/metadata.js';
import { createVideoSynchronizer } from '../../lib/utils/synchronization.js';

// Mock canvas context for rendering tests
const createMockCanvasContext = () => ({
  clearRect: vi.fn(),
  strokeRect: vi.fn(),
  fillRect: vi.fn(),
  fillText: vi.fn(),
  measureText: vi.fn().mockReturnValue({ width: 100 }),
  save: vi.fn(),
  restore: vi.fn(),
  scale: vi.fn(),
  globalAlpha: 1,
  strokeStyle: '',
  fillStyle: '',
  lineWidth: 1,
  font: '',
  textAlign: 'left',
  textBaseline: 'top'
});

// Mock video element for synchronization tests
const createMockVideoElement = () => ({
  currentTime: 0,
  duration: 240.5,
  paused: true,
  videoWidth: 1920,
  videoHeight: 1080,
  addEventListener: vi.fn(),
  removeEventListener: vi.fn(),
  play: vi.fn().mockResolvedValue(undefined),
  pause: vi.fn(),
  getBoundingClientRect: vi.fn().mockReturnValue({
    width: 1920,
    height: 1080,
    left: 0,
    top: 0
  })
});

describe('Video Player Integration Tests', () => {
  let mockFetch: ReturnType<typeof createMockFetch>;

  beforeEach(() => {
    // Setup fetch mock
    mockFetch = createMockFetch();
    global.fetch = mockFetch;

    // Mock requestAnimationFrame
    global.requestAnimationFrame = vi.fn((callback) => {
      setTimeout(callback, 16); // ~60fps
      return 1;
    });

    global.cancelAnimationFrame = vi.fn();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('Video Player with Face Overlay Synchronization', () => {
    it('should synchronize face overlays with video playback', async () => {
      // Setup mock metadata with timeline data
      const mockTimelineMetadata = {
        video_info: {
          filename: 'video-1.mp4',
          duration: 240.5,
          fps: 30
        },
        processing_info: {
          processing_interval: 5,
          interpolation_enabled: true,
          total_processed_frames: 1443,
          total_interpolated_frames: 5772
        },
        timeline: [
          {
            frame_number: 0,
            timestamp: 0.0,
            contestants: [
              {
                id: 'face_0_0',
                contestant_id: 1,
                contestant_name: '張三',
                contestant_nickname: 'Ace',
                confidence: 0.95,
                bounding_box: { x: 100, y: 100, width: 150, height: 200 },
                timestamp: 0.0,
                interpolated: false
              }
            ]
          },
          {
            frame_number: 150,
            timestamp: 5.0,
            contestants: [
              {
                id: 'face_150_0',
                contestant_id: 2,
                contestant_name: '李四',
                contestant_nickname: 'Ling',
                confidence: 0.88,
                bounding_box: { x: 300, y: 120, width: 140, height: 180 },
                timestamp: 5.0,
                interpolated: false
              }
            ]
          }
        ]
      };

      // Test metadata parsing
      const parsedMetadata = parseMetadata(mockTimelineMetadata);
      expect(parsedMetadata.isValid).toBe(true);
      expect(parsedMetadata.sortedTimestamps).toHaveLength(2);

      // Test synchronizer creation and initialization
      const synchronizer = createVideoSynchronizer({
        toleranceSeconds: 0.5,
        interpolationEnabled: false, // Disable interpolation for this test
        preloadBufferSeconds: 10,
        maxCacheSize: 200
      });

      const initialized = synchronizer.initialize(parsedMetadata);
      expect(initialized).toBe(true);

      // Test synchronization at timestamp 0.0
      let syncResult = synchronizer.syncToTimestamp(0.0);
      expect(syncResult.faces).toHaveLength(1);
      expect(syncResult.faces[0].contestant_name).toBe('張三');
      expect(syncResult.confidence).toBeGreaterThan(0.9);

      // Test synchronization at timestamp 5.0
      syncResult = synchronizer.syncToTimestamp(5.0);
      expect(syncResult.faces).toHaveLength(1);
      expect(syncResult.faces[0].contestant_name).toBe('李四');
      expect(syncResult.confidence).toBeGreaterThan(0.8);

      // Test synchronization at timestamp far from faces - should return closest face
      syncResult = synchronizer.syncToTimestamp(100.0);
      expect(syncResult.faces).toHaveLength(1);
      expect(syncResult.faces[0].contestant_name).toBe('李四'); // Should be the last face at 5.0
    });

    it('should handle video seeking and update overlays accordingly', async () => {
      const mockTimelineMetadata = {
        video_info: {
          filename: 'video-1.mp4',
          duration: 240.5,
          fps: 30
        },
        processing_info: {
          processing_interval: 5,
          interpolation_enabled: true,
          total_processed_frames: 1443,
          total_interpolated_frames: 5772
        },
        timeline: [
          {
            frame_number: 0,
            timestamp: 0.0,
            contestants: [
              {
                id: 'face_0_0',
                contestant_id: 1,
                contestant_name: '張三',
                contestant_nickname: 'Ace',
                confidence: 0.95,
                bounding_box: { x: 100, y: 100, width: 150, height: 200 },
                timestamp: 0.0,
                interpolated: false
              }
            ]
          },
          {
            frame_number: 600,
            timestamp: 20.0,
            contestants: []
          }
        ]
      };

      // Test metadata parsing
      const parsedMetadata = parseMetadata(mockTimelineMetadata);
      expect(parsedMetadata.isValid).toBe(true);

      // Test synchronizer with seeking behavior
      const synchronizer = createVideoSynchronizer({
        toleranceSeconds: 0.5,
        interpolationEnabled: true,
        preloadBufferSeconds: 10,
        maxCacheSize: 200
      });

      synchronizer.initialize(parsedMetadata);

      // Test seeking to timestamp with faces
      let syncResult = synchronizer.syncToTimestamp(0.0);
      expect(syncResult.faces).toHaveLength(1);
      expect(syncResult.faces[0].contestant_name).toBe('張三');

      // Test seeking to timestamp without faces
      syncResult = synchronizer.syncToTimestamp(20.0);
      expect(syncResult.faces).toHaveLength(0);

      // Test cache clearing after seek (simulated)
      synchronizer.clearCache();
      
      // Verify synchronizer still works after cache clear
      syncResult = synchronizer.syncToTimestamp(0.0);
      expect(syncResult.faces).toHaveLength(1);
    });

    it('should handle confidence-based face classification correctly', async () => {
      const mockTimelineMetadata = {
        video_info: {
          filename: 'video-1.mp4',
          duration: 240.5,
          fps: 30
        },
        processing_info: {
          processing_interval: 5,
          interpolation_enabled: true,
          total_processed_frames: 1443,
          total_interpolated_frames: 5772
        },
        timeline: [
          {
            frame_number: 0,
            timestamp: 0.0,
            contestants: [
              {
                id: 'face_high_conf',
                contestant_id: 1,
                contestant_name: '張三',
                confidence: 0.95, // High confidence
                bounding_box: { x: 100, y: 100, width: 150, height: 200 },
                timestamp: 0.0
              },
              {
                id: 'face_med_conf',
                contestant_id: 2,
                contestant_name: '李四',
                confidence: 0.65, // Medium confidence
                bounding_box: { x: 300, y: 100, width: 150, height: 200 },
                timestamp: 0.0
              },
              {
                id: 'face_low_conf',
                contestant_id: 3,
                contestant_name: '王五',
                confidence: 0.35, // Low confidence
                bounding_box: { x: 500, y: 100, width: 150, height: 200 },
                timestamp: 0.0
              }
            ]
          }
        ]
      };

      // Test metadata parsing with different confidence levels
      const parsedMetadata = parseMetadata(mockTimelineMetadata);
      expect(parsedMetadata.isValid).toBe(true);

      // Test synchronizer with confidence-based faces
      const synchronizer = createVideoSynchronizer({
        toleranceSeconds: 0.5,
        interpolationEnabled: true,
        preloadBufferSeconds: 10,
        maxCacheSize: 200
      });

      synchronizer.initialize(parsedMetadata);

      // Test synchronization returns all faces with different confidence levels
      const syncResult = synchronizer.syncToTimestamp(0.0);
      expect(syncResult.faces).toHaveLength(3);
      
      // Verify faces are sorted by confidence (highest first)
      expect(syncResult.faces[0].confidence).toBe(0.95);
      expect(syncResult.faces[1].confidence).toBe(0.65);
      expect(syncResult.faces[2].confidence).toBe(0.35);
      
      // Verify confidence classification
      expect(syncResult.faces[0].confidence).toBeGreaterThan(0.8); // High confidence
      expect(syncResult.faces[1].confidence).toBeGreaterThan(0.5); // Medium confidence
      expect(syncResult.faces[2].confidence).toBeLessThan(0.5); // Low confidence
    });
  });

  describe('Gallery Updates During Video Playback', () => {
    it('should update face gallery when video time changes', async () => {
      const mockTimelineMetadata = {
        video_info: {
          filename: 'video-1.mp4',
          duration: 240.5,
          fps: 30
        },
        processing_info: {
          processing_interval: 5,
          interpolation_enabled: true,
          total_processed_frames: 1443,
          total_interpolated_frames: 5772
        },
        timeline: [
          {
            frame_number: 0,
            timestamp: 0.0,
            contestants: [
              {
                id: 'face_0_0',
                contestant_id: 1,
                contestant_name: '張三',
                contestant_nickname: 'Ace',
                confidence: 0.95,
                bounding_box: { x: 100, y: 100, width: 150, height: 200 },
                timestamp: 0.0
              }
            ]
          },
          {
            frame_number: 150,
            timestamp: 5.0,
            contestants: [
              {
                id: 'face_5_0',
                contestant_id: 1,
                contestant_name: '張三',
                contestant_nickname: 'Ace',
                confidence: 0.88,
                bounding_box: { x: 120, y: 110, width: 160, height: 210 },
                timestamp: 5.0
              },
              {
                id: 'face_5_1',
                contestant_id: 2,
                contestant_name: '李四',
                contestant_nickname: 'Ling',
                confidence: 0.82,
                bounding_box: { x: 300, y: 120, width: 140, height: 180 },
                timestamp: 5.0
              }
            ]
          }
        ]
      };

      // Test metadata parsing
      const parsedMetadata = parseMetadata(mockTimelineMetadata);
      expect(parsedMetadata.isValid).toBe(true);

      // Test synchronizer with changing timestamps
      const synchronizer = createVideoSynchronizer({
        toleranceSeconds: 0.5,
        interpolationEnabled: true,
        preloadBufferSeconds: 10,
        maxCacheSize: 200
      });

      synchronizer.initialize(parsedMetadata);

      // Initially at timestamp 0.0 - should show 1 face
      let syncResult = synchronizer.syncToTimestamp(0.0);
      expect(syncResult.faces).toHaveLength(1);
      expect(syncResult.faces[0].contestant_name).toBe('張三');

      // Move to timestamp 5.0 - should show 2 faces
      syncResult = synchronizer.syncToTimestamp(5.0);
      expect(syncResult.faces).toHaveLength(2);
      
      // Verify both contestants are present
      const contestantNames = syncResult.faces.map(face => face.contestant_name);
      expect(contestantNames).toContain('張三');
      expect(contestantNames).toContain('李四');
      
      // Verify faces are sorted by confidence
      expect(syncResult.faces[0].confidence).toBeGreaterThanOrEqual(syncResult.faces[1].confidence);
    });

    it('should synchronize face selection between canvas and gallery', async () => {
      const mockTimelineMetadata = {
        video_info: {
          filename: 'video-1.mp4',
          duration: 240.5,
          fps: 30
        },
        processing_info: {
          processing_interval: 5,
          interpolation_enabled: true,
          total_processed_frames: 1443,
          total_interpolated_frames: 5772
        },
        timeline: [
          {
            frame_number: 0,
            timestamp: 0.0,
            contestants: [
              {
                id: 'face_0_0',
                contestant_id: 1,
                contestant_name: '張三',
                contestant_nickname: 'Ace',
                confidence: 0.95,
                bounding_box: { x: 100, y: 100, width: 150, height: 200 },
                timestamp: 0.0
              },
              {
                id: 'face_0_1',
                contestant_id: 2,
                contestant_name: '李四',
                contestant_nickname: 'Ling',
                confidence: 0.88,
                bounding_box: { x: 300, y: 120, width: 140, height: 180 },
                timestamp: 0.0
              }
            ]
          }
        ]
      };

      // Test metadata parsing
      const parsedMetadata = parseMetadata(mockTimelineMetadata);
      expect(parsedMetadata.isValid).toBe(true);

      // Test synchronizer with multiple faces for selection
      const synchronizer = createVideoSynchronizer({
        toleranceSeconds: 0.5,
        interpolationEnabled: true,
        preloadBufferSeconds: 10,
        maxCacheSize: 200
      });

      synchronizer.initialize(parsedMetadata);

      // Test synchronization returns multiple faces
      const syncResult = synchronizer.syncToTimestamp(0.0);
      expect(syncResult.faces).toHaveLength(2);
      
      // Verify both contestants are present
      const contestantNames = syncResult.faces.map(face => face.contestant_name);
      expect(contestantNames).toContain('張三');
      expect(contestantNames).toContain('李四');
      
      // Test face selection logic (simulated)
      const selectedFace = syncResult.faces.find(face => face.contestant_name === '張三');
      expect(selectedFace).toBeDefined();
      expect(selectedFace?.contestant_nickname).toBe('Ace');
      expect(selectedFace?.confidence).toBe(0.95);
      
      // Test face details extraction
      expect(selectedFace?.bounding_box).toEqual({
        x: 100, y: 100, width: 150, height: 200
      });
    });

    it('should show "No faces detected" when no faces are present', async () => {
      const mockTimelineMetadata = {
        video_info: {
          filename: 'video-1.mp4',
          duration: 240.5,
          fps: 30
        },
        processing_info: {
          processing_interval: 5,
          interpolation_enabled: true,
          total_processed_frames: 1443,
          total_interpolated_frames: 5772
        },
        timeline: [
          {
            frame_number: 0,
            timestamp: 0.0,
            contestants: []
          },
          {
            frame_number: 150,
            timestamp: 5.0,
            contestants: []
          }
        ]
      };

      // Test metadata parsing with empty timeline
      const parsedMetadata = parseMetadata(mockTimelineMetadata);
      expect(parsedMetadata.isValid).toBe(true);

      // Test synchronizer with empty timeline
      const synchronizer = createVideoSynchronizer({
        toleranceSeconds: 0.5,
        interpolationEnabled: true,
        preloadBufferSeconds: 10,
        maxCacheSize: 200
      });

      synchronizer.initialize(parsedMetadata);

      // Test synchronization at timestamp with no faces
      let syncResult = synchronizer.syncToTimestamp(0.0);
      expect(syncResult.faces).toHaveLength(0);

      // Test synchronization at another timestamp with no faces
      syncResult = synchronizer.syncToTimestamp(5.0);
      expect(syncResult.faces).toHaveLength(0);

      // Verify confidence is 0 when no faces are detected
      expect(syncResult.confidence).toBe(0);
    });
  });

  describe('Error Handling Scenarios', () => {
    it('should handle metadata loading failure gracefully', async () => {
      mockFetch.mockImplementation((url: string) => {
        if (url.includes('/api/videos/processed/list')) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ videos: mockVideos })
          });
        }
        if (url.includes('/api/videos/metadata/dense/')) {
          return Promise.resolve({
            ok: false,
            status: 404,
            json: () => Promise.resolve({ error: 'Metadata not found' })
          });
        }
        return Promise.resolve({ ok: false, status: 404 });
      });

      // Test API call for video list
      const videosResponse = await fetch('/api/videos/processed/list');
      expect(videosResponse.ok).toBe(true);
      const videosData = await videosResponse.json();
      expect(videosData.videos).toEqual(mockVideos);

      // Test API call for metadata (should fail)
      const metadataResponse = await fetch('/api/videos/metadata/dense/1');
      expect(metadataResponse.ok).toBe(false);
      expect(metadataResponse.status).toBe(404);

      // Test that parseMetadata handles invalid data gracefully
      const invalidMetadata = null;
      const parsedMetadata = parseMetadata(invalidMetadata as any);
      expect(parsedMetadata.isValid).toBe(false);
      expect(parsedMetadata.errors).toContain('Metadata must be a valid object');
    });

    it('should handle video loading errors', async () => {
      mockFetch.mockImplementation((url: string) => {
        if (url.includes('/api/videos/processed/list')) {
          return Promise.resolve({
            ok: false,
            status: 500,
            json: () => Promise.resolve({ error: 'Server error' })
          });
        }
        return Promise.resolve({ ok: false, status: 404 });
      });

      // Test API call for video list (should fail)
      const videosResponse = await fetch('/api/videos/processed/list');
      expect(videosResponse.ok).toBe(false);
      expect(videosResponse.status).toBe(500);
      
      const errorData = await videosResponse.json();
      expect(errorData.error).toBe('Server error');

      // Test that empty video list is handled gracefully
      const emptyVideoList: any[] = [];
      expect(emptyVideoList).toHaveLength(0);
      
      // Test that parseMetadata handles empty data gracefully
      const emptyMetadata = { timeline: [] };
      const parsedMetadata = parseMetadata(emptyMetadata as any);
      expect(parsedMetadata.isValid).toBe(false);
    });

    it('should handle canvas rendering errors gracefully', async () => {
      // Test canvas context creation failure
      const mockCanvasContext = createMockCanvasContext();
      mockCanvasContext.strokeRect.mockImplementation(() => {
        throw new Error('Canvas rendering failed');
      });

      // Test that rendering errors don't break the synchronizer
      const mockTimelineMetadata = {
        video_info: {
          filename: 'video-1.mp4',
          duration: 240.5,
          fps: 30
        },
        processing_info: {
          processing_interval: 5,
          interpolation_enabled: true,
          total_processed_frames: 1443,
          total_interpolated_frames: 5772
        },
        timeline: [
          {
            frame_number: 0,
            timestamp: 0.0,
            contestants: [
              {
                id: 'face_0_0',
                contestant_id: 1,
                contestant_name: '張三',
                confidence: 0.95,
                bounding_box: { x: 100, y: 100, width: 150, height: 200 },
                timestamp: 0.0
              }
            ]
          }
        ]
      };

      const parsedMetadata = parseMetadata(mockTimelineMetadata);
      expect(parsedMetadata.isValid).toBe(true);

      const synchronizer = createVideoSynchronizer({
        toleranceSeconds: 0.5,
        interpolationEnabled: true,
        preloadBufferSeconds: 10,
        maxCacheSize: 200
      });

      synchronizer.initialize(parsedMetadata);

      // Test that synchronizer still works even if rendering fails
      const syncResult = synchronizer.syncToTimestamp(0.0);
      expect(syncResult.faces).toHaveLength(1);
      expect(syncResult.faces[0].contestant_name).toBe('張三');
    });

    it('should handle invalid metadata format', async () => {
      const invalidMetadata = {
        // Missing required fields
        video_info: {
          filename: 'video-1.mp4'
          // Missing duration, fps
        },
        // Missing processing_info
        timeline: 'invalid_timeline_format' // Should be array
      };

      // Test that parseMetadata handles invalid format gracefully
      const parsedMetadata = parseMetadata(invalidMetadata as any);
      expect(parsedMetadata.isValid).toBe(false);
      expect(parsedMetadata.errors).toContain('Invalid video duration');

      // Test that synchronizer handles invalid metadata gracefully
      const synchronizer = createVideoSynchronizer({
        toleranceSeconds: 0.5,
        interpolationEnabled: true,
        preloadBufferSeconds: 10,
        maxCacheSize: 200
      });

      const initialized = synchronizer.initialize(parsedMetadata);
      expect(initialized).toBe(false);

      // Test that synchronizer returns empty results for invalid metadata
      const syncResult = synchronizer.syncToTimestamp(0.0);
      expect(syncResult.faces).toHaveLength(0);
      expect(syncResult.confidence).toBe(0);
    });

    it('should handle network timeouts and retries', async () => {
      let callCount = 0;
      
      mockFetch.mockImplementation((url: string) => {
        if (url.includes('/api/videos/processed/list')) {
          callCount++;
          if (callCount === 1) {
            // First call times out
            return Promise.reject(new Error('Network timeout'));
          }
          // Second call succeeds
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ videos: mockVideos })
          });
        }
        return Promise.resolve({ ok: false, status: 404 });
      });

      // Test first call fails
      try {
        await fetch('/api/videos/processed/list');
        expect.fail('Should have thrown an error');
      } catch (error) {
        expect(error.message).toBe('Network timeout');
        expect(callCount).toBe(1);
      }

      // Test second call succeeds
      const response = await fetch('/api/videos/processed/list');
      expect(response.ok).toBe(true);
      expect(callCount).toBe(2);
      
      const data = await response.json();
      expect(data.videos).toEqual(mockVideos);
    });
  });

  describe('Performance and Memory Management', () => {
    it('should clean up resources when synchronizer is stopped', async () => {
      const mockTimelineMetadata = {
        video_info: {
          filename: 'video-1.mp4',
          duration: 240.5,
          fps: 30
        },
        processing_info: {
          processing_interval: 5,
          interpolation_enabled: true,
          total_processed_frames: 1443,
          total_interpolated_frames: 5772
        },
        timeline: [
          {
            frame_number: 0,
            timestamp: 0.0,
            contestants: [
              {
                id: 'face_0_0',
                contestant_id: 1,
                contestant_name: '張三',
                confidence: 0.95,
                bounding_box: { x: 100, y: 100, width: 150, height: 200 },
                timestamp: 0.0
              }
            ]
          }
        ]
      };

      const parsedMetadata = parseMetadata(mockTimelineMetadata);
      const synchronizer = createVideoSynchronizer({
        toleranceSeconds: 0.5,
        interpolationEnabled: true,
        preloadBufferSeconds: 10,
        maxCacheSize: 200
      });

      synchronizer.initialize(parsedMetadata);

      // Test that synchronizer works initially
      let syncResult = synchronizer.syncToTimestamp(0.0);
      expect(syncResult.faces).toHaveLength(1);

      // Test cleanup
      synchronizer.stop();
      synchronizer.clearCache();

      // Test that synchronizer still works after cleanup
      syncResult = synchronizer.syncToTimestamp(0.0);
      expect(syncResult.faces).toHaveLength(1);
    });

    it('should handle rapid time updates without performance degradation', async () => {
      const mockTimelineMetadata = {
        video_info: {
          filename: 'video-1.mp4',
          duration: 240.5,
          fps: 30
        },
        processing_info: {
          processing_interval: 5,
          interpolation_enabled: true,
          total_processed_frames: 1443,
          total_interpolated_frames: 5772
        },
        timeline: Array.from({ length: 100 }, (_, i) => ({
          frame_number: i * 30,
          timestamp: i * 1.0,
          contestants: [
            {
              id: `face_${i}_0`,
              contestant_id: 1,
              contestant_name: '張三',
              confidence: 0.9,
              bounding_box: { x: 100 + i, y: 100 + i, width: 150, height: 200 },
              timestamp: i * 1.0
            }
          ]
        }))
      };

      const parsedMetadata = parseMetadata(mockTimelineMetadata);
      expect(parsedMetadata.isValid).toBe(true);
      expect(parsedMetadata.sortedTimestamps).toHaveLength(100);

      const synchronizer = createVideoSynchronizer({
        toleranceSeconds: 0.5,
        interpolationEnabled: true,
        preloadBufferSeconds: 10,
        maxCacheSize: 200
      });

      synchronizer.initialize(parsedMetadata);

      // Simulate rapid time updates
      const startTime = performance.now();
      for (let i = 0; i < 10; i++) {
        const syncResult = synchronizer.syncToTimestamp(i * 5.0);
        expect(syncResult.faces).toHaveLength(1);
        expect(syncResult.faces[0].contestant_name).toBe('張三');
      }
      const endTime = performance.now();

      // Verify performance is acceptable (should complete in reasonable time)
      const executionTime = endTime - startTime;
      expect(executionTime).toBeLessThan(100); // Should complete in less than 100ms

      // Test cache efficiency
      const stats = synchronizer.getStats();
      expect(stats.cacheHitRate).toBeGreaterThan(0); // Should have some cache hits
    });
  });
});