import { describe, expect, it } from 'vite-plus/test';
import type { ContestantTimelineEntry, FrameData } from '../types';
import { ledgerRows, spanPercent } from './ledgerRows';

const entry = (over: Partial<ContestantTimelineEntry>): ContestantTimelineEntry =>
  ({
    appearances: [],
    total_appearances: 0,
    average_match_score: 0,
    first_appearance: 0,
    last_appearance: 0,
    contestant_info: { id: '0', name: '', nickname: '' },
    ...over,
  }) as ContestantTimelineEntry;

const timeline = {
  '7': entry({
    total_appearances: 124,
    average_match_score: 0.49,
    first_appearance: 24,
    last_appearance: 167,
    contestant_info: { id: '7', name: '梁式昕', nickname: 'Catrina' },
    appearances: [
      { timestamp: 24, frame_number: 150, match_score: 0.45, bbox: [0, 0, 1, 1] },
      { timestamp: 30, frame_number: 187, match_score: 0.6, bbox: [0, 0, 1, 1] },
    ],
  }),
  '15': entry({
    total_appearances: 85,
    average_match_score: 0.54,
    contestant_info: { id: '15', name: '李晞彤', nickname: 'Carina' },
  }),
};

describe('ledgerRows', () => {
  it('ranks by appearances, highest first', () => {
    expect(ledgerRows(timeline, 'appearances').map((r) => r.nickname)).toEqual([
      'Catrina',
      'Carina',
    ]);
  });

  it('ranks by average score, highest first', () => {
    expect(ledgerRows(timeline, 'avgMatchScore').map((r) => r.nickname)).toEqual([
      'Carina',
      'Catrina',
    ]);
  });

  it('takes the highest score from the appearances', () => {
    expect(ledgerRows(timeline, 'appearances')[0].maxMatchScore).toBe(0.6);
  });

  it('falls back to the key when a contestant has no info', () => {
    const row = ledgerRows({ '9': entry({ contestant_info: undefined }) }, 'appearances')[0];
    expect(row.nickname).toBe('9');
    expect(row.maxMatchScore).toBe(0);
  });

  it('points at the crop of the best-scoring appearance', () => {
    const frames = [
      {
        frame_number: 187,
        detections: [{ contestant_id: null }, { contestant_id: '7' }],
      },
    ] as unknown as FrameData[];
    expect(ledgerRows(timeline, 'appearances', frames)[0].crop).toEqual({
      frameNumber: 187,
      detectionIndex: 1,
    });
  });

  it('crops the highest-scoring detection when a contestant is matched twice in a frame', () => {
    const frames = [
      {
        frame_number: 187,
        detections: [
          { contestant_id: '7', match_score: 0.42 },
          { contestant_id: null, match_score: null },
          { contestant_id: '7', match_score: 0.6 },
        ],
      },
    ] as unknown as FrameData[];
    expect(ledgerRows(timeline, 'appearances', frames)[0].crop?.detectionIndex).toBe(2);
  });

  it('has no crop when the frame is not in the metadata', () => {
    expect(ledgerRows(timeline, 'appearances', [])[0].crop).toBeNull();
  });

  it('has no rows without a timeline', () => {
    expect(ledgerRows(undefined, 'appearances')).toEqual([]);
  });
});

describe('spanPercent', () => {
  it('places a span as percentages of the reel', () => {
    expect(spanPercent(25, 75, 100)).toEqual({ left: 25, width: 50 });
  });

  it('is null when the duration is unknown', () => {
    expect(spanPercent(25, 75, 0)).toBeNull();
    expect(spanPercent(25, 75, undefined)).toBeNull();
  });
});
