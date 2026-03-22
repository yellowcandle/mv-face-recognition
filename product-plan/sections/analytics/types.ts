// =============================================================================
// Data Types
// =============================================================================

export interface LeaderboardEntry {
  contestantId: string
  chineseName: string
  nickname: string
  photoUrl: string
  totalScreenTime: number
  appearanceCount: number
  avgPerVideo: number
}

export interface CoAppearance {
  contestant1Id: string
  contestant1Name: string
  contestant1Nickname: string
  contestant1Photo: string
  contestant2Id: string
  contestant2Name: string
  contestant2Nickname: string
  contestant2Photo: string
  sharedScreenTime: number
}

export interface TrendDataPoint {
  contestantId: string
  videoId: string
  videoTitle: string
  screenTime: number
}

export interface VideoOption {
  id: string
  title: string
}

export interface ContestantOption {
  id: string
  chineseName: string
  nickname: string
}

export type SortColumn = 'totalScreenTime' | 'appearanceCount' | 'avgPerVideo'
export type SortDirection = 'asc' | 'desc'

// =============================================================================
// Component Props
// =============================================================================

export interface AnalyticsProps {
  /** Screen time leaderboard data */
  leaderboardEntries: LeaderboardEntry[]
  /** Top co-appearing contestant pairs */
  coAppearances: CoAppearance[]
  /** Data points for trend line chart */
  trendDataPoints: TrendDataPoint[]
  /** Available videos for filtering */
  videos: VideoOption[]
  /** Available contestants for trend comparison */
  contestants: ContestantOption[]
  /** Currently selected video filter (null = all videos) */
  filterVideoId: string | null
  /** IDs of contestants selected for trend comparison */
  selectedContestantIds: string[]
  /** Current sort column for leaderboard */
  sortColumn: SortColumn
  /** Current sort direction */
  sortDirection: SortDirection
  /** Called when user clicks a contestant to open their modal */
  onContestantClick?: (contestantId: string) => void
  /** Called when user clicks a video to open it */
  onVideoClick?: (videoId: string) => void
  /** Called when user changes the video filter */
  onFilterVideo?: (videoId: string | null) => void
  /** Called when user selects/deselects contestants for trend comparison */
  onSelectContestantsForTrend?: (contestantIds: string[]) => void
  /** Called when user changes leaderboard sort */
  onSort?: (column: SortColumn) => void
}
