/**
 * The 2026-11-15 street-photo check: two frames of an outdoor shoot, run through the same
 * detector and matcher the reels go through — but at a **threshold dropped for this job**.
 *
 * Where the numbers come from — `mvp-processor/src/face_detector.py` with
 * `config/processing_config.yaml` (buffalo_l, `min_face_size: 20`) against the 638-reference /
 * 94-contestant cache in `source/photo/contestants/reference_embeddings.npz`. Matching is max
 * cosine over every reference photo, exactly as `FaceRecognizer.recognize_faces` computes it.
 *
 * The site threshold (0.412) is the measured 1% false-match boundary. This job runs at 0.35 to
 * see what a looser bar would surface, so `candidate` is filled only where a face clears
 * `JOB_THRESHOLD`, and `CUTOFF_SWEEP` states what that bar costs: at 0.35 more than one in ten
 * reference photos matches a stranger. A candidate here is a candidate, never an identification.
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
  mode: 'native' | 'tiled 4x';
  width: number;
  height: number;
  faces: StreetFace[];
}

/** The bar this job was run at. Not the site default — see `SITE_THRESHOLD`. */
export const JOB_THRESHOLD = 0.35;
/** The site default: the measured 1% false-match boundary. Unchanged by this job. */
export const SITE_THRESHOLD = 0.412;

/** The gallery this run matched against: one vector per curated photo, one id per contestant. */
export const REFERENCE_COUNT = 638;
export const CONTESTANT_COUNT = 94;

