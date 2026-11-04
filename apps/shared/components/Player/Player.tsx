import { useState, useRef, useCallback, useEffect } from 'react';
import type { FaceDetection, FlaggedFace, Video, VideoMetadata } from '../../types';
import { adminFetch, assertOk, isSessionExpired } from '../../lib/adminApi';
import { AdminErrorNotice } from '../AdminErrorNotice';
import { useVideos } from '../../hooks/useVideos';
import { useContestants } from '../../hooks/useContestants';
import { useFlaggedFaces } from '../../hooks/useFlaggedFaces';
import { VideoCanvas, type VideoCanvasHandle } from './VideoCanvas';
import { FaceOverlay } from './FaceOverlay';
import { PlayerControls } from './PlayerControls';
import { DetectionBar } from './DetectionBar';
import { FlagDialog } from './FlagDialog';
import { getVideoRenderRect } from './useAnnotations';
import { formatMmSs, videoShortName } from '../../lib/format';
import { X } from 'lucide-react';
import { Button } from '../Button';
import { Masthead } from '../Masthead';
import { DetectionStamp, Stamp } from '../Stamp';
import { FrameFace } from './FrameFace';
import { faceName, tickPercent } from './faceView';
import { useViewerMetadata } from '../../hooks/useViewerMetadata';
import { ContestantTimeline } from './ContestantTimeline';
import { pickInitialVideo } from './pickInitialVideo';

interface PlayerProps {
  mode: 'admin' | 'viewer';
  apiBase: string;
  /** Video to open on mount. Falls back to the first video when absent or unmatched. */
  initialVideoId?: string | null;
}

/** A flag's state on the slip. Decided flags were decided by a human, so they tilt. */
const FLAG_STATUS = {
  pending: { word: '待核', tone: 'stamp', tilt: false },
  accepted: { word: '已核對', tone: 'carbon', tilt: true },
  rejected: { word: '作廢', tone: 'muted', tilt: true },
} as const;

