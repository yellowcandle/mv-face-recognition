/**
 * Metadata parsing utilities for face detection data processing
 * Handles timeline data indexing, face data validation, and timestamp synchronization
 */

export interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface DetectedFace {
  id: string;
  contestant_id: number;
  contestant_name: string;
  contestant_nickname: string;
  confidence: number;
  bounding_box: BoundingBox;
  timestamp: number;
  interpolated?: boolean;
}

export interface TimelineFrame {
  frame_number: number;
  timestamp: number;
  contestants: DetectedFace[];
}

export interface VideoInfo {
  filename: string;
  duration: number;
  fps: number;
}

export interface ProcessingInfo {
  processing_interval: number;
  interpolation_enabled: boolean;
  total_processed_frames: number;
  total_interpolated_frames: number;
}

export interface FaceMetadata {
  video_info: VideoInfo;
  processing_info: ProcessingInfo;
  timeline: TimelineFrame[];
}

export interface ParsedMetadata {
  metadata: FaceMetadata;
  timestampIndex: Map<number, TimelineFrame>;
  sortedTimestamps: number[];
  isValid: boolean;
  errors: string[];
}

/**
 * Validates face detection metadata structure and data integrity
 */
export function validateMetadata(metadata: any): { isValid: boolean; errors: string[] } {
  const errors: string[] = [];

  // Check top-level structure
  if (!metadata || typeof metadata !== 'object') {
    errors.push('Metadata must be a valid object');
    return { isValid: false, errors };
  }

  // Validate video_info
  if (!metadata.video_info) {
    errors.push('Missing video_info section');
  } else {
    const { filename, duration, fps } = metadata.video_info;
    if (!filename || typeof filename !== 'string') {
      errors.push('Invalid or missing video filename');
    }
    if (typeof duration !== 'number' || duration <= 0) {
      errors.push('Invalid video duration');
    }
    if (typeof fps !== 'number' || fps <= 0) {
      errors.push('Invalid video fps');
    }
  }

  // Validate processing_info
  if (!metadata.processing_info) {
    errors.push('Missing processing_info section');
  } else {
    const { processing_interval, interpolation_enabled, total_processed_frames, total_interpolated_frames } = metadata.processing_info;
    if (typeof processing_interval !== 'number' || processing_interval <= 0) {
      errors.push('Invalid processing_interval');
    }
    if (typeof interpolation_enabled !== 'boolean') {
      errors.push('Invalid interpolation_enabled flag');
    }
    if (typeof total_processed_frames !== 'number' || total_processed_frames < 0) {
      errors.push('Invalid total_processed_frames');
    }
    if (typeof total_interpolated_frames !== 'number' || total_interpolated_frames < 0) {
      errors.push('Invalid total_interpolated_frames');
    }
  }

  // Validate timeline
  if (!Array.isArray(metadata.timeline)) {
    errors.push('Timeline must be an array');
  } else {
    metadata.timeline.forEach((frame: any, index: number) => {
      if (!frame || typeof frame !== 'object') {
        errors.push(`Timeline frame ${index} is invalid`);
        return;
      }

      if (typeof frame.frame_number !== 'number' || frame.frame_number < 0) {
        errors.push(`Timeline frame ${index} has invalid frame_number`);
      }

      if (typeof frame.timestamp !== 'number' || frame.timestamp < 0) {
        errors.push(`Timeline frame ${index} has invalid timestamp`);
      }

      if (!Array.isArray(frame.contestants)) {
        errors.push(`Timeline frame ${index} contestants must be an array`);
      } else {
        // Skip individual face validation during metadata validation
        // Face validation will happen during sanitization
        if (!Array.isArray(frame.contestants)) {
          errors.push(`Timeline frame ${index} contestants must be an array`);
        }
      }
    });
  }

  return { isValid: errors.length === 0, errors };
}

/**
 * Validates individual face detection data
 */
