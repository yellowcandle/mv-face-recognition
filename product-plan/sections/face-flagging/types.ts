// =============================================================================
// Data Types
// =============================================================================

export interface PendingReview {
  id: string
  detectionId: string
  videoId: string
  videoTitle: string
  timestamp: number
  faceCropUrl: string
  currentContestantId: string | null
  currentContestantName: string | null
  currentContestantNickname: string | null
  currentContestantPhoto: string | null
  confidence: number
}

export interface ContestantOption {
  id: string
  chineseName: string
  nickname: string
  photoUrl: string
}

export type FlagStatus = 'pending' | 'accepted' | 'rejected'

export interface SubmittedFlag {
  id: string
  detectionId: string
  videoTitle: string
  originalContestantName: string | null
  correctedContestantName: string | null
  submittedAt: string
  status: FlagStatus
  notes: string | null
}

export interface VideoOption {
  id: string
  title: string
}

// =============================================================================
// Component Props
// =============================================================================

export interface FaceFlaggingProps {
  /** Faces pending review */
  pendingReviews: PendingReview[]
  /** Available contestants for correction selection */
  contestants: ContestantOption[]
  /** History of submitted flags */
  submittedFlags: SubmittedFlag[]
  /** Available videos for filtering */
  videos: VideoOption[]
  /** Filter by video (null = all videos) */
  filterVideoId: string | null
  /** Filter by contestant (null = all contestants) */
  filterContestantId: string | null
  /** Only show detections below this confidence threshold */
  filterConfidenceThreshold: number
  /** IDs of reviews selected for bulk action */
  selectedReviewIds: string[]
  /** Search query for contestant filtering */
  searchQuery: string
  /** Called when user flags a face as incorrect */
  onFlagIncorrect?: (reviewId: string) => void
  /** Called when user selects the correct contestant */
  onSelectCorrectContestant?: (reviewId: string, contestantId: string | null) => void
  /** Called when user marks a face as unknown */
  onMarkUnknown?: (reviewId: string) => void
  /** Called when user submits a correction */
  onSubmitCorrection?: (reviewId: string, correctContestantId: string | null, notes?: string) => void
  /** Called when user submits multiple corrections at once */
  onBulkSubmit?: (reviewIds: string[], correctContestantId: string | null) => void
  /** Called when user changes video filter */
  onFilterVideo?: (videoId: string | null) => void
  /** Called when user changes contestant filter */
  onFilterContestant?: (contestantId: string | null) => void
  /** Called when user changes confidence threshold */
  onFilterConfidence?: (threshold: number) => void
  /** Called when user selects/deselects a review */
  onToggleReviewSelection?: (reviewId: string) => void
  /** Called when user selects/deselects all visible reviews */
  onToggleSelectAll?: () => void
  /** Called when user searches for a contestant */
  onSearch?: (query: string) => void
}
