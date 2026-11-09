import { describe, expect, it } from 'vite-plus/test';
import {
  QUALITY_WORD,
  coverageFigures,
  formatJobCreated,
  isPair,
  jobModeLabel,
  jobProgressLine,
  jobStatusLabel,
} from './pipeline';

describe('job labels', () => {
  it('names the three modes and passes an unknown one through', () => {
    expect(jobModeLabel('initial')).toBe('首次處理');
    expect(jobModeLabel('embedding-update')).toBe('更新向量');
    expect(jobModeLabel('coverage-refresh')).toBe('覆蓋率與相似度');
    expect(jobModeLabel('rescue')).toBe('rescue');
    expect(jobModeLabel(undefined)).toBe('處理');
  });

  it('names every status', () => {
    expect(jobStatusLabel('queued')).toBe('排隊中');
    expect(jobStatusLabel('running')).toBe('進行中');
    expect(jobStatusLabel('completed')).toBe('已完成');
    expect(jobStatusLabel('failed')).toBe('失敗');
    expect(jobStatusLabel('cancelled')).toBe('已取消');
  });
});

describe('jobProgressLine', () => {
  const name = '2-《全民造星IV》主題曲 《前傳》MV 2021夏の次部曲：始発の駅';

  it('joins the short reel name and the count', () => {
    expect(jobProgressLine({ current_video: name, videos_processed: 2, total_videos: 5 })).toBe(
      '次部曲 · 2 / 5 部影片',
    );
  });

  it('shows whichever half it has', () => {
    expect(jobProgressLine({ current_video: name })).toBe('次部曲');
    expect(jobProgressLine({ videos_processed: 0, total_videos: 5 })).toBe('0 / 5 部影片');
  });

  it('has no count for a job that processes no videos', () => {
    expect(
      jobProgressLine({ mode: 'embedding-update', videos_processed: 0, total_videos: 1 }),
    ).toBeNull();
    expect(
      jobProgressLine({
        mode: 'initial',
        current_video: name,
        videos_processed: 1,
        total_videos: 1,
      }),
    ).toBe('次部曲 · 1 / 1 部影片');
  });

  it('has no line when neither is known, or the total is zero', () => {
    expect(jobProgressLine({})).toBeNull();
    expect(jobProgressLine({ videos_processed: 0, total_videos: 0 })).toBeNull();
  });
});

describe('formatJobCreated', () => {
  it('writes month, day and a padded local time', () => {
    expect(formatJobCreated(new Date(2026, 10, 4, 9, 5).toISOString())).toBe('11月4日 09:05');
  });

  it('marks a missing or unreadable time', () => {
    expect(formatJobCreated(undefined)).toBe('--');
    expect(formatJobCreated('soon')).toBe('--');
  });
});

describe('coverageFigures', () => {
  const summary = {
    total: 96,
    good: 86,
    weak: 8,
    missing: 2,
    avg_match_score: 0.4976,
    recognition_rate: 0.304796,
    total_faces_detected: 26795,
    total_faces_recognized: 8167,
  };

  it('counts weak contestants as covered and says how many', () => {
    const figures = coverageFigures(summary);
    expect(figures.covered).toBe('94 / 96');
    expect(figures.coveredNote).toBe('98%，含 8 位偏弱');
    expect(figures.average).toBe('0.50');
    expect(figures.rate).toBe('30.5%');
    expect(figures.rateNote).toBe('8,167 / 26,795 張臉');
  });

  it('does not divide by an empty roster', () => {
    expect(coverageFigures({ ...summary, total: 0, good: 0, weak: 0 }).coveredNote).toBe(
      '0%，含 0 位偏弱',
    );
  });
});

describe('isPair', () => {
  it('matches two ids in either order', () => {
    const pair = { contestant_a: { id: '49' }, contestant_b: { id: '71' } };
    expect(isPair(pair, '49', '71')).toBe(true);
    expect(isPair(pair, '71', '49')).toBe(true);
    expect(isPair(pair, '49', '49')).toBe(false);
  });
});

it('calls a good reference set 齊全, not the band word 清楚', () => {
  expect(QUALITY_WORD).toEqual({ good: '齊全', weak: '偏弱', missing: '缺' });
});
