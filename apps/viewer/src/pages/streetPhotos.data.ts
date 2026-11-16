import {
  CONTESTANT_COUNT,
  CUTOFF_SWEEP,
  FACE_SIZE_CEILING,
  RESOLUTION_LADDER,
  JOB_THRESHOLD,
  MATCHER_CHECK,
  NAMED_PRESENT,
  OPEN_TOP1,
  POST_PHOTOS,
  REFERENCE_COUNT,
  ROSTER_NOISE,
  SITE_THRESHOLD,
  STREET_IMAGES as MEASURED_IMAGES,
  VIVA_COVERAGE,
} from './streetPhotos.measurements';

/**
 * What this page shows, and what it does not.
 *
 * Two frames of an outdoor shoot, run through the same detector and matcher the reels go through —
 * but at a **threshold dropped for this job**. The numbers live in `streetPhotos.measurements.ts`,
 * which `mvp-processor/scripts/street_snapshot.py` generates; this file holds the prose and the
 * types, so regenerating measurements never requires retyping a caption.
 *
 * `streetPhotos.fixtures.json` records the sha256 of every frame and of the reference gallery, so a
 * number on the page can be traced to the exact inputs that produced it.
 *
 * A candidate here is a candidate: the site's acceptance threshold is `SITE_THRESHOLD`, and nothing
 * on this page reaches it.
 */

/** Per-detection record. Boxes are frame fractions `[x1, y1, x2, y2]`, canonical order. */
export interface StreetFace {
  /** 1-based, left to right. */
  i: number;
  box: [number, number, number, number];
  /** Face box in pixels of the published image — the number that decides everything below. */
  px: [number, number];
  det_score: number;
  top1: number;
  top2: number;
  margin: number;
  /** The best-scoring contestant, and only when `top1` clears `JOB_THRESHOLD`. */
  candidate: { id: string; name: string; nickname: string } | null;
}

export interface StreetImage {
  key: 'a' | 'b';
  /** Same-origin R2 key under `/videos/`. */
  src: string;
  alt: string;
  caption: string;
  /** How the faces were found: the pipeline path, or tiles because the pipeline found nothing. */
  mode: string;
  width: number;
  height: number;
  faces: StreetFace[];
}

/** A measured frame: everything a `StreetImage` has except the prose, which is hand-written. */
export type MeasuredImage = Omit<StreetImage, 'src' | 'alt' | 'caption'>;

export interface NamedContestant {
  id: string;
  nickname: string;
  name: string;
  best: number;
  rank: number;
  face: string;
  px: [number, number];
  /** `best` clears the 90th percentile of the contestants this list does not name. */
  aboveNoise: boolean;
  /** Named as possible rather than recognised. */
  maybe: boolean;
}

/** The prose that belongs to each measured frame, keyed by the frame it describes. */
const FRAME_PROSE: Record<string, { src: string; alt: string; caption: string }> = {
  a: {
    src: '/videos/reports/street-photos-2026-11-15/frame-1.jpg',
    alt: '街拍一：一班人橫過馬路，臉部框出十三個',
    caption: '一 · 過路 — 原生解像度直接偵測。十三張臉，框 21×28 至 40×49 像素。',
  },
  b: {
    src: '/videos/reports/street-photos-2026-11-15/frame-2.jpg',
    alt: '街拍二：一排人在 Sogo 門外排隊合照，臉部框出十個',
    caption:
      '二 · 排隊 — 原生解像度零偵測（臉只有 14×19 像素，低於 min_face_size 20）。同一個區帶以 4× 分格（220 px 窗、150 px 步長）重跑，得十張臉。',
  },
};

export const STREET_IMAGES: StreetImage[] = MEASURED_IMAGES.map((image) => ({
  ...image,
  ...FRAME_PROSE[image.key],
}));

/**
 * The public replies under the post, quoted verbatim with their authors. Logged out, Threads shows
 * five of the 63; the rest sit behind a login. They split three ways — 造星 IV, VIVA, Cookies — and
 * two of those are compatible: VIVA's Carina (李晞彤) and Ada (姜咏鑫) *are* 造星 IV contestants.
 */
export const POST_REPLIES = [
  {
    handle: 'nicole_s.h.y',
    text: '好似唔係同一個團？見有VIVA嘅Carina Ada，之前有人見過ivyso Elka會唔會系造星4嘅野？',
    verdict: '對：Carina、Ada 屬於 VIVA；兩人同時是造星 IV 參賽者。',
  },
  {
    handle: 'kkkcywww',
    text: '全部都係造星4（？見好似有 karen 暐翹 咖哩 carina ada 馬欣 其他認唔出😂',
    verdict: '本頁採用的名單來源；九位之中過雜訊線的幾位見下表。',
  },
  {
    handle: 'waiwaiwai9413',
    text: '超酸story好似見到elka同ivyso同carina',
    verdict: '兩人在同一張相裡，一個排第 10，一個排第 90——名單要逐位核，不能整句當真。',
  },
  {
    handle: 'pang_fred',
    text: '似係Cookies',
    verdict: 'Cookies 是 2002 年的組合，不在本站名冊。',
  },
  {
    handle: 'lezona_b',
    text: '期待吓先🤪',
    verdict: '這是坂部佩莎（莎莎，5 號）本人的帳號——相中人自己回覆，她的在場不靠辨識。',
  },
];

/**
 * A reply the logged-out page does not load, reported to us rather than read by us: 蘇菲（陳莉詩，
 * 18 號）replied in the same thread. Published as a second-hand claim about who replied, never as a
 * quotation, and labelled as such on the page.
 */
export const REPORTED_REPLY_AUTHORS = [{ id: '18', nickname: '蘇菲', name: '陳莉詩' }];

export const TOTALS = {
  faces: STREET_IMAGES.reduce((count, image) => count + image.faces.length, 0),
  accepted: STREET_IMAGES.flatMap((image) => image.faces).filter((face) => face.candidate !== null)
    .length,
  best: Math.max(...STREET_IMAGES.flatMap((image) => image.faces.map((face) => face.top1))),
  /** The narrowest #1−#2 gap: how close the ranking comes to being pure noise. */
  tightestMargin: Math.min(
    ...STREET_IMAGES.flatMap((image) => image.faces.map((face) => face.margin)),
  ),
  widestMargin: Math.max(
    ...STREET_IMAGES.flatMap((image) => image.faces.map((face) => face.margin)),
  ),
};

export {
  CONTESTANT_COUNT,
  CUTOFF_SWEEP,
  FACE_SIZE_CEILING,
  RESOLUTION_LADDER,
  JOB_THRESHOLD,
  MATCHER_CHECK,
  NAMED_PRESENT,
  OPEN_TOP1,
  POST_PHOTOS,
  REFERENCE_COUNT,
  ROSTER_NOISE,
  SITE_THRESHOLD,
  VIVA_COVERAGE,
};