export const STREET_IMAGES: StreetImage[] = [
  {
    key: 'a',
    src: '/videos/reports/street-photos-2026-11-15/frame-1.jpg',
    alt: '街拍一：一班人橫過馬路，臉部框出十三個',
    caption: '一 · 過路 — 原生解像度直接偵測。十三張臉，框 21×28 至 40×49 像素。',
    mode: 'native',
    width: 1085,
    height: 814,
    faces: [
      {
        i: 1,
        box: [0.0462, 0.3626, 0.0656, 0.3976],
        px: [21, 28],
        det_score: 0.746,
        top1: 0.168,
        top2: 0.155,
        margin: 0.014,
        candidate: null,
      },
      {
        i: 2,
        box: [0.186, 0.3242, 0.2107, 0.3897],
        px: [26, 53],
        det_score: 0.568,
        top1: 0.153,
        top2: 0.125,
        margin: 0.028,
        candidate: null,
      },
      {
        i: 3,
        box: [0.2784, 0.2628, 0.3114, 0.3174],
        px: [35, 44],
        det_score: 0.891,
        top1: 0.388,
        top2: 0.169,
        margin: 0.219,
        candidate: { id: '22', name: '林暐翹', nickname: '暐翹' },
      },
      {
        i: 4,
        box: [0.3627, 0.317, 0.3939, 0.3722],
        px: [33, 44],
        det_score: 0.853,
        top1: 0.264,
        top2: 0.229,
        margin: 0.036,
        candidate: null,
      },
      {
        i: 5,
        box: [0.4304, 0.3152, 0.4634, 0.3735],
        px: [35, 47],
        det_score: 0.882,
        top1: 0.219,
        top2: 0.187,
        margin: 0.033,
        candidate: null,
      },
      {
        i: 6,
        box: [0.5047, 0.293, 0.5338, 0.3491],
        px: [31, 45],
        det_score: 0.84,
        top1: 0.227,
        top2: 0.21,
        margin: 0.017,
        candidate: null,
      },
      {
        i: 7,
        box: [0.574, 0.2746, 0.6061, 0.3349],
        px: [34, 49],
        det_score: 0.891,
        top1: 0.325,
        top2: 0.224,
        margin: 0.101,
        candidate: null,
      },
      {
        i: 8,
        box: [0.6453, 0.2714, 0.6775, 0.3328],
        px: [34, 49],
        det_score: 0.852,
        top1: 0.316,
        top2: 0.224,
        margin: 0.092,
        candidate: null,
      },
      {
        i: 9,
        box: [0.7033, 0.2941, 0.7292, 0.3488],
        px: [28, 44],
        det_score: 0.802,
        top1: 0.247,
        top2: 0.191,
        margin: 0.057,
        candidate: null,
      },
      {
        i: 10,
        box: [0.7289, 0.2874, 0.7635, 0.3479],
        px: [37, 49],
        det_score: 0.881,
        top1: 0.276,
        top2: 0.255,
        margin: 0.021,
        candidate: null,
      },
      {
        i: 11,
        box: [0.7881, 0.313, 0.8194, 0.3713],
        px: [33, 47],
        det_score: 0.837,
        top1: 0.212,
        top2: 0.205,
        margin: 0.007,
        candidate: null,
      },
      {
        i: 12,
        box: [0.8026, 0.2231, 0.8258, 0.2966],
        px: [25, 59],
        det_score: 0.534,
        top1: 0.213,
        top2: 0.185,
        margin: 0.029,
        candidate: null,
      },
      {
        i: 13,
        box: [0.8791, 0.3035, 0.9157, 0.3636],
        px: [39, 48],
        det_score: 0.736,
        top1: 0.186,
        top2: 0.172,
        margin: 0.014,
        candidate: null,
      },
    ],
  },
  {
    key: 'b',
    src: '/videos/reports/street-photos-2026-11-15/frame-2.jpg',
    alt: '街拍二：一排人在 Sogo 門外排隊合照，臉部框出十個',
    caption:
      '二 · 排隊 — 原生解像度零偵測（臉只有 14×19 像素，低於 min_face_size 20）。同一個區帶以 4× 分格（220 px 窗、150 px 步長）重跑，得十張臉。',
    mode: 'tiled 4x',
    width: 1085,
    height: 814,
    faces: [
      {
        i: 1,
        box: [0.2976, 0.3921, 0.3107, 0.4167],
        px: [14, 20],
        det_score: 0.793,
        top1: 0.232,
        top2: 0.22,
        margin: 0.013,
        candidate: null,
      },
      {
        i: 2,
        box: [0.3288, 0.3847, 0.3428, 0.4087],
        px: [15, 19],
        det_score: 0.801,
        top1: 0.207,
        top2: 0.172,
        margin: 0.035,
        candidate: null,
      },
      {
        i: 3,
        box: [0.364, 0.3989, 0.3736, 0.4211],
        px: [10, 18],
        det_score: 0.667,
        top1: 0.224,
        top2: 0.211,
        margin: 0.012,
        candidate: null,
      },
      {
        i: 4,
        box: [0.413, 0.4039, 0.4259, 0.4271],
        px: [13, 18],
        det_score: 0.758,
        top1: 0.227,
        top2: 0.196,
        margin: 0.032,
        candidate: null,
      },
      {
        i: 5,
        box: [0.4371, 0.3978, 0.4517, 0.4238],
        px: [15, 21],
        det_score: 0.732,
        top1: 0.198,
        top2: 0.163,
        margin: 0.035,
        candidate: null,
      },
      {
        i: 6,
        box: [0.4659, 0.3892, 0.4803, 0.4153],
        px: [15, 21],
        det_score: 0.825,
        top1: 0.229,
        top2: 0.222,
        margin: 0.006,
        candidate: null,
      },
      {
        i: 7,
        box: [0.5036, 0.3821, 0.5158, 0.4067],
        px: [13, 19],
        det_score: 0.762,
        top1: 0.326,
        top2: 0.186,
        margin: 0.14,
        candidate: null,
      },
      {
        i: 8,
        box: [0.5372, 0.4037, 0.5512, 0.4286],
        px: [15, 20],
        det_score: 0.638,
        top1: 0.133,
        top2: 0.132,
        margin: 0.001,
        candidate: null,
      },
      {
        i: 9,
        box: [0.6079, 0.4028, 0.6208, 0.4239],
        px: [13, 17],
        det_score: 0.629,
        top1: 0.244,
        top2: 0.23,
        margin: 0.014,
        candidate: null,
      },
      {
        i: 10,
        box: [0.6343, 0.3964, 0.649, 0.42],
        px: [15, 19],
        det_score: 0.643,
        top1: 0.164,
        top2: 0.16,
        margin: 0.004,
        candidate: null,
      },
    ],
  },
];

/**
 * What lowering the bar costs, measured on the reference cache: for each cutoff, the share of the
 * 638 reference photos whose best score against a *different* contestant reaches it. That is the
 * rate at which a stranger is accepted, so it is read as the price of the cutoff, not as a
 * property of these photos.
 */
export const CUTOFF_SWEEP = [
  { cutoff: 0.25, rate: 0.8793 },
  { cutoff: 0.3, rate: 0.4687 },
  { cutoff: 0.35, rate: 0.1066 },
  { cutoff: 0.38, rate: 0.0502 },
  { cutoff: 0.412, rate: 0.0094 },
];

