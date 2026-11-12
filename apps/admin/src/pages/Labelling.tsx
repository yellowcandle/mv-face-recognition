import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Search, X } from 'lucide-react';
import { useSearchParams } from 'react-router';
import {
  AdminErrorNotice,
  Button,
  Card,
  FaceCrop,
  DetectionStamp,
  Masthead,
  Stamp,
  adminFetch,
  assertOk,
  useContestants,
  useVideos,
  videoShortName,
  isSessionExpired,
} from '@mv/shared';
import type { Contestant, VideoInfo, VideoMetadata } from '@mv/shared';
import { sheetPosition, slipTime } from '@mv/shared/lib/labelling';

// ---------------------------------------------------------------------------
// labels/v2 — one verdict per TRACK, keyed by `tracker_id`. The tracker links a
// face across frames, so one verdict covers every detection in that track.
// Detections with `tracker_id < 0` were never tracked and are not labelable.
// An absent entry means "not labelled", never a verdict. Declared here rather
// than in @mv/shared: nothing else in either app reads this file yet.
// ---------------------------------------------------------------------------

type Verdict = 'contestant' | 'not_a_contestant' | 'unsure' | 'box_wrong';

const VERDICTS: Verdict[] = ['contestant', 'not_a_contestant', 'unsure', 'box_wrong'];

const VERDICT_LABEL: Record<Verdict, string> = {
  contestant: '參賽者',
  not_a_contestant: '非參賽者',
  unsure: '未確定',
  box_wrong: '框錯了',
};

const VERDICT_BLURB: Record<Exclude<Verdict, 'contestant'>, string> = {
  not_a_contestant: '不是 96 人之一：工作人員、背景、臨時演員',
  unsure: '這個裁切看不出來，不影響閘門',
  box_wrong: '不是人臉或框錯位置，屬偵測錯誤，不是配對錯誤',
};

interface Label {
  tracker_id: number;
  verdict: Verdict;
  contestant_id?: string;
  note?: string;
}

interface LabelSource {
  processing_date: string;
  detections: number;
}

interface LabelsFile {
  schema: string | null;
  video_id: string | null;
  labelled_at: string | null;
  source?: LabelSource;
  labels?: Label[];
  /** A labels/v1 file was found, could not be mapped onto tracks, and was left on disk. */
  legacy_ignored?: boolean;
  legacy_detail?: string;
}

/** `GET /api/labels/{video_id}` either yields the file or refuses a stale v2 one (409). */
type LabelsResult = { status: 'conflict'; detail: string } | { status: 'loaded'; file: LabelsFile };

interface Detection {
  frame_number: number;
  timestamp: number;
  detection_index: number;
  tracker_id: number | null;
  match_source?: string | null;
  match_score: number | null;
  det_score: number;
  bbox: [number, number, number, number];
  contestant_id: string | null;
  contestant_name: string | null;
  contestant_nickname: string | null;
}

interface TrackVote {
  contestant_id: string;
  nickname: string | null;
  name: string | null;
  count: number;
}

interface Track {
  key: string;
  tracker_id: number;
  frame_count: number;
  /** Highest match_score in the track; earliest frame on a tie, first detection on a fallback. */
  representative: Detection;
  /** Contestant ids claimed by this track's detections, most votes first. */
  votes: TrackVote[];
  /** The plurality claim shown in the UI; null when no detection in the track was named. */
  claim: TrackVote | null;
}

/** The metadata route also stamps the run's `processing_date`, which `VideoInfo` does not declare. */
type DenseMetadata = Omit<VideoMetadata, 'video_info'> & {
  video_info: VideoInfo & { processing_date?: string };
};

// ---------------------------------------------------------------------------
// Layout constants
// ---------------------------------------------------------------------------

/** Tracks rendered at once. 530 lazy images at once is a request storm, not a grid. */
const PAGE_SIZE = 120;
const AUTOSAVE_DEBOUNCE_MS = 400;
/**
 * How long the sheet's verdict controls stay inert after a commit. The commit advances to the
 * next unlabelled track in the same geometry, so without a window a double-click would label
 * two tracks: the second click lands on a sheet that has already moved on. The window covers
 * the advance plus the autosave debounce it starts.
 */
const COMMIT_SETTLE_MS = AUTOSAVE_DEBOUNCE_MS + 100;

/** The separation gate the labels exist to decide (ticket 005). */
const GATE = { trueMatchMean: 0.45, worstImpostor: 0.2 } as const;
/** Below this many labelled tracks neither number means anything, so neither is coloured. */
const MIN_LABELS_FOR_GATE = 10;
const MIN_TRUE_MATCHES_FOR_MEAN = 5;
const MIN_IMPOSTORS_FOR_WORST = 3;

/** FaceCrop sets its width inline and sizes its image by height-auto; these make it a square tile. */
const CROP_FILL =
  'aspect-square overflow-hidden rounded bg-paper-dark [&_img]:h-full [&_img]:object-cover';
const BANNER = 'flex flex-col gap-2 rounded-md border border-stamp/50 px-4 py-3';

/** Stable, track-ordered output so a save only rewrites what actually changed. */
function serializeLabels(labels: Record<string, Label>): Label[] {
  return Object.values(labels).sort((a, b) => a.tracker_id - b.tracker_id);
}

/** The model's plurality claim for a track, in the same shape the cards use. */
function claimText(track: Track, contestantsById: Record<string, Contestant>): string {
  if (!track.claim) return '未命名';
  const contestant = contestantsById[track.claim.contestant_id];
  if (contestant) return `#${contestant.id} ${contestant.nickname}`;
  return `#${track.claim.contestant_id}${track.claim.nickname ? ` ${track.claim.nickname}` : ''}`;
}

/** Every named identity the track's frames voted for, with counts. */
function voteBreakdown(track: Track, contestantsById: Record<string, Contestant>): string {
  if (track.votes.length === 0) return '沒有命名的格';
  return track.votes
    .map((vote) => {
      const contestant = contestantsById[vote.contestant_id];
      const name = contestant ? contestant.nickname : vote.nickname;
      return `${name ?? `#${vote.contestant_id}`} ${vote.count}`;
    })
    .join(' · ');
}

// ---------------------------------------------------------------------------
// Reading the wire
//
// Fetch payloads are asserted at their fetch boundary against the type the contract fixes
// (each site says which); the one body read by hand is the local API's error reply, whose
// shape is not part of that contract.
// ---------------------------------------------------------------------------

/** `{ error, detail }` from either a 409 or a 400 — the detail is the useful half. */
function readErrorDetail(value: unknown): string | null {
  if (typeof value !== 'object' || value === null) return null;
  const detail = 'detail' in value ? value.detail : undefined;
  if (typeof detail === 'string' && detail !== '') return detail;
  const error = 'error' in value ? value.error : undefined;
  return typeof error === 'string' && error !== '' ? error : null;
}

/**
 * `GET /api/videos/metadata/dense/{video_id}` — the endpoint the shared viewer consumes as
 * `VideoMetadata`; `DenseMetadata` only adds the run's `processing_date` to `video_info`.
 */
async function fetchDenseMetadata(videoId: string): Promise<DenseMetadata> {
  const res = await fetch(`/api/videos/metadata/dense/${encodeURIComponent(videoId)}`);
  // Public route, so no Access plumbing: `assertOk` still turns a non-2xx into an error that
  // carries the server's detail instead of a bare status code.
  await assertOk(res);
  return (await res.json()) as DenseMetadata;
}

/**
 * Why a video cannot be labelled at all, or null when it can.
 *
 * Metadata written before the current box/score contract (ticket 014) has no
 * `frame_data[].detections`: it holds `recognitions` — pixel boxes and threshold-relative
 * scores — which is a different coordinate space and a different score. There is nothing under
 * the current contract to judge, so this page refuses to invent detections for it and says so.
 * Only metadata carrying a `detections` array on *every* frame is offered for labelling.
 */
function metadataContractIssue(metadata: DenseMetadata | undefined): string | null {
  if (!metadata) return null;
  const frames = metadata.frame_data;
  if (!Array.isArray(frames)) return '它沒有 frame_data 陣列';
  const stale = frames.find((frame) => !Array.isArray(frame.detections));
  if (!stale) return null;
  const fields = Object.keys(stale).filter(
    (field) => field !== 'frame_number' && field !== 'timestamp',
  );
  return `第 ${stale.frame_number} 格帶的是 ${fields.length > 0 ? fields.join('、') : '空白欄位'}，不是 detections 陣列`;
}

