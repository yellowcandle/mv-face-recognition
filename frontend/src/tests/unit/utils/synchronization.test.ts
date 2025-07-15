import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import {
  VideoTimestampSynchronizer,
  createVideoSynchronizer,
  syncTimestamp,
  validateSyncPerformance,
  type SynchronizationOptions
} from '../../../lib/utils/synchronization.js';
import { parseMetadata, type FaceMetadata } from '../../../lib/utils/metadata.js';

// Mock requestAnimationFrame and cancelAnimationFrame
global.requestAnimationFrame = vi.fn((cb) => {
  return setTimeout(cb, 16); // ~60fps
});
global.cancelAnimationFrame = vi.fn((id) => {
  clearTimeout(id);
});

describe('Timestamp Synchronization System', () => {
  let validMetadata: FaceMetadata;
  let mockVideoElement: HTMLVideoElement;

  beforeEach(() => {
    validMetadata = {
      video_info: {
        filename: 'video-1.mp4',
        duration: 10.0,
        fps: 30
      },
      processing_info: {
        processing_interval: 5,
        interpolation_enabled: true,
        total_processed_frames: 60,
        total_interpolated_frames: 240
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
              contestant_nickname: '小張',
              confidence: 0.89,
              bounding_box: { x: 120, y: 80, width: 180, height: 240 },
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
              contestant_id: 1,
              contestant_name: '張三',
              contestant_nickname: '小張',
              confidence: 0.92,
              bounding_box: { x: 130, y: 85, width: 185, height: 245 },
              timestamp: 5.0,
              interpolated: false
            }
          ]
        },
        {
          frame_number: 300,
          timestamp: 10.0,
          contestants: []
        }
      ]
    };

    // Mock video element
    mockVideoElement = {
      currentTime: 0,
      paused: false,
      duration: 10.0
    } as HTMLVideoElement;
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('VideoTimestampSynchronizer', () => {
    it('should initialize with valid metadata', () => {
      const synchronizer = new VideoTimestampSynchronizer();
      const parsed = parseMetadata(validMetadata);
      
      const result = synchronizer.initialize(parsed);
      expect(result).toBe(true);
    });

    it('should reject invalid metadata', () => {
      const synchronizer = new VideoTimestampSynchronizer();
      const parsed = parseMetadata(null);
      
      const result = synchronizer.initialize(parsed);
      expect(result).toBe(false);
    });

    it('should sync to specific timestamp', () => {
      const synchronizer = new VideoTimestampSynchronizer();
      const parsed = parseMetadata(validMetadata);
      synchronizer.initialize(parsed);
      
      const result = synchronizer.syncToTimestamp(0.0);
      
      expect(result.timestamp).toBe(0.0);
      expect(result.faces).toHaveLength(1);
      expect(result.faces[0].contestant_name).toBe('張三');
      expect(result.frameNumber).toBe(0);
      expect(result.confidence).toBeGreaterThan(0);
    });

    it('should handle interpolation', () => {
      const synchronizer = new VideoTimestampSynchronizer();
      const parsed = parseMetadata(validMetadata);
      synchronizer.initialize(parsed);
      
      const result = synchronizer.syncToTimestamp(2.5); // Between 0.0 and 5.0
      
      expect(result.timestamp).toBe(2.5);
      expect(result.interpolated).toBe(true);
      expect(result.faces).toHaveLength(1);
      expect(result.faces[0].interpolated).toBe(true);
    });

    it('should start and stop synchronization', () => {
      const synchronizer = new VideoTimestampSynchronizer();
      const parsed = parseMetadata(validMetadata);
      synchronizer.initialize(parsed);
      
      expect(() => {
        synchronizer.start(mockVideoElement);
        synchronizer.stop();
      }).not.toThrow();
    });

    it('should handle sync callbacks', () => {
      const synchronizer = new VideoTimestampSynchronizer();
      const parsed = parseMetadata(validMetadata);
      synchronizer.initialize(parsed);
      
      const callback = vi.fn();
      const unsubscribe = synchronizer.onSync(callback);
      
      synchronizer.syncToTimestamp(0.0);
      expect(callback).toHaveBeenCalledOnce();
      
      unsubscribe();
      synchronizer.syncToTimestamp(1.0);
      expect(callback).toHaveBeenCalledOnce(); // Should not be called again
    });

    it('should update options', () => {
      const synchronizer = new VideoTimestampSynchronizer();
      const parsed = parseMetadata(validMetadata);
      synchronizer.initialize(parsed);
      
      expect(() => {
        synchronizer.updateOptions({ toleranceSeconds: 1.0 });
      }).not.toThrow();
    });

    it('should get current state', () => {
      const synchronizer = new VideoTimestampSynchronizer();
      const parsed = parseMetadata(validMetadata);
      synchronizer.initialize(parsed);
      
      const state = synchronizer.getCurrentState();
      expect(state).toHaveProperty('currentTimestamp');
      expect(state).toHaveProperty('currentFaces');
      expect(state).toHaveProperty('isPlaying');
    });

    it('should get statistics', () => {
      const synchronizer = new VideoTimestampSynchronizer();
      const parsed = parseMetadata(validMetadata);
      synchronizer.initialize(parsed);
      
      const stats = synchronizer.getStats();
      expect(stats).toHaveProperty('totalFrames');
      expect(stats).toHaveProperty('processedFrames');
      expect(stats).toHaveProperty('interpolatedFrames');
      expect(stats).toHaveProperty('averageConfidence');
      expect(stats.totalFrames).toBe(3);
      expect(stats.processedFrames).toBe(60);
    });

    it('should preload time range', () => {
      const synchronizer = new VideoTimestampSynchronizer();
      const parsed = parseMetadata(validMetadata);
      synchronizer.initialize(parsed);
      
      expect(() => {
        synchronizer.preloadTimeRange(0, 5);
      }).not.toThrow();
    });

    it('should clear cache', () => {
      const synchronizer = new VideoTimestampSynchronizer();
      const parsed = parseMetadata(validMetadata);
      synchronizer.initialize(parsed);
      
      expect(() => {
        synchronizer.clearCache();
      }).not.toThrow();
    });
  });

  describe('createVideoSynchronizer', () => {
    it('should create synchronizer with default options', () => {
      const synchronizer = createVideoSynchronizer();
      expect(synchronizer).toBeInstanceOf(VideoTimestampSynchronizer);
    });

    it('should create synchronizer with custom options', () => {
      const options: Partial<SynchronizationOptions> = {
        toleranceSeconds: 1.0,
        interpolationEnabled: false
      };
      
      const synchronizer = createVideoSynchronizer(options);
      expect(synchronizer).toBeInstanceOf(VideoTimestampSynchronizer);
    });
  });

  describe('syncTimestamp', () => {
    it('should sync timestamp manually', () => {
      const parsed = parseMetadata(validMetadata);
      const result = syncTimestamp(parsed, 0.0);
      
      expect(result.timestamp).toBe(0.0);
      expect(result.faces).toHaveLength(1);
      expect(result.frameNumber).toBe(0);
      expect(result.confidence).toBeGreaterThan(0);
    });

    it('should handle interpolation in manual sync', () => {
      const parsed = parseMetadata(validMetadata);
      const result = syncTimestamp(parsed, 2.5);
      
      expect(result.timestamp).toBe(2.5);
      expect(result.interpolated).toBe(true);
      expect(result.faces).toHaveLength(1);
    });

    it('should respect tolerance in manual sync', () => {
      const parsed = parseMetadata(validMetadata);
      const result = syncTimestamp(parsed, 7.5, { tolerance: 0.1 });
      
      expect(result.faces).toHaveLength(0); // Outside tolerance
      expect(result.confidence).toBe(0);
    });
  });

  describe('validateSyncPerformance', () => {
    it('should validate performance', async () => {
      const synchronizer = new VideoTimestampSynchronizer();
      const parsed = parseMetadata(validMetadata);
      synchronizer.initialize(parsed);
      
      // Mock performance validation with shorter duration
      const performancePromise = validateSyncPerformance(synchronizer, 0.1);
      
      // Trigger some sync events
      synchronizer.syncToTimestamp(0.0);
      synchronizer.syncToTimestamp(1.0);
      synchronizer.syncToTimestamp(2.0);
      
      const results = await performancePromise;
      
      expect(results).toHaveProperty('averageLatency');
      expect(results).toHaveProperty('maxLatency');
      expect(results).toHaveProperty('frameDrops');
      expect(results).toHaveProperty('accuracy');
    });
  });

  describe('Error Handling', () => {
    it('should handle uninitialized synchronizer', () => {
      const synchronizer = new VideoTimestampSynchronizer();
      
      // Should not throw, but should return empty result
      const result = synchronizer.syncToTimestamp(0.0);
      expect(result.faces).toHaveLength(0);
      expect(result.confidence).toBe(0);
    });

    it('should handle callback errors gracefully', () => {
      const synchronizer = new VideoTimestampSynchronizer();
      const parsed = parseMetadata(validMetadata);
      synchronizer.initialize(parsed);
      
      const errorCallback = vi.fn(() => {
        throw new Error('Callback error');
      });
      
      synchronizer.onSync(errorCallback);
      
      // Should not throw even if callback throws
      expect(() => {
        synchronizer.syncToTimestamp(0.0);
      }).not.toThrow();
      
      expect(errorCallback).toHaveBeenCalled();
    });

    it('should handle video element without duration', () => {
      const synchronizer = new VideoTimestampSynchronizer();
      const parsed = parseMetadata(validMetadata);
      synchronizer.initialize(parsed);
      
      const videoWithoutDuration = {
        ...mockVideoElement,
        duration: NaN
      } as HTMLVideoElement;
      
      expect(() => {
        synchronizer.start(videoWithoutDuration);
      }).not.toThrow();
    });
  });

  describe('Performance Optimizations', () => {
    it('should handle high-frequency timestamp updates', () => {
      const synchronizer = new VideoTimestampSynchronizer();
      const parsed = parseMetadata(validMetadata);
      synchronizer.initialize(parsed);
      
      // Simulate rapid timestamp updates
      const timestamps = Array.from({ length: 100 }, (_, i) => i * 0.1);
      
      expect(() => {
        timestamps.forEach(timestamp => {
          synchronizer.syncToTimestamp(timestamp);
        });
      }).not.toThrow();
    });

    it('should handle large metadata efficiently', () => {
      // Create metadata with many frames
      const largeTimeline = Array.from({ length: 1000 }, (_, i) => ({
        frame_number: i,
        timestamp: i * 0.1,
        contestants: i % 10 === 0 ? [
          {
            id: `face_${i}_0`,
            contestant_id: 1,
            contestant_name: '張三',
            contestant_nickname: '小張',
            confidence: 0.8 + Math.random() * 0.2,
            bounding_box: { x: 100 + i, y: 80, width: 180, height: 240 },
            timestamp: i * 0.1,
            interpolated: false
          }
        ] : []
      }));

      const largeMetadata = {
        ...validMetadata,
        timeline: largeTimeline
      };

      const synchronizer = new VideoTimestampSynchronizer();
      const parsed = parseMetadata(largeMetadata);
      
      const startTime = performance.now();
      synchronizer.initialize(parsed);
      const initTime = performance.now() - startTime;
      
      // Initialization should be reasonably fast even with large metadata
      expect(initTime).toBeLessThan(100); // Less than 100ms
      
      // Sync operations should also be fast
      const syncStartTime = performance.now();
      synchronizer.syncToTimestamp(50.0);
      const syncTime = performance.now() - syncStartTime;
      
      expect(syncTime).toBeLessThan(10); // Less than 10ms
    });
  });
});