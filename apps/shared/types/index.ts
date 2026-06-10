export interface Contestant {
  id: string;
  name: string;
  nickname: string;
  age: number | null;
  has_embedding: boolean;
  embedding_dim: number;
  avg_confidence: number;
  max_confidence: number;
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
  width: number;
  height: number;
  duration: number;
}

// Bbox contract: stored metadata keeps `face_location` as [top, right, bottom, left]
// (face_recognition convention, written by mvp-processor). Every serving path
// (local_api.py, worker handleFaceDetection, useViewerMetadata) converts it to
// canonical wire/display order [x1, y1, x2, y2] at the boundary — readers of
// FaceDetection.bbox must never reorder it again.
export interface FaceDetection {
  bbox: [number, number, number, number]; // [x1, y1, x2, y2]
  confidence: number;
  contestant_name: string | null;
  contestant_id?: string;
  contestant_nickname?: string;
  detection_confidence: number;
  recognition_confidence: number;
  matched: boolean;
}

// Matches the JSON emitted by mvp-processor (metadata_generator.py / process_video.py)
export interface FrameRecognition {
  contestant_id: string;
  contestant_name: string;
  contestant_nickname: string;
  confidence: number;
  face_location: [number, number, number, number]; // [top, right, bottom, left]
}

export interface FrameData {
  frame_number: number;
  timestamp: number;
  detections_count: number;
  recognitions_count: number;
  recognitions: FrameRecognition[];
}

export interface ContestantTimelineEntry {
  appearances: Array<{
    timestamp: number;
    frame_number: number;
    confidence: number;
    face_location: [number, number, number, number]; // [top, right, bottom, left]
  }>;
  total_appearances: number;
  average_confidence: number;
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
    confidence_stats?: { average: number; minimum: number; maximum: number };
    processing_timestamp?: string;
  };
  contestant_timeline: Record<string, ContestantTimelineEntry>;
  frame_data: FrameData[];
}

export interface CoverageSummary {
  total: number;
  good: number;
  weak: number;
  missing: number;
  avg_confidence: number;
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

export interface FlaggedFace {
  id: string;
  contestant_id: number;
  video_id: string;
  timestamp: number;
  confidence: number;
  bbox: [number, number, number, number];
  status: 'pending' | 'accepted' | 'rejected';
  user_label?: string;
  thumbnail?: string;
}