/**
 * What a face has to survive to be matched: the embedding of the *same* face re-embedded after
 * the frame is downsampled to that face height (9 faces from frame 一, aligned on their own
 * landmarks), as a cosine against the embedding at native size. Below ~24 px the embedding stops
 * being a fingerprint of the face and starts being a fingerprint of the downsampling.
 */
export const FACE_SIZE_CEILING = [
  { height: 49, mean: 0.986, min: 0.968 },
  { height: 32, mean: 0.942, min: 0.863 },
  { height: 24, mean: 0.867, min: 0.807 },
  { height: 18, mean: 0.791, min: 0.745 },
  { height: 12, mean: 0.589, min: 0.458 },
];

/**
 * The matcher itself, measured on the reference cache (leave-one-out, 200 sampled references):
 * a held-out photo of a contestant against the rest of that contestant's set, and against every
 * other contestant. The site threshold sits where 1% of impostors would pass.
 */
export const MATCHER_CHECK = {
  genuineMean: 0.615,
  genuineP05: 0.419,
  genuineAboveThreshold: 0.96,
  impostorMax: 0.445,
  impostorAboveThreshold: 0.005,
};

/**
 * Contestants a viewer of the show recognised by eye in these two frames — ground truth by human
 * judgement, not by this system. Two of the eleven they could not place are omitted. The frames
 * themselves come from a public Threads post (@zisha_1001) asking who the group was.
 *
 * `best` is the highest cosine any of the 23 faces scored against that contestant's reference set,
 * `rank` is where that puts them among all 94 contestants, and `face` is the box that produced it
 * (`一-3` = frame 一, box 3). `aboveNoise` compares `best` with the 90th percentile of the
 * contestants the photographer did *not* name (0.231) — the line where a score stops looking like
 * it could have come from anyone.
 *
 * Two entries carry `maybe`: named as possible rather than recognised.
 */
export interface NamedContestant {
  id: string;
  nickname: string;
  name: string;
  best: number;
  rank: number;
  face: string;
  px: [number, number];
  /** `best` clears the 90th percentile of the 85 contestants the list does not name. */
  aboveNoise: boolean;
  /** Named as possible rather than recognised. */
  maybe: boolean;
}

export const NAMED_PRESENT: NamedContestant[] = [
  {
    id: '22',
    nickname: '暐翹',
    name: '林暐翹',
    best: 0.388,
    rank: 1,
    face: '一-3',
    px: [35, 44],
    aboveNoise: true,
    maybe: false,
  },
  {
    id: '15',
    nickname: 'Carina',
    name: '李晞彤',
    best: 0.325,
    rank: 3,
    face: '一-7',
    px: [34, 49],
    aboveNoise: true,
    maybe: false,
  },
  {
    id: '83',
    nickname: '何佩',
    name: '何佩婷',
    best: 0.264,
    rank: 6,
    face: '一-4',
    px: [33, 44],
    aboveNoise: true,
    maybe: false,
  },
  {
    id: '20',
    nickname: 'Karen',
    name: '余嘉熙',
    best: 0.22,
    rank: 18,
    face: '二-1',
    px: [14, 20],
    aboveNoise: false,
    maybe: false,
  },
  {
    id: '2',
    nickname: '咖喱',
    name: '黃雅慧',
    best: 0.219,
    rank: 19,
    face: '一-5',
    px: [35, 47],
    aboveNoise: false,
    maybe: false,
  },
  {
    id: '27',
    nickname: 'Ada 仔',
    name: '姜咏鑫',
    best: 0.186,
    rank: 39,
    face: '二-1',
    px: [14, 20],
    aboveNoise: false,
    maybe: false,
  },
  {
    id: '5',
    nickname: '莎莎',
    name: '坂部佩莎',
    best: 0.206,
    rank: 28,
    face: '一-8',
    px: [34, 49],
    aboveNoise: false,
    maybe: false,
  },
  {
    id: '78',
    nickname: '馬欣',
    name: '馬彩欣',
    best: 0.211,
    rank: 23,
    face: '二-3',
    px: [10, 18],
    aboveNoise: false,
    maybe: false,
  },
  {
    id: '18',
    nickname: '蘇菲',
    name: '陳莉詩',
    best: 0.207,
    rank: 26,
    face: '二-9',
    px: [13, 17],
    aboveNoise: false,
    maybe: false,
  },
  {
    id: '14',
    nickname: 'Elka',
    name: '鄭芷淇',
    best: 0.238,
    rank: 10,
    face: '一-10',
    px: [37, 49],
    aboveNoise: true,
    maybe: true,
  },
  {
    id: '1',
    nickname: 'Ivy So',
    name: '蘇雅琳',
    best: 0.111,
    rank: 90,
    face: '一-11',
    px: [33, 47],
    aboveNoise: false,
    maybe: true,
  },
];

