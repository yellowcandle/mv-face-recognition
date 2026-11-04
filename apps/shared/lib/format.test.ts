import { expect, test } from 'vite-plus/test';
import { videoShortName } from './format';

test('videoShortName', () => {
  expect(videoShortName('1-《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅')).toBe('首部曲');
  expect(videoShortName('5-《全民造星IV》播前熱身！率先表演《前傳》')).toBe('播前熱身');
  expect(videoShortName('test-video-mv2')).toBe('test-video-mv2');
});
