import type { FaceDetection } from '../../types';

/** A detection's name on screen. Nickname first: it is what the ledger and 名冊 lead with. */
export function faceName(face: FaceDetection): string {
  if (!face.matched) return '未認出';
  return face.contestant_nickname || face.contestant_name || '未認出';
}

const CROP_PADDING = 0.2;

/**
 * The square of the frame, in the video's own pixels, that shows this box: padded, centred, and
 * slid back inside the frame at an edge. Null until the video has a decoded frame.
 */
export function squareCrop(
  [x1, y1, x2, y2]: [number, number, number, number],
  frameWidth: number,
  frameHeight: number,
): { x: number; y: number; size: number } | null {
  if (!frameWidth || !frameHeight) return null;
  const w = (x2 - x1) * frameWidth;
  const h = (y2 - y1) * frameHeight;
  const long = Math.max(w, h);
  const size = Math.round(Math.min(long * (1 + 2 * CROP_PADDING), frameWidth, frameHeight));
  const slide = (centre: number, limit: number) =>
    Math.round(Math.max(0, Math.min(limit - size, centre - size / 2)));
  return {
    x: slide(x1 * frameWidth + w / 2, frameWidth),
    y: slide(y1 * frameHeight + h / 2, frameHeight),
    size,
  };
}

/** A moment's position along the reel, as a percentage. Zero until the duration is known. */
export function tickPercent(time: number, duration: number): number {
  return duration > 0 ? Math.min(100, (time / duration) * 100) : 0;
}
