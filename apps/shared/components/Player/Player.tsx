import { useState, useRef, useCallback, useEffect } from 'react';
import type { FaceDetection, Video, VideoMetadata } from '../../types';
import { BAND_STAMP, bandFor } from '../../lib/bands';
import { useVideos } from '../../hooks/useVideos';
import { useContestants } from '../../hooks/useContestants';
import { useFlaggedFaces } from '../../hooks/useFlaggedFaces';
import { VideoCanvas, type VideoCanvasHandle } from './VideoCanvas';
import { FaceOverlay } from './FaceOverlay';
import { PlayerControls } from './PlayerControls';
import { DetectionBar } from './DetectionBar';
import { FlagDialog } from './FlagDialog';
import { getVideoRenderRect } from './useAnnotations';
import { formatMmSs } from '../../lib/format';
import { useViewerMetadata } from '../../hooks/useViewerMetadata';
import { ContestantTimeline } from './ContestantTimeline';
import { pickInitialVideo } from './pickInitialVideo';

interface PlayerProps {
  mode: 'admin' | 'viewer';
  apiBase: string;
  /** Video to open on mount. Falls back to the first video when absent or unmatched. */
  initialVideoId?: string | null;
}

/**
 * How a detection reads in the UI: an unmatched one has no contestant and no match
 * score, so it names no band; a matched one shows its band, and its raw cosine goes in
 * the tooltip — never a percentage.
 */
function detectionTier(face: FaceDetection): { label: string; className: string; title: string } {
  if (!face.matched) {
    return {
      label: 'unmatched',
      className: 'text-ledger',
      title: `unmatched · detection score ${face.det_score.toFixed(2)}`,
    };
  }
  const band = bandFor(face.match_score);
  return {
    label: band,
    className: BAND_STAMP[band].ink,
    title: face.match_score != null ? `${face.match_score.toFixed(2)} cosine` : 'no match score',
  };
}

