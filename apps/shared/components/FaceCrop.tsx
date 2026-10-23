import { useEffect, useState } from 'react';

export interface FaceCropProps {
  videoId: string;
  frameNumber?: number;
  detectionIndex?: number;
  /** Seconds into the rendition; used by the client-side frame fallback. */
  timestamp?: number;
  /** Canonical `[x1, y1, x2, y2]` in frame fractions (see `FaceDetection` in types). */
  bbox?: [number, number, number, number] | null;
  /** Same-origin rendition URL, e.g. `/videos/processed_videos/foo.mp4`. */
  streamUrl?: string;
  width?: number;
  className?: string;
  alt?: string;
}

/** Cropped data URLs, keyed by stream, timestamp, box and width. */
const cropCache = new Map<string, string>();
const CROP_CACHE_MAX = 200;

/**
 * The crop route is all-or-nothing: a deployment either has pre-extracted crops in R2 or it
 * has none. Asking per tile cost one 404 for every face on the page before the canvas path it
 * was going to use anyway. One tile discovers the answer, once per page load, and everyone
 * else waits for it.
 */
type CropRouteState = 'unknown' | 'present' | 'missing';
let cropRouteState: CropRouteState = 'unknown';
let cropRouteClaimed = false;
const cropRouteListeners = new Set<(state: CropRouteState) => void>();

function setCropRouteState(state: CropRouteState): void {
  if (cropRouteState === state) return;
  cropRouteState = state;
  for (const notify of cropRouteListeners) notify(state);
}

/** An `<img>` error cannot say why; this asks once, then retires the primary path if it is gone. */
async function classifyCropRoute(src: string): Promise<void> {
  try {
    const response = await fetch(src, { cache: 'no-store' });
    setCropRouteState(response.status === 404 || response.status === 410 ? 'missing' : 'present');
  } catch {
    setCropRouteState('missing');
  }
}

/**
 * One seek queue per stream. A `Promise` chain is the lock: every job appends with
 * `previous.then(job, job)`, so a job only starts once the preceding one has settled,
 * and a failed seek neither stalls nor skips the queue. The shared video element is
 * keyed the same way, so all crops of a stream seek the same `<video>` in turn.
 */
const seekQueues = new Map<string, Promise<void>>();
const videoPool = new Map<string, HTMLVideoElement>();

function getVideo(streamUrl: string): HTMLVideoElement {
  let video = videoPool.get(streamUrl);
  if (!video) {
    video = document.createElement('video');
    video.muted = true;
    video.playsInline = true;
    video.preload = 'metadata';
    video.src = streamUrl;
    videoPool.set(streamUrl, video);
  }
  return video;
}

function waitForMetadata(video: HTMLVideoElement): Promise<void> {
  if (video.readyState >= 1) return Promise.resolve();
  // `Promise.withResolvers` is ES2024; this package targets ES2022 (see tsconfig).
  return new Promise<void>((resolve, reject) => {
    const cleanup = () => {
      video.removeEventListener('loadedmetadata', onLoaded);
      video.removeEventListener('error', onError);
      clearTimeout(timer);
    };
    const onLoaded = () => {
      cleanup();
      resolve();
    };
    const onError = () => {
      cleanup();
      reject(new Error('video could not be loaded'));
    };
    const timer = setTimeout(() => {
      cleanup();
      reject(new Error('video metadata timed out'));
    }, 15000);
    video.addEventListener('loadedmetadata', onLoaded);
    video.addEventListener('error', onError);
    if (video.networkState === HTMLMediaElement.NETWORK_EMPTY) video.load();
  });
}

function seekTo(video: HTMLVideoElement, timestamp: number): Promise<void> {
  if (video.readyState >= 2 && Math.abs(video.currentTime - timestamp) < 0.001) {
    return Promise.resolve();
  }
  return new Promise<void>((resolve, reject) => {
    const cleanup = () => {
      video.removeEventListener('seeked', onSeeked);
      video.removeEventListener('error', onError);
      clearTimeout(timer);
    };
    const onSeeked = () => {
      cleanup();
      resolve();
    };
    const onError = () => {
      cleanup();
      reject(new Error('video seek failed'));
    };
    const timer = setTimeout(() => {
      cleanup();
      reject(new Error('video seek timed out'));
    }, 15000);
    video.addEventListener('seeked', onSeeked);
    video.addEventListener('error', onError);
    video.currentTime = timestamp;
  });
}

function cropFrame(
  streamUrl: string,
  timestamp: number,
  bbox: [number, number, number, number],
  width: number,
): Promise<string> {
  return (async () => {
    if (typeof document === 'undefined') throw new Error('no canvas available');
    const video = getVideo(streamUrl);
    await waitForMetadata(video);
    await seekTo(video, timestamp);

    const frameWidth = video.videoWidth;
    const frameHeight = video.videoHeight;
    if (!frameWidth || !frameHeight) throw new Error('video has no decoded frame');

    const [x1, y1, x2, y2] = bbox;
    const padX = (x2 - x1) * 0.25;
    const padY = (y2 - y1) * 0.25;
    const cx1 = Math.min(1, Math.max(0, x1 - padX));
    const cy1 = Math.min(1, Math.max(0, y1 - padY));
    const cx2 = Math.min(1, Math.max(0, x2 + padX));
    const cy2 = Math.min(1, Math.max(0, y2 + padY));

    const cropWidth = (cx2 - cx1) * frameWidth;
    const cropHeight = (cy2 - cy1) * frameHeight;
    if (cropWidth < 1 || cropHeight < 1) throw new Error('crop is empty');

    const canvas = document.createElement('canvas');
    canvas.width = Math.max(1, Math.round(width));
    canvas.height = Math.max(1, Math.round((width * cropHeight) / cropWidth));
    const context = canvas.getContext('2d');
    if (!context) throw new Error('canvas context unavailable');
    context.drawImage(
      video,
      cx1 * frameWidth,
      cy1 * frameHeight,
      cropWidth,
      cropHeight,
      0,
      0,
      canvas.width,
      canvas.height,
    );
    return canvas.toDataURL('image/jpeg', 0.82);
  })();
}

