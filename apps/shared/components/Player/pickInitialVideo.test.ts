import { test } from 'node:test';
import assert from 'node:assert/strict';
import { pickInitialVideo } from './pickInitialVideo.ts';

const videos = [
  { id: '1-《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅' },
  { id: '4-《全民造星IV》極限拍MV' },
  { id: 'test-video-mv2' },
];

test('picks the requested video, not the first', () => {
  assert.equal(pickInitialVideo(videos, '4-《全民造星IV》極限拍MV')?.id, videos[1].id);
  assert.equal(pickInitialVideo(videos, 'test-video-mv2')?.id, videos[2].id);
});

test('survives the encode/decode round trip a CJK id makes through the URL', () => {
  for (const v of videos) {
    // Home.tsx builds the link with encodeURIComponent; URLSearchParams.get decodes it.
    const fromUrl = new URLSearchParams(`video=${encodeURIComponent(v.id)}`).get('video');
    assert.equal(pickInitialVideo(videos, fromUrl)?.id, v.id);
  }
});

test('falls back to the first video when the id is absent or unknown', () => {
  assert.equal(pickInitialVideo(videos, null)?.id, videos[0].id);
  assert.equal(pickInitialVideo(videos, 'no-such-video')?.id, videos[0].id);
});

test('is safe on an empty list', () => {
  assert.equal(pickInitialVideo([], 'anything'), undefined);
});
