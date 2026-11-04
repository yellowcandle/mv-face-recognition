import { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import type { ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { LoaderCircle } from 'lucide-react';
import { Button, Masthead, adminFetch, formatMmSs, LOCAL_API_OFFLINE_NOTICE } from '@mv/shared';
import {
  formatJobCreated,
  jobModeLabel,
  jobProgressLine,
  jobStatusLabel,
} from '@mv/shared/lib/pipeline';

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

const STATUS_INK: Record<ProcessingJob['status'], string> = {
  queued: 'text-carbon-soft',
  running: 'text-carbon',
  completed: 'text-ink-muted',
  failed: 'text-stamp',
  cancelled: 'text-ink-muted',
};

const BAR_FILL: Record<ProcessingJob['status'], string> = {
  queued: 'bg-carbon',
  running: 'bg-carbon',
  completed: 'bg-carbon',
  failed: 'bg-stamp',
  cancelled: 'bg-ink-muted',
};

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
      <div className="flex h-[72px] flex-col gap-1">
        <h2 className="font-kai text-[18px] font-normal text-carbon-deep">{title}</h2>
        <p className="font-kai text-[14px] leading-[1.4] text-carbon-soft">{description}</p>
      </div>
      <div className="flex h-[60px] flex-row items-end gap-2">{controls}</div>
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
  // Coverage refresh needs the local API; the Worker has no path into the KV read model.
  const [isEdge, setIsEdge] = useState(false);
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
      if (!res.ok) throw new Error(await failureMessage(res, '無法開始處理'));
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
      setError(e instanceof Error ? e.message : '無法開始處理');
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
      if (!res.ok) throw new Error(await failureMessage(res, '無法取消工作'));
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
      setError(e instanceof Error ? e.message : '無法取消工作');
    }
  }

  async function clearCompleted() {
    try {
      const res = await adminFetch('/admin/api/processing/clear-completed', { method: 'POST' });
      if (!res.ok) throw new Error(await failureMessage(res, '無法清除已完成工作'));
      // The server drops every terminal record (completed, failed, cancelled); a local filter
      // would keep the rows it disagrees about until the next poll.
      await fetchJobs();
    } catch (e) {
      setError(e instanceof Error ? e.message : '無法清除已完成工作');
    }
  }

  const unavailableBecauseProcessing = !jobsAvailable || isProcessing;
  const startingLabel = '啟動中…';

  return (
    <div className="flex min-h-full flex-1 flex-col gap-6 px-8 pb-5 pt-8">
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
      {error && <Banner>{error}</Banner>}

      <div className="flex flex-row border-y border-carbon-deep/13 py-5">
        <ActionColumn
          className="min-w-0 flex-1 border-r border-carbon-deep/13 pr-6"
          title="首次處理"
          description="用本機流程處理這台機器上的所有影片"
          does={[
            '處理所有未處理的影片',
            '偵測並辨識人臉',
            '可用時啟用硬件加速',
            '結果寫入 local_output/',
          ]}
          controls={
            <>
              <div className="flex min-w-0 flex-1 flex-col gap-1">
                <label htmlFor="source-reel" className="font-kai text-[12px] text-ink-muted">
                  來源影片
                </label>
                <select
                  id="source-reel"
                  value={selectedVideo}
                  onChange={(e) => setSelectedVideo(e.target.value)}
                  disabled={!jobsAvailable}
                  className="field field-select h-10 w-full disabled:opacity-45"
                >
                  <option value="">全部來源影片</option>
                  {videoOptions.map((v) => (
                    <option key={v.filename} value={v.filename}>
                      {v.filename} ({v.size_mb.toFixed(1)} MB)
                    </option>
                  ))}
                </select>
              </div>
              <Button
                variant="primary"
                onClick={startInitialProcessing}
                disabled={unavailableBecauseProcessing}
              >
                {isProcessing ? startingLabel : '開始處理'}
              </Button>
            </>
          }
        />

        <ActionColumn
          className="w-[296px] shrink-0 border-r border-carbon-deep/13 px-6"
          title="更新向量"
          description="由硬碟上揀選好的參考相重建參考向量"
          does={[
            '提升人臉辨識準確度',
            '重建 reference_embeddings.npz',
            '快速重算向量',
            '自動更新覆蓋率',
          ]}
          controls={
            <Button
              className="w-full"
              onClick={startEmbeddingUpdate}
              disabled={unavailableBecauseProcessing}
            >
              {isProcessing ? startingLabel : '更新向量'}
            </Button>
          }
        />

        <ActionColumn
          className="w-[296px] shrink-0 pl-6"
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
              className="w-full"
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
        <div className="flex flex-row items-center justify-between">
          <h2 className="font-kai text-[18px] font-normal text-carbon-deep">處理工作</h2>
          <div className="flex h-8 flex-row items-center gap-4 font-kai text-[13px] text-carbon-soft">
            <span>
              <span className="font-mono tabular-nums">{activeCount}</span> 進行中
            </span>
            <span>
              <span className="font-mono tabular-nums">{completedCount}</span> 已完成
            </span>
            {completedCount > 0 && (
              <Button size="sm" onClick={clearCompleted}>
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
                  className="flex flex-row items-center gap-6 border-t border-carbon-deep/13 py-2"
                >
                  <div className="flex w-[280px] shrink-0 flex-col gap-0.5">
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

                  <div className="flex w-[136px] shrink-0 flex-col items-end gap-0.5 whitespace-nowrap font-mono text-[12px] tabular-nums text-ink-muted">
                    {job.created_at && <span>建立 {formatJobCreated(job.created_at)}</span>}
                    {job.started_at && (
                      <span>歷時 {formatDuration(job.started_at, job.completed_at)}</span>
                    )}
                  </div>

                  <div className="flex h-8 w-16 shrink-0 flex-row justify-end">
                    {(job.status === 'queued' || job.status === 'running') && (
                      <Button variant="destructive" size="sm" onClick={() => cancelJob(job.id)}>
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
