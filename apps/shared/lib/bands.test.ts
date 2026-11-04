import { describe, expect, it } from 'vite-plus/test';
import { detectionWord, flagScore, isFlagDecision } from './bands';

describe('a detection decided by an accepted flag', () => {
  it('reads as the human decision, not as a band for its null score', () => {
    const face = { match_source: 'flag', match_score: null } as const;
    expect(isFlagDecision(face)).toBe(true);
    expect(detectionWord(face)).toBe('已核對');
  });
});

describe('any other detection', () => {
  it('keeps its band word', () => {
    expect(isFlagDecision({ match_source: 'frame' })).toBe(false);
    expect(isFlagDecision({})).toBe(false);
    expect(detectionWord({ match_source: 'frame', match_score: 0.5 })).toBe('清楚');
    expect(detectionWord({ match_source: 'track', match_score: 0.42 })).toBe('尚可');
    expect(detectionWord({ match_source: null, match_score: null })).toBe('存疑');
  });
});

describe('flagScore', () => {
  it('treats null and a stored 0 as no score, keeps real cosines', () => {
    expect(flagScore(null)).toBeNull();
    expect(flagScore(undefined)).toBeNull();
    expect(flagScore(0)).toBeNull();
    expect(flagScore(0.38)).toBe(0.38);
  });
});
