export interface Contestant {
  id: string;
  name: string;
  nickname: string;
  age: number | null;
  has_embedding: boolean;
  reference_count: number;
  /** Cropped face thumbnail for the public gallery (R2). Absent until Phase 3 publishes it. */
  portrait_url?: string | null;
  avg_match_score: number;
  max_match_score: number;
  detection_count: number;
  videos_seen_in: number;
  quality: 'good' | 'weak' | 'missing';
}

export interface Video {
  id: string;
  name: string;
  stream_url: string;
  filename?: string;
}

export interface VideoInfo {
  filename: string;
  fps: number;
  frame_count: number;
  /**
   * SOURCE dimensions, display-only. They are not the detection space and not a
   * scale factor: no box may be multiplied or divided by them (see `bbox` below).
   */
  width: number;
  height: number;
  duration: number;
}

// Bbox contract: every stored face box is in FRAME FRACTIONS — a proportion of the
// frame's width or height, range 0..1 — written `[x1, y1, x2, y2]` (left, top, right,
// bottom) in that order. mvp-processor converts to fractions once, at the metadata
// write boundary; every serving path (local_api.py, worker handleFaceDetection,
// useViewerMetadata) passes the box through untouched. Nothing reorders it.
//
// To draw a box: multiply by the RENDERED element's dimensions and nothing else —
// `left = x1 * renderW`, `top = y1 * renderH`, `width = (x2 - x1) * renderW`,
// `height = (y2 - y1) * renderH`. No consumer scales a bbox by any width or height;
// `video_info.width`/`.height` and `video.videoWidth`/`.videoHeight` are NOT scale
// factors for it (see "Detection space" in CONTEXT.md).
export interface FaceDetection {
  bbox: [number, number, number, number]; // frame fractions, canonical [x1, y1, x2, y2]
  /** ByteTrack id within a shot; -1 when the detection was not tracked. */
  tracker_id?: number | null;
  match_score: number | null; // raw cosine; null when the detection is unmatched
  det_score: number; // the detector's own face score — always present, and the only score an unmatched detection carries
  contestant_id: string | null;
  contestant_name: string | null;
  contestant_nickname: string | null;
  matched: boolean; // === (contestant_id !== null)
}

// Matches the JSON emitted by mvp-processor (metadata_generator.py / process_video.py).
// One entry per DETECTION — matched or not: `frame_data[].detections` carries all 399
// of them, 260 of which carry no contestant.
export interface FrameDetection {
  contestant_id: string | null;
  contestant_name: string | null;
  contestant_nickname: string | null;
  match_score: number | null; // raw cosine; null when unmatched
  det_score: number;
  bbox: [number, number, number, number]; // frame fractions, canonical [x1, y1, x2, y2]
}

export interface FrameData {
  frame_number: number;
  timestamp: number;
  detections_count: number;
  recognitions_count: number;
  detections: FrameDetection[];
}

export interface ContestantTimelineEntry {
  appearances: Array<{
    timestamp: number;
    frame_number: number;
    match_score: number; // raw cosine
    bbox: [number, number, number, number]; // frame fractions, canonical [x1, y1, x2, y2]
  }>;
  total_appearances: number;
  average_match_score: number; // raw cosine
  first_appearance: number;
  last_appearance: number;
  contestant_info: { id: string; name: string; nickname: string };
}

export interface VideoMetadata {
  video_info: VideoInfo;
  processing_summary: {
    frames_processed: number;
    total_faces_detected: number;
    total_recognitions: number;
    unique_contestants: number;
    recognition_rate: number;
    match_score_stats?: { average: number; minimum: number; maximum: number };
    processing_timestamp?: string;
  };
  contestant_timeline: Record<string, ContestantTimelineEntry>;
  timeline_markers?: Array<{
    start_time: number;
    end_time: number;
    contestants: string[];
    recognition_count: number;
    average_match_score: number;
  }>;
  frame_data: FrameData[];
  /** What the pipeline actually ran, including the band cutoffs it applied (provisional). */
  recognition_config?: {
    acceptance_threshold: number;
    detection_model: string;
    band_cutoffs: { high: number; medium: number };
    provisional: boolean;
  };
}

export interface CoverageSummary {
  total: number;
  good: number;
  weak: number;
  missing: number;
  avg_match_score: number;
  recognition_rate: number;
  total_faces_detected: number;
  total_faces_recognized: number;
}

export interface CoverageData {
  contestants: Contestant[];
  summary: CoverageSummary;
}

export interface ConfusionPair {
  contestant_a: { id: string; name: string; nickname: string };
  contestant_b: { id: string; name: string; nickname: string };
  similarity: number;
}

export interface SimilarityData {
  labels: { id: string; name: string; nickname: string }[];
  matrix: number[][];
  stats: {
    min_off_diagonal: number;
    max_off_diagonal: number;
    mean_off_diagonal: number;
    contestant_count: number;
  };
}

// A FLAG is a human claim about who a detection really is, stored by the flagging API
// (local_api.py / the worker's flag routes). `confidence` here is that API's own field
// name for the detection's match score at the moment it was flagged — a raw cosine, or
// null when the flagged detection was unmatched. It survives the band rewrite
// deliberately: the flag/labelling schema is settled elsewhere (tickets 015/005), not by
// the recognition contract. Render it as a band, never as a percentage.
export interface FlaggedFace {
  id: string;
  contestant_id: number;
  video_id: string;
  timestamp: number;
  confidence: number | null;
  bbox: [number, number, number, number]; // frame fractions, canonical [x1, y1, x2, y2]
  status: 'pending' | 'accepted' | 'rejected';
  user_label?: string;
  thumbnail?: string;
}