export function Player({ mode, apiBase, initialVideoId = null }: PlayerProps) {
  // Flagging is an admin act. The deployed Worker is read-only and no longer serves the flag
  // routes at all (ADR 0003), so this single derivation decides what the player offers — and
  // whether it even asks for flagged faces.
  const canFlag = mode === 'admin';

  // Data queries
  // 管理 links into test clips, so the admin player has to be able to open them.
  const {
    data: videos = [],
    isLoading,
    error: videosError,
  } = useVideos(apiBase, { includeTests: canFlag });
  const { data: contestants = [] } = useContestants(apiBase);
  const { data: flaggedFaces = [], refetch: refetchFlagged } = useFlaggedFaces(apiBase, canFlag);

  // Refs
  const videoCanvasRef = useRef<VideoCanvasHandle>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // A flag can point at another video: the seek waits for that video's metadata to load.
  const pendingSeekRef = useRef<{ videoId: string; time: number } | null>(null);

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
  const [flagError, setFlagError] = useState<unknown>(null);
  const [flagNotice, setFlagNotice] = useState<string | null>(null);

  // Freezing the frame on first interaction keeps face-object identity stable across the
  // 200 ms poll, and pins the timestamp the correction is written against.
  const [selectionSnapshot, setSelectionSnapshot] = useState<{
    faces: FaceDetection[];
    timestamp: number;
    videoId: string;
  } | null>(null);

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
      void handleSelectVideo(pickInitialVideo(videos, initialVideoId)!);
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

  const clearSelection = useCallback(() => {
    setSelectedFace(null);
    setShowFlagDialog(false);
    setSelectedFaces(new Set());
    setSelectionSnapshot(null);
    setFlagError(null);
  }, []);

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
        void fetchFacesAtTime(video.currentTime);
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
      clearSelection();
      setBatchMode(false);
      setFlagNotice(null);
      setFilterContestantId(null);
      setContestantAppearances([]);
      await loadVideoMetadata(video.id);
    },
    [loadVideoMetadata, stopPolling, clearSelection],
  );

  const handleTogglePlay = useCallback(() => {
    const video = getVideoEl();
    if (!video) return;
    if (video.paused) {
      void video.play();
    } else {
      video.pause();
    }
  }, [getVideoEl]);

  const handleSeek = useCallback(
    (time: number) => {
      // A seek lands on a different frame; anything selected against the old one is stale.
      clearSelection();
      const video = getVideoEl();
      if (video) {
        video.currentTime = time;
        void fetchFacesAtTime(time);
      }
    },
    [getVideoEl, fetchFacesAtTime, clearSelection],
  );

  /** Metadata of a freshly loaded video is where a queued cross-video seek lands. */
  const handleLoadedMetadata = useCallback(
    (loadedDuration: number) => {
      setDuration(loadedDuration);
      const pending = pendingSeekRef.current;
      if (!pending) return;
      pendingSeekRef.current = null;
      // A quick switch can surface another video's metadata first; the queued seek names one.
      if (pending.videoId !== selectedVideo?.id) return;
      handleSeek(pending.time);
    },
    [handleSeek, selectedVideo],
  );

  /** Jump to the frame a flag was taken from, switching videos first when it belongs elsewhere. */
  const handleJumpToFlag = useCallback(
    (flag: FlaggedFace) => {
      if (selectedVideo && flag.video_id === selectedVideo.id) {
        handleSeek(flag.timestamp);
        return;
      }
      const target = videos.find((v) => v.id === flag.video_id);
      if (!target) {
        setFlagNotice(`找不到影片 ${flag.video_id}，無法跳到標記位置。`);
        return;
      }
      pendingSeekRef.current = { videoId: target.id, time: flag.timestamp };
      void handleSelectVideo(target);
    },
    [selectedVideo, videos, handleSeek, handleSelectVideo],
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
      clearSelection();
      const fps = videoMetadata?.video_info?.fps || 25;
      const newTime = Math.max(0, Math.min(duration, video.currentTime + frames / fps));
      video.currentTime = newTime;
      void fetchFacesAtTime(newTime);
    },
    [getVideoEl, videoMetadata, duration, fetchFacesAtTime, clearSelection],
  );

  const handleSkipSeconds = useCallback(
    (seconds: number) => {
      const video = getVideoEl();
      if (!video) return;
      clearSelection();
      const newTime = Math.max(0, Math.min(duration, video.currentTime + seconds));
      video.currentTime = newTime;
      void fetchFacesAtTime(newTime);
    },
    [getVideoEl, duration, fetchFacesAtTime, clearSelection],
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
      if (!canFlag) return;
      // First interaction freezes the frame: pausing stops the poll from replacing the
      // objects, and the snapshot pins the timestamp the correction is written against.
      if (!selectionSnapshot) {
        const video = getVideoEl();
        if (video && !video.paused) video.pause();
        setSelectionSnapshot({
          faces: detectedFaces,
          timestamp: video?.currentTime ?? currentTime,
          videoId: selectedVideo?.id ?? '',
        });
      }
      if (batchMode) {
        setSelectedFaces((prev) => {
          const next = new Set(prev);
          if (next.has(face)) next.delete(face);
          else next.add(face);
          return next;
        });
      } else {
        setSelectedFace(face);
        setFlagError(null);
        setShowFlagDialog(true);
      }
    },
    [batchMode, canFlag, selectionSnapshot, detectedFaces, currentTime, selectedVideo, getVideoEl],
  );

  const handleToggleBatchMode = useCallback(() => {
    setBatchMode((prev) => !prev);
    setSelectedFaces(new Set());
    setSelectionSnapshot(null);
    setFlagError(null);
  }, []);

  const handleSelectAllFaces = useCallback(() => {
    const faces = selectionSnapshot?.faces ?? detectedFaces;
    if (faces.length === 0) return;
    if (!selectionSnapshot) {
      const video = getVideoEl();
      if (video && !video.paused) video.pause();
      setSelectionSnapshot({
        faces,
        timestamp: video?.currentTime ?? currentTime,
        videoId: selectedVideo?.id ?? '',
      });
    }
    setSelectedFaces(new Set(faces));
  }, [selectionSnapshot, detectedFaces, getVideoEl, currentTime, selectedVideo]);

  const handleClearSelection = useCallback(() => {
    setSelectedFaces(new Set());
    setSelectionSnapshot(null);
  }, []);

  const handleFlagSubmit = useCallback(
    async (contestantId: number, userLabel: string) => {
      if (!selectedVideo || !selectedFace) return;
      setIsFlagging(true);
      setFlagError(null);
      const snapshot = selectionSnapshot;
      const timestamp = snapshot?.timestamp ?? currentTime;
      const videoId = snapshot?.videoId ?? selectedVideo.id;
      try {
        const thumbnail = extractFaceThumbnail(selectedFace);
        const res = await adminFetch(`${apiBase}/admin/api/faces/flag`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            contestant_id: contestantId,
            video_id: videoId,
            timestamp,
            bbox: selectedFace.bbox,
            confidence: selectedFace.match_score ?? null,
            user_label: userLabel || `Flagged by user at ${formatMmSs(timestamp)}`,
            thumbnail,
          }),
        });
        await assertOk(res);
        setShowFlagDialog(false);
        setSelectedFace(null);
        setSelectionSnapshot(null);
        setFlagNotice(`已標記一張人臉於 ${formatMmSs(timestamp)}，已送入待核。`);
        void refetchFlagged();
      } catch (e) {
        setFlagError(e);
      } finally {
        setIsFlagging(false);
      }
    },
    [
      apiBase,
      selectedVideo,
      selectedFace,
      selectionSnapshot,
      currentTime,
      extractFaceThumbnail,
      refetchFlagged,
    ],
  );

  const handleBatchFlagSubmit = useCallback(
    async (contestantId: number, _userLabel: string) => {
      if (!selectedVideo || selectedFaces.size === 0) return;
      setIsFlagging(true);
      setFlagError(null);
      const snapshot = selectionSnapshot;
      const timestamp = snapshot?.timestamp ?? currentTime;
      const videoId = snapshot?.videoId ?? selectedVideo.id;
      const facesArray = Array.from(selectedFaces);
      const failed: FaceDetection[] = [];
      let successCount = 0;

      for (let i = 0; i < facesArray.length; i++) {
        const face = facesArray[i];
        try {
          const thumbnail = extractFaceThumbnail(face);
          const res = await adminFetch(`${apiBase}/admin/api/faces/flag`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              contestant_id: contestantId,
              video_id: videoId,
              timestamp,
              bbox: face.bbox,
              confidence: face.match_score ?? null,
              user_label: `Batch flagged (${facesArray.length} faces) at ${formatMmSs(timestamp)}`,
              thumbnail,
            }),
          });
          await assertOk(res);
          successCount++;
        } catch (e) {
          // Keep the failed (and, on session expiry, all remaining) faces selected so the
          // operator can retry instead of losing the batch.
          if (isSessionExpired(e)) {
            failed.push(...facesArray.slice(i));
            setFlagError(e);
            break;
          }
          failed.push(face);
        }
      }

      setSelectedFaces(new Set(failed));
      void refetchFlagged();
      if (failed.length === 0) {
        setShowBatchFlagDialog(false);
        setBatchMode(false);
        setSelectionSnapshot(null);
        setFlagNotice(`已標記 ${successCount} 張人臉，已送入待核。`);
      } else {
        setFlagNotice(`已標記 ${successCount} 張，${failed.length} 張失敗；保留選取以便重試。`);
      }
      setIsFlagging(false);
    },
    [
      apiBase,
      selectedVideo,
      selectedFaces,
      selectionSnapshot,
      currentTime,
      extractFaceThumbnail,
      refetchFlagged,
    ],
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
      return c ? `${c.nickname}（${c.name}）` : `參賽者 #${id}`;
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

  // Stable identities: the canvas redraws, and the dialog rebinds Escape, whenever these change.
  const isFaceSelected = useCallback(
    (face: FaceDetection) => selectedFace === face || (batchMode && selectedFaces.has(face)),
    [selectedFace, batchMode, selectedFaces],
  );

  const closeFlagDialog = useCallback(() => {
    setShowFlagDialog(false);
    setSelectedFace(null);
    setSelectionSnapshot(null);
    setFlagError(null);
  }, []);

  const closeBatchDialog = useCallback(() => {
    setShowBatchFlagDialog(false);
    setFlagError(null);
  }, []);

  // --- Render ---

  const videoSrc = getVideoSource(selectedVideo);
  const fps = videoMetadata?.video_info?.fps || 25;
  const frameNumber = Math.floor(currentTime * fps);
  const displayFaces = selectionSnapshot?.faces ?? detectedFaces;

  if (isLoading) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4 font-kai text-[14px] text-carbon-soft">
        <div className="size-10 animate-spin rounded-full border-2 border-carbon-deep/13 border-t-stamp" />
        <p>正在載入影片…</p>
      </div>
    );
  }

  if (videosError) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 font-kai text-[14px]">
        <p className="text-stamp">讀不到影片清單。</p>
        <Button size="sm" onClick={() => window.location.reload()}>
          重試
        </Button>
      </div>
    );
  }

  const info = videoMetadata?.video_info;
  const summary = videoMetadata?.processing_summary;
  const videoEl = getVideoEl();
  const shortName = selectedVideo ? videoShortName(selectedVideo.name) : '';
  const contestantList = contestants as Array<{ number: number; name: string; nickname: string }>;

  return (
    <div className="relative flex min-h-full flex-1 flex-col gap-6 px-8 pb-5 pt-8">
      <Masthead title="播放" hint={canFlag ? '播放影片並標記人臉' : '看片、人臉框與時間軸'}>
        <div className="flex items-center gap-2">
          {canFlag && (
            <Button
              size="sm"
              aria-expanded={showFlaggedPanel}
              onClick={() => setShowFlaggedPanel((p) => !p)}
            >
              已標記 {flaggedFaces.length}
            </Button>
          )}
          <select
            aria-label="影片"
            className="field field-select w-[220px]"
            value={selectedVideo?.id ?? ''}
            onChange={(e) => {
              const v = videos.find((v) => v.id === e.target.value);
              if (v) void handleSelectVideo(v);
            }}
          >
            {videos.map((v) => (
              <option key={v.id} value={v.id}>
                {videoShortName(v.name)}
              </option>
            ))}
          </select>
        </div>
      </Masthead>

      {flagError ? <AdminErrorNotice error={flagError} label="標記失敗" /> : null}
      {flagNotice ? (
        <div
          role="status"
          aria-live="polite"
          className="rounded-md border border-carbon-deep/13 bg-tint px-4 py-2 font-kai text-[13px] text-carbon-deep"
        >
          {flagNotice}
        </div>
      ) : null}

      <div className="flex flex-col gap-2">
        <div
          ref={containerRef}
          className="relative aspect-[2.4/1] w-full overflow-hidden rounded bg-black"
        >
          {selectedVideo ? (
            <>
              <VideoCanvas
                ref={videoCanvasRef}
                videoSrc={videoSrc}
                faces={displayFaces}
                showAnnotations={showAnnotations}
                isSelected={isFaceSelected}
                containerRef={containerRef}
                onTimeUpdate={setCurrentTime}
                onLoadedMetadata={handleLoadedMetadata}
                onPlay={handlePlay}
                onPause={handlePause}
                onEnded={handleEnded}
              />
              <FaceOverlay
                faces={displayFaces}
                onFaceClick={handleFaceClick}
                selectedFace={selectedFace}
                batchMode={batchMode}
                canFlag={canFlag}
                selectedFaces={selectedFaces}
                getVideoRenderRect={getRenderRect}
              />
            </>
          ) : (
            <div className="flex h-full items-center justify-center font-kai text-[14px] text-paper-light/70">
              請選擇影片
            </div>
          )}
        </div>

        <PlayerControls
          videoRef={{ current: videoEl }}
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
      </div>

      <div className="flex flex-1 gap-6">
        <div className="flex min-w-0 flex-1 flex-col gap-6">
          <DetectionBar
            faceCount={displayFaces.length}
            recognizedCount={displayFaces.filter((f) => f.matched).length}
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
              <Button
                className={batchMode ? 'bg-tint font-bold text-carbon-deep' : ''}
                aria-pressed={batchMode}
                onClick={handleToggleBatchMode}
              >
                {batchMode ? '批次模式 開' : '批次模式'}
              </Button>

              {batchMode && (
                <>
                  <Button onClick={handleSelectAllFaces} disabled={displayFaces.length === 0}>
                    全選
                  </Button>
                  <Button onClick={handleClearSelection} disabled={selectedFaces.size === 0}>
                    清除
                  </Button>
                  <div className="flex-1" />
                  <Button
                    variant="primary"
                    onClick={() => {
                      if (selectedFaces.size > 0) setShowBatchFlagDialog(true);
                    }}
                    disabled={selectedFaces.size === 0}
                  >
                    標記所選 {selectedFaces.size}
                  </Button>
                </>
              )}
            </div>
          )}

          {/* Timeline filter (admin mode only) */}
          {mode === 'admin' && (
            <div className="flex flex-col gap-2">
              <div className="flex items-center gap-3">
                <label
                  htmlFor="contestant-filter"
                  className="font-kai text-[13px] text-carbon-soft"
                >
                  篩選時間軸
                </label>
                <select
                  id="contestant-filter"
                  className="field field-select w-[200px]"
                  onChange={(e) =>
                    handleFilterByContestant(e.target.value ? parseInt(e.target.value, 10) : null)
                  }
                  value={filterContestantId ?? ''}
                >
                  <option value="">全部參賽者</option>
                  {contestantList.map((c) => (
                    <option key={c.number} value={c.number}>
                      #{c.number} · {c.nickname}
                    </option>
                  ))}
                </select>
                {filterContestantId !== null && (
                  <span className="font-kai text-[12px] text-ink-muted">
                    出場 {contestantAppearances.length} 次
                  </span>
                )}
              </div>

              {filterContestantId !== null && contestantAppearances.length > 0 && (
                <>
                  <div className="relative h-8 overflow-hidden rounded-xs bg-tint">
                    {contestantAppearances.map((a, i) => (
                      <button
                        key={i}
                        className="absolute top-0 h-full w-0.5 bg-carbon-soft hover:bg-carbon-deep"
                        style={{ left: `${tickPercent(a.timestamp, duration)}%` }}
                        onClick={() => handleSeek(a.timestamp)}
                        title={`跳到 ${formatMmSs(a.timestamp)}`}
                        aria-label={`跳到 ${formatMmSs(a.timestamp)}`}
                      />
                    ))}
                    <div
                      className="pointer-events-none absolute top-0 h-full w-0.5 bg-stamp"
                      style={{ left: `${tickPercent(currentTime, duration)}%` }}
                    />
                  </div>
                  <div className="flex justify-between font-mono text-[12px] tabular-nums text-ink-muted">
                    <span>00:00</span>
                    <span>{formatMmSs(duration)}</span>
                  </div>
                </>
              )}
            </div>
          )}
        </div>

        <div className="flex w-[300px] shrink-0 flex-col gap-0.5 border-l border-carbon-deep/13 pl-6">
          <h3 className="pb-2 font-kai text-[18px] font-normal text-carbon-deep">目前畫格人臉</h3>
          {displayFaces.length === 0 ? (
            <p className="font-kai text-[13px] text-ink-muted">這個時間點沒有偵測到人臉。</p>
          ) : (
            displayFaces.map((face, i) => (
              <button
                key={i}
                className={`flex h-8 w-full shrink-0 items-center gap-2 rounded-md px-1 text-left transition-colors hover:bg-tint ${
                  isFaceSelected(face) ? 'bg-tint' : ''
                }`}
                onClick={() => handleFaceClick(face)}
                title={face.matched ? undefined : `未認出 · 偵測分 ${face.det_score.toFixed(2)}`}
              >
                <FrameFace video={videoEl} bbox={face.bbox} size={24} alt="" />
                <span
                  className={`min-w-0 flex-1 truncate font-kai text-[14px] ${
                    face.matched ? 'text-carbon-deep' : 'text-carbon-soft'
                  }`}
                >
                  {faceName(face)}
                </span>
                {face.matched && (
                  <>
                    {face.match_score != null && (
                      <span className="font-mono text-[12px] tabular-nums text-carbon">
                        {face.match_score.toFixed(2)}
                      </span>
                    )}
                    <DetectionStamp detection={face} />
                  </>
                )}
              </button>
            ))
          )}
        </div>

        <div className="flex w-[236px] shrink-0 flex-col gap-4 border-l border-carbon-deep/13 pl-6">
          {selectedVideo && (
            <>
              <InfoBlock
                title="影片資料"
                rows={[
                  { key: '標題', value: shortName, text: true },
                  {
                    key: '解析度',
                    value: info?.width && info?.height ? `${info.width}×${info.height}` : '—',
                  },
                  { key: '每秒格數', value: String(fps) },
                ]}
              />
              <InfoBlock
                title="辨識摘要"
                rows={[
                  { key: '參賽者', value: count(summary?.unique_contestants) },
                  { key: '偵測人臉', value: count(summary?.total_faces_detected) },
                  { key: '認出人臉', value: count(summary?.total_recognitions) },
                ]}
              />
            </>
          )}
        </div>
      </div>

      {/* Flag Dialog — admin only; a viewer cannot reach these states either way */}
      {canFlag && showFlagDialog && selectedFace && (
        <FlagDialog
          mode="single"
          face={selectedFace}
          contestants={contestantList}
          video={videoEl}
          where={`${formatMmSs(selectionSnapshot?.timestamp ?? currentTime)} · ${shortName}`}
          onSubmit={handleFlagSubmit}
          onClose={closeFlagDialog}
          isSubmitting={isFlagging}
          error={flagError}
        />
      )}

      {/* Batch Flag Dialog */}
      {canFlag && showBatchFlagDialog && (
        <FlagDialog
          mode="batch"
          selectedFaces={Array.from(selectedFaces)}
          contestants={contestantList}
          video={videoEl}
          onSubmit={handleBatchFlagSubmit}
          onClose={closeBatchDialog}
          isSubmitting={isFlagging}
          error={flagError}
        />
      )}

      {/* Flagged Faces Panel */}
      {canFlag && showFlaggedPanel && (
        <div className="absolute right-0 top-0 z-40 flex h-full w-80 flex-col border-l border-carbon-deep/33 bg-ground">
          <div className="flex items-center justify-between border-b border-carbon-deep/13 px-4 py-3">
            <h3 className="font-kai text-[18px] font-normal text-carbon-deep">已標記人臉</h3>
            <button
              className="inline-flex size-8 items-center justify-center rounded-md text-carbon-soft transition-colors hover:bg-tint"
              aria-label="關閉"
              onClick={() => setShowFlaggedPanel(false)}
            >
              <X size={16} aria-hidden />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto px-4">
            {flaggedFaces.length === 0 ? (
              <p className="py-4 font-kai text-[13px] text-ink-muted">還沒有標記任何人臉。</p>
            ) : (
              flaggedFaces.map((flag) => {
                const status = FLAG_STATUS[flag.status];
                return (
                  <div
                    key={flag.id}
                    className="flex flex-col gap-2 border-b border-carbon-deep/13 py-3"
                  >
                    <div className="flex items-center gap-3">
                      {flag.thumbnail ? (
                        <img
                          src={flag.thumbnail}
                          alt={`被標記的人臉 @ ${formatMmSs(flag.timestamp)}`}
                          className="size-14 shrink-0 rounded bg-tint object-cover"
                        />
                      ) : (
                        <div
                          aria-hidden="true"
                          className="flex size-14 shrink-0 items-center justify-center rounded bg-tint font-kai text-[12px] text-ink-muted"
                        >
                          無縮圖
                        </div>
                      )}
                      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                        <span className="truncate font-kai text-[14px] text-carbon-deep">
                          {getContestantName(flag.contestant_id)}
                        </span>
                        <span className="truncate font-kai text-[12px] text-ink-muted">
                          {videoShortName(flag.video_id)}
                        </span>
                        <span className="font-mono text-[12px] tabular-nums text-ink-muted">
                          {formatMmSs(flag.timestamp)}
                        </span>
                      </div>
                      <Stamp tone={status.tone} tilt={status.tilt}>
                        {status.word}
                      </Stamp>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button size="sm" onClick={() => handleJumpToFlag(flag)}>
                        跳到該幀
                      </Button>
                      {/* The admin SPA is mounted at /admin; a plain anchor survives the trip. */}
                      <a
                        href="/admin/flagging"
                        className="inline-flex h-8 items-center rounded-md px-3 font-kai text-[13px] text-carbon transition-colors hover:bg-tint"
                      >
                        前往待核
                      </a>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function count(value: number | undefined): string {
  return value?.toLocaleString() ?? '—';
}

function InfoBlock({
  title,
  rows,
}: {
  title: string;
  rows: Array<{ key: string; value: string; text?: boolean }>;
}) {
  return (
    <div className="flex flex-col gap-2">
      <h3 className="font-kai text-[18px] font-normal text-carbon-deep">{title}</h3>
      {rows.map((r) => (
        <div key={r.key} className="flex items-center justify-between gap-2 text-[13px]">
          <span className="shrink-0 font-kai text-carbon-soft">{r.key}</span>
          <span
            className={`truncate text-carbon-deep ${r.text ? 'font-kai' : 'font-mono tabular-nums'}`}
          >
            {r.value}
          </span>
        </div>
      ))}
    </div>
  );
}
