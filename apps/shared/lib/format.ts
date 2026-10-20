/** A timecode as zero-padded mm:ss (minutes are not wrapped at 60). */
export function formatMmSs(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}
