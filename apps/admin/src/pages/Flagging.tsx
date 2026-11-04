import { useState, useMemo, useCallback, useEffect, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  BAND_CUTOFFS,
  AdminErrorNotice,
  BAND_STAMP,
  Button,
  Masthead,
  Stamp,
  adminFetch,
  assertOk,
  bandFor,
  formatMmSs,
  rulerPercent,
  isSessionExpired,
  useContestants,
  useFlaggedFaces,
  useVideos,
  videoShortName,
} from '@mv/shared';
import type { Band, FlaggedFace, Contestant, FrameData, VideoMetadata } from '@mv/shared';

/** The pipeline's acceptance threshold: a score below it is not called a match. */
const ACCEPTANCE_THRESHOLD = BAND_CUTOFFS.medium;

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

const STATUS_TABS: FlaggedFace['status'][] = ['pending', 'accepted', 'rejected'];

/**
 * 待核 — the flag queue beside the sheet being decided: what the system saw against who it was
 * filed as, then a stamp.
 */
export function Flagging() {
  const queryClient = useQueryClient();
  const { data: flaggedFaces = [], isLoading, error, refetch } = useFlaggedFaces();
  const { data: contestants = [] } = useContestants();

  const [statusFilter, setStatusFilter] = useState<'all' | FlaggedFace['status']>('pending');
  const [videoFilter, setVideoFilter] = useState('');
  const [bandFilter, setBandFilter] = useState<'all' | Band>('all');
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [focusedId, setFocusedId] = useState<string | null>(null);
  const [reassignTo, setReassignTo] = useState<string>('');
  const [reassignOpen, setReassignOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  // The last failed write (ApiError with the server's detail, or an expired session) and the last
  // successful stamp word. Both render above the tray so they survive the slip being filtered out.
  const [writeError, setWriteError] = useState<unknown>(null);
  const [notice, setNotice] = useState('');
  // The most recent single decision, the only one 復原 can target. Cleared by any other write
  // (bulk, 改派, undo itself) so the affordance never reverts an older slip by surprise.
  const [lastDecision, setLastDecision] = useState<{
    id: string;
    status: 'accepted' | 'rejected';
  } | null>(null);

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
    setReassignOpen(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusedKey]);

  const { data: videos = [] } = useVideos('', { includeTests: true });
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

  function openReassign() {
    setReassignOpen(true);
    reassignRef.current?.focus();
  }

  // The picker mounts on open, so a first open has to focus it after the render.
  useEffect(() => {
    if (reassignOpen) reassignRef.current?.focus();
  }, [reassignOpen]);
  /**
   * 作廢 is destructive and only the latest single decision can be undone, so it always asks
   * first and says how many slips the press will void. Bulk has no undo — the prompt says so.
   */
  function confirmReject(count: number, bulk = false): boolean {
    if (count === 0) return false;
    return window.confirm(
      bulk
        ? `確定作廢 ${count} 張待核紀錄？批量作廢沒有復原。`
        : `確定作廢 ${count} 張待核紀錄？作廢後可從上方提示復原。`,
    );
  }

  /** Tray/sheet 作廢: confirm, then drive the same single-decision primitive. */
  function rejectOne(faceId: string) {
    if (!confirmReject(1)) return;
    void applyStatus(faceId, 'rejected');
  }

  async function decideFocused(status: 'accepted' | 'rejected') {
    if (!focused || focused.status !== 'pending') return;
    if (status === 'rejected' && !confirmReject(1)) return;
    const i = filtered.findIndex((f) => f.id === focused.id);
    const next = filtered.slice(i + 1).find((f) => f.status === 'pending');
    // A rejected write keeps the slip under the stamps, so 1/2 retries it instead of skipping it.
    if (!(await applyStatus(focused.id, status))) return;
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
        openReassign();
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

  /** One PATCH. A non-2xx throws — ApiError with the server's `.detail`, or SessionExpiredError. */
  async function updateFaceStatus(
    faceId: string,
    status: 'pending' | 'accepted' | 'rejected',
  ): Promise<void> {
    const res = await adminFetch(`/admin/api/faces/flagged/${faceId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    });
    await assertOk(res);
  }

  /**
   * A single decision with its feedback: true only when the write landed, so the caller can hold
   * the slip where it is on failure. The write itself never refreshes — this path refreshes once,
   * and bulk drives the same primitive and refreshes once for the whole run.
   */
  async function applyStatus(faceId: string, status: 'accepted' | 'rejected'): Promise<boolean> {
    setWriteError(null);
    setNotice('');
    setLastDecision(null);
    try {
      await updateFaceStatus(faceId, status);
    } catch (e) {
      setWriteError(e);
      return false;
    }
    const word = status === 'accepted' ? '已核對' : '已作廢';
    setNotice(word);
    setLastDecision({ id: faceId, status });
    void queryClient.invalidateQueries({ queryKey: ['flaggedFaces'] });
    return true;
  }

  /** 復原 the latest single decision: the same PATCH back to 待核. */
  async function undoLastDecision() {
    if (!lastDecision) return;
    const { id } = lastDecision;
    setWriteError(null);
    setNotice('');
    try {
      await updateFaceStatus(id, 'pending');
    } catch (e) {
      setWriteError(e);
      return;
    }
    setLastDecision(null);
    setNotice('已復原 · 待核');
    // Keep the slip under the sheet so it can be decided again.
    setFocusedId(id);
    void queryClient.invalidateQueries({ queryKey: ['flaggedFaces'] });
  }

  /**
   * The same primitive once per selected slip, so a failure is counted, not swallowed: the failed
   * ids stay selected, an expired session stops the run and keeps the untouched ids too, and the
   * queue is invalidated once instead of once per row.
   */
  async function bulkUpdateStatus(status: 'accepted' | 'rejected') {
    if (selected.size === 0) return;
    setBusy(true);
    setWriteError(null);
    setNotice('');
    setLastDecision(null);
    const ids = [...selected];
    const failed = new Set<string>();
    let done = 0;
    let failure: unknown = null;
    try {
      for (let i = 0; i < ids.length; i++) {
        try {
          await updateFaceStatus(ids[i], status);
          done++;
        } catch (e) {
          failed.add(ids[i]);
          failure = e;
          if (isSessionExpired(e)) {
            for (const rest of ids.slice(i + 1)) failed.add(rest);
            break;
          }
        }
      }
    } finally {
      setBusy(false);
      void queryClient.invalidateQueries({ queryKey: ['flaggedFaces'] });
    }
    setSelected(failed);
    setWriteError(failure);
    const word = status === 'accepted' ? '已核對' : '已作廢';
    setNotice(failed.size > 0 ? `${word} ${done} 張 · ${failed.size} 失敗` : `${word} ${done} 張`);
  }

  async function reassignFace() {
    if (!focused || !reassignTo) return;
    // Unchanged picker = no write: the face is already filed there.
    if (reassignTo === String(focused.contestant_id)) return;
    setWriteError(null);
    setNotice('');
    setLastDecision(null);
    try {
      const res = await adminFetch('/admin/api/faces/flag/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ face_id: focused.id, contestant_id: Number(reassignTo) }),
      });
      await assertOk(res);
    } catch (e) {
      setWriteError(e);
      return;
    }
    setReassignOpen(false);
    setNotice(`已改派 · SLIP ${String(focused.id).slice(-4).toUpperCase()}`);
    void queryClient.invalidateQueries({ queryKey: ['flaggedFaces'] });
  }

  function toggleSelection(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  const counts: Record<'all' | FlaggedFace['status'], number> = {
    pending: flaggedFaces.filter((f) => f.status === 'pending').length,
    accepted: flaggedFaces.filter((f) => f.status === 'accepted').length,
    rejected: flaggedFaces.filter((f) => f.status === 'rejected').length,
    all: flaggedFaces.length,
  };

  const focusedContestant = focused ? contestantOf(focused.contestant_id) : undefined;
  const lowEnd = rulerPercent(BAND_CUTOFFS.medium);
  const midWidth = rulerPercent(BAND_CUTOFFS.high) - lowEnd;

  return (
    <div className="flex h-full min-h-0 flex-1 flex-row">
      {/* Tray */}
      <div className="flex w-[392px] shrink-0 flex-col border-r border-carbon-deep/13">
        <div className="flex flex-col gap-4 px-5 pt-8">
          <Masthead title="待核" hint="核對系統標記的人臉" align="center">
            <Button
              size="sm"
              onClick={() => void queryClient.invalidateQueries({ queryKey: ['flaggedFaces'] })}
            >
              重新調閱
            </Button>
          </Masthead>

          <div className="flex flex-row gap-5 border-b border-carbon-deep/13">
            {[...STATUS_TABS, 'all' as const].map((tab) => {
              const active = statusFilter === tab;
              return (
                <button
                  key={tab}
                  type="button"
                  aria-pressed={active}
                  onClick={() => setStatusFilter(tab)}
                  className={`-mb-px flex flex-row items-end gap-1 border-b-2 pb-2 font-kai text-[14px] ${
                    active
                      ? 'border-stamp font-bold text-carbon-deep'
                      : 'border-transparent text-carbon-soft hover:text-carbon-deep'
                  }`}
                >
                  {tab === 'all' ? '全部' : STATUS_WORD[tab]}
                  <span
                    className={`font-mono text-[12px] font-normal tabular-nums ${
                      active ? 'text-stamp' : 'text-ink-muted'
                    }`}
                  >
                    {counts[tab]}
                  </span>
                </button>
              );
            })}
          </div>

          <div className="flex flex-row gap-2">
            <Filter
              label="分級"
              value={bandFilter}
              onChange={(v) => setBandFilter(v as typeof bandFilter)}
              options={[
                ['all', '全部分級'],
                ['high', BAND_STAMP.high.word],
                ['medium', BAND_STAMP.medium.word],
                ['low', BAND_STAMP.low.word],
              ]}
            />
            <Filter
              label="影片"
              value={videoFilter}
              onChange={setVideoFilter}
              options={[
                ['', '全部影片'],
                ...uniqueVideos.map((v) => [v, videoShortName(v)] as [string, string]),
              ]}
            />
          </div>

          {selected.size > 0 && (
            <div className="flex flex-row items-center gap-2">
              <span className="flex-1 font-kai text-[13px] text-carbon-soft">
                已選 <span className="font-mono tabular-nums">{selected.size}</span>
              </span>
              <Button
                size="sm"
                variant="primary"
                disabled={busy}
                onClick={() => bulkUpdateStatus('accepted')}
              >
                全部蓋印
              </Button>
              <Button
                size="sm"
                disabled={busy}
                onClick={() => {
                  if (confirmReject(selected.size, true)) void bulkUpdateStatus('rejected');
                }}
              >
                全部作廢
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setSelected(new Set())}>
                取消
              </Button>
            </div>
          )}
        </div>

        {isLoading ? (
          <div className="py-16 text-center font-kai text-[13px] text-carbon-soft">正在調閱…</div>
        ) : error ? (
          <div className="mx-5 mt-4">
            <AdminErrorNotice error={error} label="讀不到待核紀錄" onRetry={() => void refetch()} />
          </div>
        ) : filtered.length === 0 ? (
          <div className="px-5 py-14 text-center">
            <div className="font-kai text-[15px] text-carbon-deep">這一疊是空的</div>
            <div className="mt-1 font-kai text-[13px] text-ink-muted">
              沒有符合目前條件的待核紀錄。
            </div>
          </div>
        ) : (
          <div ref={trayRef} className="flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto p-3">
            {filtered.slice(0, 200).map((face) => {
              const isFocused = focused?.id === face.id;
              const c = contestantOf(face.contestant_id);
              const isPending = face.status === 'pending';
              return (
                <div
                  key={face.id}
                  data-slip={face.id}
                  onClick={() => setFocusedId(face.id)}
                  role="button"
                  tabIndex={isFocused ? 0 : -1}
                  aria-current={isFocused ? 'true' : undefined}
                  onKeyDown={(e) => {
                    // Only the row itself: Enter/Space inside the checkbox or a stamp stays theirs.
                    if (e.target !== e.currentTarget) return;
                    if (e.key === 'Enter' || e.key === ' ' || e.key === 'Spacebar') {
                      e.preventDefault();
                      setFocusedId(face.id);
                      return;
                    }
                    // Arrow keys walk the tray and carry focus with the roving tab stop; the
                    // window-level ↓ 下一張 handler is kept for focus outside the tray.
                    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
                      const rows = [
                        ...(trayRef.current?.querySelectorAll<HTMLElement>('[data-slip]') ?? []),
                      ];
                      const at = rows.indexOf(e.currentTarget);
                      const next = rows[at + (e.key === 'ArrowDown' ? 1 : -1)];
                      if (next) {
                        e.preventDefault();
                        e.stopPropagation();
                        setFocusedId(next.dataset.slip ?? null);
                        next.focus();
                      }
                    }
                  }}
                  className={`group flex h-16 shrink-0 cursor-pointer flex-row items-center gap-2.5 rounded-md px-2 ${
                    isFocused ? 'bg-tint' : 'hover:bg-tint/50'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={selected.has(face.id)}
                    onChange={() => toggleSelection(face.id)}
                    onClick={(e) => e.stopPropagation()}
                    className="h-4 w-4 shrink-0 cursor-pointer accent-stamp"
                    aria-label={`選取 ${c?.nickname ?? `#${face.contestant_id}`} ${formatMmSs(face.timestamp)}`}
                  />
                  <div className="h-12 w-12 shrink-0 overflow-hidden rounded bg-tint">
                    {face.thumbnail && (
                      <img src={face.thumbnail} alt="" className="h-full w-full object-cover" />
                    )}
                  </div>
                  <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                    <div className="flex flex-row items-baseline gap-1.5">
                      <span
                        className={`truncate font-kai text-[15px] text-carbon-deep ${
                          isFocused ? 'font-bold' : ''
                        }`}
                      >
                        {c?.nickname ?? `#${face.contestant_id}`}
                      </span>
                      <span className="shrink-0 font-mono text-[12px] text-ink-muted">
                        #{face.contestant_id}
                      </span>
                    </div>
                    <span className="truncate font-mono text-[12px] text-ink-muted">
                      {formatMmSs(face.timestamp)} · {videoShortName(face.video_id)}
                    </span>
                  </div>
                  {!isPending && <Stamp tilt>{STATUS_WORD[face.status]}</Stamp>}
                  {/* Score and actions share one grid cell, so swapping them never reflows the row. */}
                  <div className="grid shrink-0 items-center justify-items-end">
                    <div
                      className={`col-start-1 row-start-1 flex flex-col items-end gap-1 ${
                        !isPending
                          ? ''
                          : isFocused
                            ? 'opacity-0'
                            : 'group-focus-within:opacity-0 group-hover:opacity-0'
                      }`}
                    >
                      <span
                        title="被標記偵測的配對分數（標記本身不帶分數）"
                        className="font-mono text-[14px] tabular-nums text-carbon-deep"
                      >
                        {face.confidence == null ? '—' : face.confidence.toFixed(2)}
                      </span>
                      <Stamp band={bandFor(face.confidence ?? 0)} />
                    </div>
                    {isPending && (
                      // Opacity, not display:none, keeps these in the tab order. Hidden ones ignore
                      // pointers, so a touch tap can't hit an invisible 蓋印.
                      <div
                        className={`col-start-1 row-start-1 flex flex-row gap-1 ${
                          isFocused
                            ? ''
                            : 'pointer-events-none opacity-0 group-focus-within:pointer-events-auto group-focus-within:opacity-100 group-hover:pointer-events-auto group-hover:opacity-100'
                        }`}
                      >
                        <RowAction
                          label="蓋印"
                          onClick={() => void applyStatus(face.id, 'accepted')}
                        />
                        <RowAction label="作廢" onClick={() => rejectOne(face.id)} />
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Every write reports here: the server's reason on failure, the stamp word on success.
            The line stays mounted so `aria-live` announces each change, and sits under the tray so
            it survives the slip being filtered out without pushing the rows. */}
        <div className="mt-auto flex shrink-0 flex-col gap-1 px-5 pb-3 pt-1">
          {writeError ? <AdminErrorNotice error={writeError} label="寫入失敗" /> : null}
          <p aria-live="polite" className="min-h-[18px] font-kai text-[13px] text-carbon-soft">
            {notice}
            {lastDecision ? (
              <>
                {notice ? ' · ' : ''}
                <button
                  type="button"
                  onClick={() => void undoLastDecision()}
                  title={`復原 SLIP ${String(lastDecision.id).slice(-4).toUpperCase()} 回待核`}
                  className="rounded-md font-kai text-[13px] text-stamp hover:underline"
                >
                  復原
                </button>
              </>
            ) : null}
          </p>
        </div>
      </div>

      {/* Review sheet */}
      <div className="flex min-w-0 flex-1 flex-col gap-5 overflow-y-auto px-8 pb-6 pt-8">
        {focused ? (
          <>
            <div className="flex shrink-0 flex-col gap-1">
              <div className="flex flex-row items-end justify-between gap-6">
                <div className="flex min-w-0 flex-row items-end gap-2.5">
                  <h2 className="truncate font-kai text-[32px] font-normal leading-tight text-carbon-deep">
                    {focusedContestant?.nickname ?? `#${focused.contestant_id}`}
                  </h2>
                  <span className="shrink-0 pb-1 font-kai text-[14px] text-carbon-soft">
                    {focusedContestant?.name ?? '—'} · 編號 {focused.contestant_id}
                  </span>
                </div>
                <span className="shrink-0 pb-1 font-mono text-[12px] text-ink-muted">
                  {formatMmSs(focused.timestamp)} · {videoShortName(focused.video_id)}
                  {context.strip[2] ? ` · 第 ${context.strip[2].frame_number} 格` : ''}
                </span>
              </div>
              {focused.user_label && (
                <p className="truncate font-kai text-[13px] text-ink-muted">{focused.user_label}</p>
              )}
            </div>

            {/* 畫面偵測 against 參考相. The only reference route serves the contestant's first
                photo by filename: no endpoint ranks references for a flag, hence 未按相似度排序. */}
            <div className="flex min-h-[260px] max-h-[428px] flex-[1_1_428px] flex-row gap-4">
              <div className="flex min-w-0 flex-1 flex-col gap-2">
                <div className="relative min-h-0 flex-1 overflow-hidden rounded bg-carbon-deep">
                  {focused.thumbnail ? (
                    <img
                      src={focused.thumbnail}
                      alt="被標記的人臉"
                      className="absolute inset-0 h-full w-full object-cover"
                    />
                  ) : (
                    <div className="flex h-full items-center justify-center font-kai text-[13px] text-paper-light">
                      沒有縮圖
                    </div>
                  )}
                </div>
                <div className="flex flex-row justify-between">
                  <span className="font-kai text-[14px] text-carbon">畫面偵測</span>
                  <span className="font-kai text-[12px] text-ink-muted">
                    檢出分數{' '}
                    <span className="font-mono tabular-nums">
                      {context.det == null ? '無資料' : context.det.toFixed(2)}
                    </span>
                  </span>
                </div>
              </div>
              <div className="flex min-w-0 flex-1 flex-col gap-2">
                <div className="relative min-h-0 flex-1 overflow-hidden rounded bg-tint">
                  <img
                    key={focused.contestant_id}
                    src={
                      focusedContestant?.portrait_url ??
                      `/api/contestants/${focused.contestant_id}/thumb/face`
                    }
                    alt={focusedContestant?.name ?? ''}
                    className="absolute inset-0 h-full w-full object-cover"
                    onError={(e) => {
                      (e.target as HTMLImageElement).style.visibility = 'hidden';
                    }}
                  />
                </div>
                <div className="flex flex-row justify-between">
                  <span className="font-kai text-[14px] text-carbon">參考相</span>
                  <span className="font-kai text-[12px] text-ink-muted">
                    共 {focusedContestant?.reference_count ?? 0} 張 · 未按相似度排序
                  </span>
                </div>
              </div>
            </div>

            {/* The flag asserts no score of its own (CONTEXT.md, "Flag"). `confidence` is the
                flagged detection's match score, carried as context for the claim. */}
            <div className="flex shrink-0 flex-col gap-2">
              <div className="flex flex-row items-end justify-between gap-6">
                <div className="flex flex-row items-end gap-2">
                  <span className="font-mono text-[28px] leading-none tabular-nums text-carbon-deep">
                    {focused.confidence == null ? '—' : focused.confidence.toFixed(3)}
                  </span>
                  {focused.confidence == null ? (
                    <Stamp tone="muted">未配對</Stamp>
                  ) : (
                    <Stamp band={bandFor(focused.confidence)} />
                  )}
                </div>
                <span className="font-kai text-[12px] text-ink-muted">
                  被標記偵測的配對分數，僅供參考；標記本身不帶分數
                </span>
              </div>
              <div className="relative flex h-2.5 flex-row gap-0.5">
                <div
                  className="h-full bg-ledger/27"
                  style={{ width: `${lowEnd}%` }}
                  title={`接受門檻 ${ACCEPTANCE_THRESHOLD}`}
                />
                <div className="h-full bg-stamp/33" style={{ width: `${midWidth}%` }} />
                <div className="h-full flex-1 bg-carbon/20" />
                {focused.confidence != null && (
                  <div
                    className="absolute -top-[3px] h-4 w-0.5 bg-carbon-deep"
                    style={{ left: `${rulerPercent(focused.confidence)}%` }}
                  />
                )}
              </div>
              <div className="flex flex-row gap-0.5 font-kai text-[12px] text-ink-muted">
                <span style={{ width: `${lowEnd}%` }}>
                  {BAND_STAMP.low.word} &lt; {BAND_CUTOFFS.medium}
                </span>
                <span className="whitespace-nowrap" style={{ width: `${midWidth}%` }}>
                  {BAND_STAMP.medium.word}
                </span>
                <span className="flex-1">
                  {BAND_STAMP.high.word} ≥ {BAND_CUTOFFS.high}
                </span>
              </div>
            </div>

            {/* The two processed frames either side of the flag's floor frame, each a real frame
                of the served rendition (`stream_url` seeked by a #t media fragment). */}
            <div className="flex shrink-0 flex-col gap-2">
              <span className="font-kai text-[14px] text-carbon">前後五格</span>
              <div className="flex flex-row gap-2">
                {context.strip.map((frame, k) => (
                  <div
                    key={k}
                    className={`flex h-20 min-w-0 flex-1 items-center justify-center overflow-hidden rounded bg-carbon-deep ${
                      k === 2 ? 'border-2 border-stamp' : ''
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
                      <span className="font-mono text-[12px] text-paper-light">—</span>
                    )}
                  </div>
                ))}
              </div>
              {!streamUrl || context.strip.every((f) => f == null) ? (
                <span className="font-kai text-[12px] text-ink-muted">
                  此片段無前後影格可調閱。
                </span>
              ) : null}
            </div>

            <div className="flex-1" />

            {reassignOpen && (
              <div className="flex shrink-0 flex-col gap-1">
                <div className="flex flex-row items-center gap-2">
                  <label className="flex min-w-0 flex-1 flex-row items-center gap-2 font-kai text-[14px] text-carbon">
                    <span className="shrink-0">改派給</span>
                    <select
                      ref={reassignRef}
                      value={reassignTo}
                      onChange={(e) => setReassignTo(e.target.value)}
                      className="field field-select min-w-0 flex-1"
                    >
                      {(contestants as Contestant[]).map((c) => (
                        <option key={c.id} value={c.id}>
                          #{c.id} · {c.nickname} ({c.name})
                        </option>
                      ))}
                    </select>
                  </label>
                  <Button
                    size="sm"
                    disabled={reassignTo === String(focused.contestant_id)}
                    onClick={() => void reassignFace()}
                  >
                    確定改派
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setReassignOpen(false)}>
                    取消
                  </Button>
                </div>
                {/* Reassign is not a silent relabel: the endpoint files the slip under the new
                    contestant and puts it back in 待核, so a human must decide it again. */}
                <span className="font-kai text-[12px] leading-snug text-ink-muted">
                  改派會把這張退回待核，需要重新核對。
                </span>
              </div>
            )}

            <div className="flex shrink-0 flex-row items-center gap-2">
              <Button
                variant="primary"
                keycap="1"
                disabled={focused.status !== 'pending'}
                onClick={() => void applyStatus(focused.id, 'accepted')}
              >
                蓋印確認
              </Button>
              <Button
                keycap="2"
                disabled={focused.status !== 'pending'}
                onClick={() => rejectOne(focused.id)}
              >
                作廢
              </Button>
              <Button keycap="3" onClick={openReassign}>
                改派給…
              </Button>
              <span className="flex-1" />
              <Button variant="ghost" keycap="↓" onClick={goNext}>
                下一張
              </Button>
            </div>
          </>
        ) : (
          <div className="flex flex-1 items-center justify-center font-kai text-[13px] text-carbon-soft">
            從左邊的托盤挑一張來核對。
          </div>
        )}
      </div>
    </div>
  );
}

function Filter({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: [string, string][];
}) {
  return (
    <select
      aria-label={label}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="field field-select min-w-0 flex-1"
    >
      {options.map(([v, text]) => (
        <option key={v} value={v}>
          {text}
        </option>
      ))}
    </select>
  );
}

function RowAction({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      className="h-7 rounded-md border border-carbon-deep/33 bg-ground px-2 font-kai text-[12px] text-carbon hover:bg-tint"
    >
      {label}
    </button>
  );
}
