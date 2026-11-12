import { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import type { ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { LoaderCircle } from 'lucide-react';
import { useIsEdge } from '../useIsEdge';
import {
  AdminErrorNotice,
  Button,
  Masthead,
  adminFetch,
  assertOk,
  formatMmSs,
  LOCAL_API_OFFLINE_NOTICE,
} from '@mv/shared';
import {
  formatJobCreated,
  jobModeLabel,
  jobProgressLine,
  jobStatusLabel,
} from '@mv/shared/lib/pipeline';

interface ProcessingJob {
  id: string;
  mode?: string;
  /** `completed_with_errors`: the run finished, but some reels failed. Never a clean success. */
  status: 'queued' | 'running' | 'completed' | 'completed_with_errors' | 'failed' | 'cancelled';
  progress: number;
  current_video?: string;
  videos_processed?: number;
  total_videos?: number;
  created_at?: string;
  // The Worker and the local API both answer with `null` for "not yet".
  started_at?: number | null;
  completed_at?: number | null;
  error?: string | null;
  /** Reels that failed inside an otherwise finished run; one row each, in run order. */
  failures?: Array<{ video: string; error: string }>;
}

interface VideoOption {
  filename: string;
  size_mb: number;
}

/**
 * A row the trigger returned that the eventual-consistency listing has not confirmed yet.
 * `missCount` counts consecutive listings that predate the row: a job that never shows up —
 * because the API restarted and lost it — is dropped instead of staying "queued" forever.
 */
type PendingJob = ProcessingJob & { missCount?: number };

/** ~30 s at the 5 s poll cadence: long enough for KV lag, short enough to admit a lost job. */
const STRANDED_LISTING_LIMIT = 6;
/** The stranded notice clears itself; the dead row it announced will not come back. */
const STRANDED_NOTICE_MS = 15_000;

/**
 * Both video lists use `filename` and byte sizes: the local API reports `size_mb` directly,
 * the Worker publishes `size` in bytes. Unknown entries are dropped rather than guessed.
 */
function toVideoOptions(list: unknown[]): VideoOption[] {
  const options: VideoOption[] = [];
  for (const item of list) {
    if (!item || typeof item !== 'object') continue;
    if (!('filename' in item) || typeof item.filename !== 'string') continue;
    const sizeMb =
      'size_mb' in item && typeof item.size_mb === 'number'
        ? item.size_mb
        : 'size' in item && typeof item.size === 'number'
          ? item.size / 1024 / 1024
          : 0;
    options.push({ filename: item.filename, size_mb: sizeMb });
  }
  return options;
}

const STATUS_INK: Record<ProcessingJob['status'], string> = {
  queued: 'text-carbon-soft',
  running: 'text-carbon',
  completed: 'text-ink-muted',
  // The run ended, but not cleanly: it never reads as a plain completed.
  completed_with_errors: 'text-stamp',
  failed: 'text-stamp',
  cancelled: 'text-ink-muted',
};

const BAR_FILL: Record<ProcessingJob['status'], string> = {
  queued: 'bg-carbon',
  running: 'bg-carbon',
  completed: 'bg-carbon',
  completed_with_errors: 'bg-stamp/60',
  failed: 'bg-stamp',
  cancelled: 'bg-ink-muted',
};

/**
 * Statuses that end a job. The first sighting of a job in one of these is the transition the
 * read-model invalidation below fires on: it must run once, not on every 5 s poll.
 */
const TERMINAL_STATUSES: Record<ProcessingJob['status'], boolean> = {
  queued: false,
  running: false,
  completed: true,
  completed_with_errors: true,
  failed: true,
  cancelled: true,
};

/** Every view whose numbers a finished job can change. */
const JOB_INVALIDATED_QUERIES = [
  ['videos'],
  ['contestants'],
  ['coverage'],
  ['similarity-matrix'],
  ['top-pairs'],
  ['labels'],
] as const;

function formatDuration(start?: number | null, end?: number | null): string {
  if (!start) return '--';
  const endTime = end || Date.now();
  return formatMmSs(Math.floor((endTime - start) / 1000));
}

function Banner({ children }: { children: ReactNode }) {
  return (
    <div role="alert" className="border-y border-stamp/33 py-2 font-kai text-[13px] text-stamp">
      {children}
    </div>
  );
}

function ActionColumn({
  className,
  title,
  description,
  does,
  controls,
  note,
}: {
  className: string;
  title: string;
  description: string;
  does: string[];
  controls: ReactNode;
  note?: ReactNode;
}) {
  return (
    <div className={`flex flex-col gap-3 ${className}`}>
      <div className="flex flex-col gap-1 xl:h-[72px]">
        <h2 className="font-kai text-[18px] font-normal text-carbon-deep">{title}</h2>
        <p className="font-kai text-[14px] leading-[1.4] text-carbon-soft">{description}</p>
      </div>
      <div className="flex flex-col justify-end gap-2 xl:h-[108px]">{controls}</div>
      {note && <p className="font-kai text-[12px] leading-[1.4] text-ink-muted">{note}</p>}
      <ul className="flex flex-col gap-1 font-kai text-[12px] text-ink-muted">
        {does.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
    </div>
  );
}

export function Processing() {
  const queryClient = useQueryClient();
  const [jobs, setJobs] = useState<ProcessingJob[]>([]);
  const [videoOptions, setVideoOptions] = useState<VideoOption[]>([]);
  const [selectedVideo, setSelectedVideo] = useState('');
  // Fail-open until the first probe answers, so a healthy API never flashes the notice.
  const [jobsAvailable, setJobsAvailable] = useState(true);
  // The poll's own failure (dead API, 5xx, expired Access session), not a click's.
  const [jobsError, setJobsError] = useState<unknown>(null);
  // A trigger/cancel/clear failure; kept apart so 重試 re-runs the read, never the write.
  const [actionError, setActionError] = useState<unknown>(null);
  // Coverage refresh needs the local API; the Worker has no path into the KV read model.
  const edge = useIsEdge();
  const isEdge = edge === true;
  const [isProcessing, setIsProcessing] = useState(false);
  // A row was dropped because the listing never confirmed it.
  const [strandedNotice, setStrandedNotice] = useState(false);
  // Job id → failures expanded. Collapsed by default: the count is the summary.
  const [openFailures, setOpenFailures] = useState<Record<string, boolean>>({});
  const pollingRef = useRef<number | undefined>(undefined);
  const strandedNoticeTimerRef = useRef<number | undefined>(undefined);
  // Last status per job: the first terminal status seen is the transition that refreshes the
  // read models, so it must fire once and not on every poll.
  const seenStatusRef = useRef<Map<string, ProcessingJob['status']>>(new Map());
  // KV listing is eventually consistent, so a job created a second ago can be missing from it.
  // Hold the row the trigger returned until a poll reports that id.
  const [pendingJobs, setPendingJobs] = useState<PendingJob[]>([]);
  // Mirror of `pendingJobs`: the reconciler counts each listing once, and a React state updater
  // may be replayed, so the miss counters cannot live inside one.
  const pendingJobsRef = useRef<PendingJob[]>([]);
  // Identity of the listing already reconciled; the same array must never be counted twice.
  const reconciledListingRef = useRef<ProcessingJob[] | null>(null);

  const updatePendingJobs = useCallback((next: PendingJob[]) => {
    pendingJobsRef.current = next;
    setPendingJobs(next);
  }, []);

  /**
   * Drop local rows the listing confirms, and drop the ones it never confirms: a job lost to an
   * API restart would otherwise sit at "queued" forever. Runs once per listing.
   */
  const reconcilePendingJobs = useCallback(
    (listing: ProcessingJob[]) => {
      if (reconciledListingRef.current === listing) return;
      reconciledListingRef.current = listing;
      if (pendingJobsRef.current.length === 0) return;
      const listedIds = new Set(listing.map((job) => job.id));
      let stranded = 0;
      const kept: PendingJob[] = [];
      for (const job of pendingJobsRef.current) {
        if (listedIds.has(job.id)) continue; // the server owns it now
        const missCount = (job.missCount ?? 0) + 1;
        if (missCount >= STRANDED_LISTING_LIMIT) {
          stranded += 1;
          continue;
        }
        kept.push({ ...job, missCount });
      }
      updatePendingJobs(kept);
      if (stranded === 0) return;
      setStrandedNotice(true);
      window.clearTimeout(strandedNoticeTimerRef.current);
      strandedNoticeTimerRef.current = window.setTimeout(
        () => setStrandedNotice(false),
        STRANDED_NOTICE_MS,
      );
    },
    [updatePendingJobs],
  );

  // Local rows the listing has not reported yet: the only ones safe to add to the server's own.
  const unconfirmedJobs = useMemo(() => {
    const listed = new Set(jobs.map((job) => job.id));
    return pendingJobs.filter((job) => !listed.has(job.id));
  }, [jobs, pendingJobs]);

  const visibleJobs = useMemo(() => [...unconfirmedJobs, ...jobs], [unconfirmedJobs, jobs]);

  // Server rows plus unconfirmed local rows only, so a listed row is never counted twice.
  const activeCount = useMemo(() => {
    let active = 0;
    for (const job of jobs) if (job.status === 'running' || job.status === 'queued') active += 1;
    for (const job of unconfirmedJobs) {
      if (job.status === 'running' || job.status === 'queued') active += 1;
    }
    return active;
  }, [jobs, unconfirmedJobs]);
  const completedCount = useMemo(
    () => visibleJobs.filter((j) => j.status === 'completed').length,
    [visibleJobs],
  );

  const fetchJobs = useCallback(async () => {
    try {
      const res = await adminFetch('/admin/api/processing/jobs');
      if (res.status === 404) {
        // A Worker without the job routes cannot run the pipeline at all.
        setJobsAvailable(false);
        setJobsError(null);
        return;
      }
      // A 5xx is a live server refusing the read: show it, but the API is not offline.
      await assertOk(res);
      setJobsAvailable(true);
      setJobsError(null);
      const data = await res.json();
      const jobList = data.jobs || data || [];
      const next: ProcessingJob[] = Array.isArray(jobList) ? jobList : [];
      setJobs(next);
      reconcilePendingJobs(next);

      for (const job of next) {
        const prev = seenStatusRef.current.get(job.id);
        seenStatusRef.current.set(job.id, job.status);
        if (!TERMINAL_STATUSES[job.status]) continue;
        // First sighting already terminal: the job ended before this page watched it, so
        // whatever this page loaded is not stale because of it. Only a real transition fires.
        if (prev === undefined || TERMINAL_STATUSES[prev]) continue;
        for (const queryKey of JOB_INVALIDATED_QUERIES) {
          // 'all', not 'active': the other admin views are unmounted, and marking them stale
          // alone would leave their cached counts on screen until a manual reload.
          void queryClient.invalidateQueries({ queryKey, refetchType: 'all' });
        }
      }
    } catch (e) {
      setJobsError(e);
      // Only a request that never reached a server means the API is down.
      if (e instanceof TypeError) setJobsAvailable(false);
      console.error('Failed to fetch jobs:', e);
    }
  }, [queryClient, reconcilePendingJobs]);

  const retryJobs = useCallback(() => {
    void fetchJobs();
  }, [fetchJobs]);

  // Source reels for the picker. The Worker has no local filesystem, so it publishes the
  // processed list instead; the local API knows what is on disk. A failure leaves the
  // "all videos" default.
  useEffect(() => {
    if (edge === undefined) return;
    let cancelled = false;
    void (async () => {
      try {
        const res = await adminFetch(
          edge ? '/admin/api/videos/processed/list' : '/admin/api/videos/local',
        );
        if (!res.ok) return;
        const data: unknown = await res.json();
        let list: unknown[] | null = null;
        if (Array.isArray(data)) list = data;
        else if (
          data &&
          typeof data === 'object' &&
          'videos' in data &&
          Array.isArray(data.videos)
        ) {
          list = data.videos;
        }
        if (cancelled || !list) return;
        setVideoOptions(toVideoOptions(list));
      } catch {
        /* the reel list is optional; the trigger surfaces the real failure */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [edge]);

  // Initial load + polling
  useEffect(() => {
    void fetchJobs();
    pollingRef.current = setInterval(fetchJobs, 5000);
    return () => {
      clearInterval(pollingRef.current);
    };
  }, [fetchJobs]);

  useEffect(
    () => () => {
      window.clearTimeout(strandedNoticeTimerRef.current);
    },
    [],
  );

  async function trigger(mode: 'initial' | 'embedding-update' | 'coverage-refresh') {
    setIsProcessing(true);
    setActionError(null);
    try {
      const body =
        mode === 'initial'
          ? { mode: 'initial', ...(selectedVideo ? { video: selectedVideo } : {}) }
          : { mode };
      const res = await adminFetch('/admin/api/processing/trigger', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      await assertOk(res);
      const started = (await res.json()) as {
        job_id?: string;
        status?: ProcessingJob['status'];
        total_videos?: number;
      };
      if (typeof started.job_id === 'string' && started.job_id !== '') {
        const row: PendingJob = {
          id: started.job_id,
          mode,
          status: started.status ?? 'queued',
          progress: started.status === 'running' ? 10 : 0,
          current_video: mode === 'initial' ? selectedVideo : undefined,
          videos_processed: 0,
          total_videos: started.total_videos,
          created_at: new Date().toISOString(),
          started_at: started.status === 'running' ? Date.now() : null,
          completed_at: null,
          error: undefined,
          missCount: 0,
        };
        updatePendingJobs([row, ...pendingJobsRef.current.filter((job) => job.id !== row.id)]);
        // Watch this id from its first status, so a job that finishes inside one poll still
        // counts as a transition and refreshes the read model.
        seenStatusRef.current.set(row.id, row.status);
      }
      await fetchJobs();
    } catch (e) {
      setActionError(e);
    } finally {
      setIsProcessing(false);
    }
  }

  async function startInitialProcessing() {
    await trigger('initial');
  }

  async function startEmbeddingUpdate() {
    await trigger('embedding-update');
  }

  async function startCoverageRefresh() {
    await trigger('coverage-refresh');
  }

  async function cancelJob(job: ProcessingJob) {
    if (
      !window.confirm(
        `取消「${jobModeLabel(job.mode)}」工作？\n已處理完成的影片會保留，此工作會標記為已取消。`,
      )
    ) {
      return;
    }
    try {
      const res = await adminFetch(`/admin/api/processing/cancel/${job.id}`, { method: 'POST' });
      await assertOk(res);
      // The list lags the write, so a row still pending locally must not keep saying `queued`.
      updatePendingJobs(
        pendingJobsRef.current.map((pending) =>
          pending.id === job.id
            ? { ...pending, status: 'cancelled' as const, progress: 100, completed_at: Date.now() }
            : pending,
        ),
      );
      await fetchJobs();
    } catch (e) {
      setActionError(e);
    }
  }

  async function clearCompleted() {
    if (
      !window.confirm(
        `清除 ${completedCount} 筆已完成的工作紀錄？\n只刪除狀態為 completed 的紀錄，失敗、部分失敗與已取消的工作都會保留。`,
      )
    ) {
      return;
    }
    try {
      const res = await adminFetch('/admin/api/processing/clear-completed', { method: 'POST' });
      await assertOk(res);
      // The server owns which records go; a local filter would keep the rows it disagrees about
      // until the next poll.
      await fetchJobs();
    } catch (e) {
      setActionError(e);
    }
  }

  // Until the mode is known the local and cloud controls differ, so nothing can be started.
  const unavailableBecauseProcessing = !jobsAvailable || isProcessing || edge === undefined;
  const startingLabel = '啟動中…';

  return (
    <div className="flex min-h-full flex-1 flex-col gap-6 px-4 pb-5 pt-8 sm:px-8">
      <Masthead title="處理" hint="觸發影片處理、查看進度">
        {activeCount > 0 && (
          <span role="status" className="flex items-center gap-2 text-carbon">
            <LoaderCircle aria-hidden className="size-4 animate-spin" />
            <span>
              <span className="font-mono tabular-nums">{activeCount}</span> 個工作執行中
            </span>
          </span>
        )}
      </Masthead>

      {!jobsAvailable && <Banner>{LOCAL_API_OFFLINE_NOTICE}</Banner>}

      {/* Poll failure: 重試 re-reads the listing; an expired session offers reload instead. */}
      <AdminErrorNotice error={jobsError} onRetry={retryJobs} label="無法讀取工作清單" />

      {/* A click failed; there is nothing to retry automatically, so the reason alone is shown. */}
      <AdminErrorNotice error={actionError} label="操作失敗" />

      {strandedNotice && (
        <div
          role="status"
          className="border-y border-carbon-deep/13 py-2 font-kai text-[13px] text-carbon-soft"
        >
          工作已不在伺服器上，可能已隨 API 重啟中止
        </div>
      )}

      <div className="flex flex-col border-y border-carbon-deep/13 py-5 xl:flex-row">
        <ActionColumn
          className="min-w-0 flex-1 border-b border-carbon-deep/13 pb-5 xl:border-b-0 xl:border-r xl:pb-0 xl:pr-5"
          title="首次處理"
          description={
            isEdge ? '在雲端工作上重新處理一部影片' : '用本機流程處理這台機器上的所有影片'
          }
          does={
            isEdge
              ? [
                  '每次處理一部影片',
                  '偵測並辨識人臉',
                  '結果寫入 bucket',
                  '之後經 publish:metadata 發佈',
                ]
              : [
                  '處理所有未處理的影片',
                  '偵測並辨識人臉',
                  '可用時啟用硬件加速',
                  '結果寫入 local_output/',
                ]
          }
          controls={
            <>
              <div className="flex min-w-0 flex-col gap-1">
                <label htmlFor="source-reel" className="font-kai text-[12px] text-ink-muted">
                  來源影片
                </label>
                <select
                  id="source-reel"
                  value={selectedVideo}
                  onChange={(e) => setSelectedVideo(e.target.value)}
                  disabled={!jobsAvailable}
                  className="field field-select h-10 w-full disabled:opacity-45 max-sm:h-11"
                >
                  <option value="" disabled={isEdge}>
                    {isEdge ? '請揀選影片' : '全部來源影片'}
                  </option>
                  {videoOptions.map((v) => (
                    <option key={v.filename} value={v.filename}>
                      {v.filename}
                      {v.size_mb > 0 ? ` (${v.size_mb.toFixed(1)} MB)` : ''}
                    </option>
                  ))}
                </select>
              </div>
              <Button
                variant="primary"
                className="max-sm:h-11"
                onClick={startInitialProcessing}
                // Each reel on the edge is a paid run, so it must be named (ADR 0006).
                disabled={unavailableBecauseProcessing || (isEdge && !selectedVideo)}
              >
                {isProcessing ? startingLabel : '開始處理'}
              </Button>
            </>
          }
        />

        <ActionColumn
          className="w-full shrink-0 border-b border-carbon-deep/13 py-5 xl:w-[232px] xl:border-b-0 xl:border-r xl:px-5 xl:py-0"
          title="更新向量"
          description={
            isEdge ? '由 bucket 內的參考相重建參考向量' : '由硬碟上揀選好的參考相重建參考向量'
          }
          does={
            isEdge
              ? ['重建 reference_embeddings.npz', '寫入 bucket', '重新處理影片後才影響辨識結果']
              : [
                  '提升人臉辨識準確度',
                  '重建 reference_embeddings.npz',
                  '快速重算向量',
                  '自動更新覆蓋率',
                ]
          }
          controls={
            <Button
              className="w-full max-sm:h-11"
              onClick={startEmbeddingUpdate}
              disabled={unavailableBecauseProcessing}
            >
              {isProcessing ? startingLabel : '更新向量'}
            </Button>
          }
        />

        <ActionColumn
          className="w-full shrink-0 pt-5 xl:w-[232px] xl:pl-5 xl:pt-0"
          title="覆蓋率與相似度"
          description="重新計算向量覆蓋率、餘弦矩陣與最相近的配對"
          does={[
            '重建 data/coverage.json',
            '重建 similarity_matrix.json',
            '重建 top_pairs.json',
            '經 /api/embedding/* 提供',
          ]}
          controls={
            <Button
              className="w-full max-sm:h-11"
              onClick={startCoverageRefresh}
              disabled={unavailableBecauseProcessing || isEdge}
            >
              {isProcessing ? startingLabel : '重新計算覆蓋率與相似度'}
            </Button>
          }
          note={
            isEdge ? (
              <>
                雲端環境不提供：覆蓋率與相似度由 bucket 經{' '}
                <code className="font-mono">npm run publish:metadata</code> 發佈，不由工作寫入。
              </>
            ) : null
          }
        />
      </div>

      <section className="flex flex-col gap-2">
        <div className="flex flex-row flex-wrap items-center justify-between gap-x-4">
          <h2 className="font-kai text-[18px] font-normal text-carbon-deep">處理工作</h2>
          <div className="flex h-8 flex-row items-center gap-4 font-kai text-[13px] text-carbon-soft">
            <span>
              <span className="font-mono tabular-nums">{activeCount}</span> 進行中
            </span>
            <span>
              <span className="font-mono tabular-nums">{completedCount}</span> 已完成
            </span>
            {completedCount > 0 && (
              <Button size="sm" className="max-sm:h-11" onClick={clearCompleted}>
                清除已完成
              </Button>
            )}
          </div>
        </div>

        {visibleJobs.length === 0 ? (
          <div className="border-t border-carbon-deep/13 py-10 text-center font-kai">
            <p className="text-[14px] text-carbon-soft">還沒有處理工作</p>
            <p className="mt-1 text-[12px] text-ink-muted">開始一項處理工作後，會在這裡顯示進度</p>
          </div>
        ) : (
          <div className="flex flex-col">
            {visibleJobs.map((job) => {
              const progressLine = jobProgressLine(job);
              const progress = job.progress || 0;
              return (
                <div
                  key={job.id}
                  className="flex flex-col gap-2 border-t border-carbon-deep/13 py-2 sm:flex-row sm:items-center sm:gap-6"
                >
                  <div className="flex shrink-0 flex-col gap-0.5 sm:w-[280px]">
                    <div className="flex flex-row items-end gap-2">
                      <h3 className="font-kai text-[15px] font-normal text-carbon-deep">
                        {jobModeLabel(job.mode)}
                      </h3>
                      <span className={`font-kai text-[12px] ${STATUS_INK[job.status]}`}>
                        {jobStatusLabel(job.status)}
                      </span>
                    </div>
                    {progressLine && (
                      <p
                        className="truncate font-kai text-[12px] text-ink-muted"
                        title={job.current_video ?? undefined}
                      >
                        {progressLine}
                      </p>
                    )}
                    {job.failures && job.failures.length > 0 && (
                      <div className="mt-1 rounded-md border border-stamp/40">
                        <button
                          type="button"
                          aria-expanded={!!openFailures[job.id]}
                          onClick={() =>
                            setOpenFailures((prev) => ({ ...prev, [job.id]: !prev[job.id] }))
                          }
                          className="flex h-11 w-full cursor-pointer sm:h-8 items-center justify-between gap-2 px-2 text-left font-kai text-[12px] text-stamp"
                        >
                          <span>
                            <span className="font-mono tabular-nums">{job.failures.length}</span>{' '}
                            失敗
                          </span>
                          <span>{openFailures[job.id] ? '收起' : '展開'}</span>
                        </button>
                        {openFailures[job.id] && (
                          <ul className="border-t border-stamp/20 px-2 py-1">
                            {job.failures.map((failure, i) => (
                              <li
                                key={`${failure.video}-${i}`}
                                className="flex flex-col gap-0.5 border-b border-stamp/20 py-1 font-mono text-[12px] leading-snug last:border-b-0"
                              >
                                <span className="break-all text-carbon-deep">{failure.video}</span>
                                <span className="break-words text-stamp">{failure.error}</span>
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    )}
                  </div>

                  <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                    <div className="flex flex-row items-center gap-3">
                      <div
                        role="progressbar"
                        aria-label={`${jobModeLabel(job.mode)}進度`}
                        aria-valuemin={0}
                        aria-valuemax={100}
                        aria-valuenow={progress}
                        className="h-1 flex-1 bg-carbon-deep/13"
                      >
                        <div
                          className={`h-full transition-[width] duration-300 ${BAR_FILL[job.status]}`}
                          style={{ width: `${progress}%` }}
                        />
                      </div>
                      <span className="w-10 text-right font-mono text-[12px] tabular-nums text-carbon-soft">
                        {progress}%
                      </span>
                    </div>
                    {job.error && <p className="font-kai text-[12px] text-stamp">{job.error}</p>}
                  </div>

                  <div className="flex shrink-0 flex-row flex-wrap gap-x-3 gap-y-0.5 whitespace-nowrap sm:w-[136px] sm:flex-col sm:items-end sm:gap-0.5 font-mono text-[12px] tabular-nums text-ink-muted">
                    {job.created_at && <span>建立 {formatJobCreated(job.created_at)}</span>}
                    {job.started_at && (
                      <span>歷時 {formatDuration(job.started_at, job.completed_at)}</span>
                    )}
                  </div>

                  <div className="flex shrink-0 flex-row justify-end max-sm:empty:hidden sm:h-8 sm:w-16">
                    {(job.status === 'queued' || job.status === 'running') && (
                      <Button
                        variant="destructive"
                        size="sm"
                        className="max-sm:h-11"
                        onClick={() => cancelJob(job)}
                      >
                        取消
                      </Button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
