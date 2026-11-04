/** A timecode as zero-padded mm:ss (minutes are not wrapped at 60). */
export function formatMmSs(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

/**
 * A reel's short title, e.g. 首部曲 from `1-《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅`.
 * ponytail: matches the five known reels; anything else falls back to its name without the prefix.
 */
export function videoShortName(name: string): string {
  return name.match(/首部曲|次部曲|三部曲|極限拍|播前熱身/)?.[0] ?? name.replace(/^\d+-/, '');
}
