import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import { ArrowLeft, Pause, Play } from 'lucide-react';
import {
  BAND_STAMP,
  Button,
  FaceCrop,
  Masthead,
  Stamp,
  VideoCanvas,
  bandFor,
  formatMmSs,
  getVideoRenderRect,
  reelHeading,
  renditionLabel,
  type VideoCanvasHandle,
  useContestants,
  useVideos,
  useViewerMetadata,
} from '@mv/shared';
import type { Band, FaceDetection, Video } from '@mv/shared';

/** The list route also sends this; `Video` doesn't declare it. */
type FiledVideo = Video & { height?: number };

function nameOf(face: FaceDetection): string {
  return face.contestant_nickname || face.contestant_name || '—';
}

interface QueueEntry {
  at: number;
  contestantId: number;
  name: string;
  band: Band;
  /** Enough of the source detection to crop the face from the reel. */
  frameNumber: number;
  detectionIndex: number;
  bbox: [number, number, number, number];
}

export function PlayerPage() {
  const [searchParams] = useSearchParams();
  const { data: videos = [] } = useVideos();
  const { data: contestants = [] } = useContestants();

  const requested = searchParams.get('video');
  const video = useMemo<FiledVideo | null>(
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
  const frame = meta.metadata ? meta.getFrameAtTime(time) : null;

  /** Every time a contestant enters after being absent — the queue reads from this. */
  const entries = useMemo<QueueEntry[]>(() => {
    const frames = meta.metadata?.frame_data;
    if (!frames) return [];
    const sorted = [...frames].sort((a, b) => a.timestamp - b.timestamp);
    const out: QueueEntry[] = [];
    let previous = new Set<number>();
    for (const frame of sorted) {
      const now = new Set<number>();
      (frame.detections ?? []).forEach((d, detectionIndex) => {
        if (d.contestant_id == null) return;
        const id = Number(d.contestant_id);
        now.add(id);
        if (!previous.has(id) && d.match_score != null) {
          out.push({
            at: frame.timestamp,
            contestantId: id,
            name: d.contestant_nickname || d.contestant_name || `#${id}`,
            band: bandFor(d.match_score),
            frameNumber: frame.frame_number,
            detectionIndex,
            bbox: d.bbox,
          });
        }
      });
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
  const played = duration ? (time / duration) * 100 : 0;
  const rendition = renditionLabel(video?.height);

  return (
    <div className="flex min-h-full flex-1 flex-row">
      <div className="flex min-w-0 flex-1 flex-col gap-4 pb-5 pl-14 pr-8 pt-8">
        <div className="flex flex-row items-center gap-3">
          <Link
            to="/"
            aria-label="返回點唱單"
            className="rounded-md text-ink-muted hover:text-stamp"
          >
            <ArrowLeft size={20} aria-hidden="true" />
          </Link>
          <div className="min-w-0 flex-1">
            <Masthead title="播放" hint="看片、人臉框與時間軸">
              <div className="flex flex-col items-end gap-1">
                <span className="text-carbon-soft">{video ? reelHeading(video.name) : '—'}</span>
                <span className="flex flex-row items-end gap-2 font-mono tabular-nums">
                  <span className="text-[18px] leading-tight text-carbon-deep">
                    {formatMmSs(time)}
                  </span>
                  <span className="text-[13px] text-ink-muted">/ {formatMmSs(duration)}</span>
                </span>
              </div>
            </Masthead>
          </div>
        </div>

        <div
          ref={containerRef}
          className="relative aspect-[12/5] max-h-[calc(100vh-330px)] w-full overflow-hidden rounded bg-carbon-deep"
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
              className="pointer-events-none absolute border-[1.5px] border-paper-light"
              style={place(face.bbox)}
            >
              <div className="absolute -left-[1.5px] -top-7 flex h-6 flex-row items-center gap-1.5 whitespace-nowrap rounded-xs bg-paper-light px-1.5">
                <span className="h-2 w-2 bg-carbon" />
                <span className="font-kai text-[14px] leading-none text-carbon-deep">
                  {nameOf(face)}
                </span>
              </div>
            </div>
          ))}
        </div>

        <div className="flex flex-row items-center gap-4">
          <Button
            variant="primary"
            onClick={togglePlay}
            aria-label={playing ? '暫停' : '播放'}
            className="w-10 shrink-0 px-0!"
          >
            {playing ? (
              <Pause size={16} aria-hidden="true" />
            ) : (
              <Play size={16} aria-hidden="true" />
            )}
          </Button>
          <span className="font-mono text-[13px] tabular-nums text-carbon-soft">
            {formatMmSs(time)}
          </span>
          <input
            type="range"
            min={0}
            max={duration || 0}
            step={0.1}
            value={time}
            onChange={(e) => seek(parseFloat(e.target.value))}
            style={{
              background: `linear-gradient(to right, var(--color-stamp) ${played}%, color-mix(in srgb, var(--color-carbon-deep) 13%, transparent) ${played}%)`,
            }}
            className="h-1 min-w-0 flex-1 cursor-pointer appearance-none rounded-full [&::-moz-range-thumb]:h-2.5 [&::-moz-range-thumb]:w-2.5 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:border-0 [&::-moz-range-thumb]:bg-stamp [&::-webkit-slider-thumb]:h-2.5 [&::-webkit-slider-thumb]:w-2.5 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-stamp"
            aria-label="播放位置"
            aria-valuetext={formatMmSs(time)}
          />
          <span className="font-mono text-[13px] tabular-nums text-ink-muted">
            {formatMmSs(duration)}
          </span>
          <span className="flex flex-row items-center gap-1.5">
            <span className="font-mono text-[13px] tabular-nums text-carbon-deep">
              {faces.length} · {matched.length}
            </span>
            <span className="font-kai text-[12px] text-ink-muted">偵測 / 配對</span>
          </span>
        </div>

        <div className="grid grid-cols-5 gap-4 border-t border-carbon-deep/13 pt-4">
          {matched.map((face, i) => (
            <div key={i} className="flex min-w-0 flex-row items-center gap-2.5">
              <div className="h-20 w-[60px] shrink-0 overflow-hidden rounded bg-tint">
                {/* ponytail: frames arrive 6 times a second and a first crop costs 1.5s, so crops
                    load only while paused. Add a throttle if they're wanted during playback. */}
                {video && frame && !playing ? (
                  <FaceCrop
                    videoId={video.id}
                    frameNumber={frame.frame_number}
                    detectionIndex={faces.indexOf(face)}
                    timestamp={frame.timestamp}
                    bbox={face.bbox}
                    streamUrl={video.stream_url}
                    alt={nameOf(face)}
                    className="h-full w-full! [&>div]:hidden [&_img]:h-full [&_img]:w-full [&_img]:object-cover"
                  />
                ) : null}
              </div>
              <div className="flex min-w-0 flex-col gap-1">
                <span className="truncate font-kai text-[15px] leading-tight text-carbon-deep">
                  {nameOf(face)}
                </span>
                <span className="flex flex-row items-center gap-1.5">
                  <span className="font-mono text-[13px] tabular-nums text-carbon-soft">
                    {face.match_score == null ? '—' : face.match_score.toFixed(2)}
                  </span>
                  <Stamp band={bandFor(face.match_score)} />
                </span>
              </div>
            </div>
          ))}
          {matched.length === 0 && (
            <span className="col-span-5 font-kai text-[13px] text-ink-muted">
              這一格沒有已核對的人臉
            </span>
          )}
        </div>

        <div className="mt-auto flex flex-row items-center justify-between font-kai text-[12px] tabular-nums text-ink-muted">
          <span>
            影格 {summary?.frames_processed.toLocaleString('en-US') ?? '—'} · 偵測{' '}
            {summary?.total_faces_detected.toLocaleString('en-US') ?? '—'} · 辨識{' '}
            {summary?.total_recognitions.toLocaleString('en-US') ?? '—'}
          </span>
          <span>
            {[video?.id.split('-')[0] ?? '—', 'R2', rendition].filter(Boolean).join(' · ')}
          </span>
        </div>
      </div>

      {/* 第二聯 — the carbon copy carries the queue, never a write. */}
      <aside className="flex w-[330px] shrink-0 flex-col gap-4 border-l border-carbon-deep/13 bg-tint px-6 pb-5 pt-8">
        <div className="flex flex-col gap-1">
          <span className="font-kai text-[13px] text-carbon-soft">本卷出場</span>
          <div className="flex flex-row items-end gap-2">
            <span className="font-mono text-[28px] leading-tight tabular-nums text-carbon-deep">
              {coverage}
            </span>
            <span className="pb-1 font-kai text-[13px] text-carbon-soft">位參賽者被辨識</span>
          </div>
        </div>

        <div className="flex flex-col">
          <h2 className="border-b border-carbon-deep/33 pb-2 font-kai text-[18px] font-normal text-carbon-deep">
            待播
          </h2>
          {queue.map((entry) => (
            <button
              type="button"
              key={`${entry.contestantId}-${entry.at}`}
              onClick={() => seek(entry.at)}
              className="flex h-14 flex-row items-center gap-3 border-b border-carbon-deep/13 text-left transition-colors hover:bg-ground/60"
            >
              <FaceCrop
                videoId={video?.id ?? ''}
                frameNumber={entry.frameNumber}
                detectionIndex={entry.detectionIndex}
                timestamp={entry.at}
                bbox={entry.bbox}
                streamUrl={video?.stream_url}
                width={64}
                alt={entry.name}
                className="h-10 w-10! shrink-0 overflow-hidden rounded bg-carbon-deep/13 [&>div]:h-full! [&>div]:w-full! [&_img]:h-full [&_img]:w-full [&_img]:object-cover"
              />
              <span className="font-mono text-[13px] tabular-nums text-carbon-soft">
                {formatMmSs(entry.at)}
              </span>
              <span className="flex min-w-0 flex-col gap-0.5">
                <span className="truncate font-kai text-[15px] leading-tight text-carbon-deep">
                  {entry.name}
                </span>
                <span className="font-kai text-[12px] tabular-nums text-ink-muted">
                  #{entry.contestantId} · {BAND_STAMP[entry.band].word}
                </span>
              </span>
            </button>
          ))}
          {queue.length === 0 && (
            <div className="py-6 font-kai text-[13px] leading-relaxed text-ink-muted">
              本片再無新的出場紀錄。
            </div>
          )}
        </div>

        <div className="mt-auto flex flex-col gap-2 border-t border-carbon-deep/13 pt-3">
          <div className="flex flex-row items-end justify-between">
            <span className="font-kai text-[13px] text-carbon-soft">覆蓋</span>
            <span className="font-mono text-[13px] tabular-nums text-carbon-deep">
              {coverage} / {total}
            </span>
          </div>
          <div className="h-1 w-full rounded-full bg-carbon-deep/13">
            <div
              className="h-1 rounded-full bg-carbon-deep"
              style={{ width: `${Math.min(100, (coverage / total) * 100)}%` }}
            />
          </div>
          <div className="flex flex-row items-center justify-between pt-1">
            <span className="font-kai text-[12px] text-ink-muted">唯讀檢視 · 所有改動在後台</span>
            <Stamp tone="muted">唯讀</Stamp>
          </div>
        </div>
      </aside>
    </div>
  );
}
