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

/** A single measured frame from a stand-alone photo (see `streetPhotos.posed.ts`). */
export interface PosedFace {
  i: number;
  /** Frame fractions `[x1, y1, x2, y2]`, canonical order. */
  box: [number, number, number, number];
  px: [number, number];
  det_score: number;
  score: number;
  id: string;
  name: string;
  nickname: string;
  /** `recognition` at or above `SITE_THRESHOLD`; `candidate` above `JOB_THRESHOLD`; else `none`. */
  verdict: 'recognition' | 'candidate' | 'none';
}

export interface PosedFrame {
  width: number;
  height: number;
  mode: string;
  faces: PosedFace[];
  recognitionCount: number;
  candidateCount: number;
}

/**
 * The post the posed frame came from, quoted verbatim. Its own words are the reason the frame is
 * worth publishing: the poster set out to make a guessing game easier, and it is the first photo in
 * this thread that the matcher could actually answer.
 */
export const POSED_POST = {
  handle: 'rinrinrin1666',
  url: 'https://www.threads.com/@rinrinrin1666/post/DgH5FprE51B',
  caption: '又來猜猜我是誰的環節🤣\n今次張相易沽好多',
  image: '/videos/reports/street-photos-2026-11-15/posed.jpg',
};

/** One contestant's showing in a reel: how often, and how well. */
export interface VideoRow {
  id: string;
  nickname: string;
  name: string;
  count: number;
  best: number;
  median: number;
  p90: number;
}

/** A processed reel, summarised (see `streetPhotos.video.ts`). */
export interface VideoReport {
  duration: number;
  frames: number;
  detections: number;
  recognitions: number;
  contestants: number;
  threshold: number;
  rows: VideoRow[];
}

/**
 * Handle → contestant, read off each account's own profile (public bios, 2026-11-24). The reel
 * tags ten of these and its author is the eleventh, so the caption plus the author names the whole
 * group without anyone's eye — which is what makes the reel's 11-for-11 worth stating.
 */
export const VIDEO_HANDLES = [
  { handle: 'geungada', id: '27', note: 'Geung Ada' },
  { handle: 'lezona_b', id: '5', note: 'LEZONA SAKABE | 莎莎' },
  { handle: 'curry_wnw', id: '2', note: 'Kelly Wong（咖喱）' },
  { handle: 'ho_pui', id: '83', note: 'HOPUI 何佩' },
  { handle: 'karen.yeeeee', id: '20', note: 'KAREN YEE' },
  { handle: 'kilbychan', id: '79', note: '💧🍋超酸🍋💧' },
  { handle: 'superaggiieee', id: '31', note: '阿杰 Aggie C' },
  { handle: 'sophiee1116', id: '18', note: 'SOPHIE 蘇菲' },
  { handle: 'myyoann', id: '78', note: 'mayan 馬欣' },
  { handle: 'wyllislwk', id: '22', note: '暐翹 WK' },
] as const;

/** The reel the shoot itself was filmed for: same people, 23 seconds of them. */
export const VIDEO_POST = {
  handle: 'carinalxt',
  url: 'https://www.instagram.com/reel/DgH25YfT995/',
  caption:
    'FINGERS CROSSED #walkchallenge with my 造星4 girls!!!\nROUND ONE with @geungada @lezona_b @curry_wnw @ho_pui @karen.yeeeee @kilbychan @superaggiieee @sophiee1116 @myyoann @wyllislwk',
};

/** The prose that belongs to each measured frame, keyed by the frame it describes. */
const FRAME_PROSE: Record<string, { src: string; alt: string; caption: string }> = {
  a: {
    src: '/videos/reports/street-photos-2026-11-15/frame-1.jpg',
    alt: '街拍一：一班人橫過馬路，臉部框出十三個',
    caption: '一 · 過路 · 原生解像度直接偵測，抓到 13 張臉，框寬 21×28 到 40×49 像素。',
  },
  b: {
    src: '/videos/reports/street-photos-2026-11-15/frame-2.jpg',
    alt: '街拍二：一排人在 Sogo 門外排隊合照，臉部框出十個',
    caption:
      '二 · 排隊 · 原生解像度零偵測（臉只有 14×19 像素，小於 20 px 下限）。改將該區域放大 4 倍分格重掃，抓出 10 張臉。',
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
    verdict: 'Carina 和 Ada 確實屬於 VIVA，而兩人本來也是造星 IV 參賽者。',
  },
  {
    handle: 'kkkcywww',
    text: '全部都係造星4（？見好似有 karen 暐翹 咖哩 carina ada 馬欣 其他認唔出😂',
    verdict: '本頁採用的觀眾名單來源，九位裡有四位在 1085 px 街拍過了雜訊線。',
  },
  {
    handle: 'waiwaiwai9413',
    text: '超酸story好似見到elka同ivyso同carina',
    verdict: '同一張街拍裡 Elka 排第 17，Ivy So 排第 81，而 23 秒原片裡也沒有見到 Ivy So。',
  },
  {
    handle: 'pang_fred',
    text: '似係Cookies',
    verdict: 'Cookies 是 2002 年出道的女團，不在這份 2021 年名冊內。',
  },
  {
    handle: 'lezona_b',
    text: '期待吓先🤪',
    verdict: '這是坂部佩莎（莎莎，5 號）本人的帳號，相中人自己留在帖文下面。',
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

export { POSED_FRAME } from './streetPhotos.posed';
export { VIDEO_REPORT } from './streetPhotos.video';

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
