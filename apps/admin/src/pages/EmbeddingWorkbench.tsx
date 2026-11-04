import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft } from 'lucide-react';
import {
  Button,
  FaceCrop,
  Masthead,
  Stamp,
  bandFor,
  formatMmSs,
  LOCAL_API_OFFLINE_NOTICE,
  useCoverage,
  useSimilarity,
  useVideos,
  videoShortName,
} from '@mv/shared';
import type { Contestant, ConfusionPair } from '@mv/shared';
import { QUALITY_WORD, coverageFigures, isPair } from '@mv/shared/lib/pipeline';

type Tab = 'coverage' | 'detail' | 'confusion' | 'unmatched';
type RefreshMode = 'coverage-refresh' | 'embedding-update';

const tabs: { id: Tab; label: string }[] = [
  { id: 'coverage', label: '覆蓋率' },
  { id: 'detail', label: '詳情' },
  { id: 'confusion', label: '相似度' },
  { id: 'unmatched', label: '未配對' },
];

const QUALITIES = ['good', 'weak', 'missing'] as const;

const QUALITY_CELL: Record<Contestant['quality'], string> = {
  good: 'border-transparent',
  weak: 'border-carbon-deep/33',
  missing: 'border-stamp',
};
const QUALITY_SWATCH: Record<Contestant['quality'], string> = {
  good: 'bg-carbon',
  weak: 'bg-ink-muted',
  missing: 'bg-stamp',
};
const QUALITY_TONE: Record<Contestant['quality'], 'carbon' | 'muted' | 'stamp'> = {
  good: 'carbon',
  weak: 'muted',
  missing: 'stamp',
};

const SCALE_STEPS = ['bg-stamp/10', 'bg-stamp/30', 'bg-stamp/50', 'bg-stamp/70', 'bg-stamp'];

function heatmapCellSize(n: number): number {
  return Math.min(6, Math.floor(600 / n));
}

function Figure({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="flex flex-1 flex-col gap-1">
      <span className="font-kai text-[13px] text-carbon-soft">{label}</span>
      <span className="font-mono text-[28px] leading-[1.15] tabular-nums text-carbon-deep">
        {value}
      </span>
      <span className="font-kai text-[12px] text-ink-muted">{note}</span>
    </div>
  );
}

function StatRow({
  label,
  value,
  title,
}: {
  label: string;
  value: string | number;
  title?: string;
}) {
  return (
    <div className="flex h-7 flex-row items-center justify-between border-b border-carbon-deep/13">
      <dt className="font-kai text-[13px] text-carbon-soft">{label}</dt>
      <dd className="font-mono text-[12px] tabular-nums text-carbon-deep" title={title}>
        {value}
      </dd>
    </div>
  );
}

/** A contestant's portrait; a failed load leaves the tint showing rather than a broken image. */
function Face({
  contestant,
  className,
  alt = '',
}: {
  contestant: { id: string; portrait_url?: string | null };
  className: string;
  alt?: string;
}) {
  return (
    <span className={`block shrink-0 overflow-hidden rounded bg-tint ${className}`}>
      <img
        src={contestant.portrait_url ?? `/api/contestants/${contestant.id}/thumb/face`}
        alt={alt}
        loading="lazy"
        decoding="async"
        className="h-full w-full object-cover"
        onError={(e) => {
          e.currentTarget.style.visibility = 'hidden';
        }}
      />
    </span>
  );
}

interface ProcessingJob {
  id: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
  error?: string | null;
  current_video?: string | null;
}

interface RecognitionResult {
  video_id: string;
  timestamp: number;
  match_score: number | null;
  frame_number?: number | null;
  bbox?: [number, number, number, number] | null;
  detection_index?: number | null;
}

interface Notice {
  tone: 'ok' | 'error';
  text: string;
}

/** The refresh modes only exist on the local API; the Worker answers 404. */
class LocalApiUnavailableError extends Error {
  constructor() {
    super('本機 API 未連線');
    this.name = 'LocalApiUnavailableError';
  }
}

