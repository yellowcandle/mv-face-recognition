import { useState, useRef, useEffect, useCallback } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  BAND_STAMP,
  Badge,
  Button,
  Card,
  FaceCrop,
  Masthead,
  bandFor,
  formatMmSs,
  LOCAL_API_OFFLINE_NOTICE,
  useCoverage,
  useSimilarity,
  useVideos,
} from '@mv/shared';
import type { Contestant, ConfusionPair } from '@mv/shared';

type Tab = 'coverage' | 'detail' | 'confusion' | 'unmatched';
type RefreshMode = 'coverage-refresh' | 'embedding-update';

const tabs: { id: Tab; label: string }[] = [
  { id: 'coverage', label: 'Coverage' },
  { id: 'detail', label: 'Detail' },
  { id: 'confusion', label: 'Confusion' },
  { id: 'unmatched', label: 'Unmatched' },
];

/** Quality is a stamp, not a status light: same ink mapping as the cast register. */
const QUALITY_CELL: Record<Contestant['quality'], string> = {
  good: 'border-carbon bg-carbon/5 hover:bg-carbon/10',
  weak: 'border-stamp bg-stamp/5 hover:bg-stamp/10',
  missing: 'border-ledger bg-ledger/5 hover:bg-ledger/10',
};
const QUALITY_INK: Record<Contestant['quality'], string> = {
  good: 'text-carbon border-carbon',
  weak: 'text-stamp border-stamp',
  missing: 'text-ledger border-ledger',
};
const QUALITY_DOT: Record<Contestant['quality'], string> = {
  good: 'bg-carbon',
  weak: 'bg-stamp',
  missing: 'bg-ledger',
};
const QUALITY_WORD: Record<Contestant['quality'], string> = {
  good: '清楚',
  weak: '偏弱',
  missing: '缺',
};

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
  const [heatmapTooltip, setHeatmapTooltip] = useState({ visible: false, x: 0, y: 0, text: '' });
  const [running, setRunning] = useState<RefreshMode | null>(null);
  const [notice, setNotice] = useState<Notice | null>(null);

  const heatmapCanvasRef = useRef<HTMLCanvasElement>(null);

  const { data: coverageData, isLoading, error } = useCoverage();
  const similarity = useSimilarity();
  const { data: videos = [] } = useVideos();

  const contestants = coverageData?.contestants ?? [];
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
    const cellSize = Math.min(6, Math.floor(600 / n));
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
        const alpha = i === j ? 1.0 : Math.min(1, val * 2);
        ctx.globalAlpha = alpha;
        ctx.fillStyle = ink;
        ctx.fillRect(j * cellSize, i * cellSize, cellSize, cellSize);
      }
    }
    ctx.globalAlpha = 1;
  }, [similarityData]);

  useEffect(() => {
    if (activeTab === 'confusion' && similarityData) {
      drawHeatmap();
    }
  }, [activeTab, similarityData, drawHeatmap]);

  const handleHeatmapHover = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      const canvas = heatmapCanvasRef.current;
      if (!similarityData || !canvas) return;

      const rect = canvas.getBoundingClientRect();
      const n = similarityData.matrix.length;
      const cellSize = Math.min(6, Math.floor(600 / n));

      const col = Math.floor((e.clientX - rect.left) / cellSize);
      const row = Math.floor((e.clientY - rect.top) / cellSize);

      if (row >= 0 && row < n && col >= 0 && col < n) {
        const a = similarityData.labels[row].nickname;
        const b = similarityData.labels[col].nickname;
        const sim = similarityData.matrix[row][col];
        setHeatmapTooltip({
          visible: true,
          x: e.clientX - rect.left + 10,
          y: e.clientY - rect.top - 20,
          text: `${a} <-> ${b}: ${(sim * 100).toFixed(1)}%`,
        });
      }
    },
    [similarityData],
  );

  const hideHeatmapTooltip = useCallback(() => {
    setHeatmapTooltip((prev) => ({ ...prev, visible: false }));
  }, []);

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-5 px-9 pb-8 pt-7">
      <Masthead
        eyebrow="BACK OFFICE · EMBEDDINGS"
        title="向量"
        latin="EMBEDDING WORKBENCH"
        size="md"
      >
        <Button
          variant="primary"
          size="sm"
          onClick={() => void runRefresh('coverage-refresh')}
          disabled={running !== null}
        >
          {running === 'coverage-refresh' ? '更新中…' : '更新覆蓋率 / 相似度'}
        </Button>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => void runRefresh('embedding-update')}
          disabled={running !== null}
        >
          {running === 'embedding-update' ? '重建中…' : '重建全部參考向量'}
        </Button>
      </Masthead>

      <div className="h-px bg-carbon/45" />

      {notice && (
        <div
          className={`border px-4 py-3 font-kai text-[13px] ${
            notice.tone === 'error'
              ? 'border-stamp/50 bg-stamp/10 text-stamp'
              : 'border-carbon/45 bg-carbon/5 text-carbon'
          }`}
        >
          {notice.text}
        </div>
      )}

      {/* Tab Bar */}
      <div className="flex rounded-full bg-paper-light p-1">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={`flex-1 cursor-pointer rounded-full border-none px-4 py-2 text-sm font-medium transition-all ${
              activeTab === tab.id
                ? 'bg-stamp font-semibold text-white'
                : 'bg-transparent text-carbon-soft hover:text-carbon-deep'
            }`}
            onClick={() => switchTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Loading / Error */}
      {isLoading ? (
        <div className="py-12 text-center text-carbon-soft">Loading coverage data...</div>
      ) : error ? (
        <div className="py-12 text-center font-mono text-[12px] text-stamp">
          {(error as Error).message}
        </div>
      ) : (
        <>
          {/* COVERAGE TAB */}
          {activeTab === 'coverage' && summary && (
            <>
              {/* Stats row */}
              <div className="flex gap-4">
                <div className="flex flex-1 flex-col gap-2 border border-paper-dark bg-paper-light p-5">
                  <span className="font-mono text-[11px] font-semibold tracking-[2px] text-carbon-soft">
                    COVERAGE
                  </span>
                  <div className="flex items-baseline gap-2">
                    <span className="text-[32px] font-semibold text-carbon-deep">
                      {summary.good + summary.weak}/{summary.total}
                    </span>
                    <span className="text-base text-carbon-soft">
                      {(((summary.good + summary.weak) / summary.total) * 100).toFixed(0)}%
                    </span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-paper-dark">
                    <div
                      className="h-full rounded-full bg-stamp transition-[width] duration-300"
                      style={{ width: `${((summary.good + summary.weak) / summary.total) * 100}%` }}
                    />
                  </div>
                </div>
                <div className="flex flex-1 flex-col gap-2 border border-paper-dark bg-paper-light p-5">
                  <span className="font-mono text-[11px] font-semibold tracking-[2px] text-carbon-soft">
                    AVG MATCH SCORE
                  </span>
                  <div className="flex items-baseline gap-2">
                    <span className="text-[32px] font-semibold text-carbon-deep">
                      {summary.avg_match_score.toFixed(2)}
                    </span>
                  </div>
                </div>
                <div className="flex flex-1 flex-col gap-2 border border-paper-dark bg-paper-light p-5">
                  <span className="font-mono text-[11px] font-semibold tracking-[2px] text-carbon-soft">
                    RECOGNITION RATE
                  </span>
                  <div className="flex items-baseline gap-2">
                    <span className="text-[32px] font-semibold text-carbon-deep">
                      {(summary.recognition_rate * 100).toFixed(1)}%
                    </span>
                  </div>
                </div>
              </div>

              {/* Grid header */}
              <div className="flex flex-wrap items-center justify-between gap-4">
                <span className="text-base font-semibold text-carbon-deep">Contestants</span>
                <div className="flex flex-wrap items-center gap-4">
                  <div className="flex gap-4 text-xs text-carbon-soft">
                    {(['good', 'weak', 'missing'] as const).map((q) => (
                      <span key={q} className="flex items-center gap-1.5">
                        <span className={`inline-block h-2 w-2 rounded-full ${QUALITY_DOT[q]}`} />{' '}
                        {q.charAt(0).toUpperCase() + q.slice(1)} ({summary[q]})
                      </span>
                    ))}
                  </div>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => void runRefresh('coverage-refresh')}
                    disabled={running !== null}
                  >
                    {running === 'coverage-refresh' ? '計算中…' : '重新計算覆蓋率與相似度'}
                  </Button>
                </div>
              </div>

              {/* Contestant grid */}
              <div className="grid grid-cols-4 gap-1.5">
                {contestants.map((c) => (
                  <button
                    key={c.id}
                    type="button"
                    className={`flex cursor-pointer flex-col items-center gap-0.5 rounded border px-1.5 py-2.5 transition-all hover:-translate-y-px ${QUALITY_CELL[c.quality]}`}
                    onClick={() => selectContestantForDetail(c)}
                  >
                    <span className="font-mono text-[11px] text-ledger">#{c.id}</span>
                    <span className="max-w-full overflow-hidden text-ellipsis whitespace-nowrap text-center text-[13px] font-semibold text-carbon-deep">
                      {c.nickname}
                    </span>
                    <span
                      className="font-mono text-[11px] text-carbon-soft"
                      title={`${c.avg_match_score.toFixed(4)} cosine average`}
                    >
                      {c.avg_match_score.toFixed(2)}
                    </span>
                    <span
                      className={`mt-0.5 -rotate-2 border px-1 py-0.5 font-kai text-[9px] tracking-[0.1em] ${QUALITY_INK[c.quality]}`}
                    >
                      {QUALITY_WORD[c.quality]}
                    </span>
                  </button>
                ))}
              </div>
            </>
          )}

          {/* DETAIL TAB */}
          {activeTab === 'detail' && (
            <>
              {selectedContestant ? (
                <>
                  {/* Detail header */}
                  <div className="flex items-center gap-3">
                    <button
                      type="button"
                      className="cursor-pointer rounded-none border border-paper-deep bg-transparent px-3 py-1.5 text-[13px] text-carbon-soft hover:border-ledger hover:text-carbon-deep"
                      onClick={() => setActiveTab('coverage')}
                    >
                      &larr; Back
                    </button>
                    <h2 className="m-0 flex-1 text-xl font-semibold text-carbon-deep">
                      #{selectedContestant.id} {selectedContestant.name}
                    </h2>
                    <Badge
                      variant={
                        selectedContestant.quality === 'good'
                          ? 'success'
                          : selectedContestant.quality === 'weak'
                            ? 'warning'
                            : 'error'
                      }
                    >
                      {selectedContestant.quality}
                    </Badge>
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={() => void runRefresh('coverage-refresh')}
                      disabled={running !== null}
                    >
                      {running === 'coverage-refresh' ? '重新生成中…' : '重新生成 Embedding'}
                    </Button>
                  </div>

                  {/* Detail layout */}
                  <div className="flex gap-6">
                    {/* Left panel */}
                    <div className="w-[340px] shrink-0">
                      <Card padding="none">
                        <div className="p-5">
                          <h3 className="mb-3 text-sm font-semibold text-carbon-deep">
                            Reference Sources
                          </h3>
                          <div className="mb-3 flex flex-row gap-3">
                            <div className="h-[96px] w-[78px] shrink-0 overflow-hidden border border-carbon/45 bg-paper-dark">
                              <img
                                src={
                                  selectedContestant.portrait_url ??
                                  `/api/contestants/${selectedContestant.id}/thumb/face`
                                }
                                alt={selectedContestant.name}
                                className="h-full w-full object-cover"
                                onError={(e) => {
                                  (e.target as HTMLImageElement).style.visibility = 'hidden';
                                }}
                              />
                            </div>
                            <div className="flex min-w-0 flex-col gap-1">
                              <span className="font-kai text-[15px] font-bold text-carbon-deep">
                                {selectedContestant.nickname}
                              </span>
                              <span className="font-kai text-[12px] text-carbon-soft">
                                {selectedContestant.name}
                              </span>
                              <span className="font-mono text-[9px] tracking-[0.14em] text-ledger">
                                參考相 {selectedContestant.reference_count} 張
                              </span>
                              <span className="font-mono text-[9px] tracking-[0.14em] text-ledger">
                                AVG {selectedContestant.avg_match_score.toFixed(2)} · MAX{' '}
                                {selectedContestant.max_match_score.toFixed(2)}
                              </span>
                            </div>
                          </div>
                        </div>
                        <div className="border-t border-paper-dark p-5">
                          <h3 className="mb-3 text-sm font-semibold text-carbon-deep">Stats</h3>
                          <div className="flex justify-between border-b border-paper-dark py-2 text-[13px] text-carbon-soft">
                            <span>Avg Match Score</span>
                            <strong
                              className="text-carbon-deep"
                              title={`${selectedContestant.avg_match_score.toFixed(4)} cosine average`}
                            >
                              {selectedContestant.avg_match_score.toFixed(2)}
                            </strong>
                          </div>
                          <div className="flex justify-between border-b border-paper-dark py-2 text-[13px] text-carbon-soft">
                            <span>Max Match Score</span>
                            <strong
                              className="text-carbon-deep"
                              title={`${selectedContestant.max_match_score.toFixed(4)} cosine max`}
                            >
                              {selectedContestant.max_match_score.toFixed(2)}
                            </strong>
                          </div>
                          <div className="flex justify-between border-b border-paper-dark py-2 text-[13px] text-carbon-soft">
                            <span>Detection Count</span>
                            <strong className="text-carbon-deep">
                              {selectedContestant.detection_count}
                            </strong>
                          </div>
                          <div className="flex justify-between border-b border-paper-dark py-2 text-[13px] text-carbon-soft">
                            <span>Videos Seen In</span>
                            <strong className="text-carbon-deep">
                              {selectedContestant.videos_seen_in}
                            </strong>
                          </div>
                          <div className="flex justify-between py-2 text-[13px] text-carbon-soft">
                            <span>Reference Photos</span>
                            <strong className="text-carbon-deep">
                              {selectedContestant.reference_count}
                            </strong>
                          </div>
                        </div>
                      </Card>
                    </div>

                    {/* Right panel */}
                    <div className="flex-1">
                      <Card padding="md">
                        <div className="mb-3 flex items-center justify-between gap-3">
                          <h3 className="text-sm font-semibold text-carbon-deep">
                            Detected Faces from Videos
                          </h3>
                          <span className="font-mono text-[9px] tracking-[0.14em] text-ledger">
                            {detectionsLoading ? '調閱中…' : `${detections.length} / 8`}
                          </span>
                        </div>
                        {detectionsLoading ? (
                          <p className="py-8 text-center font-kai text-[12px] text-carbon-soft">
                            正在調閱出場紀錄…
                          </p>
                        ) : detectionsError ? (
                          <p className="py-8 text-center font-mono text-[11px] text-stamp">
                            {detectionsError instanceof Error
                              ? detectionsError.message
                              : '無法讀取出場紀錄'}
                          </p>
                        ) : detections.length === 0 ? (
                          <p className="py-8 text-center font-kai text-[12px] text-carbon-soft">
                            沒有可對應到影片的面孔紀錄。
                          </p>
                        ) : (
                          <div className="grid grid-cols-4 gap-2">
                            {detections.map((r, i) => {
                              const video = videoById.get(r.video_id);
                              const band = BAND_STAMP[bandFor(r.match_score)];
                              return (
                                <div
                                  key={`${r.video_id}-${r.frame_number ?? r.timestamp}-${i}`}
                                  className="border border-carbon/25 bg-paper p-1.5"
                                >
                                  <div className="flex h-[120px] items-center justify-center overflow-hidden border border-carbon/20 bg-paper-dark">
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
                                  <div className="mt-1.5 flex items-center justify-between gap-1">
                                    <span className="font-mono text-[10px] text-carbon-soft">
                                      {formatMmSs(r.timestamp)}
                                    </span>
                                    <span
                                      className={`inline-block -rotate-2 border px-1.5 py-0.5 font-kai text-[9px] tracking-[0.12em] ${band.ink}`}
                                    >
                                      {band.word}
                                    </span>
                                  </div>
                                  <div
                                    className="mt-1 truncate font-kai text-[10px] text-ledger"
                                    title={video?.name}
                                  >
                                    {video?.name ?? ''}
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </Card>
                    </div>
                  </div>
                </>
              ) : (
                <div className="py-12 text-center text-carbon-soft">
                  <p className="mb-4">Select a contestant from the Coverage tab to see details.</p>
                  <Button variant="secondary" size="sm" onClick={() => setActiveTab('coverage')}>
                    Go to Coverage
                  </Button>
                </div>
              )}
            </>
          )}

          {/* CONFUSION TAB */}
          {activeTab === 'confusion' && (
            <>
              {confusionLoading ? (
                <div className="py-12 text-center text-carbon-soft">Loading similarity data...</div>
              ) : similarityData ? (
                <div className="flex gap-6">
                  {/* Heatmap */}
                  <div className="flex-1">
                    <h3 className="mb-3 text-sm font-semibold text-carbon-deep">
                      Pairwise Similarity ({similarityData.stats.contestant_count}x
                      {similarityData.stats.contestant_count})
                    </h3>
                    <div className="relative inline-block" onMouseLeave={hideHeatmapTooltip}>
                      <canvas
                        ref={heatmapCanvasRef}
                        className="border border-paper-deep"
                        onMouseMove={handleHeatmapHover}
                      />
                      {heatmapTooltip.visible && (
                        <div
                          className="pointer-events-none absolute z-10 whitespace-nowrap rounded border border-carbon bg-paper px-2 py-1 text-xs text-carbon-deep"
                          style={{ left: heatmapTooltip.x, top: heatmapTooltip.y }}
                        >
                          {heatmapTooltip.text}
                        </div>
                      )}
                    </div>
                    <div className="mt-2 flex items-center gap-2 font-mono text-[11px] text-ledger">
                      <span>Low similarity</span>
                      <div className="h-2 flex-1 rounded bg-gradient-to-r from-stamp/5 to-stamp" />
                      <span>High similarity</span>
                    </div>
                  </div>

                  {/* Pairs sidebar */}
                  <div className="w-[320px] shrink-0">
                    <h3 className="mb-3 text-sm font-semibold text-carbon-deep">
                      Top Confusion Pairs
                    </h3>
                    <div className="flex flex-col gap-1">
                      {topPairs.map((pair, i) => (
                        <button
                          key={`${pair.contestant_a.id}-${pair.contestant_b.id}`}
                          type="button"
                          className="flex w-full cursor-pointer items-center gap-2 rounded border border-paper-dark bg-paper-light px-3 py-2.5 text-left transition-colors hover:bg-paper-dark"
                          onClick={() => {
                            const c = contestants.find(
                              (x) => x.nickname === pair.contestant_a.nickname,
                            );
                            if (c) selectContestantForDetail(c);
                          }}
                        >
                          <span className="w-6 font-mono text-[11px] text-ledger">#{i + 1}</span>
                          <span className="flex-1 font-kai text-[13px] text-carbon-deep">
                            {pair.contestant_a.nickname} &harr; {pair.contestant_b.nickname}
                          </span>
                          <span
                            className={`font-mono text-[13px] font-semibold ${
                              pair.similarity > 0.5 ? 'text-stamp' : 'text-carbon-soft'
                            }`}
                          >
                            {(pair.similarity * 100).toFixed(1)}%
                          </span>
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="py-12 text-center text-carbon-soft">
                  <p>
                    No similarity data available. Run:{' '}
                    <code>python scripts/compute_similarity.py</code>
                  </p>
                </div>
              )}
            </>
          )}

          {/* UNMATCHED TAB */}
          {activeTab === 'unmatched' && (
            <div className="py-12 text-center text-carbon-soft">
              <h3 className="mb-2 text-carbon-deep">Unmatched Faces</h3>
              <p>
                Clustered unrecognized faces will appear here after running the clustering pipeline
                (Phase 5).
              </p>
              <p className="mt-1 font-mono text-[13px] text-ledger">
                Requires: T0.4 (save unmatched embeddings) + T0.5 (HDBSCAN clustering)
              </p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
