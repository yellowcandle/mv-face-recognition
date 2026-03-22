// =============================================================================
// Data Types
// =============================================================================

export interface Video {
  id: string
  title: string
  youtubeUrl: string
  duration: number
  thumbnailUrl: string
  processedAt: string
  faceCount: number
}

export interface Contestant {
  id: string
  chineseName: string
  nickname: string
  age: number
  photoUrl: string
}

export interface BoundingBox {
  x: number
  y: number
  width: number
  height: number
}

export interface FaceDetection {
  id: string
  videoId: string
  contestantId: string
  timestamp: number
  frameNumber: number
  boundingBox: BoundingBox
  confidence: number
}

export interface PlaybackState {
  id: string
  currentTime: number
  playbackSpeed: number
  isPlaying: boolean
}

// =============================================================================
// Component Props
// =============================================================================

export interface VideoPlayerProps {
  /** List of available videos in the sidebar */
  videos: Video[]
  /** All contestants for reference and thumbnails */
  contestants: Contestant[]
  /** Face detections for the current video */
  faceDetections: FaceDetection[]
  /** Current playback state */
  currentVideo: PlaybackState | null
  /** IDs of contestants currently visible on screen */
  visibleContestants: string[]
  /** Currently applied contestant filter (null = no filter) */
  filterContestantId: string | null
  /** Called when user selects a video from sidebar */
  onSelectVideo?: (videoId: string) => void
  /** Called when play button is clicked */
  onPlay?: () => void
  /** Called when pause button is clicked */
  onPause?: () => void
  /** Called when stop button is clicked */
  onStop?: () => void
  /** Called when user seeks to a specific time */
  onSeek?: (timestamp: number) => void
  /** Called when user skips forward/backward by frames */
  onSkipFrames?: (frames: number) => void
  /** Called when user skips forward/backward by seconds */
  onSkipSeconds?: (seconds: number) => void
  /** Called when playback speed is changed */
  onSpeedChange?: (speed: number) => void
  /** Called when user clicks a face or thumbnail to view contestant */
  onContestantClick?: (contestantId: string) => void
  /** Called when user applies a contestant filter */
  onFilterContestant?: (contestantId: string | null) => void
  /** Called when user clicks a timeline marker to jump to timestamp */
  onJumpToTimestamp?: (timestamp: number) => void
}