/** One label-and-figure line in the rail. */
function RailRow({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center justify-between gap-3 text-[13px]">
      <span className="font-kai text-carbon-soft">{label}</span>
      <span className="font-mono tabular-nums text-carbon-deep">{value}</span>
    </div>
  );
}

function FileRow({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="font-kai text-carbon-soft">{label}</span>
      <span className="font-mono tabular-nums text-carbon-deep">{value}</span>
    </div>
  );
}

/** A gate statistic beside the test it faces. Red only once enough is labelled and it fails. */
function GateFigure({ value, failing, test }: { value: number; failing: boolean; test: string }) {
  return (
    <span className="flex items-end gap-2 font-mono tabular-nums">
      <span className={`text-[28px] leading-tight ${failing ? 'text-stamp' : 'text-carbon-deep'}`}>
        {value.toFixed(3)}
      </span>
      <span className="pb-1 text-[12px] text-ink-muted">{test}</span>
    </span>
  );
}

// ---------------------------------------------------------------------------
// The contestant picker: search by number / nickname / name, Enter takes the
// first match, Escape closes the sheet.
// ---------------------------------------------------------------------------

function ContestantPicker({
  contestants,
  busy,
  onPick,
}: {
  contestants: Contestant[];
  /** True while the commit that just ran is still settling; every control is inert. */
  busy: boolean;
  onPick: (contestantId: string) => void;
}) {
  const [query, setQuery] = useState('');
  const hits = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return contestants;
    return contestants.filter(
      (c) =>
        String(c.id).startsWith(needle) ||
        (c.nickname ?? '').toLowerCase().includes(needle) ||
        (c.name ?? '').toLowerCase().includes(needle),
    );
  }, [contestants, query]);

  return (
    <div className="flex flex-col gap-1">
      <div className="rounded-md border border-carbon-deep/33">
        <div className="relative border-b border-carbon-deep/13">
          <Search
            aria-hidden
            className="pointer-events-none absolute left-2.5 top-3.5 size-4 text-carbon-soft sm:top-2.5"
          />
          <input
            autoFocus
            aria-label="選擇參賽者"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                if (busy) return;
                const first = hits[0];
                if (first) onPick(String(first.id));
              }
            }}
            placeholder="參賽者編號、暱稱或姓名…"
            className="h-11 w-full rounded-t-md sm:h-9 bg-transparent pl-8.5 pr-2.5 font-kai text-[14px] text-carbon-deep placeholder:text-ink-muted"
          />
        </div>
        <div className="max-h-[140px] overflow-y-auto">
          {hits.length === 0 ? (
            <p className="px-2.5 py-1.5 font-kai text-[12px] text-ink-muted">
              沒有參賽者符合「{query}」。
            </p>
          ) : (
            hits.map((c, i) => (
              <button
                key={c.id}
                type="button"
                disabled={busy}
                onClick={() => onPick(String(c.id))}
                className={`flex h-11 w-full items-center gap-2 px-2.5 sm:h-7 text-left font-kai transition-colors hover:bg-tint disabled:cursor-not-allowed disabled:opacity-50 ${
                  i === 0 ? 'bg-tint' : ''
                }`}
              >
                <span className="font-mono text-[12px] tabular-nums text-carbon-soft">#{c.id}</span>
                <span className="truncate text-[14px] text-carbon-deep">{c.nickname}</span>
                <span className="truncate text-[12px] text-ink-muted">{c.name}</span>
              </button>
            ))
          )}
        </div>
      </div>
      <p className="font-kai text-[12px] text-ink-muted">
        <span className="font-mono tabular-nums">{contestants.length}</span> 位中的{' '}
        <span className="font-mono tabular-nums">{hits.length}</span> 位 · Enter 選第一個
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// The page
// ---------------------------------------------------------------------------

type SaveState = 'idle' | 'saving' | 'saved' | 'failed';

