import { videoShortName } from './format';

const SHOW_PREFIX = /^\d+-《全民造星IV》/;

/**
 * The line under a reel's title, e.g. 主題曲《前傳》MV · 造星の駅.
 * ponytail: matches the five known reel names; anything else (test clips) has no subtitle.
 */
export function reelSubtitle(name: string): string {
  if (!SHOW_PREFIX.test(name)) return '';
  const rest = name.replace(SHOW_PREFIX, '');
  const theme = rest.match(/^(.+?)\s*\d{4}夏の.+?：(.+)$/);
  if (theme) return `${theme[1].replace(/\s+/g, '')} · ${theme[2]}`;
  return rest.split('！').pop()!.replace(/MV$/, ' MV');
}

/** Processing test clips, kept out of the public reel list. */
export function isTestClip(id: string): boolean {
  return id.startsWith('test-');
}

/** A reel by number, title and station, e.g. 第 1 卷 · 首部曲 · 造星の駅. Test clips keep their name. */
export function reelHeading(name: string): string {
  const number = name.match(/^(\d+)-/)?.[1];
  if (!number) return name;
  const station = name.includes('：') ? name.split('：').pop() : null;
  return [`第 ${number} 卷`, videoShortName(name), station].filter(Boolean).join(' · ');
}

/** The head of the reel list, e.g. 第 01 至 05 卷. */
export function reelRange(count: number): string {
  if (count === 0) return '未有影片';
  const pad = (n: number) => String(n).padStart(2, '0');
  return count === 1 ? `第 ${pad(1)} 卷` : `第 ${pad(1)} 至 ${pad(count)} 卷`;
}

/** The rendition stamp, from the file's real height. Null when the API sent none. */
export function renditionLabel(height: number | null | undefined): string | null {
  return height ? `${height}P` : null;
}

/** How many contestants were detected at all, as opposed to how many are on file. */
export function contestantsSeen(contestants: { detection_count: number }[]): number {
  return contestants.filter((c) => c.detection_count > 0).length;
}

/** "Most seen" is a count, not a recency: the read model has no cross-reel timeline. */
export function mostSeen<T extends { detection_count: number }>(contestants: T[], limit: number): T[] {
  return contestants
    .filter((c) => c.detection_count > 0)
    .sort((a, b) => b.detection_count - a.detection_count)
    .slice(0, limit);
}
