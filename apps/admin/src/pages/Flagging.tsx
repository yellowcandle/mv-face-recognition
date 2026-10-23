import { useState, useMemo, useCallback, useEffect, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  BAND_STAMP,
  Masthead,
  adminFetch,
  bandFor,
  formatMmSs,
  useContestants,
  useFlaggedFaces,
  useVideos,
} from '@mv/shared';
import type { Band, FlaggedFace, Contestant, FrameData, VideoMetadata } from '@mv/shared';

/**
 * The pipeline's acceptance threshold, as a cosine. Source: the header of
 * apps/shared/lib/bands.ts ("The pipeline's acceptance threshold (0.45)"); each run also
 * stamps it into `recognition_config.acceptance_threshold`.
 */
const ACCEPTANCE_THRESHOLD = 0.45;

/**
 * DET and the context strip for one flag. The flag record (`GET /api/faces/flagged`) carries
 * neither a det_score nor a frame number — only video_id, timestamp and bbox — so both are
 * recovered from the video's dense metadata (`GET /api/videos/metadata/dense/{id}`):
 * - the floor frame is the last processed frame at or before the flag's timestamp (the same
 *   floor rule `/api/faces/detect` and the player use, which is where the flagged bbox came from);
 * - DET is the det_score of the floor frame's detection whose bbox equals the flag's bbox.
 *   No exact match (or metadata from before detections were stored) → null, never estimated;
 * - the strip is the two processed frames either side of the floor frame. A slot past either end
 *   of the video is null.
 */
function flagContext(meta: VideoMetadata | undefined, face: FlaggedFace) {
  const frames = [...(meta?.frame_data ?? [])].sort((a, b) => a.timestamp - b.timestamp);
  let i = -1;
  while (i + 1 < frames.length && frames[i + 1].timestamp <= face.timestamp) i++;
  const bbox = face.bbox;
  const sameBox = (b: number[] | undefined) =>
    !!bbox && !!b && b.length === 4 && b.every((v, j) => Math.abs(v - bbox[j]) < 1e-6);
  const det =
    i >= 0 ? (frames[i].detections?.find((d) => sameBox(d.bbox))?.det_score ?? null) : null;
  const strip: (FrameData | null)[] = [-2, -1, 0, 1, 2].map((o) =>
    i >= 0 ? (frames[i + o] ?? null) : null,
  );
  return { det, strip };
}

const STATUS_WORD: Record<FlaggedFace['status'], string> = {
  pending: '待核',
  accepted: '已核對',
  rejected: '作廢',
};

/**
 * 存根 / 待核 — the flag queue as a tray of slips. Each row is one flag awaiting a human
 * decision; the right-hand sheet is the one being decided. Every state is a stamp.
 */