const POLL_INTERVAL_MS = 1500;
const POLL_TIMEOUT_MS = 15 * 60 * 1000;

async function waitForJob(jobId: string): Promise<ProcessingJob> {
  const deadline = Date.now() + POLL_TIMEOUT_MS;
  for (;;) {
    let res: Response;
    try {
      res = await fetch(`/api/processing/jobs/${encodeURIComponent(jobId)}`);
    } catch {
      throw new LocalApiUnavailableError();
    }
    if (!res.ok) throw new Error(`讀取工作狀態失敗：HTTP ${res.status}`);
    const job = (await res.json()) as ProcessingJob;
    if (job.status === 'completed') return job;
    if (job.status === 'failed' || job.status === 'cancelled') {
      throw new Error(job.error || `工作${job.status === 'failed' ? '失敗' : '已取消'}`);
    }
    if (Date.now() >= deadline) throw new Error('等待工作完成逾時（15 分鐘）');
    await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
  }
}

export function EmbeddingWorkbench() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<Tab>('coverage');
  const [selectedContestant, setSelectedContestant] = useState<Contestant | null>(null);
  const [hoveredCell, setHoveredCell] = useState<{
    row: number;
    col: number;
    x: number;
    y: number;
    text: string;
  } | null>(null);
  const [running, setRunning] = useState<RefreshMode | null>(null);
  const [notice, setNotice] = useState<Notice | null>(null);

  const heatmapCanvasRef = useRef<HTMLCanvasElement>(null);

  const { data: coverageData, isLoading, error } = useCoverage();
  const similarity = useSimilarity();
  const { data: videos = [] } = useVideos();

  const contestants = useMemo(() => coverageData?.contestants ?? [], [coverageData]);
  const contestantById = useMemo(() => new Map(contestants.map((c) => [c.id, c])), [contestants]);
  const summary = coverageData?.summary ?? null;
  const similarityData = similarity.matrix.data ?? null;
  const topPairs: ConfusionPair[] = similarity.pairs.data ?? [];
  const confusionLoading = similarity.matrix.isLoading || similarity.pairs.isLoading;

  const videoById = new Map(videos.map((v) => [v.id, v]));

  const {
    data: recognition,
    isLoading: detectionsLoading,
    error: detectionsError,
  } = useQuery<{
    results: RecognitionResult[];
  }>({
    queryKey: ['recognition-results', selectedContestant?.id],
    enabled: !!selectedContestant,
    queryFn: async () => {
      const contestantId = selectedContestant?.id;
      if (!contestantId) return { results: [] };
      const res = await fetch(
        `/api/recognition/results?contestant_id=${encodeURIComponent(contestantId)}`,
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return (await res.json()) as { results: RecognitionResult[] };
    },
    staleTime: 60 * 1000,
  });

  // Only detections whose reel is known can be cropped; an unresolved reel is not a card.
  // Eight, not twenty-four: with no pre-extracted crops in R2, each card seeks the reel and
  // cuts the box on a canvas, and the seeks are serialised per stream. The wait is linear in
  // card count, so the grid shows the first eight and stops.
  const detections = (recognition?.results ?? [])
    .filter((r) => videoById.has(r.video_id))
    .slice(0, 8);

  const runRefresh = useCallback(
    async (mode: RefreshMode) => {
      setRunning(mode);
      setNotice(null);
      try {
        let res: Response;
        try {
          res = await fetch('/api/processing/trigger', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode }),
          });
        } catch {
          throw new LocalApiUnavailableError();
        }
        if (res.status === 404) throw new LocalApiUnavailableError();
        if (!res.ok) {
          const detail = await res.text().catch(() => '');
          throw new Error(
            `觸發工作失敗：HTTP ${res.status}${detail ? ` — ${detail.slice(0, 160)}` : ''}`,
          );
        }
        const payload = (await res.json()) as { job_id?: string };
        if (!payload.job_id) throw new Error('本機 API 未回傳 job id');
        await waitForJob(payload.job_id);
        await Promise.all([
          queryClient.invalidateQueries({ queryKey: ['coverage'] }),
          queryClient.invalidateQueries({ queryKey: ['similarity-matrix'] }),
          queryClient.invalidateQueries({ queryKey: ['top-pairs'] }),
        ]);
        setNotice({
          tone: 'ok',
          text:
            mode === 'embedding-update'
              ? '參考向量已重建，覆蓋率與相似度已更新。'
              : '覆蓋率與相似度已重新計算。',
        });
      } catch (e) {
        if (e instanceof LocalApiUnavailableError) {
          setNotice({ tone: 'error', text: LOCAL_API_OFFLINE_NOTICE });
        } else {
          setNotice({ tone: 'error', text: e instanceof Error ? e.message : '操作失敗' });
        }
      } finally {
        setRunning(null);
      }
    },
    [queryClient],
  );

  const switchTab = useCallback(
    (tab: Tab) => {
      setActiveTab(tab);
      if (tab === 'confusion') similarity.load();
    },
    [similarity],
  );

  const selectContestantForDetail = useCallback((c: Contestant) => {
    setSelectedContestant(c);
    setActiveTab('detail');
  }, []);

  // Draw heatmap when data is available and tab is active
  const drawHeatmap = useCallback(() => {
    const canvas = heatmapCanvasRef.current;
    if (!canvas || !similarityData) return;

    const { matrix } = similarityData;
    const n = matrix.length;
    const cellSize = heatmapCellSize(n);
    const size = n * cellSize;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = size * dpr;
    canvas.height = size * dpr;
    canvas.style.width = `${size}px`;
    canvas.style.height = `${size}px`;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.scale(dpr, dpr);

    // Read the ink from the catalogue token rather than hardcoding a second red.
    const ink =
      getComputedStyle(canvas).getPropertyValue('--color-stamp').trim() || 'rgb(174, 59, 44)';
    for (let i = 0; i < n; i++) {
      for (let j = 0; j < n; j++) {
        const val = matrix[i][j];
        // globalAlpha ignores out-of-range values, so an unclamped negative cosine would keep
        // the previous cell's ink.
        const alpha = i === j ? 1.0 : Math.max(0, Math.min(1, val * 2));
        ctx.globalAlpha = alpha;
        ctx.fillStyle = ink;
        ctx.fillRect(j * cellSize, i * cellSize, cellSize, cellSize);
      }
    }
    ctx.globalAlpha = 1;
  }, [similarityData]);

  useEffect(() => {
    // The canvas mounts once both queries settle, which can be after the matrix arrives.
    if (activeTab === 'confusion' && similarityData && !confusionLoading) {
      drawHeatmap();
    }
  }, [activeTab, similarityData, confusionLoading, drawHeatmap]);

  const handleHeatmapHover = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      const canvas = heatmapCanvasRef.current;
      if (!similarityData || !canvas) return;

      const rect = canvas.getBoundingClientRect();
      const n = similarityData.matrix.length;
      const cellSize = heatmapCellSize(n);

      const col = Math.floor((e.clientX - rect.left) / cellSize);
      const row = Math.floor((e.clientY - rect.top) / cellSize);

      if (row >= 0 && row < n && col >= 0 && col < n) {
        const a = similarityData.labels[row].nickname;
        const b = similarityData.labels[col].nickname;
        const sim = similarityData.matrix[row][col];
        setHoveredCell({
          row,
          col,
          x: e.clientX - rect.left + 10,
          y: e.clientY - rect.top - 20,
          text: `${a} ↔ ${b}：${(sim * 100).toFixed(1)}%`,
        });
      }
    },
    [similarityData],
  );

  const hideHeatmapTooltip = useCallback(() => {
    setHoveredCell(null);
  }, []);

  const figures = summary ? coverageFigures(summary) : null;
  const heatmapN = similarityData?.matrix.length ?? 0;
  const hoveredLabels =
    hoveredCell && similarityData
      ? ([similarityData.labels[hoveredCell.row], similarityData.labels[hoveredCell.col]] as const)
      : null;

  return (
    <div className="flex min-h-full flex-1 flex-col gap-5 px-8 pb-5 pt-8">
      <Masthead title="向量" hint="檢查覆蓋率、重建參考向量">
        <div className="flex flex-row items-center gap-2">
          <Button onClick={() => void runRefresh('embedding-update')} disabled={running !== null}>
            {running === 'embedding-update' ? '重建中…' : '重建全部參考向量'}
          </Button>
          <Button
            variant="primary"
            onClick={() => void runRefresh('coverage-refresh')}
            disabled={running !== null}
          >
            {running === 'coverage-refresh' ? '更新中…' : '更新覆蓋率 / 相似度'}
          </Button>
        </div>
      </Masthead>

      {notice && (
        <div
          role={notice.tone === 'error' ? 'alert' : 'status'}
          className={`border-y py-2 font-kai text-[13px] ${
            notice.tone === 'error'
              ? 'border-stamp/33 text-stamp'
              : 'border-carbon-deep/13 text-carbon'
          }`}
        >
          {notice.text}
        </div>
      )}

      <div role="tablist" className="flex flex-row gap-5 border-b border-carbon-deep/13">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={activeTab === tab.id}
            className={`-mb-px cursor-pointer border-b-2 pb-2 font-kai text-[14px] leading-tight ${
              activeTab === tab.id
                ? 'border-stamp font-bold text-carbon-deep'
                : 'border-transparent text-carbon-soft hover:text-carbon-deep'
            }`}
            onClick={() => switchTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="py-12 text-center font-kai text-[14px] text-carbon-soft">
          正在讀取覆蓋率資料…
        </div>
      ) : error ? (
        <div role="alert" className="py-12 text-center font-mono text-[12px] text-stamp">
          {(error as Error).message}
        </div>
      ) : (
        <>
          {/* 覆蓋率 */}
          {activeTab === 'coverage' && summary && figures && (
            <>
              <div className="flex flex-row border-b border-carbon-deep/13 pb-4">
                <Figure label="覆蓋率" value={figures.covered} note={figures.coveredNote} />
                <Figure label="平均配對分數" value={figures.average} note="全部配對的餘弦平均" />
                <Figure label="辨識率" value={figures.rate} note={figures.rateNote} />
              </div>

              <div className="flex flex-row items-end justify-between">
                <h2 className="font-kai text-[18px] font-normal text-carbon-deep">參賽者</h2>
                <div className="flex flex-row items-center gap-4 font-kai text-[12px] text-carbon-soft">
                  {QUALITIES.map((q) => (
                    <span key={q} className="flex flex-row items-center gap-1.5">
                      <span aria-hidden className={`size-2 ${QUALITY_SWATCH[q]}`} />
                      {QUALITY_WORD[q]} <span className="font-mono tabular-nums">{summary[q]}</span>
                    </span>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-[repeat(auto-fill,minmax(132px,1fr))] gap-1">
                {contestants.map((c) => (
                  <button
                    key={c.id}
                    type="button"
                    className={`flex h-[51px] min-w-0 cursor-pointer flex-row items-center gap-2 rounded border p-1 text-left hover:bg-tint ${QUALITY_CELL[c.quality]}`}
                    title={`${c.avg_match_score.toFixed(4)} 餘弦平均`}
                    aria-label={`#${c.id} ${c.nickname}，${QUALITY_WORD[c.quality]}，查看詳情`}
                    onClick={() => selectContestantForDetail(c)}
                  >
                    {c.quality === 'missing' ? (
                      <span aria-hidden className="h-full w-11 shrink-0 rounded bg-tint" />
                    ) : (
                      <Face contestant={c} className="h-full w-11" />
                    )}
                    <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                      <span className="truncate font-kai text-[13px] leading-[1.15] text-carbon-deep">
                        {c.nickname}
                      </span>
                      <span className="flex flex-row justify-between gap-1 text-[12px] leading-tight">
                        <span className="font-mono tabular-nums text-ink-muted">#{c.id}</span>
                        {c.quality === 'good' ? (
                          <span className="font-mono tabular-nums text-carbon-soft">
                            {c.avg_match_score.toFixed(2)}
                          </span>
                        ) : (
                          <span
                            className={`font-kai ${
                              c.quality === 'missing' ? 'text-stamp' : 'text-ink-muted'
                            }`}
                          >
                            {QUALITY_WORD[c.quality]}
                          </span>
                        )}
                      </span>
                    </span>
                  </button>
                ))}
              </div>
            </>
          )}

          {/* 詳情 */}
          {activeTab === 'detail' &&
            (selectedContestant ? (
              <>
                <div className="flex flex-row items-center gap-3">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="-ml-3"
                    onClick={() => setActiveTab('coverage')}
                  >
                    <ArrowLeft aria-hidden className="size-4" />
                    返回
                  </Button>
                  <h2 className="min-w-0 flex-1 truncate font-kai text-[18px] font-normal text-carbon-deep">
                    <span className="font-mono tabular-nums">#{selectedContestant.id}</span>{' '}
                    {selectedContestant.name}
                  </h2>
                  <Stamp tone={QUALITY_TONE[selectedContestant.quality]}>
                    {QUALITY_WORD[selectedContestant.quality]}
                  </Stamp>
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => void runRefresh('coverage-refresh')}
                    disabled={running !== null}
                  >
                    {running === 'coverage-refresh' ? '重新生成中…' : '重新生成向量'}
                  </Button>
                </div>

                <div className="flex flex-row gap-10">
                  <div className="flex w-[340px] shrink-0 flex-col gap-5">
                    <section className="flex flex-col gap-2">
                      <h3 className="font-kai text-[18px] font-normal text-carbon-deep">
                        參考來源
                      </h3>
                      <div className="flex flex-row gap-3">
                        <Face
                          contestant={selectedContestant}
                          alt={selectedContestant.name}
                          className="h-24 w-[78px]"
                        />
                        <div className="flex min-w-0 flex-col gap-1">
                          <span className="font-kai text-[15px] text-carbon-deep">
                            {selectedContestant.nickname}
                          </span>
                          <span className="font-kai text-[13px] text-carbon-soft">
                            {selectedContestant.name}
                          </span>
                          <span className="font-kai text-[12px] text-ink-muted">
                            參考相{' '}
                            <span className="font-mono tabular-nums">
                              {selectedContestant.reference_count}
                            </span>{' '}
                            張
                          </span>
                        </div>
                      </div>
                    </section>
                    <section className="flex flex-col gap-2">
                      <h3 className="font-kai text-[18px] font-normal text-carbon-deep">統計</h3>
                      <dl className="flex flex-col">
                        <StatRow
                          label="平均配對分數"
                          value={selectedContestant.avg_match_score.toFixed(2)}
                          title={`${selectedContestant.avg_match_score.toFixed(4)} 餘弦平均`}
                        />
                        <StatRow
                          label="最高配對分數"
                          value={selectedContestant.max_match_score.toFixed(2)}
                          title={`${selectedContestant.max_match_score.toFixed(4)} 餘弦最高`}
                        />
                        <StatRow label="偵測次數" value={selectedContestant.detection_count} />
                        <StatRow label="出現影片" value={selectedContestant.videos_seen_in} />
                        <StatRow label="參考相" value={selectedContestant.reference_count} />
                      </dl>
                    </section>
                  </div>

                  <section className="flex min-w-0 flex-1 flex-col gap-2">
                    <div className="flex flex-row items-end justify-between gap-3">
                      <h3 className="font-kai text-[18px] font-normal text-carbon-deep">
                        影片中偵測到的臉
                      </h3>
                      {detectionsLoading ? (
                        <span className="font-kai text-[12px] text-ink-muted">調閱中…</span>
                      ) : (
                        <span className="font-mono text-[12px] tabular-nums text-ink-muted">
                          {detections.length} / 8
                        </span>
                      )}
                    </div>
                    {detectionsLoading ? (
                      <p className="border-t border-carbon-deep/13 py-8 text-center font-kai text-[13px] text-carbon-soft">
                        正在調閱出場紀錄…
                      </p>
                    ) : detectionsError ? (
                      <p
                        role="alert"
                        className="border-t border-carbon-deep/13 py-8 text-center font-mono text-[12px] text-stamp"
                      >
                        {detectionsError instanceof Error
                          ? detectionsError.message
                          : '無法讀取出場紀錄'}
                      </p>
                    ) : detections.length === 0 ? (
                      <p className="border-t border-carbon-deep/13 py-8 text-center font-kai text-[13px] text-carbon-soft">
                        沒有可對應到影片的面孔紀錄。
                      </p>
                    ) : (
                      <div className="grid grid-cols-4 gap-x-3 gap-y-4 border-t border-carbon-deep/13 pt-3">
                        {detections.map((r, i) => {
                          const video = videoById.get(r.video_id);
                          return (
                            <div
                              key={`${r.video_id}-${r.frame_number ?? r.timestamp}-${i}`}
                              className="flex min-w-0 flex-col gap-1"
                            >
                              <div className="flex h-[120px] items-center justify-center overflow-hidden rounded bg-tint">
                                <FaceCrop
                                  videoId={r.video_id}
                                  frameNumber={r.frame_number ?? undefined}
                                  detectionIndex={r.detection_index ?? undefined}
                                  timestamp={r.timestamp}
                                  bbox={r.bbox ?? null}
                                  streamUrl={video?.stream_url}
                                  width={160}
                                />
                              </div>
                              <div className="flex flex-row items-center justify-between gap-1 font-mono text-[12px] tabular-nums text-carbon-soft">
                                <span>{formatMmSs(r.timestamp)}</span>
                                <span className="flex flex-row items-center gap-1">
                                  {r.match_score != null && (
                                    <span title={`${r.match_score.toFixed(4)} 餘弦`}>
                                      {r.match_score.toFixed(2)}
                                    </span>
                                  )}
                                  <Stamp band={bandFor(r.match_score)} />
                                </span>
                              </div>
                              <div
                                className="truncate font-kai text-[12px] text-ink-muted"
                                title={video?.name}
                              >
                                {video ? videoShortName(video.name) : ''}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </section>
                </div>
              </>
            ) : (
              <div className="py-12 text-center font-kai">
                <p className="mb-4 text-[14px] text-carbon-soft">
                  在覆蓋率選一位參賽者，就會在這裡顯示詳情。
                </p>
                <Button size="sm" onClick={() => setActiveTab('coverage')}>
                  前往覆蓋率
                </Button>
              </div>
            ))}

          {/* 相似度 */}
          {activeTab === 'confusion' &&
            (confusionLoading ? (
              <div className="py-12 text-center font-kai text-[14px] text-carbon-soft">
                正在讀取相似度資料…
              </div>
            ) : similarityData ? (
              <div className="flex flex-row gap-10">
                <section className="flex shrink-0 flex-col gap-2">
                  <h2 className="font-kai text-[18px] font-normal text-carbon-deep">
                    參賽者兩兩相似度（{similarityData.stats.contestant_count} ×{' '}
                    {similarityData.stats.contestant_count}）
                  </h2>
                  <div className="relative self-start" onMouseLeave={hideHeatmapTooltip}>
                    <canvas
                      ref={heatmapCanvasRef}
                      className="block outline-1 outline-carbon-deep/33"
                      onMouseMove={handleHeatmapHover}
                    />
                    {hoveredCell && (
                      <>
                        <div
                          aria-hidden
                          className="pointer-events-none absolute border border-carbon-deep"
                          style={{
                            left: hoveredCell.col * heatmapCellSize(heatmapN),
                            top: hoveredCell.row * heatmapCellSize(heatmapN),
                            width: heatmapCellSize(heatmapN),
                            height: heatmapCellSize(heatmapN),
                          }}
                        />
                        <div
                          className="pointer-events-none absolute z-10 whitespace-nowrap rounded border border-carbon bg-ground px-2 py-1 font-kai text-[12px] text-carbon-deep"
                          style={{
                            left: hoveredCell.x,
                            top: hoveredCell.y,
                            // Near the right edge the tip opens leftward, so it stays over the map.
                            transform:
                              hoveredCell.col > (heatmapN * 2) / 3
                                ? 'translateX(calc(-100% - 20px))'
                                : undefined,
                          }}
                        >
                          {hoveredCell.text}
                        </div>
                      </>
                    )}
                  </div>
                  <div className="flex flex-row items-center gap-2 font-kai text-[12px] text-ink-muted">
                    <span>低相似度</span>
                    <div aria-hidden className="flex h-2 flex-1 flex-row">
                      {SCALE_STEPS.map((step) => (
                        <div key={step} className={`flex-1 ${step}`} />
                      ))}
                    </div>
                    <span>高相似度</span>
                  </div>
                </section>

                <section className="flex min-w-0 flex-1 flex-col gap-2">
                  <h2 className="font-kai text-[18px] font-normal text-carbon-deep">
                    最易混淆的配對
                  </h2>
                  <div className="flex flex-col">
                    {topPairs.map((pair, i) => (
                      <button
                        key={`${pair.contestant_a.id}-${pair.contestant_b.id}`}
                        type="button"
                        className={`flex h-8 w-full cursor-pointer flex-row items-center gap-2 rounded border-b border-carbon-deep/13 px-2 text-left hover:bg-tint ${
                          hoveredLabels && isPair(pair, hoveredLabels[0].id, hoveredLabels[1].id)
                            ? 'bg-tint'
                            : ''
                        }`}
                        onClick={() => {
                          const c = contestantById.get(pair.contestant_a.id);
                          if (c) selectContestantForDetail(c);
                        }}
                      >
                        <span className="w-7 shrink-0 font-mono text-[12px] tabular-nums text-ink-muted">
                          #{i + 1}
                        </span>
                        <span className="flex shrink-0 flex-row gap-0.5">
                          {[pair.contestant_a, pair.contestant_b].map((side) => (
                            <Face
                              key={side.id}
                              contestant={contestantById.get(side.id) ?? side}
                              className="size-7"
                            />
                          ))}
                        </span>
                        <span className="min-w-0 flex-1 truncate font-kai text-[14px] text-carbon-deep">
                          {pair.contestant_a.nickname} ↔ {pair.contestant_b.nickname}
                        </span>
                        <span className="font-mono text-[12px] tabular-nums text-carbon-soft">
                          {(pair.similarity * 100).toFixed(1)}%
                        </span>
                      </button>
                    ))}
                  </div>
                </section>
              </div>
            ) : (
              <div className="py-12 text-center font-kai text-[14px] text-carbon-soft">
                沒有相似度資料。請執行{' '}
                <code className="font-mono text-[13px]">python scripts/compute_similarity.py</code>
              </div>
            ))}

          {/* 未配對 */}
          {activeTab === 'unmatched' && (
            <div className="py-12 text-center font-kai">
              <h2 className="mb-2 text-[18px] font-normal text-carbon-deep">未配對的臉</h2>
              <p className="text-[14px] text-carbon-soft">
                執行分群流程（第五階段）後，未能辨識的臉會分群顯示在這裡。
              </p>
              <p className="mt-1 text-[12px] text-ink-muted">
                需要 <span className="font-mono">T0.4</span>（儲存未配對向量）及{' '}
                <span className="font-mono">T0.5</span>（HDBSCAN 分群）
              </p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
