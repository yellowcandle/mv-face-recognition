/** Reels are sampled at a fixed stride, and frames with no faces aren't stored. */
export function sampleGap(frames: { timestamp: number }[]): number {
  let gap = Infinity;
  for (let i = 1; i < frames.length; i++) {
    const step = frames[i].timestamp - frames[i - 1].timestamp;
    if (step > 0 && step < gap) gap = step;
  }
  return gap;
}

/**
 * The stored frame on screen at `time`, from frames sorted by timestamp. A frame only speaks for
 * its own sample: past that the faces have left the shot, however long until the next one.
 */
export function frameAt<T extends { timestamp: number }>(
  frames: T[],
  time: number,
  gap: number,
): T | null {
  let lo = 0;
  let hi = frames.length - 1;
  let found = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (frames[mid].timestamp <= time) {
      found = mid;
      lo = mid + 1;
    } else {
      hi = mid - 1;
    }
  }
  if (found < 0) return null;
  // 1.25: float timestamps and a frame's own display time, without reaching the next sample.
  return time - frames[found].timestamp <= gap * 1.25 ? frames[found] : null;
}
