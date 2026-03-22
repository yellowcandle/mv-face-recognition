// =============================================================================
// Data Types
// =============================================================================

export interface Contestant {
  id: string
  chineseName: string
  nickname: string
  age: number
  photoUrl: string
  totalScreenTime: number
  appearanceCount: number
}

export interface Appearance {
  id: string
  contestantId: string
  videoId: string
  videoTitle: string
  timestamp: number
  duration: number
}

// =============================================================================
// Component Props
// =============================================================================

export interface ContestantDirectoryProps {
  /** List of all contestants to display in the grid */
  contestants: Contestant[]
  /** Appearance history for the selected contestant */
  appearances: Appearance[]
  /** Current search query for filtering */
  searchQuery: string
  /** ID of the currently selected contestant (for modal) */
  selectedContestantId: string | null
  /** Called when user types in the search field */
  onSearch?: (query: string) => void
  /** Called when user clicks a contestant card to open modal */
  onSelectContestant?: (contestantId: string) => void
  /** Called when user closes the contestant modal */
  onCloseModal?: () => void
  /** Called when user clicks an appearance to jump to video */
  onPlayAppearance?: (videoId: string, timestamp: number) => void
}
