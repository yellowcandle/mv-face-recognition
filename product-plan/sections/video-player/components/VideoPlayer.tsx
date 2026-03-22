import { useState } from "react";
import {
  Play,
  Pause,
  Square,
  SkipBack,
  SkipForward,
  ChevronLeft,
  ChevronRight,
  Maximize2,
  Volume2,
  VolumeX,
  Filter,
  X,
  Clock,
  Users,
  Menu,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type {
  VideoPlayerProps,
  Video,
  Contestant,
  FaceDetection,
} from "@product/sections/video-player/types";

const styleId = "video-player-animations";
if (typeof document !== "undefined" && !document.getElementById(styleId)) {
  const style = document.createElement("style");
  style.id = styleId;
  style.textContent = `
    @keyframes detection-pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.5; }
    }
    @keyframes detection-ping {
      0% { transform: scale(1); opacity: 0.8; }
      100% { transform: scale(1.5); opacity: 0; }
    }
    @keyframes corner-glow {
      0%, 100% { filter: drop-shadow(0 0 2px rgb(56 189 248 / 0.6)); }
      50% { filter: drop-shadow(0 0 6px rgb(56 189 248 / 0.9)); }
    }
    @keyframes progress-shimmer {
      0% { background-position: -200% 0; }
      100% { background-position: 200% 0; }
    }
    @keyframes fade-slide-in {
      from { opacity: 0; transform: translateY(8px); }
      to { opacity: 1; transform: translateY(0); }
    }
    @keyframes sidebar-slide {
      from { transform: translateX(-100%); opacity: 0; }
      to { transform: translateX(0); opacity: 1; }
    }
    .animate-detection-pulse { animation: detection-pulse 2s ease-in-out infinite; }
    .animate-detection-ping { animation: detection-ping 1.5s ease-out infinite; }
    .animate-corner-glow { animation: corner-glow 2s ease-in-out infinite; }
    .animate-progress-shimmer {
      background: linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent);
      background-size: 200% 100%;
      animation: progress-shimmer 2s linear infinite;
    }
    .animate-fade-slide-in { animation: fade-slide-in 0.3s ease-out forwards; }
    .animate-sidebar-slide { animation: sidebar-slide 0.25s ease-out forwards; }
  `;
  document.head.appendChild(style);
}

function formatTime(seconds: number): string {
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  if (hrs > 0) {
    return `${hrs}:${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  }
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  return `${mins} 分鐘`;
}

function formatFrameNumber(timestamp: number, fps: number = 30): string {
  return `F${Math.floor(timestamp * fps).toString().padStart(6, "0")}`;
}

interface CornerFrameProps {
  className?: string;
  color?: string;
  animated?: boolean;
}

function CornerFrame({ className, color = "sky", animated = true }: CornerFrameProps) {
  const cornerSize = "20%";
  const strokeWidth = "2px";
  const colorClasses = {
    sky: "border-sky-400",
    blue: "border-blue-400",
  };
  const glowClasses = {
    sky: "shadow-[0_0_8px_rgba(56,189,248,0.5)]",
    blue: "shadow-[0_0_8px_rgba(59,130,246,0.5)]",
  };

  return (
    <div className={cn("absolute inset-0 pointer-events-none", className)}>
      <div
        className={cn(
          "absolute top-0 left-0 border-t border-l",
          colorClasses[color as keyof typeof colorClasses],
          glowClasses[color as keyof typeof glowClasses],
          animated && "animate-corner-glow"
        )}
        style={{ width: cornerSize, height: cornerSize, borderWidth: strokeWidth }}
      />
      <div
        className={cn(
          "absolute top-0 right-0 border-t border-r",
          colorClasses[color as keyof typeof colorClasses],
          glowClasses[color as keyof typeof glowClasses],
          animated && "animate-corner-glow"
        )}
        style={{ width: cornerSize, height: cornerSize, borderWidth: strokeWidth }}
      />
      <div
        className={cn(
          "absolute bottom-0 left-0 border-b border-l",
          colorClasses[color as keyof typeof colorClasses],
          glowClasses[color as keyof typeof glowClasses],
          animated && "animate-corner-glow"
        )}
        style={{ width: cornerSize, height: cornerSize, borderWidth: strokeWidth }}
      />
      <div
        className={cn(
          "absolute bottom-0 right-0 border-b border-r",
          colorClasses[color as keyof typeof colorClasses],
          glowClasses[color as keyof typeof glowClasses],
          animated && "animate-corner-glow"
        )}
        style={{ width: cornerSize, height: cornerSize, borderWidth: strokeWidth }}
      />
    </div>
  );
}

interface VideoSidebarProps {
  videos: Video[];
  currentVideoId: string | null;
  onSelectVideo?: (videoId: string) => void;
  isOpen: boolean;
  onClose: () => void;
}

function VideoSidebar({ videos, currentVideoId, onSelectVideo, isOpen, onClose }: VideoSidebarProps) {
  return (
    <>
      <div
        className={cn(
          "fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-40 lg:hidden transition-opacity duration-300",
          isOpen ? "opacity-100" : "opacity-0 pointer-events-none"
        )}
        onClick={onClose}
      />

      <div
        className={cn(
          "fixed lg:relative inset-y-0 left-0 z-50 lg:z-auto",
          "w-72 xl:w-80 flex flex-col",
          "bg-slate-900/70 backdrop-blur-xl",
          "border-r border-slate-700/50",
          "lg:translate-x-0 transition-transform duration-300 ease-out",
          isOpen ? "translate-x-0 animate-sidebar-slide" : "-translate-x-full lg:translate-x-0"
        )}
      >
        <div className="p-4 xl:p-5 border-b border-slate-700/50">
          <div className="flex items-center justify-between">
            <h2 className="font-medium text-slate-100 flex items-center gap-2.5" style={{ fontFamily: "'Noto Sans TC', sans-serif" }}>
              <div className="w-8 h-8 rounded-lg bg-blue-500/20 flex items-center justify-center">
                <Clock className="w-4 h-4 text-blue-400" />
              </div>
              影片列表
            </h2>
            <button
              onClick={onClose}
              className="lg:hidden p-2 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
          <p className="text-xs text-slate-500 mt-2 ml-10.5" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
            {videos.length} ITEMS
          </p>
        </div>

        <div className="flex-1 overflow-y-auto scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
          {videos.map((video, index) => {
            const isActive = video.id === currentVideoId;
            return (
              <button
                key={video.id}
                onClick={() => onSelectVideo?.(video.id)}
                className={cn(
                  "w-full text-left p-3 xl:p-4 transition-all duration-200",
                  "border-b border-slate-800/30",
                  "hover:bg-slate-800/40",
                  "group relative",
                  isActive && "bg-blue-500/10 border-l-2 border-l-blue-400"
                )}
                style={{ animationDelay: `${index * 50}ms` }}
              >
                <div className="flex gap-3">
                  <div className="w-24 xl:w-28 h-14 xl:h-16 rounded-lg bg-slate-800 flex-shrink-0 overflow-hidden relative">
                    <div className="absolute inset-0 bg-gradient-to-t from-slate-900/90 via-slate-900/20 to-transparent z-10" />
                    <div className="absolute inset-0 bg-[repeating-linear-gradient(0deg,transparent,transparent_2px,rgba(0,0,0,0.1)_2px,rgba(0,0,0,0.1)_4px)] z-10" />
                    <div className="absolute inset-0 bg-gradient-to-br from-blue-600/20 via-slate-800 to-sky-500/10" />
                    <div
                      className="absolute bottom-1.5 right-1.5 z-20 bg-slate-900/90 backdrop-blur-sm text-[10px] px-1.5 py-0.5 rounded text-slate-300 border border-slate-700/50"
                      style={{ fontFamily: "'JetBrains Mono', monospace" }}
                    >
                      {formatTime(video.duration)}
                    </div>
                    <div className="absolute inset-1 opacity-0 group-hover:opacity-100 transition-opacity duration-300 z-20">
                      <CornerFrame color="sky" animated={false} />
                    </div>
                  </div>

                  <div className="flex-1 min-w-0 py-0.5">
                    <h3
                      className={cn(
                        "text-sm font-medium truncate leading-tight",
                        isActive ? "text-blue-300" : "text-slate-200 group-hover:text-slate-100"
                      )}
                      style={{ fontFamily: "'Noto Sans TC', sans-serif" }}
                    >
                      {video.title}
                    </h3>
                    <div className="flex items-center gap-2 mt-1.5">
                      <span
                        className="text-[10px] text-sky-400/80 bg-sky-400/10 px-1.5 py-0.5 rounded"
                        style={{ fontFamily: "'JetBrains Mono', monospace" }}
                      >
                        {video.faceCount} FACES
                      </span>
                    </div>
                  </div>
                </div>

                {isActive && (
                  <div className="absolute inset-y-0 left-0 w-0.5 bg-gradient-to-b from-blue-400 via-sky-400 to-blue-400 shadow-[0_0_12px_rgba(56,189,248,0.6)]" />
                )}
              </button>
            );
          })}
        </div>
      </div>
    </>
  );
}

interface VideoControlsProps {
  isPlaying: boolean;
  currentTime: number;
  duration: number;
  playbackSpeed: number;
  onPlay?: () => void;
  onPause?: () => void;
  onStop?: () => void;
  onSeek?: (timestamp: number) => void;
  onSkipFrames?: (frames: number) => void;
  onSkipSeconds?: (seconds: number) => void;
  onSpeedChange?: (speed: number) => void;
}

function VideoControls({
  isPlaying,
  currentTime,
  duration,
  playbackSpeed,
  onPlay,
  onPause,
  onStop,
  onSeek,
  onSkipFrames,
  onSkipSeconds,
  onSpeedChange,
}: VideoControlsProps) {
  const [isMuted, setIsMuted] = useState(false);
  const speedOptions = [0.25, 0.5, 1, 1.5, 2];

  const progressPercent = duration > 0 ? (currentTime / duration) * 100 : 0;

  return (
    <div className="bg-slate-900/80 backdrop-blur-xl border-t border-slate-700/50 p-4 xl:p-5">
      <div className="mb-5">
        <div
          className="h-2 bg-slate-800 rounded-full cursor-pointer group relative overflow-hidden"
          onClick={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            const percent = (e.clientX - rect.left) / rect.width;
            onSeek?.(percent * duration);
          }}
        >
          <div className="absolute inset-0 bg-[repeating-linear-gradient(90deg,transparent,transparent_4px,rgba(100,116,139,0.1)_4px,rgba(100,116,139,0.1)_8px)]" />

          <div
            className="absolute inset-y-0 left-0 rounded-full transition-all duration-150 ease-out"
            style={{ width: `${progressPercent}%` }}
          >
            <div className="absolute inset-0 bg-gradient-to-r from-blue-600 via-blue-500 to-sky-400 rounded-full" />
            <div className="absolute inset-0 animate-progress-shimmer rounded-full" />
            <div className="absolute inset-x-0 top-0 h-1/2 bg-gradient-to-b from-white/20 to-transparent rounded-t-full" />
          </div>

          <div
            className="absolute top-1/2 -translate-y-1/2 w-4 h-4 -ml-2 opacity-0 group-hover:opacity-100 transition-all duration-200"
            style={{ left: `${progressPercent}%` }}
          >
            <div className="absolute inset-0 bg-white rounded-full shadow-[0_0_12px_rgba(56,189,248,0.8)]" />
            <div className="absolute inset-1 bg-sky-400 rounded-full" />
          </div>
        </div>

        <div className="flex justify-between mt-2.5">
          <div className="flex items-center gap-3">
            <span
              className="text-sm text-slate-100 tabular-nums"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}
            >
              {formatTime(currentTime)}
            </span>
            <span className="text-xs text-slate-500">/</span>
            <span
              className="text-xs text-slate-500 tabular-nums"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}
            >
              {formatTime(duration)}
            </span>
          </div>
          <span
            className="text-[10px] text-sky-400/70 bg-sky-400/10 px-2 py-0.5 rounded"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}
          >
            {formatFrameNumber(currentTime)}
          </span>
        </div>
      </div>

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5 sm:gap-2">
          <button
            onClick={() => onSkipFrames?.(-10)}
            className="p-2 sm:p-2.5 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-slate-800/60 transition-all duration-200 active:scale-95"
            title="倒退 10 幀"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>

          <button
            onClick={() => onSkipSeconds?.(-5)}
            className="p-2 sm:p-2.5 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-slate-800/60 transition-all duration-200 active:scale-95"
            title="倒退 5 秒"
          >
            <SkipBack className="w-5 h-5" />
          </button>

          <button
            onClick={isPlaying ? onPause : onPlay}
            className={cn(
              "p-3 sm:p-3.5 rounded-xl transition-all duration-200 active:scale-95",
              "bg-gradient-to-br from-blue-500 to-blue-600",
              "hover:from-blue-400 hover:to-blue-500",
              "text-white shadow-[0_0_20px_rgba(59,130,246,0.4)]",
              "hover:shadow-[0_0_30px_rgba(59,130,246,0.6)]"
            )}
          >
            {isPlaying ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5 ml-0.5" />}
          </button>

          <button
            onClick={onStop}
            className="p-2 sm:p-2.5 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-slate-800/60 transition-all duration-200 active:scale-95"
          >
            <Square className="w-5 h-5" />
          </button>

          <button
            onClick={() => onSkipSeconds?.(5)}
            className="p-2 sm:p-2.5 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-slate-800/60 transition-all duration-200 active:scale-95"
            title="快進 5 秒"
          >
            <SkipForward className="w-5 h-5" />
          </button>

          <button
            onClick={() => onSkipFrames?.(10)}
            className="p-2 sm:p-2.5 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-slate-800/60 transition-all duration-200 active:scale-95"
            title="快進 10 幀"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>

        <div className="flex items-center gap-2 sm:gap-4">
          <div className="hidden sm:flex items-center gap-2">
            <span className="text-xs text-slate-500" style={{ fontFamily: "'Noto Sans TC', sans-serif" }}>
              速度
            </span>
            <select
              value={playbackSpeed}
              onChange={(e) => onSpeedChange?.(parseFloat(e.target.value))}
              className="bg-slate-800/60 border border-slate-700/50 rounded-lg px-2.5 py-1.5 text-sm text-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50 transition-all cursor-pointer"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}
            >
              {speedOptions.map((speed) => (
                <option key={speed} value={speed}>
                  {speed}x
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={() => setIsMuted(!isMuted)}
            className="p-2 sm:p-2.5 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-slate-800/60 transition-all duration-200"
          >
            {isMuted ? <VolumeX className="w-5 h-5" /> : <Volume2 className="w-5 h-5" />}
          </button>

          <button className="p-2 sm:p-2.5 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-slate-800/60 transition-all duration-200">
            <Maximize2 className="w-5 h-5" />
          </button>
        </div>
      </div>
    </div>
  );
}

interface FaceOverlayProps {
  detections: FaceDetection[];
  contestants: Contestant[];
  videoWidth: number;
  videoHeight: number;
  onContestantClick?: (contestantId: string) => void;
}

function FaceOverlay({
  detections,
  contestants,
  videoWidth,
  videoHeight,
  onContestantClick,
}: FaceOverlayProps) {
  const contestantMap = new Map(contestants.map((c) => [c.id, c]));

  return (
    <div className="absolute inset-0 pointer-events-none">
      {detections.map((det, index) => {
        const contestant = contestantMap.get(det.contestantId);
        const scaleX = 100 / videoWidth;
        const scaleY = 100 / videoHeight;

        return (
          <div
            key={det.id}
            className="absolute pointer-events-auto cursor-pointer group animate-fade-slide-in"
            style={{
              left: `${det.boundingBox.x * scaleX}%`,
              top: `${det.boundingBox.y * scaleY}%`,
              width: `${det.boundingBox.width * scaleX}%`,
              height: `${det.boundingBox.height * scaleY}%`,
              animationDelay: `${index * 100}ms`,
            }}
            onClick={() => onContestantClick?.(det.contestantId)}
          >
            <div className="absolute inset-0 border-2 border-sky-400/50 rounded animate-detection-ping" />

            <CornerFrame color="sky" animated={true} />

            <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
              <div className="w-2 h-2 border border-sky-400 rotate-45" />
            </div>

            <div
              className={cn(
                "absolute -bottom-8 left-1/2 -translate-x-1/2",
                "bg-slate-900/90 backdrop-blur-md",
                "border border-slate-700/50",
                "px-3 py-1 rounded-lg",
                "opacity-0 group-hover:opacity-100 transition-all duration-200",
                "whitespace-nowrap shadow-lg shadow-slate-950/50"
              )}
            >
              <span className="text-xs text-slate-100" style={{ fontFamily: "'Noto Sans TC', sans-serif" }}>
                {contestant?.nickname || "未知"}
              </span>
              <span
                className="ml-2 text-[10px] text-sky-400"
                style={{ fontFamily: "'JetBrains Mono', monospace" }}
              >
                {Math.round(det.confidence * 100)}%
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

interface ContestantThumbnailStripProps {
  visibleContestantIds: string[];
  contestants: Contestant[];
  onContestantClick?: (contestantId: string) => void;
}

function ContestantThumbnailStrip({
  visibleContestantIds,
  contestants,
  onContestantClick,
}: ContestantThumbnailStripProps) {
  const contestantMap = new Map(contestants.map((c) => [c.id, c]));
  const visibleContestants = visibleContestantIds
    .map((id) => contestantMap.get(id))
    .filter((c): c is Contestant => c !== undefined);

  if (visibleContestants.length === 0) return null;

  return (
    <div className="bg-slate-900/60 backdrop-blur-xl border-t border-slate-700/50 p-3 xl:p-4">
      <div className="flex items-center gap-2 mb-3">
        <div className="w-6 h-6 rounded bg-blue-500/20 flex items-center justify-center">
          <Users className="w-3.5 h-3.5 text-blue-400" />
        </div>
        <span className="text-xs text-slate-400" style={{ fontFamily: "'Noto Sans TC', sans-serif" }}>
          畫面中出現
        </span>
        <span
          className="text-[10px] text-sky-400 bg-sky-400/10 px-1.5 py-0.5 rounded"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          {visibleContestants.length} DETECTED
        </span>
      </div>
      <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
        {visibleContestants.map((contestant, index) => (
          <button
            key={contestant.id}
            onClick={() => onContestantClick?.(contestant.id)}
            className={cn(
              "flex items-center gap-2.5 flex-shrink-0",
              "bg-slate-800/50 hover:bg-slate-700/50",
              "border border-slate-700/50 hover:border-sky-500/30",
              "rounded-lg px-3 py-2",
              "transition-all duration-200",
              "hover:shadow-[0_0_20px_rgba(56,189,248,0.1)]",
              "animate-fade-slide-in"
            )}
            style={{ animationDelay: `${index * 75}ms` }}
          >
            <div className="relative">
              <div className="w-9 h-9 rounded-full bg-gradient-to-br from-blue-500 to-sky-400 flex items-center justify-center text-white text-sm font-medium shadow-[0_0_12px_rgba(56,189,248,0.3)]">
                {contestant.chineseName.charAt(0)}
              </div>
              <div className="absolute inset-0 rounded-full border-2 border-sky-400/50 animate-detection-pulse" />
            </div>
            <div className="text-left">
              <div className="text-sm text-slate-100" style={{ fontFamily: "'Noto Sans TC', sans-serif" }}>
                {contestant.nickname}
              </div>
              <div className="text-[10px] text-slate-500" style={{ fontFamily: "'Noto Sans TC', sans-serif" }}>
                {contestant.chineseName}
              </div>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

interface ContestantFilterProps {
  contestants: Contestant[];
  filterContestantId: string | null;
  onFilterContestant?: (contestantId: string | null) => void;
}

function ContestantFilter({
  contestants,
  filterContestantId,
  onFilterContestant,
}: ContestantFilterProps) {
  const [isOpen, setIsOpen] = useState(false);
  const selectedContestant = contestants.find((c) => c.id === filterContestantId);

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          "flex items-center gap-2 px-3 py-2 rounded-lg border transition-all duration-200",
          filterContestantId
            ? "bg-blue-500/20 border-blue-500/50 text-blue-300 shadow-[0_0_15px_rgba(59,130,246,0.2)]"
            : "bg-slate-800/60 border-slate-700/50 text-slate-300 hover:border-slate-600 hover:bg-slate-800"
        )}
      >
        <Filter className="w-4 h-4" />
        <span className="text-sm" style={{ fontFamily: "'Noto Sans TC', sans-serif" }}>
          {selectedContestant ? selectedContestant.nickname : "篩選參賽者"}
        </span>
        {filterContestantId && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onFilterContestant?.(null);
            }}
            className="ml-1 hover:text-white transition-colors"
          >
            <X className="w-3 h-3" />
          </button>
        )}
      </button>

      {isOpen && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setIsOpen(false)} />
          <div className="absolute top-full mt-2 right-0 z-20 w-64 bg-slate-800/95 backdrop-blur-xl border border-slate-700/50 rounded-xl shadow-2xl shadow-slate-950/50 overflow-hidden animate-fade-slide-in">
            <div className="p-3 border-b border-slate-700/50">
              <span className="text-xs text-slate-500" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                SELECT CONTESTANT
              </span>
            </div>
            <div className="max-h-64 overflow-y-auto scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
              {contestants.map((contestant) => (
                <button
                  key={contestant.id}
                  onClick={() => {
                    onFilterContestant?.(contestant.id);
                    setIsOpen(false);
                  }}
                  className={cn(
                    "w-full flex items-center gap-3 px-4 py-3",
                    "hover:bg-slate-700/50 transition-all duration-200",
                    contestant.id === filterContestantId && "bg-blue-500/20"
                  )}
                >
                  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-sky-400 flex items-center justify-center text-white text-xs font-medium">
                    {contestant.chineseName.charAt(0)}
                  </div>
                  <div className="text-left">
                    <div className="text-sm text-slate-100" style={{ fontFamily: "'Noto Sans TC', sans-serif" }}>
                      {contestant.nickname}
                    </div>
                    <div className="text-xs text-slate-500" style={{ fontFamily: "'Noto Sans TC', sans-serif" }}>
                      {contestant.chineseName}
                    </div>
                  </div>
                  {contestant.id === filterContestantId && (
                    <div className="ml-auto w-2 h-2 rounded-full bg-blue-400 shadow-[0_0_8px_rgba(96,165,250,0.8)]" />
                  )}
                </button>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

interface TimelineMarkersProps {
  detections: FaceDetection[];
  filterContestantId: string | null;
  duration: number;
  onJumpToTimestamp?: (timestamp: number) => void;
}

function TimelineMarkers({
  detections,
  filterContestantId,
  duration,
  onJumpToTimestamp,
}: TimelineMarkersProps) {
  if (!filterContestantId || duration === 0) return null;

  const filteredDetections = detections.filter(
    (d) => d.contestantId === filterContestantId
  );

  if (filteredDetections.length === 0) return null;

  return (
    <div className="bg-slate-800/40 backdrop-blur-sm border border-slate-700/30 rounded-lg p-3 animate-fade-slide-in">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-xs text-slate-400" style={{ fontFamily: "'Noto Sans TC', sans-serif" }}>
          出場時間點
        </span>
        <span
          className="text-[10px] text-sky-400 bg-sky-400/10 px-1.5 py-0.5 rounded"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          {filteredDetections.length} MARKERS
        </span>
      </div>
      <div className="relative h-3 bg-slate-700/50 rounded-full overflow-hidden">
        <div className="absolute inset-0 bg-[repeating-linear-gradient(90deg,transparent,transparent_10%,rgba(100,116,139,0.1)_10%,rgba(100,116,139,0.1)_10.5%)]" />

        {filteredDetections.map((det) => (
          <button
            key={det.id}
            onClick={() => onJumpToTimestamp?.(det.timestamp)}
            className={cn(
              "absolute top-1/2 -translate-y-1/2 w-2.5 h-2.5 -ml-1.25",
              "bg-sky-400 rounded-full",
              "hover:bg-sky-300 hover:scale-150",
              "shadow-[0_0_8px_rgba(56,189,248,0.6)]",
              "transition-all duration-200 cursor-pointer"
            )}
            style={{ left: `${(det.timestamp / duration) * 100}%` }}
            title={formatTime(det.timestamp)}
          />
        ))}
      </div>
    </div>
  );
}

export function VideoPlayer({
  videos,
  contestants,
  faceDetections,
  currentVideo,
  visibleContestants,
  filterContestantId,
  onSelectVideo,
  onPlay,
  onPause,
  onStop,
  onSeek,
  onSkipFrames,
  onSkipSeconds,
  onSpeedChange,
  onContestantClick,
  onFilterContestant,
  onJumpToTimestamp,
}: VideoPlayerProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const selectedVideo = videos.find((v) => v.id === currentVideo?.id);
  const currentDetections = faceDetections.filter(
    (d) =>
      d.videoId === currentVideo?.id &&
      Math.abs(d.timestamp - (currentVideo?.currentTime || 0)) < 0.5
  );

  const videoWidth = 1920;
  const videoHeight = 1080;

  return (
    <div className="flex h-[calc(100vh-8rem)] bg-slate-950 rounded-xl overflow-hidden border border-slate-800/50 shadow-2xl shadow-slate-950/50">
      <VideoSidebar
        videos={videos}
        currentVideoId={currentVideo?.id || null}
        onSelectVideo={onSelectVideo}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      <div className="flex-1 flex flex-col min-w-0">
        <div className="flex items-center justify-between p-4 xl:p-5 border-b border-slate-800/50 bg-slate-900/30 backdrop-blur-sm">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setSidebarOpen(true)}
              className="lg:hidden p-2 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 transition-colors"
            >
              <Menu className="w-5 h-5" />
            </button>

            <div>
              <h1
                className="text-lg font-medium text-slate-100"
                style={{ fontFamily: "'Noto Sans TC', sans-serif" }}
              >
                {selectedVideo?.title || "選擇影片"}
              </h1>
              {selectedVideo && (
                <p
                  className="text-xs text-slate-500 mt-0.5"
                  style={{ fontFamily: "'JetBrains Mono', monospace" }}
                >
                  {formatDuration(selectedVideo.duration)} • {selectedVideo.faceCount} FACE DETECTIONS
                </p>
              )}
            </div>
          </div>
          <ContestantFilter
            contestants={contestants}
            filterContestantId={filterContestantId}
            onFilterContestant={onFilterContestant}
          />
        </div>

        <div className="flex-1 relative bg-slate-950">
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div className="w-[80%] h-[80%] bg-gradient-radial from-blue-500/5 via-slate-950 to-transparent blur-3xl" />
          </div>

          {selectedVideo ? (
            <>
              <div className="absolute inset-4 sm:inset-6 xl:inset-8 rounded-lg overflow-hidden border border-slate-700/30 shadow-[0_0_60px_rgba(59,130,246,0.1)]">
                <div className="absolute inset-0 bg-[repeating-linear-gradient(0deg,transparent,transparent_2px,rgba(0,0,0,0.03)_2px,rgba(0,0,0,0.03)_4px)] pointer-events-none z-30" />

                <div className="absolute inset-0 flex items-center justify-center bg-gradient-to-br from-slate-900 via-slate-950 to-slate-900">
                  <div className="text-center">
                    <div className="w-20 h-20 mx-auto mb-4 rounded-2xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center shadow-[0_0_30px_rgba(59,130,246,0.2)]">
                      <Play className="w-10 h-10 text-blue-400" />
                    </div>
                    <p className="text-slate-500" style={{ fontFamily: "'Noto Sans TC', sans-serif" }}>
                      影片預覽區域
                    </p>
                    <p
                      className="text-xs text-slate-600 mt-1"
                      style={{ fontFamily: "'JetBrains Mono', monospace" }}
                    >
                      STANDBY
                    </p>
                  </div>
                </div>

                <FaceOverlay
                  detections={currentDetections}
                  contestants={contestants}
                  videoWidth={videoWidth}
                  videoHeight={videoHeight}
                  onContestantClick={onContestantClick}
                />

                <CornerFrame color="blue" animated={false} />
              </div>
            </>
          ) : (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center">
                <div className="w-24 h-24 mx-auto mb-5 rounded-2xl bg-slate-800/50 border border-slate-700/50 flex items-center justify-center">
                  <Play className="w-12 h-12 text-slate-600" />
                </div>
                <p className="text-slate-400" style={{ fontFamily: "'Noto Sans TC', sans-serif" }}>
                  從左側選擇影片開始觀看
                </p>
                <p
                  className="text-xs text-slate-600 mt-2"
                  style={{ fontFamily: "'JetBrains Mono', monospace" }}
                >
                  SELECT VIDEO TO BEGIN ANALYSIS
                </p>
              </div>
            </div>
          )}
        </div>

        {selectedVideo && (
          <ContestantThumbnailStrip
            visibleContestantIds={visibleContestants}
            contestants={contestants}
            onContestantClick={onContestantClick}
          />
        )}

        {selectedVideo && (
          <div className="px-4 xl:px-5 pb-2">
            <TimelineMarkers
              detections={faceDetections.filter((d) => d.videoId === selectedVideo.id)}
              filterContestantId={filterContestantId}
              duration={selectedVideo.duration}
              onJumpToTimestamp={onJumpToTimestamp}
            />
          </div>
        )}

        {selectedVideo && currentVideo && (
          <VideoControls
            isPlaying={currentVideo.isPlaying}
            currentTime={currentVideo.currentTime}
            duration={selectedVideo.duration}
            playbackSpeed={currentVideo.playbackSpeed}
            onPlay={onPlay}
            onPause={onPause}
            onStop={onStop}
            onSeek={onSeek}
            onSkipFrames={onSkipFrames}
            onSkipSeconds={onSkipSeconds}
            onSpeedChange={onSpeedChange}
          />
        )}
      </div>
    </div>
  );
}

export default VideoPlayer;