export function validateFaceData(face: any): string[] {
  const errors: string[] = [];

  if (!face || typeof face !== 'object') {
    errors.push('Face data must be an object');
    return errors;
  }

  // Required fields
  if (!face.id || typeof face.id !== 'string') {
    errors.push('Missing or invalid face id');
  }

  if (typeof face.contestant_id !== 'number' || face.contestant_id < 0) {
    errors.push('Invalid contestant_id');
  }

  if (!face.contestant_name || typeof face.contestant_name !== 'string') {
    errors.push('Missing or invalid contestant_name');
  }

  if (typeof face.confidence !== 'number' || face.confidence < 0 || face.confidence > 1) {
    errors.push('Confidence must be a number between 0 and 1');
  }

  if (typeof face.timestamp !== 'number' || face.timestamp < 0) {
    errors.push('Invalid timestamp');
  }

  // Validate bounding box
  if (!face.bounding_box || typeof face.bounding_box !== 'object') {
    errors.push('Missing or invalid bounding_box');
  } else {
    const { x, y, width, height } = face.bounding_box;
    if (typeof x !== 'number' || x < 0) {
      errors.push('Invalid bounding box x coordinate');
    }
    if (typeof y !== 'number' || y < 0) {
      errors.push('Invalid bounding box y coordinate');
    }
    if (typeof width !== 'number' || width <= 0) {
      errors.push('Invalid bounding box width');
    }
    if (typeof height !== 'number' || height <= 0) {
      errors.push('Invalid bounding box height');
    }
  }

  return errors;
}

/**
 * Sanitizes face detection data by cleaning and normalizing values
 */
export function sanitizeFaceData(face: any): DetectedFace | null {
  try {
    if (!face || typeof face !== 'object') {
      return null;
    }

    // Sanitize and normalize first, then validate
    const sanitized: DetectedFace = {
      id: String(face.id || '').trim() || `face_${Date.now()}`,
      contestant_id: Math.max(0, Math.floor(Number(face.contestant_id) || 0)),
      contestant_name: String(face.contestant_name || 'Unknown').trim(),
      contestant_nickname: String(face.contestant_nickname || '').trim(),
      confidence: Math.max(0, Math.min(1, Number(face.confidence) || 0)),
      timestamp: Math.max(0, Number(face.timestamp) || 0),
      interpolated: Boolean(face.interpolated),
      bounding_box: {
        x: Math.max(0, Number(face.bounding_box?.x) || 0),
        y: Math.max(0, Number(face.bounding_box?.y) || 0),
        width: Math.max(1, Number(face.bounding_box?.width) || 1),
        height: Math.max(1, Number(face.bounding_box?.height) || 1)
      }
    };

    // Validate the sanitized data
    const errors = validateFaceData(sanitized);
    if (errors.length > 0) {
      console.warn('Face data validation failed after sanitization:', errors);
      return null;
    }

    return sanitized;
  } catch (error) {
    console.error('Error sanitizing face data:', error);
    return null;
  }
}

/**
 * Parses and indexes timeline data for efficient timestamp lookups
 */
export function parseMetadata(rawMetadata: any): ParsedMetadata {
  // First validate the basic structure
  const basicValidation = validateMetadata(rawMetadata);
  
  // If basic structure is invalid, return early
  if (!basicValidation.isValid) {
    return {
      metadata: rawMetadata,
      timestampIndex: new Map(),
      sortedTimestamps: [],
      isValid: false,
      errors: basicValidation.errors
    };
  }

  const metadata = rawMetadata as FaceMetadata;
  const timestampIndex = new Map<number, TimelineFrame>();
  const sortedTimestamps: number[] = [];
  const processingErrors: string[] = [];

  try {
    // Process timeline frames with sanitization
    metadata.timeline.forEach((frame, frameIndex) => {
      try {
        // Sanitize all faces in the frame
        const sanitizedContestants = frame.contestants
          .map((face, faceIndex) => {
            const sanitized = sanitizeFaceData(face);
            if (!sanitized) {
              processingErrors.push(`Frame ${frameIndex}, face ${faceIndex}: Could not sanitize face data`);
            }
            return sanitized;
          })
          .filter((face): face is DetectedFace => face !== null);

        const processedFrame: TimelineFrame = {
          frame_number: frame.frame_number,
          timestamp: frame.timestamp,
          contestants: sanitizedContestants
        };

        // Index by timestamp for fast lookup
        timestampIndex.set(frame.timestamp, processedFrame);
        sortedTimestamps.push(frame.timestamp);
      } catch (error) {
        processingErrors.push(`Frame ${frameIndex}: ${error instanceof Error ? error.message : 'Unknown error'}`);
      }
    });

    // Sort timestamps for binary search
    sortedTimestamps.sort((a, b) => a - b);

    return {
      metadata,
      timestampIndex,
      sortedTimestamps,
      isValid: true,
      errors: processingErrors
    };
  } catch (error) {
    return {
      metadata: rawMetadata,
      timestampIndex: new Map(),
      sortedTimestamps: [],
      isValid: false,
      errors: [...basicValidation.errors, `Processing error: ${error instanceof Error ? error.message : 'Unknown error'}`]
    };
  }
}