export function Player({ mode, apiBase, initialVideoId = null }: PlayerProps) {
  // Flagging is an admin act. The deployed Worker is read-only and no longer serves the flag
  // routes at all (ADR 0003), so this single derivation decides what the player offers — and
  // whether it even asks for flagged faces.
  const canFlag = mode === 'admin';

  // Data queries
  const { data: videos = [], isLoading, error: videosError } = useVideos(apiBase);
  const { data: contestants = [] } = useContestants(apiBase);
  const { data: flaggedFaces = [], refetch: refetchFlagged } = useFlaggedFaces(apiBase, canFlag);

  // Refs
  const videoCanvasRef = useRef<VideoCanvasHandle>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Video state
  const [selectedVideo, setSelectedVideo] = useState<Video | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  const [volume, setVolume] = useState(0.8);
  const [showAnnotations, setShowAnnotations] = useState(true);

  // Face detection state
  const [detectedFaces, setDetectedFaces] = useState<FaceDetection[]>([]);
  const [selectedFace, setSelectedFace] = useState<FaceDetection | null>(null);
  const [batchMode, setBatchMode] = useState(false);
  const [selectedFaces, setSelectedFaces] = useState<Set<FaceDetection>>(new Set());

  // Dialog state
  const [showFlagDialog, setShowFlagDialog] = useState(false);
  const [showBatchFlagDialog, setShowBatchFlagDialog] = useState(false);
  const [isFlagging, setIsFlagging] = useState(false);

  // Panel state
  const [showFlaggedPanel, setShowFlaggedPanel] = useState(false);

  // Metadata
  const [videoMetadata, setVideoMetadata] = useState<VideoMetadata | null>(null);

  // Timeline filter (admin mode)
  const [filterContestantId, setFilterContestantId] = useState<number | null>(null);
  const [contestantAppearances, setContestantAppearances] = useState<
    { timestamp: number; duration: number }[]
  >([]);

  // Viewer mode: load metadata locally instead of polling API
  // Hook is always called (React rules) but videoId is null when not in viewer mode
  const viewerVideoId = mode === 'viewer' && selectedVideo ? selectedVideo.id : null;
  const viewerMeta = useViewerMetadata(apiBase, viewerVideoId);
  const lastViewerFrameRef = useRef<string | null>(null);

  // Auto-select the requested video, else the first
  useEffect(() => {
    if (videos.length > 0 && !selectedVideo) {
      handleSelectVideo(pickInitialVideo(videos, initialVideoId)!);
    }
  }, [videos]); // eslint-disable-line react-hooks/exhaustive-deps

  // --- Helpers ---

  const getVideoEl = useCallback(() => videoCanvasRef.current?.video ?? null, []);

  // There is exactly one video source: the rendition the API serves. The old "show original"
  // toggle pointed at `/source/videos/<file>`, which nothing serves — not the Worker, not
  // `local_api`, not the admin dev server — so it blanked the player in both apps.
  const getVideoSource = useCallback(
    (video: Video | null): string => (video ? `${apiBase}${video.stream_url}` : ''),
    [apiBase],
  );

  const getRenderRect = useCallback(
    () => getVideoRenderRect(getVideoEl(), containerRef.current),
    [getVideoEl],
  );

  // --- Data fetching ---

  const fetchFacesAtTime = useCallback(
    async (timestamp: number, video: Video | null = selectedVideo) => {
      if (!video) return;
      try {
        const res = await fetch(
          `${apiBase}/api/faces/detect?video_id=${encodeURIComponent(video.id)}&timestamp=${timestamp}`,
        );
        if (res.ok) {
          const data = await res.json();
          setDetectedFaces(data.faces || []);
        }
      } catch (e) {
        console.error('Failed to fetch faces:', e);
      }
    },
    [apiBase, selectedVideo],
  );

  const loadVideoMetadata = useCallback(
    async (videoId: string) => {
      try {
        const res = await fetch(
          `${apiBase}/api/videos/metadata/dense/${encodeURIComponent(videoId)}`,
        );
        if (res.ok) {
          setVideoMetadata(await res.json());
        }
      } catch (e) {
        console.error('Failed to load video metadata:', e);
      }
    },
    [apiBase],
  );

  // --- Polling ---

  const startPolling = useCallback(() => {
    if (pollingRef.current) clearInterval(pollingRef.current);
    pollingRef.current = setInterval(() => {
      const video = getVideoEl();
      if (video && !video.paused) {
        fetchFacesAtTime(video.currentTime);
      }
    }, 200);
  }, [fetchFacesAtTime, getVideoEl]);

  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  useEffect(() => () => stopPolling(), [stopPolling]);

  // --- Actions ---

  const handleSelectVideo = useCallback(
    async (video: Video) => {
      stopPolling();
      setSelectedVideo(video);
      setIsPlaying(false);
      setCurrentTime(0);
      setDetectedFaces([]);
      setSelectedFace(null);
      setFilterContestantId(null);
      setContestantAppearances([]);
      await loadVideoMetadata(video.id);
    },
    [loadVideoMetadata, stopPolling],
  );

  const handleTogglePlay = useCallback(() => {
    const video = getVideoEl();
    if (!video) return;
    if (video.paused) {
      video.play();
    } else {
      video.pause();
    }
  }, [getVideoEl]);

  const handleSeek = useCallback(
    (time: number) => {
      const video = getVideoEl();
      if (video) {
        video.currentTime = time;
        fetchFacesAtTime(time);
      }
    },
    [getVideoEl, fetchFacesAtTime],
  );

  const handleSpeedChange = useCallback(
    (speed: number) => {
      setPlaybackSpeed(speed);
      const video = getVideoEl();
      if (video) video.playbackRate = speed;
    },
    [getVideoEl],
  );

  const handleVolumeChange = useCallback(
    (vol: number) => {
      setVolume(vol);
      const video = getVideoEl();
      if (video) video.volume = vol;
    },
    [getVideoEl],
  );

  const handleSkipFrames = useCallback(
    (frames: number) => {
      const video = getVideoEl();
      if (!video) return;
      const fps = videoMetadata?.video_info?.fps || 25;
      const newTime = Math.max(0, Math.min(duration, video.currentTime + frames / fps));
      video.currentTime = newTime;
      fetchFacesAtTime(newTime);
    },
    [getVideoEl, videoMetadata, duration, fetchFacesAtTime],
  );

  const handleSkipSeconds = useCallback(
    (seconds: number) => {
      const video = getVideoEl();
      if (!video) return;
      const newTime = Math.max(0, Math.min(duration, video.currentTime + seconds));
      video.currentTime = newTime;
      fetchFacesAtTime(newTime);
    },
    [getVideoEl, duration, fetchFacesAtTime],
  );

  const handleToggleAnnotations = useCallback(() => {
    setShowAnnotations((prev) => !prev);
  }, []);

  // --- Face interaction ---

  const extractFaceThumbnail = useCallback(
    (face: FaceDetection): string | null => {
      const video = getVideoEl();
      if (!video || !face.bbox || face.bbox.length < 4) return null;
      try {
        const [x1, y1, x2, y2] = face.bbox;
        const vw = video.videoWidth;
        const vh = video.videoHeight;
        if (!vw || !vh) return null;
        // `drawImage`'s source rectangle is in the element's own decoded pixels, so this
        // is the one place a frame fraction becomes pixels — and it uses the frame
        // actually being drawn, never `video_info.width` (the SOURCE dimensions).
        const padding = 0.2;
        const padX = (x2 - x1) * padding;
        const padY = (y2 - y1) * padding;
        const cropX = Math.max(0, x1 - padX) * vw;
        const cropY = Math.max(0, y1 - padY) * vh;
        const cropW = Math.min(vw - cropX, (x2 - x1 + 2 * padX) * vw);
        const cropH = Math.min(vh - cropY, (y2 - y1 + 2 * padY) * vh);

        const canvas = document.createElement('canvas');
        const targetSize = 150;
        const aspectRatio = cropW / cropH;
        if (aspectRatio > 1) {
          canvas.width = targetSize;
          canvas.height = Math.round(targetSize / aspectRatio);
        } else {
          canvas.height = targetSize;
          canvas.width = Math.round(targetSize * aspectRatio);
        }
        const ctx = canvas.getContext('2d');
        if (!ctx) return null;
        ctx.drawImage(video, cropX, cropY, cropW, cropH, 0, 0, canvas.width, canvas.height);
        return canvas.toDataURL('image/jpeg', 0.8);
      } catch {
        return null;
      }
    },
    [getVideoEl],
  );

  const handleFaceClick = useCallback(
    (face: FaceDetection) => {
      if (batchMode) {
        setSelectedFaces((prev) => {
          const next = new Set(prev);
          if (next.has(face)) next.delete(face);
          else next.add(face);
          return next;
        });
      } else if (canFlag) {
        setSelectedFace(face);
        setShowFlagDialog(true);
      }
    },
    [batchMode, canFlag],
  );

  const handleToggleBatchMode = useCallback(() => {
    setBatchMode((prev) => {
      if (prev) setSelectedFaces(new Set());
      return !prev;
    });
  }, []);

  const handleSelectAllFaces = useCallback(() => {
    setSelectedFaces(new Set(detectedFaces));
  }, [detectedFaces]);

  const handleClearSelection = useCallback(() => {
    setSelectedFaces(new Set());
  }, []);

  const handleFlagSubmit = useCallback(
    async (contestantId: number, userLabel: string) => {
      if (!selectedVideo) return;
      setIsFlagging(true);
      try {
        const thumbnail = selectedFace ? extractFaceThumbnail(selectedFace) : null;
        const res = await fetch(`${apiBase}/api/faces/flag`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            contestant_id: contestantId,
            video_id: selectedVideo.id,
            timestamp: currentTime,
            bbox: selectedFace?.bbox,
            confidence: selectedFace?.match_score ?? null,
            user_label: userLabel || `Flagged by user at ${formatMmSs(currentTime)}`,
            thumbnail,
          }),
        });
        if (res.ok) {
          setShowFlagDialog(false);
          setSelectedFace(null);
          refetchFlagged();
          alert('Face flagged successfully!');
        } else {
          alert('Failed to flag face');
        }
      } catch (e) {
        console.error('Failed to flag face:', e);
        alert('Error flagging face');
      } finally {
        setIsFlagging(false);
      }
    },
    [apiBase, selectedVideo, selectedFace, currentTime, extractFaceThumbnail, refetchFlagged],
  );

  const handleBatchFlagSubmit = useCallback(
    async (contestantId: number, _userLabel: string) => {
      if (!selectedVideo || selectedFaces.size === 0) return;
      setIsFlagging(true);
      let successCount = 0;
      let failCount = 0;
      const facesArray = Array.from(selectedFaces);

      try {
        for (const face of facesArray) {
          try {
            const thumbnail = extractFaceThumbnail(face);
            const res = await fetch(`${apiBase}/api/faces/flag`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                contestant_id: contestantId,
                video_id: selectedVideo.id,
                timestamp: currentTime,
                bbox: face.bbox,
                confidence: face.match_score ?? null,
                user_label: `Batch flagged (${facesArray.length} faces) at ${formatMmSs(currentTime)}`,
                thumbnail,
              }),
            });
            if (res.ok) successCount++;
            else failCount++;
          } catch {
            failCount++;
          }
        }

        setShowBatchFlagDialog(false);
        setSelectedFaces(new Set());
        setBatchMode(false);
        refetchFlagged();

        if (failCount === 0) {
          alert(`Successfully flagged ${successCount} faces!`);
        } else {
          alert(`Flagged ${successCount} faces. ${failCount} failed.`);
        }
      } catch (e) {
        console.error('Batch flag error:', e);
        alert('Error during batch flagging');
      } finally {
        setIsFlagging(false);
      }
    },
    [apiBase, selectedVideo, selectedFaces, currentTime, extractFaceThumbnail, refetchFlagged],
  );

  // --- Timeline filter (admin mode) ---

  const handleFilterByContestant = useCallback(
    async (cId: number | null) => {
      setFilterContestantId(cId);
      setContestantAppearances([]);
      if (cId === null || !selectedVideo) return;
      try {
        const res = await fetch(
          `${apiBase}/api/recognition/results?video_id=${encodeURIComponent(selectedVideo.id)}&contestant_id=${cId}`,
        );
        if (res.ok) {
          const data = await res.json();
          setContestantAppearances(
            (data.results || []).map((r: { timestamp: number }) => ({
              timestamp: r.timestamp,
              duration: 0.5,
            })),
          );
        }
      } catch (e) {
        console.error('Failed to load contestant appearances:', e);
      }
    },
    [apiBase, selectedVideo],
  );

  const getContestantName = useCallback(
    (id: number): string => {
      const c = (
        contestants as Array<{ number: number; id: string; nickname: string; name: string }>
      ).find((c) => c.number === id || c.id === String(id));
      return c ? `${c.nickname} (${c.name})` : `Contestant #${id}`;
    },
    [contestants],
  );

  // --- Video event handlers ---

  const handlePlay = useCallback(() => {
    setIsPlaying(true);
    // Only poll API in admin mode
    if (mode === 'admin') {
      startPolling();
    }
  }, [mode, startPolling]);

  const handlePause = useCallback(() => {
    setIsPlaying(false);
    stopPolling();
  }, [stopPolling]);

  const handleEnded = useCallback(() => {
    setIsPlaying(false);
    stopPolling();
  }, [stopPolling]);

  // Viewer mode: get faces from pre-loaded metadata.
  // Only update state when the underlying metadata frame changes — setting a
  // fresh array on every render would loop (state update → render → effect).
  useEffect(() => {
    if (mode !== 'viewer' || !viewerMeta.metadata) return;
    const frame = viewerMeta.getFrameAtTime(currentTime);
    const frameKey = `${viewerVideoId}:${frame?.frame_number ?? -1}`;
    if (frameKey === lastViewerFrameRef.current) return;
    lastViewerFrameRef.current = frameKey;
    setDetectedFaces(viewerMeta.getFacesAtTime(currentTime));
  }, [mode, currentTime, viewerMeta, viewerVideoId]);

  // --- Render ---

  const videoSrc = getVideoSource(selectedVideo);
  const fps = videoMetadata?.video_info?.fps || 25;
  const frameNumber = Math.floor(currentTime * fps);

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-carbon-soft">
        <div className="w-10 h-10 border-2 border-paper-deep border-t-stamp rounded-full animate-spin mb-4" />
        <p>Loading videos...</p>
      </div>
    );
  }

  if (videosError) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-carbon-soft">
        <p className="text-stamp mb-2">Failed to load videos</p>
        <button
          className="px-4 py-2 bg-paper-dark border border-paper-deep rounded text-sm text-carbon hover:bg-paper-deep"
          onClick={() => window.location.reload()}
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-paper text-carbon-deep relative">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-paper-dark">
        <h1 className="text-xl font-semibold text-carbon-deep">Annotated Video Player</h1>
        <div className="flex items-center gap-4">
          {canFlag && (
            <button
              className="px-3 py-1.5 bg-paper-dark border border-paper-deep rounded-none text-sm text-carbon hover:bg-paper-deep"
              onClick={() => setShowFlaggedPanel((p) => !p)}
            >
              Flagged ({flaggedFaces.length})
            </button>
          )}
          <div className="flex items-center gap-2">
            <label htmlFor="video-select" className="text-sm text-carbon-soft">
              Video:
            </label>
            <select
              id="video-select"
              className="bg-paper-dark text-carbon-deep border border-paper-deep rounded-none px-3 py-1.5 text-sm max-w-[300px]"
              value={selectedVideo?.id ?? ''}
              onChange={(e) => {
                const v = videos.find((v) => v.id === e.target.value);
                if (v) handleSelectVideo(v);
              }}
            >
              {videos.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.name}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex gap-5 p-5 min-h-0">
        {/* Video area */}
        <div className="flex-[2] flex flex-col gap-2">
          {/* Video frame */}
          <div
            ref={containerRef}
            className="flex-1 bg-black rounded-none overflow-hidden relative min-h-[400px]"
          >
            {selectedVideo ? (
              <>
                <VideoCanvas
                  ref={videoCanvasRef}
                  videoSrc={videoSrc}
                  faces={detectedFaces}
                  showAnnotations={showAnnotations}
                  containerRef={containerRef}
                  onTimeUpdate={setCurrentTime}
                  onLoadedMetadata={setDuration}
                  onPlay={handlePlay}
                  onPause={handlePause}
                  onEnded={handleEnded}
                />
                <FaceOverlay
                  faces={detectedFaces}
                  onFaceClick={handleFaceClick}
                  selectedFace={selectedFace}
                  batchMode={batchMode}
                  canFlag={canFlag}
                  selectedFaces={selectedFaces}
                  getVideoRenderRect={getRenderRect}
                />
              </>
            ) : (
              <div className="flex items-center justify-center h-full text-ledger">
                Select a video to play
              </div>
            )}
          </div>

          {/* Controls */}
          <PlayerControls
            videoRef={{ current: getVideoEl() }}
            isPlaying={isPlaying}
            currentTime={currentTime}
            duration={duration}
            playbackSpeed={playbackSpeed}
            volume={volume}
            onTogglePlay={handleTogglePlay}
            onSeek={handleSeek}
            onSpeedChange={handleSpeedChange}
            onVolumeChange={handleVolumeChange}
            onSkipFrames={handleSkipFrames}
            onSkipSeconds={handleSkipSeconds}
            disabled={!selectedVideo}
          />

          {/* Detection bar */}
          <DetectionBar
            faceCount={detectedFaces.length}
            recognizedCount={detectedFaces.filter((f) => f.matched).length}
            frameNumber={frameNumber}
            showAnnotations={showAnnotations}
            batchMode={batchMode}
            selectedCount={selectedFaces.size}
            canFlag={canFlag}
            onToggleAnnotations={handleToggleAnnotations}
          />

          {/* Contestant Timeline (viewer mode) */}
          {mode === 'viewer' && viewerMeta.metadata?.contestant_timeline && (
            <ContestantTimeline
              contestantTimeline={viewerMeta.metadata.contestant_timeline}
              duration={duration}
              currentTime={currentTime}
              onSeek={(t) => {
                const video = getVideoEl();
                if (video) {
                  video.currentTime = t;
                  setCurrentTime(t);
                }
              }}
            />
          )}

          {/* Batch controls — admin only: every button in here ends in a flag */}
          {canFlag && (
            <div className="flex items-center gap-2">
              <button
                className={`px-3 py-1.5 rounded-none text-xs font-medium transition-colors border ${
                  batchMode
                    ? 'bg-stamp/20 text-stamp border-stamp/40'
                    : 'bg-paper-dark text-carbon-soft border-paper-deep hover:text-carbon-deep'
                }`}
                onClick={handleToggleBatchMode}
              >
                {batchMode ? 'Batch Mode ON' : 'Batch Mode'}
              </button>

              {batchMode && (
                <>
                  <button
                    className="px-3 py-1.5 bg-paper-dark border border-paper-deep rounded-none text-xs text-carbon hover:bg-paper-deep disabled:opacity-40"
                    onClick={handleSelectAllFaces}
                    disabled={detectedFaces.length === 0}
                  >
                    Select All
                  </button>
                  <button
                    className="px-3 py-1.5 bg-paper-dark border border-paper-deep rounded-none text-xs text-carbon hover:bg-paper-deep disabled:opacity-40"
                    onClick={handleClearSelection}
                    disabled={selectedFaces.size === 0}
                  >
                    Clear
                  </button>
                  <button
                    className="px-3 py-1.5 bg-stamp text-white rounded-none text-xs font-medium hover:bg-stamp disabled:opacity-40"
                    onClick={() => {
                      if (selectedFaces.size > 0) setShowBatchFlagDialog(true);
                    }}
                    disabled={selectedFaces.size === 0}
                  >
                    Flag Selected ({selectedFaces.size})
                  </button>
                </>
              )}
            </div>
          )}

          {/* Timeline filter (admin mode only) */}
          {mode === 'admin' && (
            <div className="bg-paper-light/80 border border-paper-dark rounded-none px-4 py-2">
              <div className="flex items-center gap-3">
                <label htmlFor="contestant-filter" className="text-xs text-carbon-soft">
                  Filter Timeline:
                </label>
                <select
                  id="contestant-filter"
                  className="bg-paper-dark text-carbon-deep border border-paper-deep rounded px-2 py-1 text-xs"
                  onChange={(e) =>
                    handleFilterByContestant(e.target.value ? parseInt(e.target.value, 10) : null)
                  }
                  value={filterContestantId ?? ''}
                >
                  <option value="">All Contestants</option>
                  {(contestants as Array<{ number: number; nickname: string }>).map((c) => (
                    <option key={c.number} value={c.number}>
                      #{c.number} - {c.nickname}
                    </option>
                  ))}
                </select>
                {filterContestantId !== null && (
                  <span className="text-xs text-ledger">
                    {contestantAppearances.length} appearances
                  </span>
                )}
              </div>

              {filterContestantId !== null && contestantAppearances.length > 0 && (
                <div className="mt-2 relative h-4 bg-paper-dark rounded-full overflow-hidden">
                  {contestantAppearances.map((a, i) => (
                    <button
                      key={i}
                      className="absolute top-0 w-1.5 h-full bg-stamp rounded-full hover:bg-stamp"
                      style={{
                        left: `${duration > 0 ? (a.timestamp / duration) * 100 : 0}%`,
                      }}
                      onClick={() => handleSeek(a.timestamp)}
                      title={`Jump to ${formatMmSs(a.timestamp)}`}
                    />
                  ))}
                  <div
                    className="absolute top-0 w-0.5 h-full bg-white"
                    style={{
                      left: `${duration > 0 ? (currentTime / duration) * 100 : 0}%`,
                    }}
                  />
                </div>
              )}
            </div>
          )}
        </div>

        {/* Info panel */}
        <div className="flex-1 max-w-xs bg-paper-light border border-paper-dark rounded-none p-4 overflow-y-auto">
          <h3 className="text-sm font-semibold text-carbon-deep mb-3">Video Information</h3>

          {selectedVideo && (
            <>
              <div className="mb-4">
                <h4 className="text-xs font-medium text-carbon-soft mb-2">Details</h4>
                <div className="space-y-1 text-xs">
                  <div className="flex justify-between">
                    <span className="text-ledger">Title</span>
                    <span className="text-carbon truncate ml-2">{selectedVideo.name}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-ledger">Resolution</span>
                    <span className="text-carbon">
                      {videoMetadata?.video_info?.width ?? 1920}x
                      {videoMetadata?.video_info?.height ?? 1080}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-ledger">FPS</span>
                    <span className="text-carbon">{fps}</span>
                  </div>
                </div>
              </div>

              <div className="mb-4">
                <h4 className="text-xs font-medium text-carbon-soft mb-2">Recognition Summary</h4>
                <div className="space-y-1 text-xs">
                  <div className="flex justify-between">
                    <span className="text-ledger">Unique Contestants</span>
                    <span className="text-carbon">
                      {videoMetadata?.processing_summary?.unique_contestants ?? 0}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-ledger">Faces Detected</span>
                    <span className="text-carbon">
                      {videoMetadata?.processing_summary?.total_faces_detected ?? 0}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-ledger">Faces Recognized</span>
                    <span className="text-carbon">
                      {videoMetadata?.processing_summary?.total_recognitions ?? 0}
                    </span>
                  </div>
                </div>
              </div>
            </>
          )}

          <div>
            <h4 className="text-xs font-medium text-carbon-soft mb-2">Current Frame Faces</h4>
            {detectedFaces.length === 0 ? (
              <p className="text-xs text-carbon italic">No faces detected at this timestamp</p>
            ) : (
              <div className="space-y-1">
                {detectedFaces.map((face, i) => {
                  const tier = detectionTier(face);
                  return (
                    <button
                      key={i}
                      className="w-full flex items-center justify-between px-2 py-1.5 bg-paper-dark rounded text-xs hover:bg-paper-deep transition-colors"
                      onClick={() => handleFaceClick(face)}
                    >
                      <span className="text-carbon-deep">
                        {face.matched
                          ? face.contestant_name || face.contestant_nickname || 'Unmatched'
                          : 'Unmatched'}
                      </span>
                      <span className={`${tier.className} font-medium`} title={tier.title}>
                        {tier.label}
                      </span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Flag Dialog — admin only; a viewer cannot reach these states either way */}
      {canFlag && showFlagDialog && selectedFace && (
        <FlagDialog
          mode="single"
          face={selectedFace}
          contestants={contestants as Array<{ number: number; name: string; nickname: string }>}
          onSubmit={handleFlagSubmit}
          onClose={() => {
            setShowFlagDialog(false);
            setSelectedFace(null);
          }}
          isSubmitting={isFlagging}
        />
      )}

      {/* Batch Flag Dialog */}
      {canFlag && showBatchFlagDialog && (
        <FlagDialog
          mode="batch"
          selectedFaces={Array.from(selectedFaces)}
          contestants={contestants as Array<{ number: number; name: string; nickname: string }>}
          onSubmit={handleBatchFlagSubmit}
          onClose={() => setShowBatchFlagDialog(false)}
          isSubmitting={isFlagging}
        />
      )}

      {/* Flagged Faces Panel */}
      {canFlag && showFlaggedPanel && (
        <div className="absolute top-0 right-0 w-80 h-full bg-paper-light border-l border-paper-dark z-40 flex flex-col shadow-2xl">
          <div className="flex items-center justify-between px-4 py-3 border-b border-paper-dark">
            <h3 className="text-sm font-semibold text-carbon-deep">Flagged Faces</h3>
            <button
              className="text-carbon-soft hover:text-carbon-deep text-lg"
              onClick={() => setShowFlaggedPanel(false)}
            >
              &#10005;
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-4">
            {flaggedFaces.length === 0 ? (
              <p className="text-sm text-carbon italic">No faces have been flagged yet.</p>
            ) : (
              <div className="space-y-2">
                {flaggedFaces.map((flag) => (
                  <div key={flag.id} className="bg-paper-dark rounded-none p-3 text-xs">
                    <div className="space-y-0.5">
                      <div className="text-carbon-deep font-medium">
                        {getContestantName(flag.contestant_id)}
                      </div>
                      <div className="text-ledger">Video: {flag.video_id}</div>
                      <div className="text-ledger">@ {formatMmSs(flag.timestamp)}</div>
                    </div>
                    <span
                      className={`inline-block mt-1 px-2 py-0.5 rounded-full text-[10px] font-medium ${
                        flag.status === 'pending'
                          ? 'bg-stamp/20 text-stamp'
                          : flag.status === 'accepted'
                            ? 'bg-carbon/20 text-carbon'
                            : 'bg-stamp/20 text-stamp'
                      }`}
                    >
                      {flag.status}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
