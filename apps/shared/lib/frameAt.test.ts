import { expect, test } from 'vite-plus/test';
import { frameAt, sampleGap } from './frameAt';

const frame = (timestamp: number) => ({ timestamp });
// Sampled every 0.16s, then the faces leave the shot for 10s.
const frames = [14.4, 14.56, 14.72, 25].map(frame);
const gap = sampleGap(frames);

test('sampleGap is the smallest step between stored frames', () => {
  expect(gap).toBeCloseTo(0.16);
  expect(sampleGap([frame(3)])).toBe(Infinity);
  expect(sampleGap([])).toBe(Infinity);
});

test('frameAt returns the latest frame while it is still within one sample', () => {
  expect(frameAt(frames, 14.56, gap)?.timestamp).toBe(14.56);
  expect(frameAt(frames, 14.7, gap)?.timestamp).toBe(14.56);
  expect(frameAt(frames, 14.8, gap)?.timestamp).toBe(14.72);
});

test('frameAt returns nothing once the faces have left the shot', () => {
  expect(frameAt(frames, 15, gap)).toBeNull();
  expect(frameAt(frames, 24.9, gap)).toBeNull();
  expect(frameAt(frames, 25, gap)?.timestamp).toBe(25);
});

test('frameAt returns nothing before the first frame or on an empty reel', () => {
  expect(frameAt(frames, 1, gap)).toBeNull();
  expect(frameAt([], 1, Infinity)).toBeNull();
});

test('a single-frame reel has no gap to measure, so its frame holds', () => {
  expect(frameAt([frame(3)], 9, Infinity)?.timestamp).toBe(3);
});
