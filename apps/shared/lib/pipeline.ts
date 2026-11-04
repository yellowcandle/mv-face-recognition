import { videoShortName } from './format';
import type { Contestant, CoverageSummary } from '../types';

const MODE_LABEL: Record<string, string> = {
  initial: '首次處理',
  'embedding-update': '更新向量',
  'coverage-refresh': '覆蓋率與相似度',
};

const STATUS_LABEL: Record<string, string> = {
  queued: '排隊中',
  running: '進行中',
  completed: '已完成',
  completed_with_errors: '完成 · 部分失敗',
  failed: '失敗',
  cancelled: '已取消',
};

export const QUALITY_WORD: Record<Contestant['quality'], string> = {
  good: '齊全',
  weak: '偏弱',
  missing: '缺',
};

export function jobModeLabel(mode: string | undefined): string {
  if (!mode) return '處理';
  return MODE_LABEL[mode] ?? mode;
}

export function jobStatusLabel(status: string): string {
  return STATUS_LABEL[status] ?? status;
}

/** The line under a job's name: which reel, and how far through the batch. */
export function jobProgressLine(job: {
  current_video?: string | null;
  videos_processed?: number;
  total_videos?: number;
}): string | null {
  const parts: string[] = [];
  if (job.current_video) parts.push(videoShortName(job.current_video));
  if (job.videos_processed !== undefined && job.total_videos) {
    parts.push(`${job.videos_processed} / ${job.total_videos} 部影片`);
  }
  return parts.length > 0 ? parts.join(' · ') : null;
}

export function formatJobCreated(iso: string | undefined): string {
  if (!iso) return '--';
  const at = new Date(iso);
  if (Number.isNaN(at.getTime())) return '--';
  const hh = String(at.getHours()).padStart(2, '0');
  const mm = String(at.getMinutes()).padStart(2, '0');
  return `${at.getMonth() + 1}月${at.getDate()}日 ${hh}:${mm}`;
}

/** The three figures above the 向量 roster. Weak contestants count as covered. */
export function coverageFigures(summary: CoverageSummary) {
  const covered = summary.good + summary.weak;
  const percent = summary.total > 0 ? Math.round((covered / summary.total) * 100) : 0;
  return {
    covered: `${covered} / ${summary.total}`,
    coveredNote: `${percent}%，含 ${summary.weak} 位偏弱`,
    average: summary.avg_match_score.toFixed(2),
    rate: `${(summary.recognition_rate * 100).toFixed(1)}%`,
    rateNote: `${summary.total_faces_recognized.toLocaleString('en-US')} / ${summary.total_faces_detected.toLocaleString('en-US')} 張臉`,
  };
}

export function isPair(
  pair: { contestant_a: { id: string }; contestant_b: { id: string } },
  a: string,
  b: string,
): boolean {
  const { contestant_a: x, contestant_b: y } = pair;
  return (x.id === a && y.id === b) || (x.id === b && y.id === a);
}
