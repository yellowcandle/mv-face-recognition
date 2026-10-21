import { describe, expect, it } from 'vitest';
import { pickInitialVideo } from './pickInitialVideo';

const videos = [
  { id: '1-《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅' },
  { id: '4-《全民造星IV》極限拍MV' },
  { id: 'test-video-mv2' },
];

describe('pickInitialVideo', () => {
  it('picks the requested video, not the first', () => {
    expect(pickInitialVideo(videos, '4-《全民造星IV》極限拍MV')?.id).toBe(videos[1].id);
    expect(pickInitialVideo(videos, 'test-video-mv2')?.id).toBe(videos[2].id);
  });

  it('survives the encode/decode round trip a CJK id makes through the URL', () => {
    for (const v of videos) {
      // Home.tsx builds the link with encodeURIComponent; URLSearchParams.get decodes it.
      const fromUrl = new URLSearchParams(`video=${encodeURIComponent(v.id)}`).get('video');
      expect(pickInitialVideo(videos, fromUrl)?.id).toBe(v.id);
    }
  });

  it('falls back to the first video when the id is absent or unknown', () => {
    expect(pickInitialVideo(videos, null)?.id).toBe(videos[0].id);
    expect(pickInitialVideo(videos, 'no-such-video')?.id).toBe(videos[0].id);
  });

  it('is safe on an empty list', () => {
    expect(pickInitialVideo([], 'anything')).toBeUndefined();
  });
});
