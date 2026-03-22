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

export interface VideoMetadata {
  video_info: VideoInfo;
  processing_date: string;
  recognition_summary: {
    total_frames_processed: number;
    total_faces_detected: number;
    total_faces_recognized: number;
    recognition_rate: number;
    unique_contestants: number;
  };
  contestant_timeline: Record<string, {
    total_appearances: number;
    avg_confidence: number;
    max_confidence: number;
    first_appearance_time: number;
    last_appearance_time: number;
  }>;
  frame_data: Array<{
    frame_number: number;
    timestamp: number;
    faces: FaceDetection[];
  }>;
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