function enqueueCrop(streamUrl: string, job: () => Promise<string>): Promise<string> {
  const previous = seekQueues.get(streamUrl) ?? Promise.resolve();
  const result = previous.then(job, job);
  const settled = result.then(
    () => undefined,
    () => undefined,
  );
  seekQueues.set(streamUrl, settled);
  void settled.then(() => {
    if (seekQueues.get(streamUrl) === settled) seekQueues.delete(streamUrl);
  });
  return result;
}

function cacheCrop(key: string, dataUrl: string): void {
  if (cropCache.size >= CROP_CACHE_MAX) {
    const oldest = cropCache.keys().next().value;
    if (oldest !== undefined) cropCache.delete(oldest);
  }
  cropCache.set(key, dataUrl);
}

/**
 * One detection's face.
 *
 * Primary: the backend's pre-cropped JPEG (`/api/faces/crop`). Fallback: when that route
 * has no crop (the Worker has no crop bucket yet), seek the same-origin rendition, draw
 * the detection's box, and cache the result. Falls back to a neutral `NO CROP` slip when
 * neither path can produce pixels — it never throws for missing data.
 */
export function FaceCrop({
  videoId,
  frameNumber,
  detectionIndex,
  timestamp,
  bbox,
  streamUrl,
  width = 160,
  className = '',
  alt,
}: FaceCropProps) {
  const [failedSrc, setFailedSrc] = useState<string | null>(null);
  const [dataUrl, setDataUrl] = useState<string | null>(null);
  const [fallbackFailed, setFallbackFailed] = useState(false);
  const primarySrc =
    frameNumber != null && detectionIndex != null
      ? `/api/faces/crop?video_id=${encodeURIComponent(videoId)}&frame_number=${frameNumber}&detection_index=${detectionIndex}&width=${width}`
      : null;

  const [routeState, setRouteState] = useState<CropRouteState>(cropRouteState);
  // A node with no crop URL cannot probe: if it claimed, everyone else would wait on a request
  // that never happens.
  const [claimant] = useState(() => {
    if (primarySrc === null) return false;
    if (cropRouteState !== 'unknown' || cropRouteClaimed) return false;
    cropRouteClaimed = true;
    return true;
  });

  useEffect(() => {
    const notify = (state: CropRouteState) => setRouteState(state);
    cropRouteListeners.add(notify);
    return () => {
      cropRouteListeners.delete(notify);
    };
  }, []);

  // A claimant that unmounts before the answer must not leave the route unclassified forever.
  useEffect(() => {
    if (!claimant) return;
    return () => {
      if (cropRouteState === 'unknown') cropRouteClaimed = false;
    };
  }, [claimant]);

  const bboxKey = bbox && bbox.length === 4 ? bbox.join(',') : '';
  const canFallback = Boolean(streamUrl && timestamp != null && bboxKey);
  const cropKey = canFallback ? `${streamUrl}|${timestamp}|${bboxKey}|${width}` : '';
  const cached = cropKey ? cropCache.get(cropKey) : undefined;

  const awaitingRoute = routeState === 'unknown' && !claimant && primarySrc !== null;
  const primaryImgSrc =
    primarySrc && !awaitingRoute && routeState !== 'missing' ? primarySrc : null;

  // A different crop is a different image: forget the previous outcome.
  useEffect(() => {
    setDataUrl(null);
    setFallbackFailed(false);
  }, [cropKey]);

  const showFallback = !awaitingRoute && (primaryImgSrc === null || failedSrc === primaryImgSrc);

  useEffect(() => {
    if (!showFallback || !canFallback || !streamUrl || timestamp == null || !bboxKey) {
      return;
    }
    if (cached) {
      setDataUrl(cached);
      return;
    }
    let cancelled = false;
    const box = bboxKey.split(',').map(Number) as [number, number, number, number];
    enqueueCrop(streamUrl, () => cropFrame(streamUrl, timestamp, box, width)).then(
      (url) => {
        if (cancelled) return;
        cacheCrop(cropKey, url);
        setDataUrl(url);
      },
      () => {
        if (!cancelled) setFallbackFailed(true);
      },
    );
    return () => {
      cancelled = true;
    };
  }, [showFallback, canFallback, streamUrl, timestamp, bboxKey, width, cropKey, cached]);

  const image = showFallback ? (dataUrl ?? cached ?? null) : null;
  const placeholderHeight = Math.max(1, Math.round(width * 0.75));

  return (
    <div className={className} style={{ width }}>
      {primaryImgSrc && failedSrc !== primaryImgSrc ? (
        <img
          src={primaryImgSrc}
          alt={alt ?? 'Face crop'}
          width={width}
          className="block h-auto w-full"
          onLoad={() => {
            if (claimant) setCropRouteState('present');
          }}
          onError={() => {
            if (claimant) void classifyCropRoute(primaryImgSrc);
            setFailedSrc(primaryImgSrc);
          }}
        />
      ) : image ? (
        <img src={image} alt={alt ?? 'Face crop'} width={width} className="block h-auto w-full" />
      ) : (
        <div
          className="flex items-center justify-center border border-dashed border-carbon/35 bg-paper-dark font-mono text-[8px] tracking-[0.18em] text-carbon-soft"
          style={{ width, height: placeholderHeight }}
        >
          {fallbackFailed || !canFallback ? 'NO CROP' : ''}
        </div>
      )}
    </div>
  );
}
