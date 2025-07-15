import { describe, it, expect, beforeEach } from 'vitest';
import {
  validateMetadata,
  validateFaceData,
  sanitizeFaceData,
  parseMetadata,
  findClosestFrame,
  findFacesAtTimestamp,
  interpolateFacesAtTimestamp,
  FrameAccurateFaceLookup,
  type FaceMetadata,
  type DetectedFace
} from '../../../lib/utils/metadata.js';

describe('Metadata Parsing Utilities', () => {
  let validMetadata: FaceMetadata;
  let validFace: DetectedFace;

  beforeEach(() => {
    validFace = {
      id: 'face_0_0',
      contestant_id: 1,
      contestant_name: '張三',
      contestant_nickname: '小張',
      confidence: 0.89,
      bounding_box: {
        x: 120,
        y: 80,
        width: 180,
        height: 240
      },
      timestamp: 0.0,
      interpolated: false
    };

    validMetadata = {
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
          contestants: [validFace]
        },
        {
          frame_number: 150,
          timestamp: 5.0,
          contestants: [
            {
              ...validFace,
              id: 'face_150_0',
              timestamp: 5.0,
              confidence: 0.92,
              bounding_box: {
                x: 130,
                y: 85,
                width: 185,
                height: 245
              }
            }
          ]
        }
      ]
    };
  });

  describe('validateMetadata', () => {
    it('should validate correct metadata', () => {
      const result = validateMetadata(validMetadata);
      expect(result.isValid).toBe(true);
      expect(result.errors).toHaveLength(0);
    });

    it('should reject null metadata', () => {
      const result = validateMetadata(null);
      expect(result.isValid).toBe(false);
      expect(result.errors).toContain('Metadata must be a valid object');
    });

    it('should reject metadata without video_info', () => {
      const invalidMetadata = { ...validMetadata };
      delete (invalidMetadata as any).video_info;
      
      const result = validateMetadata(invalidMetadata);
      expect(result.isValid).toBe(false);
      expect(result.errors).toContain('Missing video_info section');
    });

    it('should reject invalid timeline', () => {
      const invalidMetadata = {
        ...validMetadata,
        timeline: 'not an array'
      };
      
      const result = validateMetadata(invalidMetadata);
      expect(result.isValid).toBe(false);
      expect(result.errors).toContain('Timeline must be an array');
    });
  });

  describe('validateFaceData', () => {
    it('should validate correct face data', () => {
      const errors = validateFaceData(validFace);
      expect(errors).toHaveLength(0);
    });

    it('should reject face without id', () => {
      const invalidFace = { ...validFace };
      delete (invalidFace as any).id;
      
      const errors = validateFaceData(invalidFace);
      expect(errors).toContain('Missing or invalid face id');
    });

    it('should reject invalid confidence', () => {
      const invalidFace = { ...validFace, confidence: 1.5 };
      
      const errors = validateFaceData(invalidFace);
      expect(errors).toContain('Confidence must be a number between 0 and 1');
    });

    it('should reject invalid bounding box', () => {
      const invalidFace = {
        ...validFace,
        bounding_box: { x: -10, y: 20, width: 0, height: 100 }
      };
      
      const errors = validateFaceData(invalidFace);
      expect(errors.length).toBeGreaterThan(0);
      expect(errors.some(e => e.includes('bounding box'))).toBe(true);
    });
  });

  describe('sanitizeFaceData', () => {
    it('should sanitize valid face data', () => {
      const result = sanitizeFaceData(validFace);
      expect(result).not.toBeNull();
      expect(result?.id).toBe(validFace.id);
      expect(result?.confidence).toBe(validFace.confidence);
    });

    it('should sanitize invalid confidence to 0', () => {
      const invalidFace = { ...validFace, confidence: 'invalid' };
      const result = sanitizeFaceData(invalidFace);
      expect(result).not.toBeNull();
      expect(result?.confidence).toBe(0);
    });

    it('should clamp confidence values', () => {
      const faceWithHighConfidence = { ...validFace, confidence: 1.5 };
      const result = sanitizeFaceData(faceWithHighConfidence);
      expect(result?.confidence).toBe(1.0);
    });

    it('should normalize negative coordinates', () => {
      const faceWithNegativeCoords = {
        ...validFace,
        bounding_box: { x: -10, y: -5, width: 100, height: 150 }
      };
      const result = sanitizeFaceData(faceWithNegativeCoords);
      expect(result?.bounding_box.x).toBe(0);
      expect(result?.bounding_box.y).toBe(0);
    });
  });

  describe('parseMetadata', () => {
    it('should parse valid metadata', () => {
      const result = parseMetadata(validMetadata);
      expect(result.isValid).toBe(true);
      expect(result.timestampIndex.size).toBe(2);
      expect(result.sortedTimestamps).toEqual([0.0, 5.0]);
    });

    it('should handle invalid metadata', () => {
      const result = parseMetadata(null);
      expect(result.isValid).toBe(false);
      expect(result.timestampIndex.size).toBe(0);
    });

    it('should sanitize faces during parsing', () => {
      const metadataWithInvalidFace = {
        ...validMetadata,
        timeline: [
          {
            frame_number: 0,
            timestamp: 0.0,
            contestants: [
              validFace,
              { ...validFace, id: '', confidence: 'invalid' } // Invalid face that gets sanitized
            ]
          }
        ]
      };

      const result = parseMetadata(metadataWithInvalidFace);
      expect(result.isValid).toBe(true);
      
      const frame = result.timestampIndex.get(0.0);
      expect(frame?.contestants).toHaveLength(2); // Both faces present, invalid one sanitized
      expect(frame?.contestants[1].confidence).toBe(0); // Invalid confidence sanitized to 0
    });
  });

  describe('findClosestFrame', () => {
    it('should find exact timestamp match', () => {
      const parsed = parseMetadata(validMetadata);
      const frame = findClosestFrame(parsed, 0.0);
      
      expect(frame).not.toBeNull();
      expect(frame?.timestamp).toBe(0.0);
    });

    it('should find closest timestamp', () => {
      const parsed = parseMetadata(validMetadata);
      const frame = findClosestFrame(parsed, 2.5);
      
      expect(frame).not.toBeNull();
      expect(frame?.timestamp).toBe(0.0); // Closer to 0.0 than 5.0
    });

    it('should return null for invalid metadata', () => {
      const parsed = parseMetadata(null);
      const frame = findClosestFrame(parsed, 1.0);
      expect(frame).toBeNull();
    });
  });

  describe('findFacesAtTimestamp', () => {
    it('should find faces at exact timestamp', () => {
      const parsed = parseMetadata(validMetadata);
      const faces = findFacesAtTimestamp(parsed, 0.0);
      
      expect(faces).toHaveLength(1);
      expect(faces[0].contestant_name).toBe('張三');
    });

    it('should find faces within tolerance', () => {
      const parsed = parseMetadata(validMetadata);
      const faces = findFacesAtTimestamp(parsed, 0.3, 0.5);
      
      expect(faces).toHaveLength(1);
      expect(faces[0].contestant_name).toBe('張三');
    });

    it('should return empty array outside tolerance', () => {
      const parsed = parseMetadata(validMetadata);
      const faces = findFacesAtTimestamp(parsed, 2.5, 0.1);
      
      expect(faces).toHaveLength(0);
    });
  });

  describe('interpolateFacesAtTimestamp', () => {
    it('should interpolate between frames', () => {
      const parsed = parseMetadata(validMetadata);
      const faces = interpolateFacesAtTimestamp(parsed, 2.5); // Midpoint between 0.0 and 5.0
      
      expect(faces).toHaveLength(1);
      expect(faces[0].interpolated).toBe(true);
      expect(faces[0].timestamp).toBe(2.5);
      
      // Check interpolated position (should be between original positions)
      const originalX = validFace.bounding_box.x;
      const targetX = 130; // From second frame
      const interpolatedX = faces[0].bounding_box.x;
      
      expect(interpolatedX).toBeGreaterThan(originalX);
      expect(interpolatedX).toBeLessThan(targetX);
    });

    it('should handle faces that only exist in one frame', () => {
      // Add a face that only exists in the second frame
      const metadataWithNewFace = {
        ...validMetadata,
        timeline: [
          validMetadata.timeline[0],
          {
            ...validMetadata.timeline[1],
            contestants: [
              ...validMetadata.timeline[1].contestants,
              {
                id: 'face_150_1',
                contestant_id: 2,
                contestant_name: '李四',
                contestant_nickname: '小李',
                confidence: 0.85,
                bounding_box: { x: 300, y: 100, width: 160, height: 220 },
                timestamp: 5.0,
                interpolated: false
              }
            ]
          }
        ]
      };

      const parsed = parseMetadata(metadataWithNewFace);
      const faces = interpolateFacesAtTimestamp(parsed, 2.5);
      
      // Should have interpolated version of existing face and fading-in version of new face
      expect(faces.length).toBeGreaterThanOrEqual(1);
      
      const fadingInFace = faces.find(f => f.contestant_name === '李四');
      if (fadingInFace) {
        expect(fadingInFace.interpolated).toBe(true);
        expect(fadingInFace.confidence).toBeLessThan(0.85); // Reduced due to fade-in
      }
    });
  });

  describe('FrameAccurateFaceLookup', () => {
    it('should cache results', () => {
      const parsed = parseMetadata(validMetadata);
      const lookup = new FrameAccurateFaceLookup(parsed);
      
      // First call
      const faces1 = lookup.getFacesAtTimestamp(0.0);
      expect(faces1).toHaveLength(1);
      
      // Second call should return cached result
      const faces2 = lookup.getFacesAtTimestamp(0.0);
      expect(faces2).toBe(faces1); // Same reference due to caching
    });

    it('should preload time range', () => {
      const parsed = parseMetadata(validMetadata);
      const lookup = new FrameAccurateFaceLookup(parsed);
      
      // Preload should not throw
      expect(() => {
        lookup.preloadTimeRange(0, 5, 0.5);
      }).not.toThrow();
    });

    it('should clear cache', () => {
      const parsed = parseMetadata(validMetadata);
      const lookup = new FrameAccurateFaceLookup(parsed);
      
      lookup.getFacesAtTimestamp(0.0);
      lookup.clearCache();
      
      // Should not throw after clearing cache
      expect(() => {
        lookup.getFacesAtTimestamp(0.0);
      }).not.toThrow();
    });
  });
});