export function Labelling() {
  const queryClient = useQueryClient();
  const { data: videos = [], isLoading: videosLoading } = useVideos('', { includeTests: true });
  const { data: contestantsRaw = [] } = useContestants();
  // `useContestants` is untyped JSON; `Contestant` is the domain type for it, asserted at this
  // boundary the same way `Flagging.tsx` asserts it. Only id/nickname/name are read, and a
  // non-array reply contributes no contestants rather than throwing through the picker.
  const contestants = Array.isArray(contestantsRaw) ? (contestantsRaw as Contestant[]) : [];

  // `?video=<id>` names the reel a link came for; the probe below tries it before falling back
  // to its usual first-labelable walk.
  const [searchParams] = useSearchParams();
  const requestedVideoId = searchParams.get('video');
  // `&tracks=1,2,3` narrows that reel to a prepared sample (ticket 020). Other reels ignore it.
  const requestedTracks = searchParams.get('tracks');

  const [videoId, setVideoId] = useState<string | null>(null);
  const streamUrl = videos.find((v) => v.id === videoId)?.stream_url;
  // Videos the probe found to be unlabelable (pre-014 metadata), so the picker can say which
  // ones need a reprocess instead of letting the next visitor land in the same message.
  const [staleVideoIds, setStaleVideoIds] = useState<Set<string>>(new Set());
  const userPickedRef = useRef(false);

  // Arriving at the page must land on a video that can actually be labelled. The list endpoint
  // carries no contract marker, so the probe walks it in order and stops at the first video
  // whose metadata parses with `frame_data[].detections`; the rest are marked stale. If no video
  // qualifies, the first one is selected and explains itself — never a blank screen. The probe
  // shares the metadata query's cache, so the chosen video is not fetched twice. A `?video=`
  // request is simply walked first, so an unlabelable one still falls back to the usual order.
  useEffect(() => {
    if (videos.length === 0 || userPickedRef.current) return;
    let cancelled = false;
    void (async () => {
      const stale: string[] = [];
      const probeOrder = requestedVideoId
        ? [
            ...videos.filter((video) => video.id === requestedVideoId),
            ...videos.filter((video) => video.id !== requestedVideoId),
          ]
        : videos;
      for (const video of probeOrder) {
        let labelable = false;
        try {
          const metadata = await queryClient.fetchQuery({
            queryKey: ['dense-metadata', video.id],
            queryFn: () => fetchDenseMetadata(video.id),
            staleTime: 5 * 60 * 1000,
          });
          if (cancelled || userPickedRef.current) return;
          labelable = metadataContractIssue(metadata) === null;
        } catch {
          // Metadata that will not load cannot be labelled either; keep looking.
          if (cancelled || userPickedRef.current) return;
        }
        if (labelable) {
          setStaleVideoIds(new Set(stale));
          setVideoId(video.id);
          return;
        }
        stale.push(video.id);
      }
      if (cancelled || userPickedRef.current) return;
      setStaleVideoIds(new Set(stale));
      setVideoId(videos[0].id);
    })();
    return () => {
      cancelled = true;
    };
  }, [videos, queryClient, requestedVideoId]);

  // ---- queries -----------------------------------------------------------

  const metadataQuery = useQuery<DenseMetadata>({
    queryKey: ['dense-metadata', videoId],
    enabled: !!videoId,
    queryFn: () => fetchDenseMetadata(videoId ?? ''),
    staleTime: 5 * 60 * 1000,
  });

  const labelsQuery = useQuery<LabelsResult>({
    queryKey: ['labels', videoId],
    enabled: !!videoId,
    queryFn: async () => {
      const res = await adminFetch(`/admin/api/labels/${encodeURIComponent(videoId ?? '')}`);
      if (res.status === 409) {
        const detail = readErrorDetail(await res.json().catch(() => null));
        return {
          status: 'conflict' as const,
          detail: detail ?? '現有標註檔的來源與目前的中繼資料不符：重新處理使它失效。',
        };
      }
      // Anything else that is not 2xx throws an `ApiError` carrying the server's detail (or a
      // `SessionExpiredError`), so the page can name the real failure instead of guessing.
      await assertOk(res);
      // `labels/v2` on the wire: the server rejects anything else on PUT, so a file that reads
      // back through GET was well-formed when it was written. A v1 file is not an error: it
      // comes back as an empty v2 set with `legacy_ignored`, so the page can explain re-labelling.
      return { status: 'loaded' as const, file: (await res.json()) as LabelsFile };
    },
    staleTime: 5 * 60 * 1000,
  });

  const file = labelsQuery.data?.status === 'loaded' ? labelsQuery.data.file : null;
  const conflict = labelsQuery.data?.status === 'conflict' ? labelsQuery.data.detail : null;
  const legacyIgnored = file?.legacy_ignored === true;
  // A labels file that cannot be read must not be silently replaced by an empty set, so the
  // failure is surfaced and labelling is blocked until it is readable. The error object is kept
  // whole: an expired Access session is not a corrupt file, and `AdminErrorNotice` tells the two
  // apart (one offers reload, the other a retry).
  const labelsLoadFailure: unknown = labelsQuery.isError
    ? (labelsQuery.error ?? new Error('無法載入標註'))
    : null;
  const labelsLoadError = labelsLoadFailure !== null;
  const labelsLoadExpired = isSessionExpired(labelsLoadFailure);

  // ---- detections and tracks ---------------------------------------------

  const metadataIssue = useMemo(
    () => metadataContractIssue(metadataQuery.data),
    [metadataQuery.data],
  );

  // Defensive by construction: a frame without a `detections` array contributes nothing rather
  // than throwing through the render. The contract check above is what tells the user why.
  const detections = useMemo<Detection[]>(() => {
    const raw = metadataQuery.data?.frame_data;
    const frames = Array.isArray(raw) ? raw : [];
    const ordered = [...frames].sort((a, b) => a.frame_number - b.frame_number);
    const out: Detection[] = [];
    for (const frame of ordered) {
      // detection_index is the index into this frame's own detections array — the same index
      // the crop endpoint takes. tracker_id decides which track a detection belongs to.
      const frameDetections = Array.isArray(frame.detections) ? frame.detections : [];
      frameDetections.forEach((d, index) => {
        out.push({
          frame_number: frame.frame_number,
          timestamp: frame.timestamp,
          detection_index: index,
          tracker_id: typeof d.tracker_id === 'number' ? d.tracker_id : null,
          match_source: d.match_source,
          match_score: d.match_score,
          det_score: d.det_score,
          bbox: d.bbox,
          contestant_id: d.contestant_id,
          contestant_name: d.contestant_name,
          contestant_nickname: d.contestant_nickname,
        });
      });
    }
    return out;
  }, [metadataQuery.data]);

  // One row per tracked face. `tracker_id` is the label key; detections with a negative or
  // missing id never become a row and are counted in `untrackedCount` instead.
  const tracks = useMemo<Track[]>(() => {
    interface Builder {
      representative: Detection;
      frameCount: number;
      votes: Map<string, TrackVote>;
    }
    const byTracker = new Map<number, Builder>();

    for (const detection of detections) {
      const trackerId = detection.tracker_id;
      if (trackerId === null || trackerId < 0) continue;

      let builder = byTracker.get(trackerId);
      if (!builder) {
        builder = { representative: detection, frameCount: 0, votes: new Map() };
        byTracker.set(trackerId, builder);
      }
      builder.frameCount += 1;

      // Representative: the highest match_score wins; an equal score keeps the earliest frame.
      // If nothing in the track is matched, the first detection (frame order) stands in.
      const representative = builder.representative;
      const score = detection.match_score;
      if (
        score !== null &&
        (representative.match_score === null ||
          score > representative.match_score ||
          (score === representative.match_score &&
            detection.frame_number < representative.frame_number))
      ) {
        builder.representative = detection;
      }

      if (detection.contestant_id) {
        const vote = builder.votes.get(detection.contestant_id);
        if (vote) {
          vote.count += 1;
        } else {
          builder.votes.set(detection.contestant_id, {
            contestant_id: detection.contestant_id,
            nickname: detection.contestant_nickname,
            name: detection.contestant_name,
            count: 1,
          });
        }
      }
    }

    return [...byTracker.entries()]
      .sort(([a], [b]) => a - b)
      .map(([trackerId, builder]) => {
        const votes = [...builder.votes.values()].sort(
          (a, b) =>
            b.count - a.count ||
            Number(a.contestant_id) - Number(b.contestant_id) ||
            a.contestant_id.localeCompare(b.contestant_id),
        );
        return {
          key: String(trackerId),
          tracker_id: trackerId,
          frame_count: builder.frameCount,
          representative: builder.representative,
          votes,
          claim: votes[0] ?? null,
        };
      });
  }, [detections]);

  const trackByKey = useMemo(() => {
    const byKey: Record<string, Track> = {};
    for (const track of tracks) byKey[track.key] = track;
    return byKey;
  }, [tracks]);

  const untrackedCount = useMemo(
    () => detections.filter((d) => d.tracker_id === null || d.tracker_id < 0).length,
    [detections],
  );

  const processingDate = metadataQuery.data?.video_info?.processing_date ?? null;
  // The server identifies a run by `{processing_date, detections}` where detections is the
  // number of detections it walks out of frame_data — so the pin this page sends is the count
  // of detections it parsed, not the summary's `total_faces_detected` or the number of tracks.
  const detectionsCount = detections.length;

  const source = useMemo<LabelSource | null>(() => {
    if (file?.source?.processing_date) return file.source;
    if (!processingDate) return null;
    return { processing_date: processingDate, detections: detectionsCount };
  }, [file, processingDate, detectionsCount]);

  const currentRun = useMemo(
    () => ({ processing_date: processingDate ?? '不明', detections: detectionsCount }),
    [processingDate, detectionsCount],
  );

  // ---- labels state ------------------------------------------------------

  const [labels, setLabels] = useState<Record<string, Label>>({});
  const [hydratedFor, setHydratedFor] = useState<string | null>(null);
  const [saveState, setSaveState] = useState<SaveState>('idle');
  const [saveError, setSaveError] = useState<unknown>(null);
  const [savedAt, setSavedAt] = useState<Date | null>(null);
  const [savedPath, setSavedPath] = useState<string | null>(null);
  /**
   * The verdict a clear removed, per track, so the reviewer can take that clear back. The label is
   * already out of `labels` — that removal is what the autosave writes — and the undo is a fresh
   * edit of its own rather than a cancellation of the write that may already be in flight.
   */
  const [clearedLabels, setClearedLabels] = useState<Record<string, Label>>({});

  const savedJsonRef = useRef<string | null>(null);
  const saveSeqRef = useRef(0);
  /** Tail of the write queue, so a labels file is never replaced by two PUTs racing each other. */
  const saveChainRef = useRef<Promise<void>>(Promise.resolve());
  /**
   * The payload the debounce is holding. It lives here, not only in the timer closure, because
   * every dependency change, a video switch and an unmount all clear that timer — and clearing
   * it is exactly what used to drop the last verdict typed inside the 400 ms window.
   */
  const pendingSaveRef = useRef<{ videoId: string; json: string } | null>(null);
  /** The video the badges describe; a write finishing after a switch must not move them. */
  const liveVideoRef = useRef<string | null>(null);
  /**
   * A write the reviewer switched away from cannot move the badges — they describe the video on
   * screen — but its failure must not vanish with it: the flush before a switch is exactly the
   * write that must not fail silently. Held per video and shown when that video is reopened.
   */
  const failedSaveRef = useRef(new Map<string, unknown>());

  useEffect(() => {
    liveVideoRef.current = videoId;
  }, [videoId]);

  // Resume: reopening a video shows the labels already on disk. The baseline for
  // "has anything changed?" is what the server last told us, so hydration never
  // triggers a save of its own.
  useEffect(() => {
    if (!videoId || !file || hydratedFor === videoId) return;
    const next: Record<string, Label> = {};
    for (const label of file.labels ?? []) {
      next[String(label.tracker_id)] = label;
    }
    setLabels(next);
    // A clear belongs to the video it happened in; the next one starts with nothing to undo.
    setClearedLabels({});
    savedJsonRef.current = JSON.stringify(serializeLabels(next));
    // A payload queued for the video being left is never written into this one's file.
    pendingSaveRef.current = null;
    const failedSave = failedSaveRef.current.get(videoId);
    setHydratedFor(videoId);
    setSaveState(failedSave ? 'failed' : 'idle');
    setSaveError(failedSave ?? null);
    setSavedAt(file.labelled_at ? new Date(file.labelled_at) : null);
  }, [videoId, file, hydratedFor]);

  const labelsJson = useMemo(() => JSON.stringify(serializeLabels(labels)), [labels]);

  const save = useCallback(
    (bodyLabelsJson: string): Promise<void> => {
      if (!videoId || !source) return Promise.resolve();
      // Everything below is pinned to this video: the request, the cache entry it refreshes and
      // the badges it may move. `live()` asks again at each step, because the reviewer can switch
      // video while a write is in flight.
      const forVideo = videoId;
      const seq = ++saveSeqRef.current;
      const live = () => forVideo === liveVideoRef.current;
      if (live()) {
        setSaveState('saving');
        setSaveError(null);
      }
      // The endpoint replaces the whole file, so writes are serialized: two overlapping PUTs can
      // otherwise finish out of order and leave the older label set on disk. `seq` was taken at
      // enqueue time, so only the newest queued payload may move the badges.
      const run = saveChainRef.current.then(async () => {
        try {
          // Round-trip of this page's own serialization, not external input: the debounce effect
          // hands over the exact JSON it built from the labels map.
          const labelList = JSON.parse(bodyLabelsJson) as Label[];
          const res = await adminFetch(`/admin/api/labels/${encodeURIComponent(forVideo)}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ source, labels: labelList }),
          });
          // A non-2xx throws here: an `ApiError` with the server's `detail`, or a
          // `SessionExpiredError` the notice renders as "reload", never as a broken file.
          await assertOk(res);
          const savedBody: unknown = await res.json().catch(() => null);
          // Keep the cache equal to disk so remounting the page mid-session shows
          // the verdicts that were just written. This is keyed by `forVideo`, so it stays correct
          // even when the reviewer has already moved to another video.
          queryClient.setQueryData<LabelsResult>(['labels', forVideo], (): LabelsResult => ({
            status: 'loaded',
            file: {
              schema: 'labels/v2',
              video_id: forVideo,
              labelled_at: new Date().toISOString(),
              source,
              labels: labelList,
              legacy_ignored: false,
            },
          }));
          failedSaveRef.current.delete(forVideo);
          if (!live() || seq !== saveSeqRef.current) return;
          savedJsonRef.current = bodyLabelsJson;
          setSaveState('saved');
          setSaveError(null);
          setSavedAt(new Date());
          setSavedPath(
            typeof savedBody === 'object' &&
              savedBody !== null &&
              'path' in savedBody &&
              typeof savedBody.path === 'string'
              ? savedBody.path
              : null,
          );
        } catch (e) {
          if (!live()) {
            failedSaveRef.current.set(forVideo, e);
            return;
          }
          if (seq !== saveSeqRef.current) return;
          setSaveState('failed');
          setSaveError(e);
        }
      });
      saveChainRef.current = run;
      return run;
    },
    [videoId, source, queryClient],
  );

  // Autosave, debounced. Skipped while a stale file blocks labelling and skipped
  // when the payload is byte-identical to what was last saved.
  useEffect(() => {
    if (!videoId || hydratedFor !== videoId || conflict || labelsLoadError || metadataIssue) return;
    if (savedJsonRef.current === labelsJson) {
      pendingSaveRef.current = null;
      return;
    }
    pendingSaveRef.current = { videoId, json: labelsJson };
    const timer = setTimeout(() => {
      pendingSaveRef.current = null;
      void save(labelsJson);
    }, AUTOSAVE_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [labelsJson, videoId, hydratedFor, conflict, labelsLoadError, metadataIssue, save]);

  /**
   * Write what the debounce is holding — or the labels in memory when the effect has not queued
   * them yet — instead of waiting out the timer. Called before a video switch and on unmount: the
   * two paths where the cleanup above would otherwise cancel the only write the reviewer's last
   * verdict had.
   */
  const flushPendingSave = useCallback(() => {
    const pending = pendingSaveRef.current;
    pendingSaveRef.current = null;
    // The same gate as the debounce: a blocked page never writes, not even on the way out, and a
    // payload queued for another video is never written into this one's file.
    if (conflict || labelsLoadError || metadataIssue) return;
    // Between a switch and that video's hydration the labels in memory still belong to the video
    // being left, so nothing in this state is theirs to write.
    if (!videoId || hydratedFor !== videoId) return;
    const queued = pending !== null && pending.videoId === videoId ? pending.json : null;
    const target = queued ?? (labelsJson !== savedJsonRef.current ? labelsJson : null);
    if (target === null) return;
    void save(target);
  }, [conflict, labelsLoadError, metadataIssue, videoId, hydratedFor, labelsJson, save]);

  // `save` (and `videoId`) change across renders; an unmount cleanup must reach the newest pair.
  const flushRef = useRef(flushPendingSave);
  useEffect(() => {
    flushRef.current = flushPendingSave;
  }, [flushPendingSave]);
  useEffect(() => () => flushRef.current(), []);

  /** Verdicts typed but not yet on disk: the debounce is still running, or a write is in flight. */
  const unsaved =
    videoId !== null &&
    hydratedFor === videoId &&
    (saveState === 'saving' || labelsJson !== savedJsonRef.current);

  // Leaving the page inside that window must not silently discard it. The browser owns the
  // prompt, so this only asks; the flush above is what actually keeps the edit.
  useEffect(() => {
    if (!unsaved) return;
    const onBeforeUnload = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = '';
    };
    window.addEventListener('beforeunload', onBeforeUnload);
    return () => window.removeEventListener('beforeunload', onBeforeUnload);
  }, [unsaved]);

  // ---- filters -----------------------------------------------------------

  const [query, setQuery] = useState('');
  const [unlabelledOnly, setUnlabelledOnly] = useState(false);
  const [claimedOnly, setClaimedOnly] = useState(false);
  const [verdictFilter, setVerdictFilter] = useState<'all' | Verdict>('all');
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);

  useEffect(() => {
    setVisibleCount(PAGE_SIZE);
  }, [videoId, query, unlabelledOnly, claimedOnly, verdictFilter]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const sample =
      requestedTracks && videoId === requestedVideoId
        ? new Set(requestedTracks.split(',').map(Number))
        : null;
    const rows = tracks.filter((track) => {
      const label = labels[track.key];
      if (sample && !sample.has(track.tracker_id)) return false;
      if (claimedOnly && !track.claim) return false;
      if (unlabelledOnly && label) return false;
      if (verdictFilter !== 'all' && label?.verdict !== verdictFilter) return false;
      if (!q) return true;
      return (
        String(track.tracker_id).includes(q) ||
        String(track.claim?.contestant_id ?? '').startsWith(q) ||
        (track.claim?.nickname ?? '').toLowerCase().includes(q) ||
        (track.claim?.name ?? '').toLowerCase().includes(q)
      );
    });
    // Highest cosine first: the claimed-track sample is meant to see the riskiest claims first.
    if (claimedOnly) {
      rows.sort((a, b) => {
        const sa = a.representative.match_score;
        const sb = b.representative.match_score;
        if (sa === null && sb === null) return a.tracker_id - b.tracker_id;
        if (sa === null) return 1;
        if (sb === null) return -1;
        return sb - sa;
      });
    }
    return rows;
  }, [
    tracks,
    labels,
    query,
    unlabelledOnly,
    claimedOnly,
    verdictFilter,
    requestedTracks,
    requestedVideoId,
    videoId,
  ]);

  // ---- the sheet ---------------------------------------------------------

  const [openKey, setOpenKey] = useState<string | null>(null);
  const openTrack = openKey ? (trackByKey[openKey] ?? null) : null;

  const closeSheet = useCallback(() => {
    setOpenKey(null);
  }, []);

  const tileRefs = useRef(new Map<string, HTMLButtonElement | null>());

  useEffect(() => {
    if (!openTrack) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeSheet();
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [openTrack, closeSheet]);

  useEffect(() => {
    if (!openKey) return;
    tileRefs.current.get(openKey)?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
  }, [openKey]);

  /** After a write, move on to the next still-unlabelled track in the current view. */
  const advanceFrom = useCallback(
    (next: Record<string, Label>, fromKey: string) => {
      // -1 when the tile just left the filtered view (an "unlabelled only" filter):
      // the wrap then starts the scan at the top of what is still shown.
      const index = filtered.findIndex((t) => t.key === fromKey);
      for (let step = 1; step <= filtered.length; step++) {
        const candidate = filtered[(index + step) % filtered.length];
        if (!next[candidate.key]) {
          const candidateIndex = filtered.findIndex((t) => t.key === candidate.key);
          if (candidateIndex >= visibleCount) setVisibleCount(candidateIndex + 1);
          setOpenKey(candidate.key);
          return;
        }
      }
      closeSheet();
    },
    [filtered, visibleCount, closeSheet],
  );

  const commit = useCallback(
    (entries: Array<[string, Label | undefined]>, fromKey: string) => {
      const next = { ...labels };
      for (const [key, label] of entries) {
        if (label) next[key] = label;
        else delete next[key];
      }
      setLabels(next);
      // A new verdict supersedes a clear: the undo offer only ever describes the last clear.
      setClearedLabels((prev) => {
        const rest = { ...prev };
        let changed = false;
        for (const [key, label] of entries) {
          if (label && key in rest) {
            delete rest[key];
            changed = true;
          }
        }
        return changed ? rest : prev;
      });
      advanceFrom(next, fromKey);
    },
    [labels, advanceFrom],
  );

  // ---- commit arming -----------------------------------------------------
  // A commit advances the sheet to the next unlabelled track *in the same geometry*, so the
  // second click of a double-click would land on a different track and label it too. The gate is
  // a ref: it flips synchronously inside the first handler, before React re-renders, so the
  // second click cannot slip between the two. `committing` only disables the controls visually.
  const [committing, setCommitting] = useState(false);
  const commitLockRef = useRef(false);
  const commitTimerRef = useRef<number | null>(null);

  const armCommit = useCallback(() => {
    commitLockRef.current = true;
    setCommitting(true);
    if (commitTimerRef.current !== null) window.clearTimeout(commitTimerRef.current);
    // Released once the advance has rendered and the autosave it queued has fired.
    commitTimerRef.current = window.setTimeout(() => {
      commitTimerRef.current = null;
      commitLockRef.current = false;
      setCommitting(false);
    }, COMMIT_SETTLE_MS);
  }, []);

  useEffect(
    () => () => {
      if (commitTimerRef.current !== null) window.clearTimeout(commitTimerRef.current);
    },
    [],
  );

  const commitOne = useCallback(
    (track: Track, verdict: Verdict, contestantId?: string) => {
      if (commitLockRef.current) return;
      armCommit();
      const existing = labels[track.key];
      if (
        existing &&
        existing.verdict === verdict &&
        (verdict !== 'contestant' || existing.contestant_id === contestantId)
      ) {
        // Re-stating the verdict already on the track writes nothing; it only moves on, which is
        // what the reviewer asked for by clicking it again.
        advanceFrom(labels, track.key);
        return;
      }
      const label: Label = {
        tracker_id: track.tracker_id,
        verdict,
        ...(verdict === 'contestant' && contestantId ? { contestant_id: contestantId } : {}),
      };
      commit([[track.key, label]], track.key);
    },
    [labels, advanceFrom, commit, armCommit],
  );

  /**
   * Backspace/Delete on a card, or "Clear label" in the sheet. The removal reaches disk through the
   * autosave effect like any other change; the previous verdict is kept so it can be put back.
   */
  const clearLabel = useCallback(
    (key: string) => {
      const previous = labels[key];
      if (!previous) return;
      const next = { ...labels };
      delete next[key];
      setLabels(next);
      setClearedLabels((prev) => ({ ...prev, [key]: previous }));
    },
    [labels],
  );

  /** Put a cleared verdict back. That edit autosaves on its own; no write is cancelled. */
  const undoClear = useCallback(
    (key: string) => {
      const previous = clearedLabels[key];
      if (!previous) return;
      setClearedLabels((prev) => {
        const next = { ...prev };
        delete next[key];
        return next;
      });
      setLabels((prev) => ({ ...prev, [key]: previous }));
    },
    [clearedLabels],
  );

  // ---- derived rail data -------------------------------------------------

  const contestantsById = useMemo(() => {
    const byId: Record<string, Contestant> = {};
    for (const c of contestants) byId[String(c.id)] = c;
    return byId;
  }, [contestants]);

  const rail = useMemo(() => {
    const counts: Record<Verdict, number> = {
      contestant: 0,
      not_a_contestant: 0,
      unsure: 0,
      box_wrong: 0,
    };
    let labelled = 0;
    const trueMatches: number[] = [];
    const impostors: number[] = [];
    let missed = 0;
    let misnamed = 0;

    // Gate statistics are per track, one score per track (the representative detection's
    // match_score):
    //   true match — verdict `contestant` and the label agrees with the matcher's plurality
    //                claim for the track;
    //   missed     — verdict `contestant` but the matcher left the track unnamed;
    //   misnamed   — verdict `contestant` but the matcher claimed another contestant;
    //   impostor   — verdict `not_a_contestant` while the matcher named the track anyway,
    //                i.e. the human label differs from the model's claim.
    for (const track of tracks) {
      const label = labels[track.key];
      if (!label) continue;
      labelled++;
      counts[label.verdict]++;

      const claimed = track.claim?.contestant_id ?? null;
      if (label.verdict === 'contestant') {
        if (claimed !== null && claimed === label.contestant_id) {
          if (track.representative.match_score !== null) {
            trueMatches.push(track.representative.match_score);
          }
        } else if (claimed === null) {
          missed++;
        } else {
          misnamed++;
        }
      } else if (label.verdict === 'not_a_contestant' && claimed !== null) {
        if (track.representative.match_score !== null) {
          impostors.push(track.representative.match_score);
        }
      }
    }

    const trueMatchMean =
      trueMatches.length > 0
        ? trueMatches.reduce((sum, value) => sum + value, 0) / trueMatches.length
        : null;

    return {
      labelled,
      counts,
      trueMatches: trueMatches.length,
      trueMatchMean,
      impostors: impostors.length,
      worstImpostor: impostors.length > 0 ? Math.max(...impostors) : null,
      missed,
      misnamed,
    };
  }, [tracks, labels]);

  const progressPct = tracks.length > 0 ? (rail.labelled / tracks.length) * 100 : 0;
  const gateReady = rail.labelled >= MIN_LABELS_FOR_GATE;
  const meanReady = rail.trueMatches >= MIN_TRUE_MATCHES_FOR_MEAN;
  const impostorReady = rail.impostors >= MIN_IMPOSTORS_FOR_WORST;

  function chipText(key: string): string | null {
    const label = labels[key];
    if (!label) return null;
    if (label.verdict === 'contestant') {
      const contestant = label.contestant_id ? contestantsById[label.contestant_id] : undefined;
      return contestant
        ? `#${contestant.id} ${contestant.nickname}`
        : `#${label.contestant_id ?? '?'}`;
    }
    return VERDICT_LABEL[label.verdict];
  }

  const visible = filtered.slice(0, visibleCount);
  // Labelling is blocked whenever the labels on disk cannot be read (a stale file, or a load
  // failure) or the metadata is not under the current contract. A blocked page never writes.
  const blocked = conflict !== null || labelsLoadError || metadataIssue !== null;
  const labelable = metadataIssue === null;
  const loading = !videoId || metadataQuery.isLoading || labelsQuery.isLoading;

  return (
    <div className="flex min-h-full flex-1 flex-col xl:flex-row">
      {/* Tracks */}
      <div className="flex min-w-0 flex-col gap-3 px-4 pb-5 pt-8 sm:pl-8 sm:pr-5 xl:flex-1 xl:overflow-y-auto">
        <div className="pb-1">
          <Masthead title="標註" hint="替未認出的臉指定參賽者">
            {/* Autosave is otherwise silent: this is what tells AT the write landed. */}
            <span role="status" aria-live="polite" className="font-mono text-[12px] tabular-nums">
              {saveState === 'saving' && '儲存中…'}
              {saveState === 'saved' && `已儲存${savedAt ? ` · ${slipTime(savedAt)}` : ''}`}
              {saveState === 'failed' && <span className="font-kai text-stamp">儲存失敗</span>}
              {saveState === 'idle' && savedAt && `已存於磁碟 · ${slipTime(savedAt)}`}
            </span>
            {saveState === 'failed' && (
              <Button variant="secondary" size="sm" onClick={() => void save(labelsJson)}>
                重試
              </Button>
            )}
          </Masthead>
        </div>

        {saveError != null && (
          <AdminErrorNotice
            error={saveError}
            onRetry={() => void save(labelsJson)}
            label="標註儲存失敗"
          />
        )}

        {legacyIgnored && (
          <div className={BANNER}>
            <p className="font-kai text-[14px] text-stamp">
              找到舊版 <span className="font-mono">labels/v1</span>{' '}
              檔案，已略過：它標註的是個別偵測，不是軌跡。
            </p>
            {file?.legacy_detail && (
              <p className="font-kai text-[12px] text-ink-muted">{file.legacy_detail}</p>
            )}
            <p className="font-kai text-[12px] text-ink-muted">
              舊檔案原封不動。你儲存的第一個判定會替這條影片寫入新的{' '}
              <span className="font-mono">labels/v2</span> 檔案，取代逐個偵測的判定。
            </p>
          </div>
        )}

        {conflict !== null && (
          <div className={BANNER}>
            <p className="font-kai text-[14px] text-stamp">
              磁碟上的標註屬於另一次處理：標註已封鎖，不會寫入任何內容，也不會從頭開始。
            </p>
            <p className="font-kai text-[12px] text-ink-muted">{conflict}</p>
            <div className="grid grid-cols-1 gap-3 font-mono text-[12px] text-carbon sm:grid-cols-2">
              <div className="rounded-md border border-carbon-deep/13 p-2">
                <div className="mb-1 font-kai text-ink-muted">目前的中繼資料</div>
                <div>processing_date {currentRun.processing_date}</div>
                <div>detections {currentRun.detections}</div>
              </div>
              <div className="rounded-md border border-carbon-deep/13 p-2">
                <div className="mb-1 font-kai text-ink-muted">標註檔</div>
                <div className="break-all">local_output/labels/{videoId}_labels.json</div>
                <div className="text-ink-muted">
                  {file?.source ? (
                    <span>
                      processing_date {file.source.processing_date} · detections{' '}
                      {file.source.detections}
                    </span>
                  ) : (
                    <span className="font-kai">所屬批次見上面的訊息；409 回覆沒有其他副本。</span>
                  )}
                </div>
              </div>
            </div>
            <p className="font-kai text-[12px] text-ink-muted">
              重新處理這條影片，或移除{' '}
              <span className="break-all font-mono">local_output/labels/{videoId}_labels.json</span>{' '}
              以從頭標註這次處理。現有判定不會被改動。
            </p>
          </div>
        )}

        {labelsLoadError && (
          <div className="flex flex-col gap-2">
            <AdminErrorNotice
              error={labelsLoadFailure}
              onRetry={() => void labelsQuery.refetch()}
              label="標註檔讀取失敗"
            />
            {/* An expired session is not a broken file: the notice above already offers the only
                action that helps, and the file is untouched and unread, not corrupt. */}
            {!labelsLoadExpired && (
              <div className={BANNER}>
                <p className="font-kai text-[14px] text-stamp">
                  標註已封鎖，直到標註檔可以讀取，以免儲存時蓋掉磁碟上已有的判定。
                </p>
                <p className="font-kai text-[12px] text-ink-muted">
                  修復或移走{' '}
                  <span className="break-all font-mono">
                    local_output/labels/{videoId}_labels.json
                  </span>{' '}
                  後重試。在此之前不會寫入任何內容。
                </p>
              </div>
            )}
          </div>
        )}

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-2">
          <select
            aria-label="影片"
            value={videoId ?? ''}
            onChange={(e) => {
              // The debounce timer is about to be cleared by this switch, so the verdict typed a
              // moment ago is written first — to the video it was typed for.
              flushPendingSave();
              // An explicit choice wins over the auto-probe for the rest of the session.
              userPickedRef.current = true;
              setVideoId(e.target.value || null);
              setHydratedFor(null);
              savedJsonRef.current = null;
              closeSheet();
            }}
            className="field field-select w-28 max-sm:h-11"
          >
            {videos.length === 0 && (
              <option value="">{videosLoading ? '載入中…' : '沒有已處理的影片'}</option>
            )}
            {videos.map((v) => (
              <option key={v.id} value={v.id}>
                {videoShortName(v.name)}
                {staleVideoIds.has(v.id) ? ' — 中繼資料早於框線規格' : ''}
              </option>
            ))}
          </select>

          {labelable && (
            <>
              <select
                aria-label="判定"
                value={verdictFilter}
                onChange={(e) => setVerdictFilter(e.target.value as 'all' | Verdict)}
                className="field field-select w-[124px] max-sm:h-11"
              >
                <option value="all">全部判定</option>
                {VERDICTS.map((v) => (
                  <option key={v} value={v}>
                    {VERDICT_LABEL[v]}
                  </option>
                ))}
              </select>

              <div className="relative min-w-40 flex-1">
                <Search
                  aria-hidden
                  className="pointer-events-none absolute left-2.5 top-2 size-4 text-carbon-soft max-sm:top-3.5"
                />
                <input
                  type="search"
                  aria-label="搜尋軌跡"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="軌跡、姓名或編號…"
                  className="field w-full pl-8 placeholder:text-ink-muted max-sm:h-11"
                />
              </div>
            </>
          )}
        </div>

        {labelable && (
          <>
            <div className="flex flex-wrap items-center gap-x-5 gap-y-1 font-kai text-[13px]">
              <label
                className={`flex cursor-pointer items-center gap-1.5 max-sm:min-h-11 ${
                  unlabelledOnly ? 'text-carbon' : 'text-carbon-soft'
                }`}
              >
                <input
                  type="checkbox"
                  checked={unlabelledOnly}
                  onChange={(e) => setUnlabelledOnly(e.target.checked)}
                  className="size-4 cursor-pointer accent-carbon"
                />
                只看未標註
              </label>
              <label
                className={`flex cursor-pointer items-center gap-1.5 max-sm:min-h-11 ${
                  claimedOnly ? 'text-carbon' : 'text-carbon-soft'
                }`}
                title="只列系統已命名的軌跡，按配對分數排序，風險最高的先看"
              >
                <input
                  type="checkbox"
                  checked={claimedOnly}
                  onChange={(e) => setClaimedOnly(e.target.checked)}
                  className="size-4 cursor-pointer accent-carbon"
                />
                只看系統已命名（分數高先）
              </label>
            </div>

            <div className="flex flex-col gap-1.5">
              <div className="flex items-end justify-between gap-3">
                <span className="flex items-end gap-1.5">
                  <span className="font-mono text-[14px] tabular-nums text-carbon-deep">
                    {rail.labelled} / {tracks.length}
                  </span>
                  <span className="font-kai text-[13px] text-carbon-soft">條軌跡已標註</span>
                </span>
                <span className="font-kai text-[12px] text-ink-muted">
                  在列 <span className="font-mono tabular-nums">{filtered.length}</span> 條
                </span>
              </div>
              <div className="h-1 overflow-hidden rounded-xs bg-paper-dark">
                <div className="h-full bg-stamp" style={{ width: `${progressPct}%` }} />
              </div>
              {untrackedCount > 0 && (
                <p className="font-kai text-[12px] text-ink-muted">
                  <span className="font-mono tabular-nums">{untrackedCount.toLocaleString()}</span>{' '}
                  個偵測未被追蹤，沒有軌跡可掛判定，已略過 (
                  <span className="font-mono">tracker_id &lt; 0</span>)
                </p>
              )}
            </div>
          </>
        )}

        {!labelable ? (
          <Card padding="lg">
            <div className="mx-auto flex max-w-3xl flex-col gap-3 py-8 text-center font-kai text-[14px] text-carbon-soft">
              <h2 className="text-[18px] font-normal text-carbon-deep">
                這條影片的中繼資料早於目前的框線與分數規格
              </h2>
              <p>
                這裏沒有東西可以標註：{metadataIssue}。標註看的是{' '}
                <span className="font-mono">frame_data[].detections</span>
                ：以畫面比例記錄的框線和原始餘弦分數。這個檔案寫於該規格之前，框線的座標不同，分數也不能比較。
              </p>
              <p>重新處理影片後再載入這一頁。中繼資料不會原地遷移，也不會替它寫入任何標註。</p>
              {videos.length > 1 && (
                <p className="text-ink-muted">
                  上面選單標示「中繼資料早於框線規格」的影片，同樣需要重新處理。
                </p>
              )}
            </div>
          </Card>
        ) : loading ? (
          <div className="flex flex-col items-center justify-center py-16 font-kai text-[14px] text-carbon-soft">
            <div className="mb-4 size-8 animate-spin rounded-full border-2 border-paper-deep border-t-stamp" />
            <p>載入軌跡中…</p>
          </div>
        ) : metadataQuery.error ? (
          <div className="flex flex-col gap-2">
            <AdminErrorNotice
              error={metadataQuery.error}
              onRetry={() => void metadataQuery.refetch()}
              label="中繼資料讀取失敗"
            />
            <p className="font-kai text-[12px] text-ink-muted">
              中繼資料讀回來之前無法標註：軌跡由它建立，也不會替讀不到的批次寫入標註檔。
            </p>
          </div>
        ) : filtered.length === 0 ? (
          <Card padding="lg">
            <div className="py-8 text-center font-kai">
              <p className="mb-1 text-[14px] text-carbon">沒有符合目前篩選的軌跡</p>
              <p className="text-[13px] text-carbon-soft">
                {tracks.length === 0
                  ? '這條影片的中繼資料裏沒有已追蹤的偵測。'
                  : '清除篩選，或取消「只看未標註」。'}
              </p>
            </div>
          </Card>
        ) : (
          <>
            <div className="grid grid-cols-[repeat(auto-fill,minmax(112px,1fr))] gap-3">
              {visible.map((track) => {
                const chip = chipText(track.key);
                const votes = voteBreakdown(track, contestantsById);
                const topVote = track.votes[0];
                const isOpen = track.key === openKey;
                const cleared = clearedLabels[track.key];
                return (
                  <div key={track.key} className="relative min-w-0">
                    <button
                      ref={(el) => {
                        tileRefs.current.set(track.key, el);
                      }}
                      type="button"
                      disabled={blocked}
                      aria-current={isOpen ? 'true' : undefined}
                      onClick={() => {
                        setOpenKey(track.key);
                      }}
                      onKeyDown={(e) => {
                        if (e.key === 'Backspace' || e.key === 'Delete') {
                          e.preventDefault();
                          clearLabel(track.key);
                        }
                      }}
                      title={`軌跡 ${track.tracker_id} · ${track.frame_count} 格 · 系統認為：${votes}。按一下標註，Backspace 清除`}
                      className={`group flex w-full min-w-0 flex-col gap-1.5 rounded text-left ${
                        blocked ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'
                      }`}
                    >
                      <span
                        className={`relative block rounded ${
                          isOpen
                            ? 'ring-2 ring-stamp'
                            : 'group-hover:ring-1 group-hover:ring-carbon-deep/33'
                        }`}
                      >
                        <FaceCrop
                          videoId={videoId ?? ''}
                          frameNumber={track.representative.frame_number}
                          detectionIndex={track.representative.detection_index}
                          timestamp={track.representative.timestamp}
                          bbox={track.representative.bbox}
                          streamUrl={streamUrl}
                          width={160}
                          className={`${CROP_FILL} !w-full`}
                        />
                        {chip && (
                          <Stamp
                            tilt
                            className="absolute bottom-2 left-1.5 max-w-[calc(100%-0.75rem)] overflow-hidden text-ellipsis"
                          >
                            {chip}
                          </Stamp>
                        )}
                      </span>
                      <span className="flex min-w-0 flex-col gap-0.5">
                        <span className="flex items-center justify-between gap-1">
                          <span className="truncate font-mono text-[12px] tabular-nums text-ink-muted">
                            {track.tracker_id} · {track.frame_count}格
                          </span>
                          <DetectionStamp detection={track.representative} />
                        </span>
                        <span
                          className={`truncate font-kai text-[14px] ${
                            isOpen
                              ? 'font-bold text-carbon-deep'
                              : track.claim
                                ? 'text-carbon'
                                : 'text-ink-muted'
                          }`}
                          title={track.claim?.name ?? undefined}
                        >
                          {claimText(track, contestantsById)}
                        </span>
                        <span
                          className="truncate font-mono text-[12px] tabular-nums text-ink-muted"
                          title={votes}
                        >
                          {topVote ? (
                            `票 ${topVote.count}/${track.frame_count}${
                              track.votes.length > 1 ? ` · +${track.votes.length - 1}` : ''
                            }`
                          ) : (
                            <span className="font-kai">沒有命名的格</span>
                          )}
                        </span>
                      </span>
                    </button>
                    {/* The tile stays a button: the undo control sits beside it, not inside. */}
                    {cleared && !labels[track.key] && (
                      <button
                        type="button"
                        disabled={blocked}
                        onClick={() => undoClear(track.key)}
                        title={`軌跡 ${track.tracker_id} 的判定已清除，按一下復原`}
                        className="absolute left-1.5 top-1.5 max-w-[calc(100%-0.75rem)] truncate rounded-md border border-carbon-deep/33 bg-ground px-1.5 py-0.5 font-kai text-[12px] text-carbon hover:bg-tint"
                      >
                        已清除 · 復原
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
            {visibleCount < filtered.length && (
              <div className="flex justify-center">
                <Button
                  variant="secondary"
                  size="sm"
                  className="max-sm:h-11"
                  onClick={() => setVisibleCount((n) => n + PAGE_SIZE)}
                >
                  再顯示 {Math.min(PAGE_SIZE, filtered.length - visibleCount)} 張（尚餘{' '}
                  {filtered.length - visibleCount}）
                </Button>
              </div>
            )}
          </>
        )}
      </div>

      {/* The sheet, docked between the grid and the rail. Stacks first below xl. */}
      {openTrack && !blocked && (
        // Docked beside the grid, so a labelled region rather than a modal dialog: no focus trap,
        // and closing it moves focus nowhere, so Esc then Backspace can't clear a tile's label.
        <aside
          aria-labelledby="label-sheet-title"
          className="order-first flex shrink-0 flex-col gap-4 border-b border-carbon-deep/13 px-4 pb-5 pt-8 sm:px-6 xl:order-none xl:w-[416px] xl:overflow-y-auto xl:border-b-0 xl:border-l"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="flex min-w-0 flex-col gap-1">
              <h2
                id="label-sheet-title"
                className="font-kai text-[18px] font-normal leading-tight text-carbon-deep"
              >
                標註這條軌跡
              </h2>
              <p className="font-mono text-[12px] tabular-nums text-ink-muted">
                軌跡 {openTrack.tracker_id} · {openTrack.frame_count} 格 ·{' '}
                {sheetPosition(
                  filtered.findIndex((t) => t.key === openKey),
                  filtered.length,
                )}
              </p>
            </div>
            <button
              type="button"
              onClick={closeSheet}
              aria-label="關閉"
              className="shrink-0 rounded-md text-carbon-soft hover:text-stamp max-sm:-m-3 max-sm:p-3"
            >
              <X aria-hidden className="size-5" />
            </button>
          </div>

          <div className="flex gap-4">
            <FaceCrop
              videoId={videoId ?? ''}
              frameNumber={openTrack.representative.frame_number}
              detectionIndex={openTrack.representative.detection_index}
              timestamp={openTrack.representative.timestamp}
              bbox={openTrack.representative.bbox}
              streamUrl={streamUrl}
              width={512}
              className={`${CROP_FILL} !w-[120px] shrink-0 max-sm:self-start sm:!w-[200px]`}
            />
            <div className="flex min-w-0 flex-1 flex-col gap-1 text-[12px] text-ink-muted">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-[28px] leading-tight tabular-nums text-carbon-deep">
                  {openTrack.representative.match_score === null
                    ? '—'
                    : openTrack.representative.match_score.toFixed(3)}
                </span>
                <DetectionStamp detection={openTrack.representative} />
              </div>
              <div className="font-kai">配對分數</div>
              <div className="font-mono tabular-nums">
                檢出分數{' '}
                {typeof openTrack.representative.det_score === 'number'
                  ? openTrack.representative.det_score.toFixed(3)
                  : '未記錄'}
              </div>
              <div className="font-mono tabular-nums">
                第 {openTrack.representative.frame_number} 格 · 偵測{' '}
                {openTrack.representative.detection_index}
              </div>
              <div className="h-1" />
              <div className="font-kai">系統認為</div>
              {openTrack.claim ? (
                <>
                  <div className="flex flex-wrap items-end gap-x-1.5 font-kai">
                    <span className="text-[15px] text-carbon-deep">
                      {openTrack.claim.nickname ?? '—'}
                    </span>
                    <span className="text-carbon-soft">
                      #{openTrack.claim.contestant_id}
                      {openTrack.claim.name ? ` ${openTrack.claim.name}` : ''}
                    </span>
                  </div>
                  <div className="font-mono tabular-nums">
                    {openTrack.claim.count}/{openTrack.frame_count} 格 · {openTrack.votes.length}{' '}
                    個身分
                  </div>
                </>
              ) : (
                <div className="font-kai text-[15px]">沒有人</div>
              )}
              <div className="break-words font-mono tabular-nums">
                票：{voteBreakdown(openTrack, contestantsById)}
              </div>
              {chipText(openTrack.key) && (
                <div className="flex flex-wrap items-center gap-2 pt-1">
                  <Stamp tilt>{chipText(openTrack.key)}</Stamp>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="max-sm:h-11"
                    onClick={() => clearLabel(openTrack.key)}
                  >
                    清除標註
                  </Button>
                </div>
              )}
              {/* The sheet stays open after a clear, so the undo has to live here as well. */}
              {!labels[openTrack.key] && clearedLabels[openTrack.key] && (
                <div className="pt-1">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="max-sm:h-11"
                    onClick={() => undoClear(openTrack.key)}
                  >
                    已清除 · 復原
                  </Button>
                </div>
              )}
            </div>
          </div>

          {openTrack.claim && (
            <Button
              variant="primary"
              size="md"
              className="w-full max-sm:h-auto max-sm:min-h-11 max-sm:whitespace-normal max-sm:py-2"
              onClick={() => commitOne(openTrack, 'contestant', openTrack.claim?.contestant_id)}
              title={`接受系統對整條軌跡的判定：${claimText(openTrack, contestantsById)}`}
            >
              接受系統判定 · {openTrack.claim.nickname ?? '—'} #{openTrack.claim.contestant_id} ·{' '}
              {openTrack.claim.count}/{openTrack.frame_count} 格
            </Button>
          )}

          <ContestantPicker
            key={openKey}
            contestants={contestants}
            busy={committing}
            onPick={(contestantId) => commitOne(openTrack, 'contestant', contestantId)}
          />

          <div className="flex flex-col gap-2">
            {(['not_a_contestant', 'unsure', 'box_wrong'] as const).map((v) => (
              <button
                key={v}
                type="button"
                disabled={committing}
                onClick={() => commitOne(openTrack, v)}
                className="flex cursor-pointer disabled:cursor-not-allowed disabled:opacity-50 flex-col gap-0.5 rounded-md border border-carbon-deep/33 px-2.5 py-1.5 text-left max-sm:min-h-11 font-kai transition-colors hover:bg-tint"
              >
                <span className="text-[14px] text-carbon-deep">{VERDICT_LABEL[v]}</span>
                <span className="text-[12px] text-carbon-soft">{VERDICT_BLURB[v]}</span>
              </button>
            ))}
          </div>

          <p className="font-kai text-[12px] text-ink-muted">
            選定判定會替整條軌跡記一個標註，並跳到下一條未標註軌跡。Esc 關閉；在軌跡卡上按 Backspace
            或 Delete 清除標註。
          </p>
        </aside>
      )}

      {/* Rail */}
      {labelable && (
        <aside
          aria-label="標註統計"
          className="flex shrink-0 flex-col gap-6 border-t border-carbon-deep/13 px-4 pb-5 pt-8 sm:px-5 xl:w-[248px] xl:overflow-y-auto xl:border-l xl:border-t-0"
        >
          <section className="flex flex-col gap-1.5">
            <h2 className="font-kai text-[18px] font-normal leading-tight text-carbon-deep">
              判定
            </h2>
            {VERDICTS.map((v) => (
              <RailRow key={v} label={VERDICT_LABEL[v]} value={rail.counts[v]} />
            ))}
            <div className="border-t border-carbon-deep/13 pt-1.5">
              <RailRow label="未標註軌跡" value={tracks.length - rail.labelled} />
            </div>
          </section>

          <section className="flex flex-col gap-2">
            <h2 className="font-kai text-[18px] font-normal leading-tight text-carbon-deep">
              這些標註解鎖的閘門
            </h2>
            <p className="font-kai text-[12px] text-ink-muted">
              只計已標註的 {rail.labelled} 條軌跡，每條取代表偵測的配對分數。閘門：真實配對平均 ≥{' '}
              {GATE.trueMatchMean}，最差冒認 ≤ {GATE.worstImpostor}。
            </p>
            {!gateReady && (
              <p className="font-kai text-[12px] text-stamp">
                標註尚未足夠（{rail.labelled} / {MIN_LABELS_FOR_GATE}）：下面只是計數，不是判定。
              </p>
            )}
            <div className="flex flex-col gap-0.5 pt-1">
              <span className="font-kai text-[12px] text-carbon-soft">
                真實配對平均 · {rail.trueMatches} 條
              </span>
              {meanReady && rail.trueMatchMean !== null ? (
                <GateFigure
                  value={rail.trueMatchMean}
                  failing={gateReady && rail.trueMatchMean < GATE.trueMatchMean}
                  test={`${rail.trueMatchMean >= GATE.trueMatchMean ? '≥' : '<'} ${GATE.trueMatchMean}`}
                />
              ) : (
                <span className="font-kai text-[14px] text-ink-muted">標註尚未足夠</span>
              )}
            </div>
            <div className="flex flex-col gap-0.5">
              <span className="font-kai text-[12px] text-carbon-soft">
                最差冒認分數 · {rail.impostors} 條
              </span>
              {impostorReady && rail.worstImpostor !== null ? (
                <GateFigure
                  value={rail.worstImpostor}
                  failing={gateReady && rail.worstImpostor > GATE.worstImpostor}
                  test={`${rail.worstImpostor <= GATE.worstImpostor ? '≤' : '>'} ${GATE.worstImpostor}`}
                />
              ) : (
                <span className="font-kai text-[14px] text-ink-muted">標註尚未足夠</span>
              )}
            </div>
            <div className="flex flex-col gap-1.5 border-t border-carbon-deep/13 pt-2">
              <RailRow label="系統漏認（未命名）" value={rail.missed} />
              <RailRow label="系統認錯（認作別人）" value={rail.misnamed} />
            </div>
          </section>

          <section className="flex flex-col gap-1.5 text-[12px]">
            <h2 className="font-kai text-[18px] font-normal leading-tight text-carbon-deep">
              標註檔
            </h2>
            <FileRow label="結構" value={file?.schema ?? 'labels/v2'} />
            <FileRow label="已標註軌跡" value={rail.labelled} />
            <FileRow label="標註時間" value={savedAt ? slipTime(savedAt) : '—'} />
            <span className="font-kai text-carbon-soft">來源</span>
            <span className="font-mono tabular-nums text-carbon-deep">
              {source ? (
                `${slipTime(source.processing_date)} · ${source.detections} 偵測`
              ) : (
                <span className="font-kai">不明批次</span>
              )}
            </span>
            {savedPath && <p className="break-all font-mono text-ink-muted">{savedPath}</p>}
          </section>

          <p className="mt-auto font-kai text-[12px] text-ink-muted">
            每條軌跡一個判定：tracker_id
            跨格連起同一張臉。裁切取自處理後的版本，這裏不會重新換算分數。
          </p>
        </aside>
      )}
    </div>
  );
}
