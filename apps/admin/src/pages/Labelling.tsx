import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  BAND_STAMP,
  Badge,
  Button,
  Card,
  FaceCrop,
  useContestants,
  useVideos,
  bandFor,
} from '@mv/shared';
import type { Band, Contestant, VideoInfo, VideoMetadata } from '@mv/shared';

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
  contestant: 'Contestant',
  not_a_contestant: 'Not a contestant',
  unsure: 'Unsure',
  box_wrong: 'Box is wrong',
};

const VERDICT_BLURB: Record<Verdict, string> = {
  contestant: 'This track is that contestant',
  not_a_contestant: 'Not one of the 96 — crew, background, an extra',
  unsure: 'Cannot tell from this crop; decides nothing in the gate',
  box_wrong: 'Not a face / the wrong region — a detector error, not a matcher error',
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

/** The separation gate the labels exist to decide (ticket 005). */
const GATE = { trueMatchMean: 0.45, worstImpostor: 0.2 } as const;
/** Below this many labelled tracks neither number means anything, so neither is coloured. */
const MIN_LABELS_FOR_GATE = 10;
const MIN_TRUE_MATCHES_FOR_MEAN = 5;
const MIN_IMPOSTORS_FOR_WORST = 3;

const VERDICT_PILL: Record<Verdict, string> = {
  contestant: 'bg-carbon/20 text-carbon border-carbon/50',
  not_a_contestant: 'bg-paper-deep/60 text-carbon border-carbon',
  unsure: 'bg-stamp/20 text-stamp border-stamp/50',
  box_wrong: 'bg-stamp/20 text-stamp border-stamp/50',
};

const FIELD =
  'bg-paper-dark border border-paper-deep text-carbon-deep text-xs rounded-none px-2 py-1.5 focus:ring-stamp focus:outline-none';

/** Stable, track-ordered output so a save only rewrites what actually changed. */
function serializeLabels(labels: Record<string, Label>): Label[] {
  return Object.values(labels).sort((a, b) => a.tracker_id - b.tracker_id);
}

/** The model's plurality claim for a track, in the same shape the cards use. */
function claimText(track: Track, contestantsById: Record<string, Contestant>): string {
  if (!track.claim) return 'unmatched';
  const contestant = contestantsById[track.claim.contestant_id];
  if (contestant) return `#${contestant.id} ${contestant.nickname}`;
  return `#${track.claim.contestant_id}${track.claim.nickname ? ` ${track.claim.nickname}` : ''}`;
}

/** Every named identity the track's frames voted for, with counts. */
function voteBreakdown(track: Track, contestantsById: Record<string, Contestant>): string {
  if (track.votes.length === 0) return 'no named frames';
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
  if (!res.ok) throw new Error(`Failed to load metadata: HTTP ${res.status}`);
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
  if (!Array.isArray(frames)) return 'it carries no `frame_data` array';
  const stale = frames.find((frame) => !Array.isArray(frame.detections));
  if (!stale) return null;
  const fields = Object.keys(stale).filter(
    (field) => field !== 'frame_number' && field !== 'timestamp',
  );
  return `frame ${stale.frame_number} carries ${fields.length > 0 ? fields.join(', ') : 'no fields'} instead of a \`detections\` array`;
}

function BandPill({ band, className = '' }: { band: Band; className?: string }) {
  // One stamp map for the whole product: BAND_STAMP carries the word and its ink.
  const stamp = BAND_STAMP[band];
  return (
    <span
      className={`inline-block -rotate-2 border px-1.5 py-0.5 font-kai text-[10px] tracking-[0.1em] ${stamp.ink} ${className}`}
    >
      {stamp.word}
    </span>
  );
}

// ---------------------------------------------------------------------------
// The contestant picker: search by number / nickname / name, Enter takes the
// first match, Escape closes the sheet.
// ---------------------------------------------------------------------------

function ContestantPicker({
  contestants,
  onPick,
}: {
  contestants: Contestant[];
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
    <div>
      <input
        autoFocus
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            e.preventDefault();
            const first = hits[0];
            if (first) onPick(String(first.id));
          }
        }}
        placeholder="Contestant number, nickname or name…"
        className="w-full bg-paper border border-paper-deep text-carbon-deep text-sm rounded-t-lg px-3 py-2 focus:ring-stamp focus:outline-none"
      />
      <div className="max-h-56 overflow-y-auto border border-t-0 border-paper-deep rounded-b-lg">
        {hits.length === 0 ? (
          <p className="px-3 py-2 text-xs text-ledger">No contestant matches “{query}”.</p>
        ) : (
          hits.map((c, i) => (
            <button
              key={c.id}
              type="button"
              onClick={() => onPick(String(c.id))}
              className={`block w-full text-left px-3 py-1.5 text-sm transition-colors ${
                i === 0 ? 'bg-paper-dark text-carbon-deep' : 'text-carbon hover:bg-paper-dark'
              }`}
            >
              <span className="font-mono text-stamp">#{c.id}</span> {c.nickname}
              <span className="text-ledger"> {c.name}</span>
            </button>
          ))
        )}
      </div>
      <p className="mt-1 text-[11px] text-ledger">
        {hits.length} of {contestants.length} contestants · Enter picks the first
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
  const { data: videos = [], isLoading: videosLoading } = useVideos();
  const { data: contestantsRaw = [] } = useContestants();
  // `useContestants` is untyped JSON; `Contestant` is the domain type for it, asserted at this
  // boundary the same way `Flagging.tsx` asserts it. Only id/nickname/name are read, and a
  // non-array reply contributes no contestants rather than throwing through the picker.
  const contestants = Array.isArray(contestantsRaw) ? (contestantsRaw as Contestant[]) : [];

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
  // shares the metadata query's cache, so the chosen video is not fetched twice.
  useEffect(() => {
    if (videos.length === 0 || userPickedRef.current) return;
    let cancelled = false;
    void (async () => {
      const stale: string[] = [];
      for (const video of videos) {
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
  }, [videos, queryClient]);

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
      const res = await fetch(`/admin/api/labels/${encodeURIComponent(videoId ?? '')}`);
      if (res.status === 409) {
        const detail = readErrorDetail(await res.json().catch(() => null));
        return {
          status: 'conflict' as const,
          detail:
            detail ??
            'A labels file exists whose source does not match the current metadata — a reprocess invalidated it.',
        };
      }
      if (!res.ok) throw new Error(`Failed to load labels: HTTP ${res.status}`);
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
  // failure is surfaced and labelling is blocked until it is readable.
  const labelsLoadError = labelsQuery.isError
    ? labelsQuery.error instanceof Error
      ? labelsQuery.error.message
      : 'Failed to load labels'
    : null;

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
    () => ({ processing_date: processingDate ?? 'unknown', detections: detectionsCount }),
    [processingDate, detectionsCount],
  );

  // ---- labels state ------------------------------------------------------

  const [labels, setLabels] = useState<Record<string, Label>>({});
  const [hydratedFor, setHydratedFor] = useState<string | null>(null);
  const [saveState, setSaveState] = useState<SaveState>('idle');
  const [saveError, setSaveError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<Date | null>(null);
  const [savedPath, setSavedPath] = useState<string | null>(null);

  const savedJsonRef = useRef<string | null>(null);
  const saveSeqRef = useRef(0);

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
    savedJsonRef.current = JSON.stringify(serializeLabels(next));
    setHydratedFor(videoId);
    setSaveState('idle');
    setSaveError(null);
    setSavedAt(file.labelled_at ? new Date(file.labelled_at) : null);
  }, [videoId, file, hydratedFor]);

  const labelsJson = useMemo(() => JSON.stringify(serializeLabels(labels)), [labels]);

  const save = useCallback(
    async (bodyLabelsJson: string) => {
      if (!videoId || !source) return;
      const seq = ++saveSeqRef.current;
      setSaveState('saving');
      setSaveError(null);
      try {
        // Round-trip of this page's own serialization, not external input: the debounce effect
        // hands over the exact JSON it built from the labels map.
        const labelList = JSON.parse(bodyLabelsJson) as Label[];
        const res = await fetch(`/admin/api/labels/${encodeURIComponent(videoId)}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ source, labels: labelList }),
        });
        if (!res.ok) {
          const detail = readErrorDetail(await res.json().catch(() => null));
          if (seq !== saveSeqRef.current) return;
          setSaveState('failed');
          setSaveError(detail ?? `HTTP ${res.status}`);
          return;
        }
        const savedBody: unknown = await res.json().catch(() => null);
        if (seq !== saveSeqRef.current) return;
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
        // Keep the cache equal to disk so remounting the page mid-session shows
        // the verdicts that were just written.
        queryClient.setQueryData<LabelsResult>(['labels', videoId], (): LabelsResult => ({
          status: 'loaded',
          file: {
            schema: 'labels/v2',
            video_id: videoId,
            labelled_at: new Date().toISOString(),
            source,
            labels: labelList,
            legacy_ignored: false,
          },
        }));
      } catch (e) {
        if (seq !== saveSeqRef.current) return;
        setSaveState('failed');
        setSaveError(e instanceof Error ? e.message : String(e));
      }
    },
    [videoId, source, queryClient],
  );

  // Autosave, debounced. Skipped while a stale file blocks labelling and skipped
  // when the payload is byte-identical to what was last saved.
  useEffect(() => {
    if (!videoId || hydratedFor !== videoId || conflict || labelsLoadError || metadataIssue) return;
    if (savedJsonRef.current === labelsJson) return;
    const timer = setTimeout(() => {
      void save(labelsJson);
    }, AUTOSAVE_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [labelsJson, videoId, hydratedFor, conflict, labelsLoadError, metadataIssue, save]);

  // ---- filters -----------------------------------------------------------

  const [query, setQuery] = useState('');
  const [unlabelledOnly, setUnlabelledOnly] = useState(false);
  const [verdictFilter, setVerdictFilter] = useState<'all' | Verdict>('all');
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);

  useEffect(() => {
    setVisibleCount(PAGE_SIZE);
  }, [videoId, query, unlabelledOnly, verdictFilter]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return tracks.filter((track) => {
      const label = labels[track.key];
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
  }, [tracks, labels, query, unlabelledOnly, verdictFilter]);

  // ---- the sheet ---------------------------------------------------------

  const [openKey, setOpenKey] = useState<string | null>(null);
  const openTrack = openKey ? (trackByKey[openKey] ?? null) : null;

  const closeSheet = useCallback(() => {
    setOpenKey(null);
  }, []);

  useEffect(() => {
    if (!openTrack) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeSheet();
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [openTrack, closeSheet]);

  const tileRefs = useRef(new Map<string, HTMLButtonElement | null>());

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
      advanceFrom(next, fromKey);
    },
    [labels, advanceFrom],
  );

  const commitOne = useCallback(
    (track: Track, verdict: Verdict, contestantId?: string) => {
      const label: Label = {
        tracker_id: track.tracker_id,
        verdict,
        ...(verdict === 'contestant' && contestantId ? { contestant_id: contestantId } : {}),
      };
      commit([[track.key, label]], track.key);
    },
    [commit],
  );

  const clearLabel = useCallback(
    (key: string) => {
      if (!labels[key]) return;
      const next = { ...labels };
      delete next[key];
      setLabels(next);
    },
    [labels],
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
    return VERDICT_LABEL[label.verdict].toLowerCase();
  }

  const visible = filtered.slice(0, visibleCount);
  // Labelling is blocked whenever the labels on disk cannot be read (a stale file, or a load
  // failure) or the metadata is not under the current contract. A blocked page never writes.
  const blocked = conflict !== null || labelsLoadError !== null || metadataIssue !== null;
  const labelable = metadataIssue === null;
  const loading = !videoId || metadataQuery.isLoading || labelsQuery.isLoading;

  return (
    <div className="space-y-6 max-w-[1700px] mx-auto">
      {/* Header */}
      <div className="flex flex-wrap justify-between items-start gap-4">
        <div>
          <h1 className="text-2xl font-bold text-carbon-deep">Labelling</h1>
          <p className="text-carbon-soft text-sm mt-1">
            One verdict per track — `tracker_id` links a face across frames, so the ground truth the
            separation gate is computed from is one label per track. Crops come from the processed
            rendition; nothing here rescales a score.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {saveState === 'saving' && (
            <Badge variant="warning" size="md">
              Saving…
            </Badge>
          )}
          {saveState === 'saved' && (
            <Badge variant="success" size="md">
              Saved{savedAt ? ` ${savedAt.toLocaleTimeString()}` : ''}
            </Badge>
          )}
          {saveState === 'failed' && (
            <>
              <Badge variant="error" size="md">
                Save failed
              </Badge>
              <Button variant="secondary" size="sm" onClick={() => void save(labelsJson)}>
                Retry
              </Button>
            </>
          )}
          {saveState === 'idle' && savedAt && (
            <Badge variant="neutral" size="md">
              On disk · {savedAt.toLocaleString()}
            </Badge>
          )}
        </div>
      </div>

      {saveError && (
        <div className="border border-stamp/50 bg-stamp/10/40 text-stamp text-sm rounded-none px-4 py-2">
          Save failed: {saveError}
        </div>
      )}

      {legacyIgnored && (
        <div className="border border-stamp/50 bg-stamp/10/40 rounded-none px-4 py-3 space-y-2">
          <p className="text-stamp text-sm font-semibold">
            An older <span className="font-mono">labels/v1</span> file was found and ignored — it
            labels individual detections, not tracks.
          </p>
          {file?.legacy_detail && <p className="text-stamp/80 text-xs">{file.legacy_detail}</p>}
          <p className="text-stamp/70 text-xs">
            The old file has been left untouched. The first verdict you save writes a new{' '}
            <span className="font-mono">labels/v2</span> file for this video, replacing the
            per-detection verdicts.
          </p>
        </div>
      )}

      {conflict !== null && (
        <div className="border border-stamp/50 bg-stamp/10/40 rounded-none px-4 py-3 space-y-2">
          <p className="text-stamp text-sm font-semibold">
            Labels on disk describe a different processing run — labelling is blocked, nothing is
            written, and nothing is started over.
          </p>
          <p className="text-stamp/80 text-xs">{conflict}</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs font-mono text-carbon">
            <div className="bg-paper-light/70 border border-paper-dark rounded p-2">
              <div className="text-ledger mb-1">Current metadata run</div>
              <div>processing_date {currentRun.processing_date}</div>
              <div>detections {currentRun.detections}</div>
            </div>
            <div className="bg-paper-light/70 border border-paper-dark rounded p-2">
              <div className="text-ledger mb-1">Labels file</div>
              <div className="break-all">local_output/labels/{videoId}_labels.json</div>
              <div className="text-ledger">
                {file?.source ? (
                  <span>
                    processing_date {file.source.processing_date} · detections{' '}
                    {file.source.detections}
                  </span>
                ) : (
                  <span>
                    pins the run quoted in the message above; the 409 carries no other copy of it
                  </span>
                )}
              </div>
            </div>
          </div>
          <p className="text-stamp/70 text-xs">
            Reprocess the video, or remove{' '}
            <span className="font-mono">local_output/labels/{videoId}_labels.json</span> to label
            this run from scratch. Existing verdicts are left untouched.
          </p>
        </div>
      )}

      {labelsLoadError !== null && (
        <div className="border border-stamp/50 bg-stamp/10/40 rounded-none px-4 py-3 space-y-2">
          <p className="text-stamp text-sm font-semibold">
            The labels file could not be read — labelling is blocked, so a save cannot replace
            verdicts that are already on disk.
          </p>
          <p className="text-stamp/80 text-xs font-mono">{labelsLoadError}</p>
          <Button variant="secondary" size="sm" onClick={() => void labelsQuery.refetch()}>
            Retry
          </Button>
        </div>
      )}

      {/* Controls */}
      <div className="flex flex-wrap items-center gap-4 bg-paper-light border border-paper-dark p-4 rounded-none">
        <div className="flex items-center gap-2">
          <label className="text-xs text-carbon-soft whitespace-nowrap">Video:</label>
          <select
            value={videoId ?? ''}
            onChange={(e) => {
              // An explicit choice wins over the auto-probe for the rest of the session.
              userPickedRef.current = true;
              setVideoId(e.target.value || null);
              setHydratedFor(null);
              savedJsonRef.current = null;
              closeSheet();
            }}
            className={FIELD}
          >
            {videos.length === 0 && (
              <option value="">{videosLoading ? 'Loading…' : 'No processed videos'}</option>
            )}
            {videos.map((v) => (
              <option key={v.id} value={v.id}>
                {v.name}
                {staleVideoIds.has(v.id) ? ' — metadata predates the box contract' : ''}
              </option>
            ))}
          </select>
        </div>

        {labelable && (
          <>
            <div className="flex items-center gap-2">
              <label className="text-xs text-carbon-soft whitespace-nowrap">Claimed:</label>
              <input
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="track, name or number…"
                className={`${FIELD} min-w-[200px]`}
              />
            </div>

            <div className="flex items-center gap-2">
              <label className="text-xs text-carbon-soft whitespace-nowrap">Verdict:</label>
              <select
                value={verdictFilter}
                onChange={(e) => setVerdictFilter(e.target.value as 'all' | Verdict)}
                className={FIELD}
              >
                <option value="all">All verdicts</option>
                {VERDICTS.map((v) => (
                  <option key={v} value={v}>
                    {VERDICT_LABEL[v]}
                  </option>
                ))}
              </select>
            </div>

            <label className="flex items-center gap-2 text-xs text-carbon-soft cursor-pointer">
              <input
                type="checkbox"
                checked={unlabelledOnly}
                onChange={(e) => setUnlabelledOnly(e.target.checked)}
                className="w-4 h-4 cursor-pointer accent-stamp"
              />
              Unlabelled only
            </label>
          </>
        )}

        {labelable && (
          <>
            <div className="flex items-center gap-3 ml-auto">
              <span className="text-xs text-carbon whitespace-nowrap">
                {rail.labelled} of {tracks.length} tracks labelled
              </span>
              <span className="w-32 h-1.5 bg-paper-dark rounded overflow-hidden">
                <span className="block h-full bg-stamp" style={{ width: `${progressPct}%` }} />
              </span>
            </div>

            <Badge variant="neutral" size="md">
              {filtered.length} in view
            </Badge>
          </>
        )}
      </div>

      {labelable && untrackedCount > 0 && (
        <p className="border border-paper-deep bg-paper-dark/40 text-carbon-soft text-xs px-4 py-2">
          <span className="font-mono text-carbon-deep">{untrackedCount}</span> detection
          {untrackedCount === 1 ? '' : 's'} skipped as untracked (
          <span className="font-mono">tracker_id &lt; 0</span>): there is no track to attach a
          verdict to.
        </p>
      )}

      {!labelable ? (
        <Card padding="lg">
          <div className="text-center py-8 space-y-3 max-w-3xl mx-auto">
            <h2 className="text-lg font-semibold text-carbon-deep">
              This video's metadata predates the current box/score contract
            </h2>
            <p className="text-carbon-soft text-sm">
              There is nothing here to label: {metadataIssue}. The labeller judges{' '}
              <span className="font-mono">frame_data[].detections</span> — frame-fraction boxes with
              raw cosines — and this file was written before that contract existed, so its boxes are
              in a different space and its scores are not comparable.
            </p>
            <p className="text-carbon-soft text-sm">
              Reprocess the video, then reload this page. Metadata is never migrated in place, and
              no labels are written for it.
            </p>
            {videos.length > 1 && (
              <p className="text-ledger text-sm">
                Videos marked “metadata predates the box contract” in the picker above need the same
                reprocess.
              </p>
            )}
          </div>
        </Card>
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_360px] gap-6 items-start">
          {/* Grid */}
          <div>
            {loading ? (
              <div className="flex flex-col items-center justify-center py-16 text-carbon-soft">
                <div className="w-10 h-10 border-3 border-paper-deep border-t-stamp rounded-full animate-spin mb-4" />
                <p>Loading tracks…</p>
              </div>
            ) : metadataQuery.error ? (
              <Card padding="lg">
                <div className="text-center py-8">
                  <p className="text-stamp mb-4">Failed to load video metadata</p>
                  <Button variant="secondary" size="sm" onClick={() => metadataQuery.refetch()}>
                    Retry
                  </Button>
                </div>
              </Card>
            ) : filtered.length === 0 ? (
              <Card padding="lg">
                <div className="text-center py-8 text-carbon-soft">
                  <p className="text-carbon mb-1">No tracks match the current filters</p>
                  <p className="text-sm">
                    {tracks.length === 0
                      ? 'This video has no tracked detections in its metadata.'
                      : 'Clear the filter or the unlabelled-only toggle.'}
                  </p>
                </div>
              </Card>
            ) : (
              <>
                <div className="grid grid-cols-[repeat(auto-fill,minmax(150px,1fr))] gap-2.5">
                  {visible.map((track) => {
                    const label = labels[track.key];
                    const chip = chipText(track.key);
                    const claim = claimText(track, contestantsById);
                    const votes = voteBreakdown(track, contestantsById);
                    const topVote = track.votes[0];
                    return (
                      <button
                        key={track.key}
                        ref={(el) => {
                          tileRefs.current.set(track.key, el);
                        }}
                        type="button"
                        disabled={blocked}
                        onClick={() => {
                          setOpenKey(track.key);
                        }}
                        onKeyDown={(e) => {
                          if (e.key === 'Backspace' || e.key === 'Delete') {
                            e.preventDefault();
                            clearLabel(track.key);
                          }
                        }}
                        title={`Track ${track.tracker_id} · ${track.frame_count} frame${track.frame_count === 1 ? '' : 's'} · matcher claim: ${votes} — click to label, Backspace to clear`}
                        className={`relative bg-paper-light border rounded-none p-2 text-left transition-colors ${
                          label ? 'border-carbon/50' : 'border-paper-dark'
                        } ${blocked ? 'opacity-50 cursor-not-allowed' : 'hover:border-carbon cursor-pointer'}`}
                      >
                        <FaceCrop
                          videoId={videoId ?? ''}
                          frameNumber={track.representative.frame_number}
                          detectionIndex={track.representative.detection_index}
                          timestamp={track.representative.timestamp}
                          bbox={track.representative.bbox}
                          streamUrl={streamUrl}
                          width={160}
                          className="w-full aspect-square object-cover rounded bg-black"
                        />
                        <div className="mt-1.5 flex items-center justify-between gap-1">
                          <span className="text-[10.5px] text-ledger font-mono">
                            track {track.tracker_id} · {track.frame_count}f
                          </span>
                          <BandPill band={bandFor(track.representative.match_score)} />
                        </div>
                        <div
                          className={`text-[11px] truncate ${track.claim ? 'text-carbon' : 'text-ledger'}`}
                          title={track.claim?.name ?? undefined}
                        >
                          {claim}
                        </div>
                        <div className="text-[10px] text-ledger truncate" title={votes}>
                          {topVote
                            ? `votes ${topVote.count}/${track.frame_count}${
                                track.votes.length > 1 ? ` · +${track.votes.length - 1}` : ''
                              }`
                            : 'no named frames'}
                        </div>
                        {label && chip && (
                          <span
                            className={`absolute top-1 right-1 max-w-[calc(100%-0.5rem)] truncate rounded-full border px-1.5 py-0.5 text-[9.5px] font-medium ${VERDICT_PILL[label.verdict]}`}
                          >
                            {chip}
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
                {visibleCount < filtered.length && (
                  <div className="flex justify-center mt-4">
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => setVisibleCount((n) => n + PAGE_SIZE)}
                    >
                      Show {Math.min(PAGE_SIZE, filtered.length - visibleCount)} more (
                      {filtered.length - visibleCount} remaining)
                    </Button>
                  </div>
                )}
              </>
            )}
          </div>

          {/* Rail */}
          <div className="space-y-4 xl:sticky xl:top-4">
            <Card padding="md">
              <h2 className="text-sm font-semibold text-carbon-deep mb-3">Verdicts</h2>
              <div className="space-y-1.5">
                {VERDICTS.map((v) => (
                  <div key={v} className="flex items-center justify-between text-xs">
                    <span className="text-carbon-soft">{VERDICT_LABEL[v]}</span>
                    <span className="text-carbon-deep font-mono">{rail.counts[v]}</span>
                  </div>
                ))}
                <div className="flex items-center justify-between text-xs border-t border-paper-dark pt-1.5">
                  <span className="text-carbon-soft">Unlabelled tracks</span>
                  <span className="text-carbon-deep font-mono">
                    {tracks.length - rail.labelled}
                  </span>
                </div>
              </div>
            </Card>

            <Card padding="md">
              <h2 className="text-sm font-semibold text-carbon-deep mb-1">
                The gate these labels unlock
              </h2>
              <p className="text-[11px] text-ledger mb-3">
                Computed over the {rail.labelled} labelled tracks only, with one cosine per track
                (its representative detection's match_score). Gate = mean true-match cosine ≥{' '}
                {GATE.trueMatchMean} and worst impostor cosine ≤ {GATE.worstImpostor}.
              </p>
              {!gateReady && (
                <p className="text-xs text-stamp mb-3">
                  Not enough labelled yet ({rail.labelled} of {MIN_LABELS_FOR_GATE} minimum) — the
                  counts below are counts, not a verdict.
                </p>
              )}
              <div className="space-y-1.5 text-xs">
                <div className="flex items-center justify-between">
                  <span className="text-carbon-soft">True matches labelled</span>
                  <span className="text-carbon-deep font-mono">{rail.trueMatches}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-carbon-soft">…their cosine mean</span>
                  {meanReady && rail.trueMatchMean !== null ? (
                    <span
                      className={`font-mono ${
                        gateReady
                          ? rail.trueMatchMean >= GATE.trueMatchMean
                            ? 'text-carbon'
                            : 'text-stamp'
                          : 'text-carbon-deep'
                      }`}
                    >
                      {rail.trueMatchMean.toFixed(3)}
                      <span className="text-ledger">
                        {' '}
                        {rail.trueMatchMean >= GATE.trueMatchMean ? '≥' : '<'} {GATE.trueMatchMean}
                      </span>
                    </span>
                  ) : (
                    <span className="text-ledger">not enough labelled yet</span>
                  )}
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-carbon-soft">Impostor tracks</span>
                  <span className="text-carbon-deep font-mono">{rail.impostors}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-carbon-soft">…worst impostor cosine</span>
                  {impostorReady && rail.worstImpostor !== null ? (
                    <span
                      className={`font-mono ${
                        gateReady
                          ? rail.worstImpostor <= GATE.worstImpostor
                            ? 'text-carbon'
                            : 'text-stamp'
                          : 'text-carbon-deep'
                      }`}
                    >
                      {rail.worstImpostor.toFixed(3)}
                      <span className="text-ledger">
                        {' '}
                        {rail.worstImpostor <= GATE.worstImpostor ? '≤' : '>'} {GATE.worstImpostor}
                      </span>
                    </span>
                  ) : (
                    <span className="text-ledger">not enough labelled yet</span>
                  )}
                </div>
                <div className="flex items-center justify-between border-t border-paper-dark pt-1.5">
                  <span className="text-carbon-soft">Matcher missed (left unnamed)</span>
                  <span className="text-carbon-deep font-mono">{rail.missed}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-carbon-soft">Matcher misnamed (someone else)</span>
                  <span className="text-carbon-deep font-mono">{rail.misnamed}</span>
                </div>
              </div>
            </Card>

            <Card padding="md">
              <h2 className="text-sm font-semibold text-carbon-deep mb-3">Labels file</h2>
              <div className="space-y-1.5 text-xs text-carbon-soft">
                <div className="flex justify-between gap-3">
                  <span>schema</span>
                  <span className="font-mono text-carbon-deep">{file?.schema ?? 'labels/v2'}</span>
                </div>
                <div className="flex justify-between gap-3">
                  <span>tracks labelled</span>
                  <span className="font-mono text-carbon-deep">{rail.labelled}</span>
                </div>
                <div className="flex justify-between gap-3">
                  <span>labelled_at</span>
                  <span className="font-mono text-carbon-deep">
                    {savedAt ? savedAt.toLocaleString() : '—'}
                  </span>
                </div>
                <div className="flex justify-between gap-3">
                  <span>source</span>
                  <span className="font-mono text-carbon-deep text-right">
                    {source ? `${source.processing_date} · ${source.detections}` : 'unknown run'}
                  </span>
                </div>
                {savedPath && (
                  <p className="font-mono text-[10.5px] text-ledger break-all">{savedPath}</p>
                )}
              </div>
            </Card>
          </div>
        </div>
      )}

      {/* The sheet */}
      {openTrack && !blocked && (
        <div
          className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4"
          onClick={closeSheet}
        >
          <div
            className="bg-paper-light border border-paper-deep rounded-none w-full max-w-xl max-h-[92vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex justify-between items-center p-4 border-b border-paper-dark">
              <div>
                <h3 className="text-lg font-semibold text-carbon-deep">Label this track</h3>
                <p className="text-xs text-ledger">
                  track {openTrack.tracker_id} · {openTrack.frame_count} frame
                  {openTrack.frame_count === 1 ? '' : 's'} · tile{' '}
                  {filtered.findIndex((t) => t.key === openKey) + 1} of {filtered.length} in view
                </p>
              </div>
              <button
                onClick={closeSheet}
                className="text-ledger hover:text-carbon text-xl"
                aria-label="Close"
              >
                &times;
              </button>
            </div>

            <div className="p-4 space-y-4">
              <div className="flex flex-col sm:flex-row gap-4">
                <FaceCrop
                  videoId={videoId ?? ''}
                  frameNumber={openTrack.representative.frame_number}
                  detectionIndex={openTrack.representative.detection_index}
                  timestamp={openTrack.representative.timestamp}
                  bbox={openTrack.representative.bbox}
                  streamUrl={streamUrl}
                  width={320}
                  className="w-full sm:w-[200px] shrink-0 aspect-square object-cover rounded bg-black"
                />
                <div className="space-y-1.5 text-xs text-carbon-soft">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-carbon-deep">
                      frame {openTrack.representative.frame_number} · det{' '}
                      {openTrack.representative.detection_index}
                    </span>
                    <BandPill band={bandFor(openTrack.representative.match_score)} />
                  </div>
                  <div className="font-mono">
                    det_score{' '}
                    {typeof openTrack.representative.det_score === 'number'
                      ? openTrack.representative.det_score.toFixed(3)
                      : 'not recorded'}
                  </div>
                  <div className="font-mono">
                    match cos{' '}
                    {openTrack.representative.match_score === null ? (
                      <span className="text-ledger">none</span>
                    ) : (
                      openTrack.representative.match_score.toFixed(3)
                    )}
                  </div>
                  <div>
                    Track: {openTrack.frame_count} frame
                    {openTrack.frame_count === 1 ? '' : 's'} ·{' '}
                    {openTrack.votes.length > 0
                      ? `${openTrack.votes.length} claimed identit${openTrack.votes.length === 1 ? 'y' : 'ies'}`
                      : 'no claimed identity'}
                  </div>
                  <div className="pt-1">
                    Matcher says:{' '}
                    {openTrack.claim ? (
                      <span className="text-carbon-deep">
                        {openTrack.claim.nickname ?? '—'} (#
                        {openTrack.claim.contestant_id}
                        {openTrack.claim.name ? ` ${openTrack.claim.name}` : ''}) —{' '}
                        {openTrack.claim.count}/{openTrack.frame_count} frames
                      </span>
                    ) : (
                      <span className="text-ledger">nobody</span>
                    )}
                  </div>
                  <div className="font-mono text-[10.5px] text-ledger break-words">
                    votes: {voteBreakdown(openTrack, contestantsById)}
                  </div>
                  {labels[openTrack.key] && (
                    <div className="flex items-center gap-2 pt-1">
                      <span className="text-ledger">Labelled:</span>
                      <span
                        className={`rounded-full border px-1.5 py-0.5 text-[10px] font-medium ${
                          VERDICT_PILL[labels[openTrack.key].verdict]
                        }`}
                      >
                        {labels[openTrack.key].verdict === 'contestant'
                          ? chipText(openTrack.key)
                          : VERDICT_LABEL[labels[openTrack.key].verdict]}
                      </span>
                      <Button variant="ghost" size="sm" onClick={() => clearLabel(openTrack.key)}>
                        Clear label
                      </Button>
                    </div>
                  )}
                </div>
              </div>

              <>
                <ContestantPicker
                  key={openKey}
                  contestants={contestants}
                  onPick={(contestantId) => commitOne(openTrack, 'contestant', contestantId)}
                />

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                  {(['not_a_contestant', 'unsure', 'box_wrong'] as Verdict[]).map((v) => (
                    <button
                      key={v}
                      type="button"
                      onClick={() => commitOne(openTrack, v)}
                      title={VERDICT_BLURB[v]}
                      className="border border-paper-deep bg-paper-dark hover:border-ledger hover:bg-paper-deep text-carbon-deep rounded-none px-3 py-2 text-xs text-left transition-colors cursor-pointer"
                    >
                      <span className="block font-semibold">{VERDICT_LABEL[v]}</span>
                      <span className="block text-[10.5px] text-carbon-soft">
                        {VERDICT_BLURB[v]}
                      </span>
                    </button>
                  ))}
                </div>

                <p className="text-[11px] text-ledger">
                  Picking a verdict records one label for the whole track and moves to the next
                  unlabelled track. Escape closes this sheet; Backspace or Delete on a card clears
                  its label.
                </p>
              </>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
