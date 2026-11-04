import { describe, expect, it } from 'vite-plus/test';
import type { FlaggedFace } from '../types';
import { recentDecisions, rulerPercent, reelSummary } from './flags';

const flag = (id: string, status: FlaggedFace['status'], created_at?: string) =>
  ({
    id,
    contestant_id: 1,
    video_id: 'v',
    timestamp: 0,
    confidence: null,
    bbox: [0, 0, 1, 1],
    status,
    created_at,
  }) as FlaggedFace;

describe('recentDecisions', () => {
  it('keeps only accepted flags, newest first', () => {
    const got = recentDecisions([
      flag('old', 'accepted', '2026-10-01T00:00:00+00:00'),
      flag('waiting', 'pending', '2026-10-09T00:00:00+00:00'),
      flag('voided', 'rejected', '2026-10-08T00:00:00+00:00'),
      flag('new', 'accepted', '2026-10-05T00:00:00+00:00'),
    ]);
    expect(got.map((f) => f.id)).toEqual(['new', 'old']);
  });

  it('caps at the limit, files undated flags last, and leaves the input alone', () => {
    const input = [
      flag('undated', 'accepted'),
      flag('a', 'accepted', '2026-10-01T00:00:00+00:00'),
      flag('b', 'accepted', '2026-10-02T00:00:00+00:00'),
    ];
    expect(recentDecisions(input, 2).map((f) => f.id)).toEqual(['b', 'a']);
    expect(recentDecisions(input, 3).map((f) => f.id)).toEqual(['b', 'a', 'undated']);
    expect(input[0].id).toBe('undated');
  });
});

describe('rulerPercent', () => {
  // The designed ruler runs 0.30 to 0.70: 0.412 falls at 28% and 0.445 at about 36% of its width.
  it('places scores on the 0.30 to 0.70 scale', () => {
    expect(rulerPercent(0.5)).toBeCloseTo(50);
    expect(rulerPercent(0.412)).toBeCloseTo(28);
  });
  it('pins scores outside the scale to its ends', () => {
    expect(rulerPercent(0)).toBe(0);
    expect(rulerPercent(0.9)).toBe(100);
  });
});

describe('reelSummary', () => {
  it('counts MVs and test clips apart', () => {
    expect(reelSummary(['1-a', '2-b', '3-c', 'test-unmatched', 'test-video-mv2'])).toBe(
      '3 卷 MV 加 2 段測試',
    );
  });
  it('omits test clips when there are none', () => {
    expect(reelSummary(['1-a'])).toBe('1 卷 MV');
  });
});
