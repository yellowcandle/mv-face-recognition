import { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import {
  Card,
  Badge,
  Button,
  Masthead,
  AdminErrorNotice,
  adminFetch,
  assertOk,
  formatMmSs,
  LOCAL_API_OFFLINE_NOTICE,
} from '@mv/shared';

interface ProcessingJob {
  id: string;
  mode?: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  current_video?: string;
  videos_processed?: number;
  total_videos?: number;
  created_at?: string;
  // The Worker and the local API both answer with `null` for "not yet".
  started_at?: number | null;
  completed_at?: number | null;
  error?: string | null;
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

function getStatusVariant(status: string): 'success' | 'warning' | 'error' | 'neutral' {
  switch (status) {
    case 'completed':
      return 'success';
    case 'running':
      return 'warning';
    case 'failed':
      return 'error';
    default:
      return 'neutral';
  }
}

function getStatusColor(status: string): string {
  switch (status) {
    case 'completed':
      return 'bg-carbon';
    case 'running':
      return 'bg-carbon';
    case 'failed':
      return 'bg-stamp';
    case 'cancelled':
      return 'bg-ledger';
    default:
      return 'bg-stamp';
  }
}

function formatDuration(start?: number | null, end?: number | null): string {
  if (!start) return '--';
  const endTime = end || Date.now();
  return formatMmSs(Math.floor((endTime - start) / 1000));
}

function formatTimestamp(iso?: string): string {
  if (!iso) return '--';
  return new Date(iso).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
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
  const [isEdge, setIsEdge] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  // A row was dropped because the listing never confirmed it.
  const [strandedNotice, setStrandedNotice] = useState(false);
  const pollingRef = useRef<number | undefined>(undefined);
  const strandedNoticeTimerRef = useRef<number | undefined>(undefined);
  // Last status per job, so a coverage/embedding job that just finished refreshes the read model.
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
        if (
          job.status === 'completed' &&
          prev !== 'completed' &&
          (job.mode === 'embedding-update' || job.mode === 'coverage-refresh')
        ) {
          void queryClient.invalidateQueries({ queryKey: ['coverage'] });
          void queryClient.invalidateQueries({ queryKey: ['similarity-matrix'] });
          void queryClient.invalidateQueries({ queryKey: ['top-pairs'] });
        }
        seenStatusRef.current.set(job.id, job.status);
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
    let cancelled = false;
    void (async () => {
      try {
        const statusRes = await adminFetch('/admin/api/system/status');
        const status: unknown = statusRes.ok ? await statusRes.json() : null;
        const edge =
          !!status && typeof status === 'object' && 'mode' in status && status.mode === 'edge';
        setIsEdge(edge);
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
  }, []);

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

  async function cancelJob(jobId: string) {
    try {
      const res = await adminFetch(`/admin/api/processing/cancel/${jobId}`, { method: 'POST' });
      await assertOk(res);
      // The list lags the write, so a row still pending locally must not keep saying `queued`.
      updatePendingJobs(
        pendingJobsRef.current.map((job) =>
          job.id === jobId
            ? { ...job, status: 'cancelled' as const, progress: 100, completed_at: Date.now() }
            : job,
        ),
      );
      await fetchJobs();
    } catch (e) {
      setActionError(e);
    }
  }

  async function clearCompleted() {
    try {
      const res = await adminFetch('/admin/api/processing/clear-completed', { method: 'POST' });
      await assertOk(res);
      // The server drops every terminal record (completed, failed, cancelled); a local filter
      // would keep the rows it disagrees about until the next poll.
      await fetchJobs();
    } catch (e) {
      setActionError(e);
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col px-9 pb-6 pt-7">
      <Masthead
        eyebrow="BACK OFFICE · PIPELINE"
        title="處理"
        latin="VIDEO PROCESSING & CACHE"
        size="md"
      />

      <div className="mt-4 h-px bg-carbon/45" />

      <div className="flex min-h-0 flex-1 flex-col gap-6 pt-5">
        {!jobsAvailable && (
          <div className="border border-stamp/50 bg-stamp/5 px-4 py-3 font-kai text-[13px] text-stamp">
            {LOCAL_API_OFFLINE_NOTICE}
          </div>
        )}

        {/* Poll failure: 重試 re-reads the listing; an expired session offers reload instead. */}
        <AdminErrorNotice error={jobsError} onRetry={retryJobs} label="無法讀取工作清單" />

        {/* A click failed; there is nothing to retry automatically, so the reason alone is shown. */}
        <AdminErrorNotice error={actionError} label="操作失敗" />

        {strandedNotice && (
          <div className="border-y border-carbon/30 bg-carbon/5 px-4 py-2 font-kai text-[12px] leading-snug text-ledger">
            工作已不在伺服器上，可能已隨 API 重啟中止
          </div>
        )}

        {/* Active Jobs Banner */}
        {activeCount > 0 && (
          <div className="flex items-center gap-2 border border-carbon/50 bg-carbon/5 px-4 py-3 font-kai text-[13px] text-carbon">
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-carbon border-t-transparent" />
            {activeCount} job{activeCount !== 1 ? 's' : ''} running
          </div>
        )}

        {/* Processing Action Cards */}
        <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
          <Card padding="lg">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-base font-semibold text-carbon-deep">Initial Processing</h2>
              <span className="h-2 w-2 rounded-full bg-carbon" />
            </div>
            <p className="mb-4 text-sm leading-relaxed text-carbon-soft">
              Process all videos on this machine with the local pipeline
            </p>
            <label className="mb-1 block font-mono text-[8px] tracking-[0.2em] text-ledger">
              SOURCE REEL 來源影片
            </label>
            <select
              value={selectedVideo}
              onChange={(e) => setSelectedVideo(e.target.value)}
              disabled={!jobsAvailable}
              className="mb-4 w-full border border-carbon/45 bg-paper-light px-2.5 py-2 font-kai text-[13px] text-carbon-deep focus:border-stamp focus:outline-none disabled:opacity-50"
            >
              <option value="">全部來源影片 (All Videos)</option>
              {videoOptions.map((v) => (
                <option key={v.filename} value={v.filename}>
                  {v.filename} ({v.size_mb.toFixed(1)} MB)
                </option>
              ))}
            </select>
            <Button
              variant="primary"
              onClick={startInitialProcessing}
              disabled={!jobsAvailable || isProcessing}
              className="mb-4 w-full"
            >
              {isProcessing ? 'Starting...' : 'Start Processing'}
            </Button>
            <ul className="space-y-1.5 text-xs text-ledger">
              <li className="flex items-center gap-2">
                <span className="text-carbon">&#x2713;</span> Process all unprocessed videos
              </li>
              <li className="flex items-center gap-2">
                <span className="text-carbon">&#x2713;</span> Detect and recognize faces
              </li>
              <li className="flex items-center gap-2">
                <span className="text-carbon">&#x2713;</span> Hardware acceleration when available
              </li>
              <li className="flex items-center gap-2">
                <span className="text-carbon">&#x2713;</span> Results written to local_output/
              </li>
            </ul>
          </Card>

          <Card padding="lg">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-base font-semibold text-carbon-deep">Embedding Update</h2>
              <span className="h-2 w-2 rounded-full bg-carbon" />
            </div>
            <p className="mb-4 text-sm leading-relaxed text-carbon-soft">
              Rebuild reference embeddings from the curated portraits on disk
            </p>
            <Button
              variant="secondary"
              onClick={startEmbeddingUpdate}
              disabled={!jobsAvailable || isProcessing}
              className="mb-4 w-full"
            >
              {isProcessing ? 'Starting...' : 'Update Embeddings'}
            </Button>
            <ul className="space-y-1.5 text-xs text-ledger">
              <li className="flex items-center gap-2">
                <span className="text-carbon">&#x2713;</span> Improve face recognition accuracy
              </li>
              <li className="flex items-center gap-2">
                <span className="text-carbon">&#x2713;</span> Rebuild reference_embeddings.npz
              </li>
              <li className="flex items-center gap-2">
                <span className="text-carbon">&#x2713;</span> Fast embedding recalculation
              </li>
              <li className="flex items-center gap-2">
                <span className="text-carbon">&#x2713;</span> Automatic coverage refresh
              </li>
            </ul>
          </Card>

          <Card padding="lg">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-base font-semibold text-carbon-deep">
                Coverage &amp; Similarity
              </h2>
              <span className="h-2 w-2 rounded-full bg-carbon" />
            </div>
            <p className="mb-4 text-sm leading-relaxed text-carbon-soft">
              Recompute embedding coverage, the cosine matrix and the closest pairs
            </p>
            <Button
              variant="secondary"
              onClick={startCoverageRefresh}
              disabled={!jobsAvailable || isProcessing || isEdge}
              className="mb-4 w-full"
            >
              {isProcessing ? 'Starting...' : '重新計算覆蓋率與相似度'}
            </Button>
            {isEdge && (
              <p className="mb-4 text-xs leading-relaxed text-ledger">
                Not available on the edge: coverage and similarity are published from the bucket
                with <code>npm run publish:metadata</code>, not written by a job.
              </p>
            )}
            <ul className="space-y-1.5 text-xs text-ledger">
              <li className="flex items-center gap-2">
                <span className="text-carbon">&#x2713;</span> Rebuild data/coverage.json
              </li>
              <li className="flex items-center gap-2">
                <span className="text-carbon">&#x2713;</span> Rebuild similarity_matrix.json
              </li>
              <li className="flex items-center gap-2">
                <span className="text-carbon">&#x2713;</span> Rebuild top_pairs.json
              </li>
              <li className="flex items-center gap-2">
                <span className="text-carbon">&#x2713;</span> Serve via /api/embedding/*
              </li>
            </ul>
          </Card>
        </div>

        {/* Jobs List */}
        <Card padding="lg">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-base font-semibold text-carbon-deep">Processing Jobs</h2>
            <div className="flex items-center gap-2">
              <Badge variant="warning" size="sm">
                {activeCount} Active
              </Badge>
              <Badge variant="success" size="sm">
                {completedCount} Completed
              </Badge>
              {completedCount > 0 && (
                <Button variant="ghost" size="sm" onClick={clearCompleted}>
                  Clear Completed
                </Button>
              )}
            </div>
          </div>

          {visibleJobs.length === 0 ? (
            <div className="py-10 text-center text-ledger">
              <p className="text-sm">No processing jobs yet</p>
              <p className="mt-1 text-xs">Start a processing job to see it here</p>
            </div>
          ) : (
            <div className="space-y-3">
              {visibleJobs.map((job) => (
                <div
                  key={job.id}
                  className="flex gap-4 border border-paper-dark bg-paper p-4 transition-colors hover:border-paper-deep"
                >
                  {/* Main Content */}
                  <div className="min-w-0 flex-1">
                    <div className="mb-2 flex items-center gap-3">
                      <h3 className="text-sm font-semibold text-carbon-deep">
                        {job.mode ? job.mode.replace('-', ' ').toUpperCase() : 'Processing'}
                      </h3>
                      <Badge variant={getStatusVariant(job.status)} size="sm">
                        {job.status}
                      </Badge>
                    </div>

                    {job.current_video && (
                      <p className="mb-1 text-xs font-medium text-carbon-soft">
                        {job.current_video}
                      </p>
                    )}

                    {job.videos_processed !== undefined && job.total_videos && (
                      <p className="mb-1 text-xs font-medium text-carbon">
                        {job.videos_processed} / {job.total_videos} videos
                      </p>
                    )}

                    {/* Progress bar */}
                    <div className="mt-2 flex items-center gap-3">
                      <div className="h-2 flex-1 overflow-hidden rounded-full bg-paper-dark">
                        <div
                          className={`h-full rounded-full transition-all duration-300 ${getStatusColor(job.status)}`}
                          style={{ width: `${job.progress || 0}%` }}
                        />
                      </div>
                      <span className="min-w-[40px] text-xs font-semibold text-carbon">
                        {job.progress || 0}%
                      </span>
                    </div>

                    {job.error && <p className="mt-2 text-xs text-stamp">{job.error}</p>}
                  </div>

                  {/* Actions & Times */}
                  <div className="flex shrink-0 flex-col items-end gap-2">
                    {(job.status === 'queued' || job.status === 'running') && (
                      <Button variant="destructive" size="sm" onClick={() => cancelJob(job.id)}>
                        Cancel
                      </Button>
                    )}
                    <div className="space-y-0.5 text-right">
                      {job.created_at && (
                        <p className="text-[11px] text-ledger">
                          Created: {formatTimestamp(job.created_at)}
                        </p>
                      )}
                      {job.started_at && (
                        <p className="text-[11px] text-ledger">
                          Duration: {formatDuration(job.started_at, job.completed_at)}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
