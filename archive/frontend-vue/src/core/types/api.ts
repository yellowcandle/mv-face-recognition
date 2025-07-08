// API Response Types
export interface VideoInfo {
  id: string
  name: string
  filename: string
  path: string
  size: number
  duration_seconds: number
  fps: number
  width: number
  height: number
  frame_count: number
  created_at?: string
}

export interface Contestant {
  id: string
  name: string
  photos: string[]
  embedding_available: boolean
  created_at?: string
}

export interface ProcessingConfig {
  frame_skip: number
  detection_threshold: number
  similarity_threshold: number
  start_time: number
  end_time?: number
  generate_annotated_video: boolean
  export_csv: boolean
}

export interface ProcessingJob {
  job_id: string
  video_id: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  progress: number
  current_frame: number
  total_frames: number
  faces_detected: number
  matches_found: number
  created_at: string
  completed_at?: string
  error_message?: string
}

export interface ProcessingProgress {
  job_id: string
  progress: number
  current_frame: number
  total_frames: number
  faces_detected: number
  matches_found: number
  current_frame_faces: number
  current_frame_recognized: number
  processing_fps: number
  frame_timestamp: number
}

export interface ProcessingResult {
  job_id: string
  video_id: string
  total_frames: number
  faces_detected: number
  matches_found: number
  unique_contestants: number
  processing_time: number
  annotated_video_path?: string
  csv_path?: string
  contestant_appearances: Record<string, ContestantStats>
}

export interface ContestantStats {
  contestant_id: string
  name: string
  total_appearances: number
  first_appearance_frame: number
  last_appearance_frame: number
  avg_confidence: number
  max_confidence: number
  confidence_scores: number[]
}

export interface BoundingBox {
  x1: number
  y1: number
  x2: number
  y2: number
}

export interface FaceDetection {
  bbox: BoundingBox
  detection_confidence: number
  contestant_name?: string
  recognition_confidence: number
  matched: boolean
}

export interface FrameResult {
  frame_number: number
  timestamp: number
  faces: FaceDetection[]
}

export interface SystemStatus {
  chromadb_connected: boolean
  model_loaded: boolean
  services_running: boolean
  video_count: number
  contestant_count: number
  processing_jobs: number
}

export interface AppSettings {
  face_detection: {
    model_name: string
    detection_threshold: number
    input_size: number[]
  }
  face_matching: {
    similarity_threshold: number
    max_results: number
  }
  video_processing: {
    frame_skip: number
    output_fps: number
    annotation_font_scale: number
    annotation_thickness: number
  }
}

export interface ApiError {
  error: string
  message: string
  details?: Record<string, any>
}

// WebSocket Message Types
export interface WebSocketMessage {
  type: 'processing_progress' | 'processing_complete' | 'processing_error' | 'system_status' | 'subscribed' | 'unsubscribed' | 'pong' | 'error'
  job_id?: string
  data?: any
  error?: string
  timestamp?: string
}