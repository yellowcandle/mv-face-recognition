import { isTestClip } from './reels';
import type { FlaggedFace } from '../types';

/**
 * Accepted flags, newest first. Sorted by when the flag was filed: the record has no decision
 * time.
 */
export function recentDecisions(flags: FlaggedFace[], limit = 6): FlaggedFace[] {
  return flags
    .filter((f) => f.status === 'accepted')
    .sort((a, b) => (b.created_at ?? '').localeCompare(a.created_at ?? ''))
    .slice(0, limit);
}

const RULER_MIN = 0.3;
const RULER_MAX = 0.7;

/** Where a match score sits on the score ruler, as a percentage of its width. */
export function rulerPercent(score: number): number {
  const percent = ((score - RULER_MIN) / (RULER_MAX - RULER_MIN)) * 100;
  return Math.min(100, Math.max(0, percent));
}

/** The note under 已存影片, e.g. `5 卷 MV 加 2 段測試`. Test clips have `test-` ids. */
export function reelSummary(videoIds: string[]): string {
  const tests = videoIds.filter(isTestClip).length;
  const reels = `${videoIds.length - tests} 卷 MV`;
  return tests ? `${reels} 加 ${tests} 段測試` : reels;
}
