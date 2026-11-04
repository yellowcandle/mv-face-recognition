import { expect, test } from 'vite-plus/test';
import {
  contestantsSeen,
  isTestClip,
  mostSeen,
  reelHeading,
  reelRange,
  reelSubtitle,
  renditionLabel,
} from './reels';

const MV1 = '1-《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅';
const MV4 = '4-《全民造星IV》極限拍MV';
const MV5 = '5-《全民造星IV》播前熱身！率先表演《前傳》';

test('reelSubtitle reads the line under a reel title, and is empty for a test clip', () => {
  expect(reelSubtitle(MV1)).toBe('主題曲《前傳》MV · 造星の駅');
  expect(reelSubtitle(MV4)).toBe('極限拍 MV');
  expect(reelSubtitle(MV5)).toBe('率先表演《前傳》');
  expect(reelSubtitle('test-video-mv2')).toBe('');
});

test('reelHeading names the reel by number, title and station', () => {
  expect(reelHeading(MV1)).toBe('第 1 卷 · 首部曲 · 造星の駅');
  expect(reelHeading(MV4)).toBe('第 4 卷 · 極限拍');
  expect(reelHeading(MV5)).toBe('第 5 卷 · 播前熱身');
  expect(reelHeading('test-video-mv2')).toBe('test-video-mv2');
});

test('reelRange spans the filed reels', () => {
  expect(reelRange(5)).toBe('第 01 至 05 卷');
  expect(reelRange(1)).toBe('第 01 卷');
  expect(reelRange(0)).toBe('未有影片');
});

test('renditionLabel comes from the real height, and is absent without one', () => {
  expect(renditionLabel(1600)).toBe('1600P');
  expect(renditionLabel(1080)).toBe('1080P');
  expect(renditionLabel(undefined)).toBeNull();
  expect(renditionLabel(0)).toBeNull();
});

test('contestantsSeen counts contestants with detections, not the total', () => {
  expect(
    contestantsSeen([{ detection_count: 3 }, { detection_count: 0 }, { detection_count: 1 }]),
  ).toBe(2);
});

test('mostSeen sorts by detections without mutating, and drops anyone never seen', () => {
  const all = [
    { id: 'a', detection_count: 1 },
    { id: 'b', detection_count: 9 },
    { id: 'c', detection_count: 0 },
    { id: 'd', detection_count: 5 },
  ];
  expect(mostSeen(all, 2).map((c) => c.id)).toEqual(['b', 'd']);
  expect(mostSeen(all, 9).map((c) => c.id)).toEqual(['b', 'd', 'a']);
  expect(all[0].id).toBe('a');
});

test('isTestClip matches only the test- prefix', () => {
  expect(isTestClip('test-video-mv2')).toBe(true);
  expect(isTestClip('test-unmatched')).toBe(true);
  expect(isTestClip(MV1)).toBe(false);
  expect(isTestClip('4-test-reel')).toBe(false);
});
