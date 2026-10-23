import { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import {
  Card,
  Badge,
  Button,
  Masthead,
  adminFetch,
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

/** FastAPI answers with `detail`; Worker handlers use `error` (string or `{message}`). */
async function failureMessage(res: Response, fallback: string): Promise<string> {
  try {
    const body: unknown = await res.json();
    if (body && typeof body === 'object') {
      const values = [
        'detail' in body ? body.detail : undefined,
        'error' in body ? body.error : undefined,
      ];
      for (const value of values) {
        if (typeof value === 'string' && value) return value;
        if (value && typeof value === 'object' && 'message' in value) {
          const message = value.message;
          if (typeof message === 'string' && message) return message;
        }
      }
    }
  } catch {
    /* non-JSON body: fall through to the generic message */
  }
  return `${fallback} (HTTP ${res.status})`;
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
  const [error, setError] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const pollingRef = useRef<number | undefined>(undefined);
  // Last status per job, so a coverage/embedding job that just finished refreshes the read model.
  const seenStatusRef = useRef<Map<string, ProcessingJob['status']>>(new Map());
  // KV listing is eventually consistent, so a job created a second ago can be missing from it.
  // Hold the row the trigger returned until a poll reports that id.
  const [pendingJobs, setPendingJobs] = useState<ProcessingJob[]>([]);
  const visibleJobs = useMemo(() => {
    const listed = new Set(jobs.map((job) => job.id));
    return [...pendingJobs.filter((job) => !listed.has(job.id)), ...jobs];
  }, [jobs, pendingJobs]);

  const activeCount = useMemo(
    () => visibleJobs.filter((j) => j.status === 'running' || j.status === 'queued').length,
    [visibleJobs],
  );
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
        return;
      }
      if (!res.ok) return;
      setJobsAvailable(true);
      const data = await res.json();
      const jobList = data.jobs || data || [];
      const next: ProcessingJob[] = Array.isArray(jobList) ? jobList : [];
      setJobs(next);
      const listed = new Set(next.map((job) => job.id));
      setPendingJobs((prev) =>
        prev.length === 0 ? prev : prev.filter((job) => !listed.has(job.id)),
      );

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
      setJobsAvailable(false);
      console.error('Failed to fetch jobs:', e);
    }
  }, [queryClient]);

  // Source reels for the picker. The Worker has no local filesystem, so it publishes the
  // processed list instead; the local API knows what is on disk. A failure leaves the
  // "all videos" default.
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const statusRes = await adminFetch('/admin/api/system/status');
        const status: unknown = statusRes.ok ? await statusRes.json() : null;
        const isEdge =
          !!status &&
          typeof status === 'object' &&
          'mode' in status &&
          status.mode === 'edge';
        const res = await adminFetch(
          isEdge ? '/admin/api/videos/processed/list' : '/admin/api/videos/local',
        );
        if (!res.ok) return;
        const data: unknown = await res.json();
        let list: unknown[] | null = null;
        if (Array.isArray(data)) list = data;
        else if (data && typeof data === 'object' && 'videos' in data && Array.isArray(data.videos)) {
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

  async function trigger(mode: 'initial' | 'embedding-update' | 'coverage-refresh') {
    setIsProcessing(true);
    setError(null);
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
      if (!res.ok) throw new Error(await failureMessage(res, 'Failed to start processing'));
      const started = (await res.json()) as {
        job_id?: string;
        status?: ProcessingJob['status'];
        total_videos?: number;
      };
      if (typeof started.job_id === 'string' && started.job_id !== '') {
        const row: ProcessingJob = {
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
        };
        setPendingJobs((prev) => [row, ...prev.filter((job) => job.id !== row.id)]);
      }
      await fetchJobs();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to start processing');
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
      if (!res.ok) throw new Error(await failureMessage(res, 'Failed to cancel job'));
      // The list lags the write, so a row still pending locally must not keep saying `queued`.
      setPendingJobs((prev) =>
        prev.map((job) =>
          job.id === jobId
            ? { ...job, status: 'cancelled', progress: 100, completed_at: Date.now() }
            : job,
        ),
      );
      await fetchJobs();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to cancel job');
    }
  }

  async function clearCompleted() {
    try {
      const res = await adminFetch('/admin/api/processing/clear-completed', { method: 'POST' });
      if (res.ok) {
        setJobs((prev) => prev.filter((j) => j.status !== 'completed'));
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to clear completed jobs');
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col px-9 pb-6 pt-7">
      <Masthead eyebrow="BACK OFFICE · PIPELINE" title="處理" latin="VIDEO PROCESSING & CACHE" size="md" />

      <div className="mt-4 h-px bg-carbon/45" />

      <div className="flex min-h-0 flex-1 flex-col gap-6 pt-5">
        {!jobsAvailable && (
          <div className="border border-stamp/50 bg-stamp/5 px-4 py-3 font-kai text-[13px] text-stamp">
            {LOCAL_API_OFFLINE_NOTICE}
          </div>
        )}

        {/* Error Banner */}
        {error && (
          <div className="border border-stamp/50 bg-stamp/5 px-4 py-3 font-kai text-[13px] text-stamp">
            {error}
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
              <h2 className="text-base font-semibold text-carbon-deep">Coverage &amp; Similarity</h2>
              <span className="h-2 w-2 rounded-full bg-carbon" />
            </div>
            <p className="mb-4 text-sm leading-relaxed text-carbon-soft">
              Recompute embedding coverage, the cosine matrix and the closest pairs
            </p>
            <Button
              variant="secondary"
              onClick={startCoverageRefresh}
              disabled={!jobsAvailable || isProcessing}
              className="mb-4 w-full"
            >
              {isProcessing ? 'Starting...' : '重新計算覆蓋率與相似度'}
            </Button>
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
