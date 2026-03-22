// =============================================================================
// Data Types
// =============================================================================

export type ProcessingStatus = 'pending' | 'processing' | 'completed' | 'failed'

export interface ProcessingJob {
  id: string
  youtubeUrl: string
  title: string
  status: ProcessingStatus
  progress: number
  submittedAt: string
  startedAt: string | null
  completedAt: string | null
  errorMessage: string | null
}

export interface ProcessedVideo {
  id: string
  title: string
  youtubeUrl: string
  duration: number
  thumbnailUrl: string
  processedAt: string
  faceCount: number
}

export type LogLevel = 'info' | 'warning' | 'error'

export interface ProcessingLog {
  jobId: string
  timestamp: string
  level: LogLevel
  message: string
}

// =============================================================================
// Component Props
// =============================================================================

export interface VideoIngestionProps {
  /** Jobs in the processing queue */
  processingJobs: ProcessingJob[]
  /** Successfully processed videos */
  processedVideos: ProcessedVideo[]
  /** Processing logs for debugging */
  processingLogs: ProcessingLog[]
  /** Current value of the URL input field */
  urlInput: string
  /** ID of the job selected for viewing details */
  selectedJobId: string | null
  /** Whether the logs modal is visible */
  showLogsModal: boolean
  /** Called when user types in the URL input */
  onUrlInputChange?: (url: string) => void
  /** Called when user submits a YouTube URL */
  onSubmitUrl?: (url: string) => void
  /** Called when user clicks to retry a failed job */
  onRetryJob?: (jobId: string) => void
  /** Called when user clicks to delete a video */
  onDeleteVideo?: (videoId: string) => void
  /** Called when user clicks to view job details/logs */
  onViewJobDetails?: (jobId: string) => void
  /** Called when user closes the logs modal */
  onCloseLogsModal?: () => void
  /** Called when user clicks to view a processed video */
  onViewVideo?: (videoId: string) => void
}