/**
 * Finds the closest timeline frame to a given timestamp
 */
export function findClosestFrame(
  parsedMetadata: ParsedMetadata, 
  targetTimestamp: number
): TimelineFrame | null {
  if (!parsedMetadata.isValid || parsedMetadata.sortedTimestamps.length === 0) {
    return null;
  }

  const { timestampIndex, sortedTimestamps } = parsedMetadata;

  // Binary search for closest timestamp
  let left = 0;
  let right = sortedTimestamps.length - 1;
  let closestTimestamp = sortedTimestamps[0];
  let minDiff = Math.abs(targetTimestamp - closestTimestamp);

  while (left <= right) {
    const mid = Math.floor((left + right) / 2);
    const currentTimestamp = sortedTimestamps[mid];
    const diff = Math.abs(targetTimestamp - currentTimestamp);

    if (diff < minDiff) {
      minDiff = diff;
      closestTimestamp = currentTimestamp;
    }

    if (currentTimestamp < targetTimestamp) {
      left = mid + 1;
    } else if (currentTimestamp > targetTimestamp) {
      right = mid - 1;
    } else {
      // Exact match
      break;
    }
  }

  return timestampIndex.get(closestTimestamp) || null;
}

/**
 * Finds faces at a specific timestamp with interpolation support
 */
export function findFacesAtTimestamp(
  parsedMetadata: ParsedMetadata,
  targetTimestamp: number,
  toleranceSeconds: number = 0.5
): DetectedFace[] {
  if (!parsedMetadata.isValid) {
    return [];
  }

  // First try exact or close match
  const exactFrame = findClosestFrame(parsedMetadata, targetTimestamp);
  if (exactFrame && Math.abs(exactFrame.timestamp - targetTimestamp) <= toleranceSeconds) {
    return exactFrame.contestants;
  }

  // If interpolation is enabled and we're within a reasonable range, try to interpolate
  if (parsedMetadata.metadata.processing_info.interpolation_enabled && toleranceSeconds > 0.2) {
    return interpolateFacesAtTimestamp(parsedMetadata, targetTimestamp);
  }

  return [];
}

/**
 * Interpolates face positions between keyframes for smooth transitions
 */
