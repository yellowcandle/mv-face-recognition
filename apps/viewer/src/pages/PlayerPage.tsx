import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import {
  BAND_STAMP,
  VideoCanvas,
  bandFor,
  formatMmSs,
  getVideoRenderRect,
  type VideoCanvasHandle,
  useContestants,
  useVideos,
  useViewerMetadata,
} from '@mv/shared';
import type { Band, FaceDetection } from '@mv/shared';

function nameOf(face: FaceDetection): string {
  return face.contestant_nickname || face.contestant_name || '—';
}

interface QueueEntry {
  at: number;
  contestantId: number;
  name: string;
  band: Band;
}

export function PlayerPage() {
  const [searchParams] = useSearchParams();
  const { data: videos = [] } = useVideos();
  const { data: contestants = [] } = useContestants();

  const requested = searchParams.get('video');
  const video = useMemo(
    () => videos.find((v) => v.id === requested) ?? videos[0] ?? null,
    [videos, requested],
  );

  const meta = useViewerMetadata('', video?.id ?? null);
  const [time, setTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [playing, setPlaying] = useState(false);

  const canvasRef = useRef<VideoCanvasHandle>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [, forceLayout] = useState(0);

  const faces = useMemo(() => (meta.metadata ? meta.getFacesAtTime(time) : []), [meta, time]);

  const matched = faces.filter((f) => f.matched && f.contestant_id != null);

  /** Every time a contestant enters after being absent — the queue reads from this. */
  const entries = useMemo<QueueEntry[]>(() => {
    const frames = meta.metadata?.frame_data;
    if (!frames) return [];
    const sorted = [...frames].sort((a, b) => a.timestamp - b.timestamp);
    const out: QueueEntry[] = [];
    let previous = new Set<number>();
    for (const frame of sorted) {
      const now = new Set<number>();
      for (const d of frame.detections ?? []) {
        if (d.contestant_id == null) continue;
        const id = Number(d.contestant_id);
        now.add(id);
        if (!previous.has(id) && d.match_score != null) {
          out.push({
            at: frame.timestamp,
            contestantId: id,
            name: d.contestant_nickname || d.contestant_name || `#${id}`,
            band: bandFor(d.match_score),
          });
        }
      }
      previous = now;
      if (out.length > 600) break;
    }
    return out;
  }, [meta.metadata]);

  const queue = useMemo(
    () => entries.filter((e) => e.at > time + 0.4).slice(0, 6),
    [entries, time],
  );

  const coverage = useMemo(() => {
    const seen = new Set<number>();
    for (const frame of meta.metadata?.frame_data ?? []) {
      for (const d of frame.detections ?? []) {
        if (d.contestant_id != null) seen.add(Number(d.contestant_id));
      }
    }
    return seen.size;
  }, [meta.metadata]);

  const togglePlay = useCallback(() => {
    const el = canvasRef.current?.video;
    if (!el) return;
    if (el.paused) void el.play();
    else el.pause();
  }, []);

  const seek = useCallback((t: number) => {
    const el = canvasRef.current?.video;
    if (el) el.currentTime = t;
  }, []);

  const videoEl = canvasRef.current?.video ?? null;
  const rect = getVideoRenderRect(videoEl, containerRef.current);

  // Boxes are frame fractions; project them against the rendered video rect.
  const place = (bbox: [number, number, number, number]) => ({
    left: `${rect.offsetX + bbox[0] * rect.renderW}px`,
    top: `${rect.offsetY + bbox[1] * rect.renderH}px`,
    width: `${(bbox[2] - bbox[0]) * rect.renderW}px`,
    height: `${(bbox[3] - bbox[1]) * rect.renderH}px`,
  });

  useEffect(() => {
    const onResize = () => forceLayout((n) => n + 1);
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  const total = Math.max(96, contestants.length);
  const summary = meta.metadata?.processing_summary;
  const reel = video ? (video.name.split('：').pop() ?? video.name) : '—';

  return (
    <div className="flex min-h-0 flex-1 flex-row">
      <div className="flex min-w-0 flex-1 flex-col px-14 pb-6 pt-7">
        <div className="flex flex-row items-center justify-between pb-4">
          <div className="flex flex-row items-baseline gap-4">
            <Link to="/" className="font-mono text-[14px] text-ledger hover:text-stamp">
              ←
            </Link>
            <h1 className="font-serif text-[26px] font-black leading-none text-carbon-deep">
              播放
            </h1>
            <span className="font-mono text-[10px] tracking-[0.2em] text-ledger">
              REEL {video?.id.split('-')[0] ?? '—'} · {reel}
            </span>
          </div>
          <div className="flex flex-row items-baseline gap-2">
            <span className="font-mono text-[13px] text-carbon-deep">{formatMmSs(time)}</span>
            <span className="font-mono text-[11px] text-ledger">/ {formatMmSs(duration)}</span>
          </div>
        </div>

        <div className="h-px bg-carbon/45" />

        <div
          ref={containerRef}
          className="relative mt-5 aspect-video w-full max-h-[calc(100vh-330px)] overflow-hidden border border-carbon bg-[#111116]"
        >
          {video && (
            <VideoCanvas
              ref={canvasRef}
              videoSrc={`${video.stream_url}`}
              faces={faces}
              showAnnotations={false}
              containerRef={containerRef}
              onTimeUpdate={setTime}
              onLoadedMetadata={setDuration}
              onPlay={() => setPlaying(true)}
              onPause={() => setPlaying(false)}
              onEnded={() => setPlaying(false)}
            />
          )}

          {/* Slip tags, not bordered buttons: a name is filed against a frame. */}
          {matched.map((face, i) => (
            <div
              key={i}
              className="pointer-events-none absolute border-[1.5px] border-paper"
              style={place(face.bbox)}
            >
              <div className="absolute -top-[30px] left-[-1px] flex flex-row items-center gap-1.5 border border-carbon bg-paper-light px-[7px] py-1 whitespace-nowrap">
                <span className="h-[7px] w-[7px] bg-carbon" />
                <span className="font-kai text-[14px] font-bold leading-none text-carbon-deep">
                  {nameOf(face)}
                </span>
                <span className="font-mono text-[8px] text-carbon-soft">{formatMmSs(time)}</span>
              </div>
            </div>
          ))}

          <div className="pointer-events-none absolute inset-x-0 bottom-0 flex flex-row items-end justify-between bg-gradient-to-t from-[#0a0a0e]/85 to-transparent px-4 pb-4 pt-10">
            <div className="flex flex-row items-center gap-3.5">
              <button
                type="button"
                onClick={togglePlay}
                className="pointer-events-auto flex h-[52px] w-[52px] items-center justify-center rounded-full border-[1.5px] border-stamp bg-stamp/20"
                aria-label={playing ? '暫停' : '播放'}
              >
                {playing ? (
                  <svg width="14" height="16" viewBox="0 0 14 16" fill="none" aria-hidden="true">
                    <rect x="1" y="1" width="4" height="14" fill="#efe4b4" />
                    <rect x="9" y="1" width="4" height="14" fill="#efe4b4" />
                  </svg>
                ) : (
                  <svg width="16" height="18" viewBox="0 0 16 18" fill="none" aria-hidden="true">
                    <path d="M1 1.4L15 9L1 16.6V1.4Z" fill="#efe4b4" />
                  </svg>
                )}
              </button>
              <div className="flex flex-col gap-0.5">
                <span className="font-mono text-[15px] tracking-[0.04em] text-paper">
                  {formatMmSs(time)}
                </span>
                <span className="font-mono text-[9px] tracking-[0.18em] text-ledger">
                  OF {formatMmSs(duration)}
                </span>
              </div>
            </div>
            <div className="flex flex-row items-center gap-4 pb-0.5">
              <div className="flex flex-col items-end gap-0.5">
                <span className="font-mono text-[11px] text-paper">
                  {faces.length} · {matched.length}
                </span>
                <span className="font-mono text-[8px] tracking-[0.16em] text-ledger">
                  DETECT / MATCH
                </span>
              </div>
            </div>
          </div>
        </div>

        <div className="flex flex-row items-center gap-3 pt-3">
          <span className="font-mono text-[10px] text-carbon-soft">{formatMmSs(time)}</span>
          <input
            type="range"
            min={0}
            max={duration || 0}
            step={0.1}
            value={time}
            onChange={(e) => seek(parseFloat(e.target.value))}
            className="h-1 flex-1 cursor-pointer appearance-none bg-carbon/20 accent-stamp [&::-webkit-slider-thumb]:h-2.5 [&::-webkit-slider-thumb]:w-2.5 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-stamp [&::-moz-range-thumb]:h-2.5 [&::-moz-range-thumb]:w-2.5 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:border-0 [&::-moz-range-thumb]:bg-stamp"
            aria-label="播放位置"
          />
          <span className="font-mono text-[10px] text-ledger">{formatMmSs(duration)}</span>
        </div>

        <div className="flex flex-row flex-wrap items-center gap-2 pt-4">
          {matched.map((face, i) => {
            const band = bandFor(face.match_score);
            return (
              <span
                key={i}
                className="flex flex-row items-center gap-2 border border-carbon/35 px-2.5 py-1"
              >
                <span className="font-kai text-[11px] text-carbon-deep">{nameOf(face)}</span>
                <span className="font-mono text-[9px] text-ledger">
                  {face.match_score == null ? '—' : face.match_score.toFixed(2)}
                </span>
                <span
                  className={`border px-1 font-kai text-[9px] tracking-[0.1em] ${BAND_STAMP[band].ink}`}
                >
                  {BAND_STAMP[band].word}
                </span>
              </span>
            );
          })}
          {matched.length === 0 && (
            <span className="font-kai text-[12px] text-carbon-soft">這一格沒有已核對的人臉</span>
          )}
        </div>

        <div className="mt-auto flex flex-row items-center justify-between border-t border-carbon/30 pt-3">
          <span className="font-mono text-[9px] tracking-[0.16em] text-ledger">
            FRAMES {summary?.frames_processed.toLocaleString() ?? '—'} · DETECTIONS{' '}
            {summary?.total_faces_detected.toLocaleString() ?? '—'} · RECOGNISED{' '}
            {summary?.total_recognitions.toLocaleString() ?? '—'}
          </span>
          <span className="font-mono text-[9px] tracking-[0.16em] text-carbon-soft">
            {video?.id.split('-')[0] ?? '—'} · R2 · 1080P
          </span>
        </div>
      </div>

      {/* 第二聯 — the carbon copy carries the queue, never a write. */}
      <aside className="flex w-[330px] shrink-0 flex-col border-l border-carbon bg-copy px-6 pb-5 pt-6">
        <div className="font-mono text-[8px] tracking-[0.26em] text-carbon-soft">
          本卷出場 · IN THIS REEL
        </div>

        <div className="flex flex-row items-baseline gap-2.5 pt-2">
          <span className="font-serif text-[36px] font-black leading-none text-carbon-deep">
            {coverage}
          </span>
          <span className="font-kai text-[12px] text-carbon-soft">位參賽者被辨識</span>
        </div>

        <div className="flex flex-row items-baseline justify-between pt-4">
          <h2 className="font-kai text-[13px] font-bold text-carbon-deep">待播</h2>
          <span className="font-mono text-[9px] tracking-[0.22em] text-carbon-soft">QUEUE</span>
        </div>
        <div className="mt-2 h-px bg-carbon/40" />

        <div className="flex flex-col pt-1">
          {queue.map((entry) => (
            <button
              type="button"
              key={`${entry.contestantId}-${entry.at}`}
              onClick={() => seek(entry.at)}
              className="flex flex-row items-center gap-3 border-b border-carbon/20 py-2.5 text-left"
            >
              <span className="w-[46px] font-mono text-[11px] text-carbon-soft">
                {formatMmSs(entry.at)}
              </span>
              <span className="flex flex-1 flex-col gap-0.5">
                <span className="font-kai text-[16px] font-bold leading-[1.1] text-carbon-deep">
                  {entry.name}
                </span>
                <span className="font-mono text-[8px] tracking-[0.14em] text-carbon-soft">
                  #{entry.contestantId} · {BAND_STAMP[entry.band].word}
                </span>
              </span>
              <span className="h-[7px] w-[7px] bg-carbon-deep" />
            </button>
          ))}
          {queue.length === 0 && (
            <div className="py-6 font-kai text-[13px] leading-relaxed text-carbon-soft">
              本片再無新的出場紀錄。
            </div>
          )}
        </div>

        <div className="flex flex-1 items-center justify-center py-5">
          <div className="-rotate-[8deg] border-[1.5px] border-carbon-deep/50 px-4 py-2.5">
            <div className="text-center font-serif text-[14px] font-bold tracking-[0.3em] text-carbon-deep/70">
              唯讀
            </div>
            <div className="text-center font-mono text-[7px] tracking-[0.2em] text-carbon-deep/60">
              PUBLIC · READ ONLY
            </div>
          </div>
        </div>

        <div className="flex flex-col gap-2 border-t border-carbon/40 pt-3.5">
          <div className="flex flex-row items-baseline justify-between">
            <span className="font-mono text-[9px] tracking-[0.18em] text-carbon-soft">
              COVERAGE
            </span>
            <span className="font-mono text-[12px] text-carbon-deep">
              {coverage} / {total}
            </span>
          </div>
          <div className="h-[3px] w-full bg-carbon-deep/20">
            <div
              className="h-[3px] bg-carbon-deep"
              style={{ width: `${Math.min(100, (coverage / total) * 100)}%` }}
            />
          </div>
          <span className="pt-1 font-kai text-[11px] leading-relaxed text-carbon-soft">
            唯讀檢視 · 所有改動在後台
          </span>
        </div>
      </aside>
    </div>
  );
}