export function Flagging() {
  const queryClient = useQueryClient();
  const { data: flaggedFaces = [], isLoading, error } = useFlaggedFaces();
  const { data: contestants = [] } = useContestants();

  const [statusFilter, setStatusFilter] = useState<'all' | FlaggedFace['status']>('pending');
  const [videoFilter, setVideoFilter] = useState('');
  const [bandFilter, setBandFilter] = useState<'all' | Band>('all');
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [focusedId, setFocusedId] = useState<string | null>(null);
  const [reassignTo, setReassignTo] = useState<string>('');
  const [busy, setBusy] = useState(false);

  const uniqueVideos = useMemo(
    () => [...new Set(flaggedFaces.map((f) => f.video_id))],
    [flaggedFaces],
  );

  const filtered = useMemo(
    () =>
      flaggedFaces.filter((f) => {
        if (statusFilter !== 'all' && f.status !== statusFilter) return false;
        if (videoFilter && f.video_id !== videoFilter) return false;
        if (bandFilter !== 'all' && bandFor(f.confidence ?? 0) !== bandFilter) return false;
        return true;
      }),
    [flaggedFaces, statusFilter, videoFilter, bandFilter],
  );

  const focused = useMemo(
    () => filtered.find((f) => f.id === focusedId) ?? filtered[0] ?? null,
    [filtered, focusedId],
  );

  // Reset the reassign picker only when the focused slip (or its filing) changes. Depending on
  // reassignTo here would snap every pick straight back, making 改派 impossible.
  const focusedKey = focused ? `${focused.id}:${focused.contestant_id}` : '';
  useEffect(() => {
    if (focused) setReassignTo(String(focused.contestant_id));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusedKey]);

  const { data: videos = [] } = useVideos();
  // Same key and endpoint as Labelling, so the two pages share one cached copy.
  const { data: denseMetadata } = useQuery<VideoMetadata>({
    queryKey: ['dense-metadata', focused?.video_id],
    enabled: !!focused,
    queryFn: async () => {
      const res = await fetch(
        `/api/videos/metadata/dense/${encodeURIComponent(focused?.video_id ?? '')}`,
      );
      if (!res.ok) throw new Error(`Failed to load metadata: HTTP ${res.status}`);
      return (await res.json()) as VideoMetadata;
    },
    staleTime: 5 * 60 * 1000,
  });
  const context = useMemo(
    () => (focused ? flagContext(denseMetadata, focused) : { det: null, strip: [] }),
    [denseMetadata, focused],
  );
  const streamUrl = videos.find((v) => v.id === focused?.video_id)?.stream_url;

  const reassignRef = useRef<HTMLSelectElement>(null);
  const trayRef = useRef<HTMLDivElement>(null);

  function goNext() {
    if (!focused) return;
    const next = filtered[filtered.findIndex((f) => f.id === focused.id) + 1];
    if (next) setFocusedId(next.id);
  }

  async function decideFocused(status: 'accepted' | 'rejected') {
    if (!focused || focused.status !== 'pending') return;
    const i = filtered.findIndex((f) => f.id === focused.id);
    const next = filtered.slice(i + 1).find((f) => f.status === 'pending');
    await updateFaceStatus(focused.id, status);
    if (next) setFocusedId(next.id);
  }

  // Keyboard: 1 蓋印 / 2 作廢 / 3 改派 / ↓ 下一張. Silent while typing in a field or while any
  // modal is open (FlagDialog renders role="dialog" aria-modal="true"). Re-bound each render so
  // the handler always sees the current slip; removed on unmount.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.metaKey || e.ctrlKey || e.altKey || e.repeat) return;
      const target = e.target as HTMLElement | null;
      if (
        target?.closest?.(
          'input, textarea, select, [contenteditable]:not([contenteditable="false"])',
        )
      )
        return;
      if (document.querySelector('[role="dialog"], [aria-modal="true"], dialog[open]')) return;
      if (!focused) return;
      if (e.key === '1' || e.key === '2') {
        e.preventDefault();
        void decideFocused(e.key === '1' ? 'accepted' : 'rejected');
      } else if (e.key === '3') {
        e.preventDefault();
        reassignRef.current?.focus();
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        goNext();
      }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  // Keep the focused slip in view as the keyboard walks the tray.
  useEffect(() => {
    if (!focused) return;
    trayRef.current
      ?.querySelector(`[data-slip="${CSS.escape(focused.id)}"]`)
      ?.scrollIntoView({ block: 'nearest' });
  }, [focused?.id]);

  const contestantOf = useCallback(
    (id: number): Contestant | undefined =>
      (contestants as Contestant[]).find((c) => Number(c.id) === id),
    [contestants],
  );

  async function updateFaceStatus(faceId: string, status: 'accepted' | 'rejected') {
    try {
      const res = await adminFetch(`/admin/api/faces/flagged/${faceId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status }),
      });
      if (res.ok) void queryClient.invalidateQueries({ queryKey: ['flaggedFaces'] });
    } catch (e) {
      console.error('Failed to update face status:', e);
    }
  }

  async function bulkUpdateStatus(status: 'accepted' | 'rejected') {
    setBusy(true);
    for (const faceId of selected) await updateFaceStatus(faceId, status);
    setSelected(new Set());
    setBusy(false);
  }

  async function reassignFace() {
    if (!focused || !reassignTo) return;
    try {
      const res = await adminFetch('/admin/api/faces/flag/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ face_id: focused.id, contestant_id: Number(reassignTo) }),
      });
      if (res.ok) void queryClient.invalidateQueries({ queryKey: ['flaggedFaces'] });
    } catch (e) {
      console.error('Failed to reassign face:', e);
    }
  }

  function toggleSelection(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  const pendingCount = flaggedFaces.filter((f) => f.status === 'pending').length;
  const acceptedCount = flaggedFaces.filter((f) => f.status === 'accepted').length;
  const rejectedCount = flaggedFaces.filter((f) => f.status === 'rejected').length;

  const focusedContestant = focused ? contestantOf(focused.contestant_id) : undefined;
  const focusedBand = focused ? bandFor(focused.confidence ?? 0) : null;

  return (
    <div className="flex min-h-0 flex-1 flex-col px-9 pb-6 pt-7">
      <Masthead
        eyebrow="BACK OFFICE · LOCAL ONLY · 127.0.0.1"
        title="待核"
        latin="OFFICE COPY · WRITABLE"
        size="md"
      >
        <button
          type="button"
          onClick={() => void queryClient.invalidateQueries({ queryKey: ['flaggedFaces'] })}
          className="border border-carbon/45 px-3 py-1.5 font-kai text-[12px] tracking-[0.12em] text-carbon hover:border-stamp hover:text-stamp"
        >
          重新調閱
        </button>
        <div className="-rotate-[6deg] border-2 border-stamp px-3 py-1.5">
          <div className="text-center font-serif text-[14px] font-bold tracking-[0.14em] text-stamp">
            待核 {pendingCount}
          </div>
          <div className="text-center font-mono text-[7px] tracking-[0.16em] text-stamp">
            PENDING FLAGS
          </div>
        </div>
      </Masthead>

      <div className="mt-4 h-px bg-carbon/45" />

      {/* Counters */}
      <div className="flex flex-row items-end gap-9 py-3">
        {[
          ['待核', pendingCount, 'text-carbon'],
          ['已核對', acceptedCount, 'text-carbon'],
          ['作廢', rejectedCount, 'text-stamp'],
          ['全部', flaggedFaces.length, 'text-carbon'],
        ].map(([label, value, ink]) => (
          <div key={String(label)} className="flex flex-col gap-1">
            <span className="font-mono text-[8px] tracking-[0.2em] text-ledger">{label}</span>
            <span className={`font-mono text-[22px] leading-none ${ink}`}>{value}</span>
          </div>
        ))}
        {selected.size > 0 && (
          <div className="flex flex-row items-center gap-2 pb-1">
            <span className="font-kai text-[12px] text-carbon-soft">已選 {selected.size}</span>
            <button
              type="button"
              disabled={busy}
              onClick={() => bulkUpdateStatus('accepted')}
              className="border border-carbon px-2.5 py-1 font-kai text-[11px] text-carbon hover:bg-carbon hover:text-paper-light"
            >
              全部蓋印
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => bulkUpdateStatus('rejected')}
              className="border border-stamp px-2.5 py-1 font-kai text-[11px] text-stamp hover:bg-stamp hover:text-paper-light"
            >
              全部作廢
            </button>
            <button
              type="button"
              onClick={() => setSelected(new Set())}
              className="px-2 py-1 font-kai text-[11px] text-carbon-soft"
            >
              取消
            </button>
          </div>
        )}
      </div>

      <div className="h-px bg-carbon/20" />

      <div className="flex min-h-0 flex-1 flex-row">
        {/* Tray */}
        <div className="flex min-w-0 flex-1 flex-col pt-3 pr-1">
          <div className="flex flex-row items-baseline justify-between pb-2">
            <div className="flex flex-row items-baseline gap-2.5">
              <span className="font-kai text-[15px] font-bold text-carbon">待核</span>
              <span className="font-mono text-[9px] tracking-[0.18em] text-ledger">
                {filtered.length} SLIPS
              </span>
            </div>
            <div className="flex flex-row items-center gap-2.5">
              <Filter
                value={statusFilter}
                onChange={(v) => setStatusFilter(v as typeof statusFilter)}
                options={[
                  ['pending', '待核'],
                  ['accepted', '已核對'],
                  ['rejected', '作廢'],
                  ['all', '全部'],
                ]}
              />
              <Filter
                value={bandFilter}
                onChange={(v) => setBandFilter(v as typeof bandFilter)}
                options={[
                  ['all', '全部分級'],
                  ['high', '清楚'],
                  ['medium', '尚可'],
                  ['low', '存疑'],
                ]}
              />
              <Filter
                value={videoFilter}
                onChange={setVideoFilter}
                options={[['', '全部影片'], ...uniqueVideos.map((v) => [v, v] as [string, string])]}
              />
            </div>
          </div>

          {isLoading ? (
            <div className="py-16 text-center font-kai text-[13px] text-carbon-soft">正在調閱…</div>
          ) : error ? (
            <div className="mt-2 border border-stamp/40 bg-stamp/5 px-4 py-10 text-center font-kai text-[13px] text-stamp">
              讀不到待核紀錄 — 後台 API 未啟動？
            </div>
          ) : filtered.length === 0 ? (
            <div className="mt-2 border border-dashed border-carbon/35 px-4 py-14 text-center">
              <div className="font-kai text-[15px] font-bold text-carbon-deep">這一疊是空的</div>
              <div className="mt-1 font-kai text-[12px] text-carbon-soft">
                沒有符合目前條件的待核紀錄。
              </div>
            </div>
          ) : (
            <div ref={trayRef} className="flex flex-col gap-1.5 overflow-y-auto pb-2">
              {filtered.slice(0, 200).map((face) => {
                const band = bandFor(face.confidence ?? 0);
                const isFocused = focused?.id === face.id;
                return (
                  <div
                    key={face.id}
                    data-slip={face.id}
                    onClick={() => setFocusedId(face.id)}
                    className={`flex cursor-pointer flex-row items-center gap-3 border py-2 pl-3 pr-2 ${
                      isFocused
                        ? 'border-carbon/55 border-l-[3px] border-l-stamp bg-paper-light'
                        : 'border-carbon/15 border-l-[3px] border-l-carbon/20'
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={selected.has(face.id)}
                      onChange={() => toggleSelection(face.id)}
                      onClick={(e) => e.stopPropagation()}
                      className="h-3.5 w-3.5 shrink-0 cursor-pointer accent-stamp"
                      aria-label={`選取 ${face.id}`}
                    />
                    <div className="h-[46px] w-[38px] shrink-0 overflow-hidden border border-carbon/40 bg-[#191922]">
                      {face.thumbnail && (
                        <img src={face.thumbnail} alt="" className="h-full w-full object-cover" />
                      )}
                    </div>
                    <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                      <span className="font-mono text-[11px] text-carbon-soft">
                        {formatMmSs(face.timestamp)}
                      </span>
                      <span className="truncate font-mono text-[8px] tracking-[0.1em] text-ledger">
                        {face.video_id}
                      </span>
                    </div>
                    <div className="flex w-[96px] shrink-0 flex-col gap-0.5">
                      <span className="truncate font-kai text-[15px] font-bold leading-tight text-carbon-deep">
                        {contestantOf(face.contestant_id)?.nickname ?? `#${face.contestant_id}`}
                      </span>
                      <span className="font-mono text-[8px] tracking-[0.12em] text-carbon-soft">
                        #{face.contestant_id}
                      </span>
                    </div>
                    <div className="flex w-[54px] shrink-0 justify-center">
                      <span
                        className={`-rotate-2 border px-1.5 py-0.5 font-kai text-[10px] tracking-[0.1em] ${BAND_STAMP[band].ink}`}
                      >
                        {BAND_STAMP[band].word}
                      </span>
                    </div>
                    <span
                      title="被標記偵測的配對分數（標記本身不帶分數）"
                      className="w-[36px] shrink-0 font-mono text-[11px] text-carbon-soft"
                    >
                      {face.confidence == null ? '—' : face.confidence.toFixed(2)}
                    </span>
                    <span className="flex-1" />
                    {face.status === 'pending' ? (
                      <div className="flex flex-row gap-1.5">
                        <MiniStamp
                          label="蓋印"
                          tone="carbon"
                          onClick={(e) => {
                            e.stopPropagation();
                            void updateFaceStatus(face.id, 'accepted');
                          }}
                        />
                        <MiniStamp
                          label="作廢"
                          tone="stamp"
                          onClick={(e) => {
                            e.stopPropagation();
                            void updateFaceStatus(face.id, 'rejected');
                          }}
                        />
                      </div>
                    ) : (
                      <span
                        className={`border px-1.5 py-0.5 font-kai text-[10px] tracking-[0.1em] ${
                          face.status === 'accepted'
                            ? 'border-carbon/50 text-carbon'
                            : 'border-ledger text-ledger'
                        }`}
                      >
                        {STATUS_WORD[face.status]}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Review sheet */}
        <div className="ml-6 flex w-[380px] shrink-0 flex-col border-l border-carbon/25 pl-6 pt-3">
          {focused ? (
            <>
              <div className="flex flex-row items-baseline justify-between">
                <span className="font-mono text-[9px] tracking-[0.2em] text-ledger">
                  SLIP {String(focused.id).slice(-4).toUpperCase()} · REVIEW
                </span>
                <span className="font-mono text-[9px] tracking-[0.1em] text-stamp">
                  {focusedBand ? BAND_STAMP[focusedBand].word : '未配對'}
                  {focused.confidence == null ? '' : ` ${focused.confidence.toFixed(2)}`}
                </span>
              </div>

              <div className="mt-3 flex flex-row gap-5">
                <div className="flex flex-col gap-2">
                  <div className="h-[210px] w-[186px] overflow-hidden border border-carbon bg-[#191922]">
                    {focused.thumbnail ? (
                      <img
                        src={focused.thumbnail}
                        alt="被標記的人臉"
                        className="h-full w-full object-cover"
                      />
                    ) : (
                      <div className="flex h-full w-full items-center justify-center">
                        <span className="font-mono text-[9px] tracking-[0.16em] text-paper/40">
                          NO THUMBNAIL
                        </span>
                      </div>
                    )}
                  </div>
                  <span className="font-mono text-[9px] tracking-[0.14em] text-carbon-soft">
                    DET {context.det == null ? '— 無資料' : context.det.toFixed(2)}
                  </span>
                  <span className="max-w-[186px] truncate font-mono text-[8px] tracking-[0.16em] text-ledger">
                    {focused.video_id} · {formatMmSs(focused.timestamp)}
                  </span>
                </div>

                <div className="flex min-w-0 flex-1 flex-col gap-2">
                  <span className="font-mono text-[8px] tracking-[0.2em] text-ledger">
                    CURRENTLY FILED AS
                  </span>
                  <div className="flex flex-row items-baseline gap-2">
                    <span className="font-kai text-[26px] font-bold leading-none text-carbon-deep">
                      {focusedContestant?.nickname ?? `#${focused.contestant_id}`}
                    </span>
                    <span className="font-mono text-[10px] text-ledger">
                      #{focused.contestant_id}
                    </span>
                  </div>
                  {/* The flag asserts no score of its own (CONTEXT.md, "Flag"). `confidence` is the
                      flagged detection's match score, carried as context for the claim. */}
                  <span className="mt-1 font-mono text-[8px] tracking-[0.2em] text-ledger">
                    DETECTION MATCH SCORE
                  </span>
                  <div className="relative h-[3px] w-full bg-carbon-deep/15">
                    <div
                      className="h-[3px] bg-stamp"
                      style={{
                        width: `${Math.max(0, Math.min(1, focused.confidence ?? 0)) * 100}%`,
                      }}
                    />
                    <div
                      className="absolute -top-[3px] h-[9px] w-px bg-carbon-deep"
                      style={{ left: `${ACCEPTANCE_THRESHOLD * 100}%` }}
                      title={`acceptance threshold ${ACCEPTANCE_THRESHOLD}`}
                    />
                  </div>
                  <div className="flex flex-row justify-between font-mono text-[9px] text-carbon-soft">
                    <span>
                      {focused.confidence == null
                        ? '無配對分數'
                        : `${focused.confidence.toFixed(2)} cosine`}
                    </span>
                    <span className="text-ledger">門檻 {ACCEPTANCE_THRESHOLD.toFixed(2)}</span>
                  </div>
                  <span className="font-kai text-[11px] leading-snug text-carbon-soft">
                    被標記偵測的配對分數，僅供參考；標記本身不帶分數。
                  </span>

                  <div className="mt-1 h-px bg-carbon/20" />

                  {/* Three reference slots. The only reference-image route is
                      GET /api/contestants/{id}/thumb/face (or the published `portrait_url`), which
                      serves the contestant's FIRST photo by filename — not ranked by cosine: no
                      endpoint returns per-reference embeddings or scores for a flag, so "nearest"
                      cannot be computed here. Slot 1 is that real photo; slots 2–3 are marked
                      unavailable rather than filled. `reference_count` (GET /api/contestants) is
                      how many exist on file. */}
                  <span className="font-mono text-[8px] tracking-[0.2em] text-ledger">
                    REFERENCES · {focusedContestant?.reference_count ?? 0} ON FILE
                  </span>
                  <div className="flex flex-row gap-1.5">
                    <div className="h-[54px] w-[46px] overflow-hidden border border-carbon/45 bg-paper-dark">
                      <img
                        src={
                          focusedContestant?.portrait_url ??
                          `/api/contestants/${focused.contestant_id}/thumb/face`
                        }
                        alt={focusedContestant?.name ?? ''}
                        className="h-full w-full object-cover"
                        onError={(e) => {
                          (e.target as HTMLImageElement).style.visibility = 'hidden';
                        }}
                      />
                    </div>
                    {[1, 2].map((k) => (
                      <div
                        key={k}
                        className="flex h-[54px] w-[46px] items-center justify-center border border-dashed border-carbon/35"
                      >
                        <span className="font-kai text-[10px] text-ledger">未提供</span>
                      </div>
                    ))}
                  </div>
                  <span className="font-mono text-[8px] tracking-[0.1em] text-ledger">
                    {focusedContestant?.name ?? '—'} · 編號 {focused.contestant_id} · 未按相似度排序
                  </span>

                  {focused.user_label && (
                    <div className="mt-1 border-l-2 border-stamp/60 pl-2 font-kai text-[12px] text-carbon-soft">
                      {focused.user_label}
                    </div>
                  )}
                </div>
              </div>

              <div className="mt-4 h-px bg-carbon/25" />

              <div className="mt-3 flex flex-col gap-2">
                <span className="font-mono text-[8px] tracking-[0.2em] text-ledger">
                  REASSIGN TO
                </span>
                <div className="flex flex-row items-center gap-2">
                  <select
                    ref={reassignRef}
                    value={reassignTo}
                    onChange={(e) => setReassignTo(e.target.value)}
                    className="min-w-0 flex-1 border border-carbon/45 bg-paper-light px-2.5 py-2 font-kai text-[13px] text-carbon-deep focus:border-stamp focus:outline-none"
                  >
                    {(contestants as Contestant[]).map((c) => (
                      <option key={c.id} value={c.id}>
                        #{c.id} · {c.nickname} ({c.name})
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    onClick={() => void reassignFace()}
                    className="border border-carbon px-3 py-2 font-kai text-[12px] tracking-[0.1em] text-carbon hover:bg-carbon hover:text-paper-light"
                  >
                    改派
                  </button>
                </div>
              </div>

              {/* Context: the two processed frames either side of the flag's floor frame, each a
                  real frame of the served rendition (`stream_url` seeked by a #t media fragment).
                  Slots with no frame — no dense metadata, or past either end — say so. */}
              <div className="mt-4 flex flex-col gap-2">
                <span className="font-mono text-[8px] tracking-[0.2em] text-ledger">
                  CONTEXT · 前後五格
                </span>
                <div className="flex flex-row gap-1">
                  {context.strip.map((frame, k) => (
                    <div
                      key={k}
                      className={`flex aspect-video min-w-0 flex-1 items-center justify-center overflow-hidden border bg-[#191922] ${
                        k === 2 ? 'border-stamp' : 'border-carbon/40'
                      }`}
                    >
                      {frame && streamUrl ? (
                        <video
                          src={`${streamUrl}#t=${frame.timestamp}`}
                          preload="metadata"
                          muted
                          playsInline
                          title={formatMmSs(frame.timestamp)}
                          className="h-full w-full object-cover"
                        />
                      ) : (
                        <span className="font-mono text-[8px] text-paper/40">—</span>
                      )}
                    </div>
                  ))}
                </div>
                {!streamUrl || context.strip.every((f) => f == null) ? (
                  <span className="font-kai text-[11px] text-carbon-soft">
                    此片段無前後影格可調閱。
                  </span>
                ) : null}
              </div>

              <div className="flex-1" />

              <div className="flex flex-row items-stretch gap-2 pb-1">
                <button
                  type="button"
                  disabled={focused.status !== 'pending'}
                  onClick={() => void updateFaceStatus(focused.id, 'accepted')}
                  className="flex min-w-0 flex-1 flex-row items-center justify-between gap-2 bg-stamp px-3 py-3 disabled:opacity-40"
                >
                  <span className="whitespace-nowrap font-kai text-[15px] font-bold tracking-[0.12em] text-paper-light">
                    蓋印確認
                  </span>
                  <span className="whitespace-nowrap font-mono text-[8px] tracking-[0.14em] text-paper-light/75">
                    ACCEPT
                  </span>
                </button>
                <button
                  type="button"
                  disabled={focused.status !== 'pending'}
                  onClick={() => void updateFaceStatus(focused.id, 'rejected')}
                  className="shrink-0 border border-carbon/45 px-3 py-3 disabled:opacity-40"
                >
                  <span className="whitespace-nowrap font-kai text-[13px] tracking-[0.1em] text-carbon-soft">
                    作廢
                  </span>
                </button>
                <button
                  type="button"
                  onClick={goNext}
                  className="shrink-0 border border-carbon/45 px-3 py-3"
                >
                  <span className="whitespace-nowrap font-kai text-[13px] tracking-[0.1em] text-carbon-soft">
                    下一張
                  </span>
                </button>
              </div>

              <div className="flex flex-row flex-wrap gap-x-4 gap-y-1 pt-2 font-mono text-[8px] tracking-[0.08em] text-carbon-soft">
                <span className="whitespace-nowrap">1 蓋印</span>
                <span className="whitespace-nowrap">2 作廢</span>
                <span className="whitespace-nowrap">3 改派</span>
                <span className="whitespace-nowrap">↓ 下一張</span>
              </div>
            </>
          ) : (
            <div className="flex flex-1 items-center justify-center font-kai text-[13px] text-carbon-soft">
              從左邊的托盤挑一張來核對。
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Filter({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (v: string) => void;
  options: [string, string][];
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="max-w-[150px] border border-carbon/35 bg-paper-light px-2 py-1 font-kai text-[11px] text-carbon-deep focus:border-stamp focus:outline-none"
    >
      {options.map(([v, label]) => (
        <option key={v} value={v}>
          {label}
        </option>
      ))}
    </select>
  );
}

function MiniStamp({
  label,
  tone,
  onClick,
}: {
  label: string;
  tone: 'carbon' | 'stamp';
  onClick: (e: React.MouseEvent) => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`border px-2 py-1 font-kai text-[10px] tracking-[0.08em] ${
        tone === 'carbon'
          ? 'border-carbon text-carbon hover:bg-carbon hover:text-paper-light'
          : 'border-stamp/70 text-stamp hover:bg-stamp hover:text-paper-light'
      }`}
    >
      {label}
    </button>
  );
}
