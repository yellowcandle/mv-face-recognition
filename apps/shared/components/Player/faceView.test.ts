import { describe, expect, it } from 'vite-plus/test';
import type { FaceDetection } from '../../types';
import { faceName, squareCrop, tickPercent } from './faceView';

const face = (over: Partial<FaceDetection>): FaceDetection => ({
  bbox: [0, 0, 1, 1],
  match_score: null,
  det_score: 0.7,
  contestant_id: null,
  contestant_name: null,
  contestant_nickname: null,
  matched: false,
  ...over,
});

describe('faceName', () => {
  it('prefers the nickname', () => {
    expect(
      faceName(
        face({ matched: true, contestant_name: '蘇雅琳', contestant_nickname: 'Ivy So' }),
      ),
    ).toBe('Ivy So');
  });

  it('falls back to the full name', () => {
    expect(faceName(face({ matched: true, contestant_name: '蘇雅琳' }))).toBe('蘇雅琳');
  });

  it('calls an unmatched detection 未認出', () => {
    expect(faceName(face({}))).toBe('未認出');
  });
});

describe('squareCrop', () => {
  it('centres a square on the box, padded by a fifth of its long side', () => {
    // box is 100×200 px at (400,400) in a 1000×1000 frame; long side 200 + 2×40 padding = 280.
    expect(squareCrop([0.4, 0.4, 0.5, 0.6], 1000, 1000)).toEqual({
      x: 310,
      y: 360,
      size: 280,
    });
  });

  it('slides back inside the frame at an edge rather than squashing', () => {
    expect(squareCrop([0, 0, 0.1, 0.1], 1000, 1000)).toEqual({ x: 0, y: 0, size: 140 });
    expect(squareCrop([0.9, 0.9, 1, 1], 1000, 1000)).toEqual({ x: 860, y: 860, size: 140 });
  });

  it('never asks for more than the frame has', () => {
    expect(squareCrop([0, 0, 1, 1], 3840, 1600)).toEqual({ x: 1120, y: 0, size: 1600 });
  });

  it('is null before the video has a decoded frame', () => {
    expect(squareCrop([0, 0, 1, 1], 0, 0)).toBeNull();
  });
});

describe('tickPercent', () => {
  it('is the share of the reel, clamped', () => {
    expect(tickPercent(50, 200)).toBe(25);
    expect(tickPercent(300, 200)).toBe(100);
  });

  it('is zero before the duration is known', () => {
    expect(tickPercent(50, 0)).toBe(0);
  });
});
