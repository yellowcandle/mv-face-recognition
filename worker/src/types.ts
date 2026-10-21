/**
 * Type definitions for Cloudflare Workers Face Recognition API
 */

/**
 * Cloudflare Worker Environment Bindings
 */
export interface CloudflareEnv {
  /** R2 bucket for video storage */
  BUCKET: R2Bucket;
  /** KV namespace for metadata storage */
  KV_NAMESPACE: KVNamespace;
  /** Optional log level configuration */
  LOG_LEVEL?: string;
}

/**
 * Video metadata stored in KV
 */
export interface VideoMetadata {
  /** Unique video identifier */
  id: string;
  /** Video title/name */
  title: string;
  /** Duration in seconds */
  duration: number;
  /** Processing status */
  processed: boolean;
  /** Optional thumbnail URL */
  thumbnail_url?: string;
  /** Upload timestamp */
  uploaded_at?: string;
  /** Processing completion timestamp */
  processed_at?: string;
  /** Video file size in bytes */
  file_size?: number;
  /** Video resolution (e.g., "1920x1080") */
  resolution?: string;
}

/**
 * Face detection — one shape at every serving boundary (`/faces/detect`, the realtime
 * WebSocket `frame_update`) and the same shape `mvp-processor` stores per detection.
 */
export interface FaceDetection {
  /** Bounding box in frame fractions, canonical [x1, y1, x2, y2] — never reordered, never scaled */
  bbox: [number, number, number, number];
  /** Raw cosine similarity to the contestant's best reference embedding; null when unmatched */
  match_score: number | null;
  /** Detector's own face score; present on every detection, matched or not */
  det_score: number;
  /** Contestant number (編號), null when unmatched */
  contestant_id: string | null;
  /** Full name (姓名), null when unmatched */
  contestant_name: string | null;
  /** Nickname (暱稱), null when unmatched */
  contestant_nickname: string | null;
  /** Track id within the video, null when the detector assigned none */
  /** Whether this detection was identified (`contestant_id !== null`) */
  matched: boolean;
}

/**
 * Contestant information from metadata
 */
export interface ContestantInfo {
  /** Contestant number (編號) */
  id: string;
  /** Full name (姓名) */
  name: string;
  /** Nickname (暱稱) */
  nickname: string;
  /** Age (年齡) */
  age: number;
  /** Profile photo URL */
  photo_url?: string;
}

/**
 * Generic API response wrapper
 */
export interface APIResponse<T = unknown> {
  /** Response data (when successful) */
  data?: T;
  /** Error message (when failed) */
  error?: string;
  /** HTTP status code */
  status: number;
  /** Optional metadata */
  meta?: {
    /** Total count for paginated results */
    total?: number;
    /** Current page */
    page?: number;
    /** Items per page */
    per_page?: number;
  };
}

/**
 * Video processing status
 */
export interface ProcessingStatus {
  /** Video ID being processed */
  video_id: string;
  /** Processing status */
  status: 'pending' | 'processing' | 'completed' | 'failed';
  /** Progress percentage (0-100) */
  progress: number;
  /** Current processing stage */
  stage?: string;
  /** Processed frames count */
  frames_processed?: number;
  /** Total frames count */
  total_frames?: number;
  /** Error message if failed */
  error?: string;
}

/**
 * Video analytics data
 */
export interface VideoAnalytics {
  /** Video ID */
  video_id: string;
  /** Total unique contestants detected */
  total_contestants: number;
  /** Total face detections */
  total_detections: number;
  /** Detection breakdown by contestant */
  contestant_breakdown: Array<{
    contestant_id: string;
    name: string;
    detection_count: number;
    /** Mean raw cosine across this contestant's recognitions */
    average_match_score: number;
    screen_time_seconds: number;
  }>;
  /** Processing metadata */
  metadata: {
    /** Total processing time in seconds */
    processing_time: number;
    /** Video duration in seconds */
    video_duration: number;
    /** Frames analyzed */
    frames_analyzed: number;
  };
}

/**
 * WebSocket message types for real-time updates
 */
export type WebSocketMessage =
  | {
      type: 'frame_update';
      data: {
        frame_number: number;
        timestamp: number;
        faces: FaceDetection[];
      };
    }
  | {
      type: 'processing_status';
      data: ProcessingStatus;
    }
  | {
      type: 'error';
      data: {
        message: string;
        code?: string;
      };
    }
  | {
      type: 'connection_ack';
      data: {
        session_id: string;
      };
    };

/**
 * HTTP request handler type
 */
export type RequestHandler = (
  pathname: string,
  request: Request,
  env: CloudflareEnv,
) => Promise<Response>;

/**
 * CORS headers type
 */
export interface CorsHeaders {
  'Access-Control-Allow-Origin': string;
  'Access-Control-Allow-Methods': string;
  'Access-Control-Allow-Headers': string;
  'Access-Control-Max-Age'?: string;
}