export function interpolateFacesAtTimestamp(
  parsedMetadata: ParsedMetadata,
  targetTimestamp: number
): DetectedFace[] {
  const { sortedTimestamps, timestampIndex } = parsedMetadata;

  // Find surrounding frames
  let beforeFrame: TimelineFrame | null = null;
  let afterFrame: TimelineFrame | null = null;

  for (let i = 0; i < sortedTimestamps.length - 1; i++) {
    const currentTime = sortedTimestamps[i];
    const nextTime = sortedTimestamps[i + 1];

    if (targetTimestamp >= currentTime && targetTimestamp <= nextTime) {
      beforeFrame = timestampIndex.get(currentTime) || null;
      afterFrame = timestampIndex.get(nextTime) || null;
      break;
    }
  }

  if (!beforeFrame || !afterFrame) {
    // Return closest frame if interpolation not possible
    const closestFrame = findClosestFrame(parsedMetadata, targetTimestamp);
    return closestFrame ? closestFrame.contestants : [];
  }

  // Calculate interpolation factor
  const timeDiff = afterFrame.timestamp - beforeFrame.timestamp;
  const factor = timeDiff > 0 ? (targetTimestamp - beforeFrame.timestamp) / timeDiff : 0;

  // Interpolate faces that exist in both frames
  const interpolatedFaces: DetectedFace[] = [];

  beforeFrame.contestants.forEach(beforeFace => {
    // Find corresponding face in after frame
    const afterFace = afterFrame!.contestants.find(
      face => face.contestant_id === beforeFace.contestant_id
    );

    if (afterFace) {
      // Interpolate position and confidence
      const interpolatedFace: DetectedFace = {
        ...beforeFace,
        id: `interpolated_${beforeFace.id}_${targetTimestamp}`,
        timestamp: targetTimestamp,
        interpolated: true,
        confidence: beforeFace.confidence + (afterFace.confidence - beforeFace.confidence) * factor,
        bounding_box: {
          x: beforeFace.bounding_box.x + (afterFace.bounding_box.x - beforeFace.bounding_box.x) * factor,
          y: beforeFace.bounding_box.y + (afterFace.bounding_box.y - beforeFace.bounding_box.y) * factor,
          width: beforeFace.bounding_box.width + (afterFace.bounding_box.width - beforeFace.bounding_box.width) * factor,
          height: beforeFace.bounding_box.height + (afterFace.bounding_box.height - beforeFace.bounding_box.height) * factor
        }
      };

      interpolatedFaces.push(interpolatedFace);
    } else {
      // Face only exists in before frame, fade out confidence
      const fadedFace: DetectedFace = {
        ...beforeFace,
        id: `fading_${beforeFace.id}_${targetTimestamp}`,
        timestamp: targetTimestamp,
        interpolated: true,
        confidence: beforeFace.confidence * (1 - factor)
      };

      // Only include if confidence is still reasonable
      if (fadedFace.confidence > 0.3) {
        interpolatedFaces.push(fadedFace);
      }
    }
  });

  // Add faces that only exist in after frame (fade in)
  afterFrame.contestants.forEach(afterFace => {
    const existsInBefore = beforeFrame!.contestants.some(
      face => face.contestant_id === afterFace.contestant_id
    );

    if (!existsInBefore) {
      const fadingInFace: DetectedFace = {
        ...afterFace,
        id: `fading_in_${afterFace.id}_${targetTimestamp}`,
        timestamp: targetTimestamp,
        interpolated: true,
        confidence: afterFace.confidence * factor
      };

      // Only include if confidence is reasonable
      if (fadingInFace.confidence > 0.3) {
        interpolatedFaces.push(fadingInFace);
      }
    }
  });

  return interpolatedFaces;
}

/**
 * Gets frame-accurate face data lookup with caching
 */
export class FrameAccurateFaceLookup {
  private cache = new Map<string, DetectedFace[]>();
  private cacheSize = 100; // Maximum cache entries

  constructor(private parsedMetadata: ParsedMetadata) {}

  /**
   * Gets faces at timestamp with caching for performance
   */
  getFacesAtTimestamp(timestamp: number, toleranceSeconds: number = 0.5): DetectedFace[] {
    const cacheKey = `${timestamp.toFixed(3)}_${toleranceSeconds}`;
    
    if (this.cache.has(cacheKey)) {
      return this.cache.get(cacheKey)!;
    }

    const faces = findFacesAtTimestamp(this.parsedMetadata, timestamp, toleranceSeconds);
    
    // Manage cache size
    if (this.cache.size >= this.cacheSize) {
      const firstKey = this.cache.keys().next().value;
      if (firstKey !== undefined) {
        this.cache.delete(firstKey);
      }
    }

    this.cache.set(cacheKey, faces);
    return faces;
  }

  /**
   * Clears the lookup cache
   */
  clearCache(): void {
    this.cache.clear();
  }

  /**
   * Preloads faces for a time range to improve performance
   */
  preloadTimeRange(startTime: number, endTime: number, intervalSeconds: number = 0.1): void {
    for (let time = startTime; time <= endTime; time += intervalSeconds) {
      this.getFacesAtTimestamp(time);
    }
  }
}