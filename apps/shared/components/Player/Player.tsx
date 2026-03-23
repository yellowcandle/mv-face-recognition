import { useState, useRef, useCallback, useEffect } from 'react';
import type { FaceDetection, Video, VideoMetadata } from '../../types';
import { useVideos } from '../../hooks/useVideos';
import { useContestants } from '../../hooks/useContestants';
import { useFlaggedFaces } from '../../hooks/useFlaggedFaces';
import { VideoCanvas, type VideoCanvasHandle } from './VideoCanvas';
import { FaceOverlay } from './FaceOverlay';
import { PlayerControls } from './PlayerControls';
import { DetectionBar } from './DetectionBar';
import { FlagDialog } from './FlagDialog';
import { getVideoRenderRect } from './useAnnotations';
import { useViewerMetadata } from '../../hooks/useViewerMetadata';
import { ContestantTimeline } from './ContestantTimeline';

interface PlayerProps {
  mode: 'admin' | 'viewer';
  apiBase: string;
}

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

export function Player({ mode, apiBase }: PlayerProps) {
  // Data queries
  const { data: videos = [], isLoading, error: videosError } = useVideos(apiBase);
  const { data: contestants = [] } = useContestants(apiBase);
  const { data: flaggedFaces = [], refetch: refetchFlagged } = useFlaggedFaces(apiBase);

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
  const [showOriginalVideo, setShowOriginalVideo] = useState(false);
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

  // Auto-select first video
  useEffect(() => {
    if (videos.length > 0 && !selectedVideo) {
      handleSelectVideo(videos[0]);
    }
  }, [videos]); // eslint-disable-line react-hooks/exhaustive-deps

  // --- Helpers ---

  const getVideoEl = useCallback(() => videoCanvasRef.current?.video ?? null, []);

  const getVideoSource = useCallback(
    (video: Video | null, useOriginal: boolean): string => {
      if (!video) return '';
      if (useOriginal) {
        const filename = video.filename || `${video.id}.mp4`;
        return `/source/videos/${filename}`;
      }
      return `${apiBase}${video.stream_url}`;
    },
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
        const numericId = video.id.match(/^(\d+)/)?.[1] || video.id;
        const res = await fetch(
          `${apiBase}/api/faces/detect?video_id=${numericId}&timestamp=${timestamp}`,
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
        const numericId = videoId.match(/^(\d+)/)?.[1] || videoId;
        const res = await fetch(`${apiBase}/api/videos/metadata/dense/${numericId}`);
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

  const handleToggleSource = useCallback(() => {
    const video = getVideoEl();
    if (!video || !selectedVideo) return;
    const savedTime = video.currentTime;
    const wasPlaying = !video.paused;
    const next = !showOriginalVideo;
    setShowOriginalVideo(next);

    // After React re-renders with the new src, restore position
    requestAnimationFrame(() => {
      const v = getVideoEl();
      if (!v) return;
      const onLoaded = () => {
        v.currentTime = savedTime;
        if (wasPlaying) v.play();
      };
      v.addEventListener('loadedmetadata', onLoaded, { once: true });
    });
  }, [getVideoEl, selectedVideo, showOriginalVideo]);

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
        const w = x2 - x1;
        const h = y2 - y1;
        const padding = 0.2;
        const padX = w * padding;
        const padY = h * padding;
        const cropX = Math.max(0, x1 - padX);
        const cropY = Math.max(0, y1 - padY);
        const cropW = Math.min(video.videoWidth - cropX, w + 2 * padX);
        const cropH = Math.min(video.videoHeight - cropY, h + 2 * padY);

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
      } else {
        setSelectedFace(face);
        setShowFlagDialog(true);
      }
    },
    [batchMode],
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
            confidence: selectedFace?.confidence,
            user_label: userLabel || `Flagged by user at ${formatTime(currentTime)}`,
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
                confidence: face.confidence,
                user_label: `Batch flagged (${facesArray.length} faces) at ${formatTime(currentTime)}`,
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
        const numericId = selectedVideo.id.match(/^(\d+)/)?.[1] || selectedVideo.id;
        const res = await fetch(
          `${apiBase}/api/recognition/results?video_id=${numericId}&contestant_id=${cId}`,
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
      const c = (contestants as Array<{ number: number; id: string; nickname: string; name: string }>).find(
        (c) => c.number === id || c.id === String(id),
      );
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

  // Viewer mode: get faces from pre-loaded metadata
  useEffect(() => {
    if (mode !== 'viewer' || !viewerMeta.metadata) return;
    const faces = viewerMeta.getFacesAtTime(currentTime);
    setDetectedFaces(faces);
  }, [mode, currentTime, viewerMeta]);

  // --- Render ---

  const videoSrc = getVideoSource(selectedVideo, showOriginalVideo);
  const fps = videoMetadata?.video_info?.fps || 25;
  const frameNumber = Math.floor(currentTime * fps);

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-slate-400">
        <div className="w-10 h-10 border-2 border-slate-700 border-t-orange-500 rounded-full animate-spin mb-4" />
        <p>Loading videos...</p>
      </div>
    );
  }

  if (videosError) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-slate-400">
        <p className="text-red-400 mb-2">Failed to load videos</p>
        <button
          className="px-4 py-2 bg-slate-800 border border-slate-700 rounded text-sm text-slate-300 hover:bg-slate-700"
          onClick={() => window.location.reload()}
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-slate-950 text-slate-200 relative">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-slate-800">
        <h1 className="text-xl font-semibold text-slate-100">Annotated Video Player</h1>
        <div className="flex items-center gap-4">
          <button
            className="px-3 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-sm text-slate-300 hover:bg-slate-700"
            onClick={() => setShowFlaggedPanel((p) => !p)}
          >
            Flagged ({flaggedFaces.length})
          </button>
          <div className="flex items-center gap-2">
            <label htmlFor="video-select" className="text-sm text-slate-400">
              Video:
            </label>
            <select
              id="video-select"
              className="bg-slate-800 text-slate-200 border border-slate-700 rounded-lg px-3 py-1.5 text-sm max-w-[300px]"
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
            className="flex-1 bg-black rounded-lg overflow-hidden relative min-h-[400px]"
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
                  selectedFaces={selectedFaces}
                  getVideoRenderRect={getRenderRect}
                  videoWidth={videoMetadata?.video_info?.width ?? 1920}
                  videoHeight={videoMetadata?.video_info?.height ?? 1080}
                />
              </>
            ) : (
              <div className="flex items-center justify-center h-full text-slate-500">
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
            frameNumber={frameNumber}
            showOriginalVideo={showOriginalVideo}
            showAnnotations={showAnnotations}
            batchMode={batchMode}
            selectedCount={selectedFaces.size}
            onToggleSource={handleToggleSource}
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

          {/* Batch controls */}
          <div className="flex items-center gap-2">
            <button
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors border ${
                batchMode
                  ? 'bg-orange-500/20 text-orange-400 border-orange-500/40'
                  : 'bg-slate-800 text-slate-400 border-slate-700 hover:text-slate-200'
              }`}
              onClick={handleToggleBatchMode}
            >
              {batchMode ? 'Batch Mode ON' : 'Batch Mode'}
            </button>

            {batchMode && (
              <>
                <button
                  className="px-3 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-300 hover:bg-slate-700 disabled:opacity-40"
                  onClick={handleSelectAllFaces}
                  disabled={detectedFaces.length === 0}
                >
                  Select All
                </button>
                <button
                  className="px-3 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-300 hover:bg-slate-700 disabled:opacity-40"
                  onClick={handleClearSelection}
                  disabled={selectedFaces.size === 0}
                >
                  Clear
                </button>
                <button
                  className="px-3 py-1.5 bg-orange-500 text-white rounded-lg text-xs font-medium hover:bg-orange-400 disabled:opacity-40"
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

          {/* Timeline filter (admin mode only) */}
          {mode === 'admin' && (
            <div className="bg-slate-900/80 border border-slate-800 rounded-lg px-4 py-2">
              <div className="flex items-center gap-3">
                <label htmlFor="contestant-filter" className="text-xs text-slate-400">
                  Filter Timeline:
                </label>
                <select
                  id="contestant-filter"
                  className="bg-slate-800 text-slate-200 border border-slate-700 rounded px-2 py-1 text-xs"
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
                  <span className="text-xs text-slate-500">
                    {contestantAppearances.length} appearances
                  </span>
                )}
              </div>

              {filterContestantId !== null && contestantAppearances.length > 0 && (
                <div className="mt-2 relative h-4 bg-slate-800 rounded-full overflow-hidden">
                  {contestantAppearances.map((a, i) => (
                    <button
                      key={i}
                      className="absolute top-0 w-1.5 h-full bg-orange-500 rounded-full hover:bg-orange-400"
                      style={{
                        left: `${duration > 0 ? (a.timestamp / duration) * 100 : 0}%`,
                      }}
                      onClick={() => handleSeek(a.timestamp)}
                      title={`Jump to ${formatTime(a.timestamp)}`}
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
        <div className="flex-1 max-w-xs bg-slate-900 border border-slate-800 rounded-lg p-4 overflow-y-auto">
          <h3 className="text-sm font-semibold text-slate-200 mb-3">Video Information</h3>

          {selectedVideo && (
            <>
              <div className="mb-4">
                <h4 className="text-xs font-medium text-slate-400 mb-2">Details</h4>
                <div className="space-y-1 text-xs">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Title</span>
                    <span className="text-slate-300 truncate ml-2">{selectedVideo.name}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Resolution</span>
                    <span className="text-slate-300">
                      {videoMetadata?.video_info?.width ?? 1920}x
                      {videoMetadata?.video_info?.height ?? 1080}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">FPS</span>
                    <span className="text-slate-300">{fps}</span>
                  </div>
                </div>
              </div>

              <div className="mb-4">
                <h4 className="text-xs font-medium text-slate-400 mb-2">Recognition Summary</h4>
                <div className="space-y-1 text-xs">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Unique Contestants</span>
                    <span className="text-slate-300">
                      {videoMetadata?.recognition_summary?.unique_contestants ?? 0}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Faces Detected</span>
                    <span className="text-slate-300">
                      {videoMetadata?.recognition_summary?.total_faces_detected ?? 0}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Faces Recognized</span>
                    <span className="text-slate-300">
                      {videoMetadata?.recognition_summary?.total_faces_recognized ?? 0}
                    </span>
                  </div>
                </div>
              </div>
            </>
          )}

          <div>
            <h4 className="text-xs font-medium text-slate-400 mb-2">Current Frame Faces</h4>
            {detectedFaces.length === 0 ? (
              <p className="text-xs text-slate-600 italic">No faces detected at this timestamp</p>
            ) : (
              <div className="space-y-1">
                {detectedFaces.map((face, i) => (
                  <button
                    key={i}
                    className="w-full flex items-center justify-between px-2 py-1.5 bg-slate-800 rounded text-xs hover:bg-slate-700 transition-colors"
                    onClick={() => handleFaceClick(face)}
                  >
                    <span className="text-slate-200">
                      {face.contestant_name || 'Unknown'}
                    </span>
                    <span className="text-slate-500">
                      {((face.confidence ?? 0) * 100).toFixed(1)}%
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Flag Dialog */}
      {showFlagDialog && selectedFace && (
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
      {showBatchFlagDialog && (
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
      {showFlaggedPanel && (
        <div className="absolute top-0 right-0 w-80 h-full bg-slate-900 border-l border-slate-800 z-40 flex flex-col shadow-2xl">
          <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800">
            <h3 className="text-sm font-semibold text-slate-200">Flagged Faces</h3>
            <button
              className="text-slate-400 hover:text-slate-200 text-lg"
              onClick={() => setShowFlaggedPanel(false)}
            >
              &#10005;
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-4">
            {flaggedFaces.length === 0 ? (
              <p className="text-sm text-slate-600 italic">No faces have been flagged yet.</p>
            ) : (
              <div className="space-y-2">
                {flaggedFaces.map((flag) => (
                  <div
                    key={flag.id}
                    className="bg-slate-800 rounded-lg p-3 text-xs"
                  >
                    <div className="space-y-0.5">
                      <div className="text-slate-200 font-medium">
                        {getContestantName(flag.contestant_id)}
                      </div>
                      <div className="text-slate-500">Video: {flag.video_id}</div>
                      <div className="text-slate-500">@ {formatTime(flag.timestamp)}</div>
                    </div>
                    <span
                      className={`inline-block mt-1 px-2 py-0.5 rounded-full text-[10px] font-medium ${
                        flag.status === 'pending'
                          ? 'bg-amber-500/20 text-amber-400'
                          : flag.status === 'accepted'
                            ? 'bg-green-500/20 text-green-400'
                            : 'bg-red-500/20 text-red-400'
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
