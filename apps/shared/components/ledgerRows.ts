import type { ContestantTimelineEntry, FrameData } from '../types';

export type LedgerSort = 'appearances' | 'avgMatchScore';

export interface LedgerRow {
  id: string;
  nickname: string;
  name: string;
  appearances: number;
  /** Null means no score to show, never 0: 0 would stamp 存疑 and pull a sort down as a score. */
  avgMatchScore: number | null;
  maxMatchScore: number | null;
  /** Named only by accepted flags, so a human decision stands where the score would. */
  decided: boolean;
  firstSeen: number;
  lastSeen: number;
  /** Where `/api/faces/crop` finds this contestant's best face in the reel. */
  crop: { frameNumber: number; detectionIndex: number } | null;
}

/** One row per contestant seen in the reel, ranked by the chosen column. */
export function ledgerRows(
  timeline: Record<string, ContestantTimelineEntry> | undefined,
  sortBy: LedgerSort,
  frames: FrameData[] = [],
): LedgerRow[] {
  if (!timeline) return [];
  const frameByNumber = new Map(frames.map((f) => [f.frame_number, f]));
  return Object.entries(timeline)
    .map(([id, info]) => {
      const best = (info.appearances ?? []).reduce<
        ContestantTimelineEntry['appearances'][number] | null
      >((top, a) => {
        if (a.match_score == null) return top;
        return top && (top.match_score ?? -Infinity) >= a.match_score ? top : a;
      }, null);
      // No score to rank by: any appearance still shows the face.
      const shown = best ?? info.appearances?.[0];
      const detections = shown ? (frameByNumber.get(shown.frame_number)?.detections ?? []) : [];
      const detectionIndex = detections.reduce((top, d, i) => {
        if (String(d.contestant_id) !== id) return top;
        return top < 0 || (d.match_score ?? -1) > (detections[top].match_score ?? -1) ? i : top;
      }, -1);
      return {
        id,
        nickname: info.contestant_info?.nickname ?? id,
        name: info.contestant_info?.name ?? id,
        appearances: info.total_appearances,
        avgMatchScore: info.average_match_score ?? null,
        maxMatchScore: best?.match_score ?? null,
        decided: !best && (info.appearances ?? []).some((a) => a.match_source === 'flag'),
        firstSeen: info.first_appearance,
        lastSeen: info.last_appearance,
        crop:
          shown && detectionIndex >= 0 ? { frameNumber: shown.frame_number, detectionIndex } : null,
      };
    })
    .sort((a, b) =>
      sortBy === 'appearances'
        ? b.appearances - a.appearances
        : (b.avgMatchScore ?? -Infinity) - (a.avgMatchScore ?? -Infinity),
    );
}

/** A first-to-last span as percentages of the reel; null while the duration is unknown. */
export function spanPercent(
  first: number,
  last: number,
  duration: number | undefined,
): { left: number; width: number } | null {
  if (!duration) return null;
  return { left: (first / duration) * 100, width: ((last - first) / duration) * 100 };
}
