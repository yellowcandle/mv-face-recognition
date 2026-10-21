import { useState, useRef, useEffect, useCallback } from 'react';
import { useCoverage, useSimilarity } from '@mv/shared';
import { Badge, Button, Card } from '@mv/shared';
import type { Contestant, ConfusionPair } from '@mv/shared';

type Tab = 'coverage' | 'detail' | 'confusion' | 'unmatched';

const tabs: { id: Tab; label: string }[] = [
  { id: 'coverage', label: 'Coverage' },
  { id: 'detail', label: 'Detail' },
  { id: 'confusion', label: 'Confusion' },
  { id: 'unmatched', label: 'Unmatched' },
];

function qualityColor(q: string): string {
  if (q === 'good') return '#22c55e';
  if (q === 'weak') return '#f59e0b';
  return '#ef4444';
}

function qualityBg(q: string): string {
  if (q === 'good') return 'rgba(34,197,94,0.1)';
  if (q === 'weak') return 'rgba(245,158,11,0.1)';
  return 'rgba(239,68,68,0.1)';
}

export function EmbeddingWorkbench() {
  const [activeTab, setActiveTab] = useState<Tab>('coverage');
  const [selectedContestant, setSelectedContestant] = useState<Contestant | null>(null);
  const [heatmapTooltip, setHeatmapTooltip] = useState({ visible: false, x: 0, y: 0, text: '' });

  const heatmapCanvasRef = useRef<HTMLCanvasElement>(null);

  const { data: coverageData, isLoading, error } = useCoverage();
  const similarity = useSimilarity();

  const contestants = coverageData?.contestants ?? [];
  const summary = coverageData?.summary ?? null;
  const similarityData = similarity.matrix.data ?? null;
  const topPairs: ConfusionPair[] = similarity.pairs.data ?? [];
  const confusionLoading = similarity.matrix.isLoading || similarity.pairs.isLoading;

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

    for (let i = 0; i < n; i++) {
      for (let j = 0; j < n; j++) {
        const val = matrix[i][j];
        const alpha = i === j ? 1.0 : Math.min(1, val * 2);
        ctx.fillStyle = `rgba(255, 132, 0, ${alpha})`;
        ctx.fillRect(j * cellSize, i * cellSize, cellSize, cellSize);
      }
    }
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
    <div className="max-w-[1200px] flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-carbon-deep">Embedding Workbench</h1>
        <Button variant="primary" size="sm">
          Regenerate All
        </Button>
      </div>

      {/* Tab Bar */}
      <div className="flex bg-paper-light rounded-full p-1">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            className={`flex-1 py-2 px-4 border-none text-sm font-medium cursor-pointer rounded-full transition-all ${
              activeTab === tab.id
                ? 'bg-stamp text-white font-semibold'
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
        <div className="py-12 text-center text-stamp text-sm">{(error as Error).message}</div>
      ) : (
        <>
          {/* COVERAGE TAB */}
          {activeTab === 'coverage' && summary && (
            <>
              {/* Stats row */}
              <div className="flex gap-4">
                <div className="flex-1 bg-paper-light border border-paper-dark p-5 flex flex-col gap-2">
                  <span className="text-[11px] font-semibold tracking-[2px] text-carbon-soft">
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
                  <div className="h-2 bg-paper-dark rounded-full overflow-hidden">
                    <div
                      className="h-full bg-stamp rounded-full transition-[width] duration-300"
                      style={{ width: `${((summary.good + summary.weak) / summary.total) * 100}%` }}
                    />
                  </div>
                </div>
                <div className="flex-1 bg-paper-light border border-paper-dark p-5 flex flex-col gap-2">
                  <span className="text-[11px] font-semibold tracking-[2px] text-carbon-soft">
                    AVG MATCH SCORE
                  </span>
                  <div className="flex items-baseline gap-2">
                    <span className="text-[32px] font-semibold text-carbon-deep">
                      {summary.avg_match_score.toFixed(2)}
                    </span>
                  </div>
                </div>
                <div className="flex-1 bg-paper-light border border-paper-dark p-5 flex flex-col gap-2">
                  <span className="text-[11px] font-semibold tracking-[2px] text-carbon-soft">
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
              <div className="flex items-center justify-between">
                <span className="text-base font-semibold text-carbon-deep">Contestants</span>
                <div className="flex gap-4 text-xs text-carbon-soft">
                  <span className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-carbon inline-block" /> Good (
                    {summary.good})
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-stamp inline-block" /> Weak (
                    {summary.weak})
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-stamp inline-block" /> Missing (
                    {summary.missing})
                  </span>
                </div>
              </div>

              {/* Contestant grid */}
              <div className="grid grid-cols-4 gap-1.5">
                {contestants.map((c) => (
                  <button
                    key={c.id}
                    className="flex flex-col items-center gap-0.5 py-2.5 px-1.5 border rounded cursor-pointer bg-transparent transition-all hover:-translate-y-px hover:brightness-125"
                    style={{
                      borderColor: qualityColor(c.quality),
                      background: qualityBg(c.quality),
                    }}
                    onClick={() => selectContestantForDetail(c)}
                  >
                    <span className="text-[11px] text-ledger">#{c.id}</span>
                    <span className="text-[13px] font-semibold text-carbon-deep text-center overflow-hidden text-ellipsis whitespace-nowrap max-w-full">
                      {c.nickname}
                    </span>
                    <span
                      className="text-[11px] text-carbon-soft"
                      title={`${c.avg_match_score.toFixed(4)} cosine average`}
                    >
                      {c.avg_match_score.toFixed(2)}
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
                      className="bg-transparent border border-paper-deep text-carbon-soft px-3 py-1.5 rounded-none cursor-pointer text-[13px] hover:text-carbon-deep hover:border-ledger"
                      onClick={() => setActiveTab('coverage')}
                    >
                      &larr; Back
                    </button>
                    <h2 className="text-xl font-semibold text-carbon-deep flex-1 m-0">
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
                    <Button variant="primary" size="sm">
                      Regenerate Embedding
                    </Button>
                  </div>

                  {/* Detail layout */}
                  <div className="flex gap-6">
                    {/* Left panel */}
                    <div className="w-[340px] shrink-0">
                      <Card padding="none">
                        <div className="p-5">
                          <h3 className="text-sm font-semibold text-carbon-deep mb-3">
                            Reference Sources
                          </h3>
                          <div className="p-6 bg-paper-dark rounded-none text-center text-carbon-soft mb-3">
                            <span>{selectedContestant.nickname}</span>
                            <p className="text-ledger text-[13px] mt-1">
                              Current embedding from Instagram screenshot
                            </p>
                          </div>
                          <Button variant="secondary" size="sm">
                            Upload New Photo
                          </Button>
                        </div>
                        <div className="p-5 border-t border-paper-dark">
                          <h3 className="text-sm font-semibold text-carbon-deep mb-3">Stats</h3>
                          <div className="flex justify-between py-2 border-b border-paper-dark text-[13px] text-carbon-soft">
                            <span>Avg Match Score</span>
                            <strong
                              className="text-carbon-deep"
                              title={`${selectedContestant.avg_match_score.toFixed(4)} cosine average`}
                            >
                              {selectedContestant.avg_match_score.toFixed(2)}
                            </strong>
                          </div>
                          <div className="flex justify-between py-2 border-b border-paper-dark text-[13px] text-carbon-soft">
                            <span>Max Match Score</span>
                            <strong
                              className="text-carbon-deep"
                              title={`${selectedContestant.max_match_score.toFixed(4)} cosine max`}
                            >
                              {selectedContestant.max_match_score.toFixed(2)}
                            </strong>
                          </div>
                          <div className="flex justify-between py-2 border-b border-paper-dark text-[13px] text-carbon-soft">
                            <span>Detection Count</span>
                            <strong className="text-carbon-deep">
                              {selectedContestant.detection_count}
                            </strong>
                          </div>
                          <div className="flex justify-between py-2 border-b border-paper-dark text-[13px] text-carbon-soft">
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
                        <h3 className="text-sm font-semibold text-carbon-deep mb-3">
                          Detected Faces from Videos
                        </h3>
                        <p className="text-ledger text-[13px]">
                          Face crops will be extracted on-demand from video frames using canvas
                          (Phase 3).
                        </p>
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
                    <h3 className="text-sm font-semibold text-carbon-deep mb-3">
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
                          className="absolute bg-paper border border-carbon text-carbon-deep px-2 py-1 rounded text-xs pointer-events-none whitespace-nowrap z-10"
                          style={{ left: heatmapTooltip.x, top: heatmapTooltip.y }}
                        >
                          {heatmapTooltip.text}
                        </div>
                      )}
                    </div>
                    <div className="flex items-center gap-2 mt-2 text-[11px] text-ledger">
                      <span>Low similarity</span>
                      <div className="flex-1 h-2 rounded bg-gradient-to-r from-stamp/5 to-stamp" />
                      <span>High similarity</span>
                    </div>
                  </div>

                  {/* Pairs sidebar */}
                  <div className="w-[320px] shrink-0">
                    <h3 className="text-sm font-semibold text-carbon-deep mb-3">
                      Top Confusion Pairs
                    </h3>
                    <div className="flex flex-col gap-1">
                      {topPairs.map((pair, i) => (
                        <button
                          key={i}
                          className="flex items-center gap-2 px-3 py-2.5 bg-paper-light border border-paper-dark rounded cursor-pointer transition-colors text-left w-full hover:bg-paper-dark"
                          onClick={() => {
                            const c = contestants.find(
                              (x) => x.nickname === pair.contestant_a.nickname,
                            );
                            if (c) selectContestantForDetail(c);
                          }}
                        >
                          <span className="text-[11px] text-ledger w-6">#{i + 1}</span>
                          <span className="flex-1 text-[13px] text-carbon-deep">
                            {pair.contestant_a.nickname} &harr; {pair.contestant_b.nickname}
                          </span>
                          <span
                            className={`text-[13px] font-semibold ${
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
              <h3 className="text-carbon-deep mb-2">Unmatched Faces</h3>
              <p>
                Clustered unrecognized faces will appear here after running the clustering pipeline
                (Phase 5).
              </p>
              <p className="text-ledger text-[13px] mt-1">
                Requires: T0.4 (save unmatched embeddings) + T0.5 (HDBSCAN clustering)
              </p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