/** The noise line the named contestants are compared against: p90 of the 85 they did not name. */
export const ROSTER_NOISE = { mean: 0.174, p90: 0.231, max: 0.326 };

/**
 * Open identification: every box's best-scoring contestant over the whole roster, no name list
 * supplied. A group this size should collapse onto a handful of names; instead 23 boxes land on
 * 16 different contestants, and one nickname is the top-1 for three separate people. Those extra
 * identities are noise, which is why the page never prints a per-box name.
 */
export const OPEN_TOP1 = {
  boxes: 23,
  distinct: 16,
  repeated: [
    { nickname: '嘉嘉', times: 3 },
    { nickname: '暐翹', times: 2 },
    { nickname: 'Carina', times: 2 },
    { nickname: 'Sica', times: 2 },
    { nickname: '阿蛋', times: 2 },
    { nickname: 'Kinki', times: 2 },
  ],
};

/**
 * The Threads post ships the first frame at 4032×3024 — 3.7× the width of the paste the page's
 * tables were built from, with faces 136×167 px instead of 35×44. Running it settles what the
 * small-face analysis could only guess at: resolution is not what holds the scores down.
 */
export const HIRES_COMPARISON = {
  paste: { width: 1085, face: [35, 44] as [number, number] },
  original: { width: 4032, face: [136, 167] as [number, number] },
  rows: [
    { nickname: '暐翹', paste: 0.388, original: 0.392 },
    { nickname: 'Carina', paste: 0.325, original: 0.325 },
    { nickname: '何佩', paste: 0.264, original: 0.227 },
  ],
  /** Every face at 12 MP: 74×103 at the smallest, 140×182 at the largest. */
  faces: 13,
  smallest: [74, 103] as [number, number],
  largest: [140, 182] as [number, number],
};

/**
 * The post is a three-photo carousel. Only the first photo is served at full size to a logged-out
 * reader; the other two arrive at 640×480, where tiling recovers 12 and 8 faces of 8–16 px and
 * nothing clears a meaningful threshold.
 */
export const POST_PHOTOS = [
  { n: 1, served: '4032×3024', faces: 13, facePx: '74–140', best: 0.392 },
  { n: 2, served: '640×480', faces: 12, facePx: '12–23', best: 0.304 },
  { n: 3, served: '640×480', faces: 8, facePx: '8–9', best: 0.24 },
];

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
    verdict: '本頁採用的名單來源；九位之中三位過雜訊線。',
  },
  {
    handle: 'waiwaiwai9413',
    text: '超酸story好似見到elka同ivyso同carina',
    verdict: 'Elka 排第 10，Ivy So 排第 90——同一張相，兩個結果。',
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
 * Replies the logged-out page does not show, so their text cannot be quoted: 蘇菲（陳莉詩，18 號）
 * replied in the same thread. Recorded as a fact about who replied, not as a quotation.
 */
export const UNSEEN_REPLY_AUTHORS = [{ id: '18', nickname: '蘇菲', name: '陳莉詩' }];

/**
 * VIVA, the group two of the replies name, is four people: Ada (姜咏鑫), Carina (李晞彤), Macy
 * (馬思惠) and VALC (張鈊貽). Only the first two appear in the 96-contestant 造星 IV roster, so a
 * VIVA shoot is half outside this system's gallery — Macy and VALC have no reference vectors at
 * all, and no score for them is possible.
 */
export const VIVA_COVERAGE = { members: 4, inRoster: 2 };

export const TOTALS = {
  faces: STREET_IMAGES.reduce((n, im) => n + im.faces.length, 0),
  accepted: STREET_IMAGES.flatMap((im) => im.faces).filter((f) => f.candidate !== null).length,
  best: Math.max(...STREET_IMAGES.flatMap((im) => im.faces.map((f) => f.top1))),
  /** The narrowest #1−#2 gap: how close the ranking comes to being pure noise. */
  tightestMargin: Math.min(...STREET_IMAGES.flatMap((im) => im.faces.map((f) => f.margin))),
  widestMargin: Math.max(...STREET_IMAGES.flatMap((im) => im.faces.map((f) => f.margin))),
};
