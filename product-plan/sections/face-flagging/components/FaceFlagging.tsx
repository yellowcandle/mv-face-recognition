import { useState } from "react";
import {
  Flag,
  AlertTriangle,
  Search,
  CheckSquare,
  Square,
  User,
  UserX,
  X,
  Clock,
  CheckCircle2,
  XCircle,
  ArrowRight,
  Play,
  SlidersHorizontal,
  Crosshair,
  Database,
  Terminal,
  Gauge,
  Radio,
  Zap,
  FileText,
  ChevronRight,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type {
  FaceFlaggingProps,
  PendingReview,
  ContestantOption,
  SubmittedFlag,
  VideoOption,
  FlagStatus,
} from "@product/sections/face-flagging/types";

// =============================================================================
// Helper Functions
// =============================================================================

function formatTimestamp(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  if (hours > 0) {
    return `${hours}:${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  }
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

function formatISOTimestamp(isoString: string): string {
  const date = new Date(isoString);
  return date.toISOString().replace("T", " ").slice(0, 19);
}

function getConfidenceLevel(confidence: number): "high" | "medium" | "low" {
  if (confidence >= 0.8) return "high";
  if (confidence >= 0.6) return "medium";
  return "low";
}

function getConfidenceColor(confidence: number): string {
  const level = getConfidenceLevel(confidence);
  if (level === "high") return "text-emerald-400";
  if (level === "medium") return "text-amber-400";
  return "text-red-400";
}

// =============================================================================
// Sub-Components
// =============================================================================

interface ConfidenceGaugeProps {
  confidence: number;
  size?: "sm" | "md";
}

function ConfidenceGauge({ confidence, size = "md" }: ConfidenceGaugeProps) {
  const percentage = Math.round(confidence * 100);
  const level = getConfidenceLevel(confidence);
  const rotation = (confidence * 180) - 90; // -90 to 90 degrees
  
  const colors = {
    high: { ring: "stroke-emerald-400", glow: "drop-shadow-[0_0_8px_rgba(52,211,153,0.6)]", text: "text-emerald-400", bg: "bg-emerald-500/10" },
    medium: { ring: "stroke-amber-400", glow: "drop-shadow-[0_0_8px_rgba(251,191,36,0.6)]", text: "text-amber-400", bg: "bg-amber-500/10" },
    low: { ring: "stroke-red-400", glow: "drop-shadow-[0_0_8px_rgba(248,113,113,0.6)]", text: "text-red-400", bg: "bg-red-500/10" },
  };

  const style = colors[level];
  const sizeClasses = size === "sm" ? "w-14 h-8" : "w-20 h-12";

  return (
    <div className={cn("relative flex items-center justify-center", sizeClasses)}>
      {/* Gauge Background */}
      <svg className={cn("absolute inset-0", style.glow)} viewBox="0 0 100 60">
        {/* Background arc */}
        <path
          d="M 10 50 A 40 40 0 0 1 90 50"
          fill="none"
          stroke="currentColor"
          strokeWidth="4"
          className="text-slate-700"
        />
        {/* Active arc */}
        <path
          d="M 10 50 A 40 40 0 0 1 90 50"
          fill="none"
          strokeWidth="4"
          strokeLinecap="round"
          className={style.ring}
          strokeDasharray={`${confidence * 126} 126`}
        />
        {/* Needle */}
        <line
          x1="50"
          y1="50"
          x2="50"
          y2="20"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          className={style.text}
          transform={`rotate(${rotation} 50 50)`}
        />
        {/* Center dot */}
        <circle cx="50" cy="50" r="4" className={cn("fill-current", style.text)} />
      </svg>
      {/* Value */}
      <span className={cn(
        "absolute bottom-0 font-mono font-bold tabular-nums",
        style.text,
        size === "sm" ? "text-[10px]" : "text-xs"
      )}>
        {percentage}%
      </span>
    </div>
  );
}

interface FilterControlsProps {
  videos: VideoOption[];
  contestants: ContestantOption[];
  filterVideoId: string | null;
  filterContestantId: string | null;
  filterConfidenceThreshold: number;
  searchQuery: string;
  onFilterVideo?: (videoId: string | null) => void;
  onFilterContestant?: (contestantId: string | null) => void;
  onFilterConfidence?: (threshold: number) => void;
  onSearch?: (query: string) => void;
}

function FilterControls({
  videos,
  contestants,
  filterVideoId,
  filterContestantId,
  filterConfidenceThreshold,
  searchQuery,
  onFilterVideo,
  onFilterContestant,
  onFilterConfidence,
  onSearch,
}: FilterControlsProps) {
  return (
    <div className="relative overflow-hidden rounded-xl border border-slate-700/50 bg-gradient-to-br from-slate-900/90 via-slate-800/50 to-slate-900/90 backdrop-blur-xl">
      {/* Glowing border effect */}
      <div className="absolute inset-0 rounded-xl bg-gradient-to-r from-blue-500/10 via-transparent to-sky-500/10 pointer-events-none" />
      
      {/* Panel Header */}
      <div className="relative flex items-center gap-3 px-5 py-3 border-b border-slate-700/50 bg-slate-800/30">
        <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-blue-500/20 border border-blue-500/30">
          <SlidersHorizontal className="w-4 h-4 text-blue-400" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-white tracking-wide" style={{ fontFamily: "'Noto Sans TC', sans-serif" }}>
            控制面板
          </h3>
          <p className="text-[10px] text-slate-500 font-mono uppercase tracking-widest">MISSION CONTROL</p>
        </div>
        {/* Status indicator */}
        <div className="ml-auto flex items-center gap-2">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30">
            <Radio className="w-3 h-3 text-emerald-400 animate-pulse" />
            <span className="text-[10px] font-mono text-emerald-400 uppercase">ACTIVE</span>
          </div>
        </div>
      </div>

      {/* Control Grid */}
      <div className="relative grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-px bg-slate-700/30">
        {/* Search Input */}
        <div className="p-4 bg-slate-900/50">
          <label className="flex items-center gap-2 text-[10px] font-mono text-slate-500 uppercase tracking-wider mb-2">
            <Search className="w-3 h-3" />
            SEARCH TARGET
          </label>
          <div className="relative group">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => onSearch?.(e.target.value)}
              placeholder="輸入名稱..."
              className="w-full px-4 py-2.5 bg-slate-800/80 border border-slate-600/50 rounded-lg text-sm text-white placeholder-slate-600 focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/30 focus:bg-slate-800 transition-all font-sans"
              style={{ fontFamily: "'Noto Sans TC', sans-serif" }}
            />
            <div className="absolute inset-0 rounded-lg bg-gradient-to-r from-blue-500/0 via-blue-500/5 to-blue-500/0 opacity-0 group-focus-within:opacity-100 pointer-events-none transition-opacity" />
          </div>
        </div>

        {/* Video Filter */}
        <div className="p-4 bg-slate-900/50">
          <label className="flex items-center gap-2 text-[10px] font-mono text-slate-500 uppercase tracking-wider mb-2">
            <Play className="w-3 h-3" />
            VIDEO SOURCE
          </label>
          <div className="relative">
            <select
              value={filterVideoId || ""}
              onChange={(e) => onFilterVideo?.(e.target.value || null)}
              className="w-full px-4 py-2.5 bg-slate-800/80 border border-slate-600/50 rounded-lg text-sm text-white focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/30 appearance-none cursor-pointer transition-all"
              style={{ fontFamily: "'Noto Sans TC', sans-serif" }}
            >
              <option value="">所有影片</option>
              {videos.map((video) => (
                <option key={video.id} value={video.id}>
                  {video.title}
                </option>
              ))}
            </select>
            <ChevronRight className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 rotate-90 pointer-events-none" />
            {filterVideoId && (
              <div className="absolute left-0 top-0 bottom-0 w-0.5 bg-blue-500 rounded-full" />
            )}
          </div>
        </div>

        {/* Contestant Filter */}
        <div className="p-4 bg-slate-900/50">
          <label className="flex items-center gap-2 text-[10px] font-mono text-slate-500 uppercase tracking-wider mb-2">
            <User className="w-3 h-3" />
            SUBJECT FILTER
          </label>
          <div className="relative">
            <select
              value={filterContestantId || ""}
              onChange={(e) => onFilterContestant?.(e.target.value || null)}
              className="w-full px-4 py-2.5 bg-slate-800/80 border border-slate-600/50 rounded-lg text-sm text-white focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/30 appearance-none cursor-pointer transition-all"
              style={{ fontFamily: "'Noto Sans TC', sans-serif" }}
            >
              <option value="">所有參賽者</option>
              {contestants.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.chineseName} ({c.nickname})
                </option>
              ))}
            </select>
            <ChevronRight className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 rotate-90 pointer-events-none" />
            {filterContestantId && (
              <div className="absolute left-0 top-0 bottom-0 w-0.5 bg-blue-500 rounded-full" />
            )}
          </div>
        </div>

        {/* Confidence Threshold */}
        <div className="p-4 bg-slate-900/50">
          <label className="flex items-center gap-2 text-[10px] font-mono text-slate-500 uppercase tracking-wider mb-2">
            <Gauge className="w-3 h-3" />
            THRESHOLD
          </label>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-lg font-mono font-bold text-white tabular-nums">
                {Math.round(filterConfidenceThreshold * 100)}
                <span className="text-xs text-slate-500">%</span>
              </span>
              <span className="text-[10px] font-mono text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/30">
                SHOW &lt; THRESHOLD
              </span>
            </div>
            <div className="relative h-2 bg-slate-700 rounded-full overflow-hidden">
              <div 
                className="absolute inset-y-0 left-0 bg-gradient-to-r from-red-500 via-amber-400 to-emerald-400 rounded-full transition-all"
                style={{ width: `${filterConfidenceThreshold * 100}%` }}
              />
              <input
                type="range"
                min="0"
                max="100"
                value={filterConfidenceThreshold * 100}
                onChange={(e) => onFilterConfidence?.(Number(e.target.value) / 100)}
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
              />
              <div 
                className="absolute top-1/2 -translate-y-1/2 w-4 h-4 bg-white rounded-full shadow-lg shadow-blue-500/50 border-2 border-blue-500 pointer-events-none transition-all"
                style={{ left: `calc(${filterConfidenceThreshold * 100}% - 8px)` }}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

interface FaceComparisonCardProps {
  review: PendingReview;
  isSelected: boolean;
  onToggleSelection?: () => void;
  onFlagIncorrect?: () => void;
  onMarkUnknown?: () => void;
}

function FaceComparisonCard({
  review,
  isSelected,
  onToggleSelection,
  onFlagIncorrect,
  onMarkUnknown,
}: FaceComparisonCardProps) {
  const confidenceLevel = getConfidenceLevel(review.confidence);
  
  return (
    <div
      className={cn(
        "group relative overflow-hidden rounded-xl transition-all duration-300",
        "bg-gradient-to-br from-slate-900/95 via-slate-800/80 to-slate-900/95",
        "border backdrop-blur-xl",
        isSelected 
          ? "border-blue-500/70 shadow-lg shadow-blue-500/20 scale-[1.02]" 
          : "border-slate-700/50 hover:border-slate-600/70 hover:shadow-lg hover:shadow-slate-900/50"
      )}
    >
      {/* Corner frame overlays */}
      <div className="absolute top-0 left-0 w-6 h-6 border-l-2 border-t-2 border-sky-500/50 rounded-tl-xl" />
      <div className="absolute top-0 right-0 w-6 h-6 border-r-2 border-t-2 border-sky-500/50 rounded-tr-xl" />
      <div className="absolute bottom-0 left-0 w-6 h-6 border-l-2 border-b-2 border-sky-500/50 rounded-bl-xl" />
      <div className="absolute bottom-0 right-0 w-6 h-6 border-r-2 border-b-2 border-sky-500/50 rounded-br-xl" />
      
      {/* Scanline effect */}
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-sky-500/[0.02] to-transparent bg-[length:100%_4px] pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity" />

      {/* Header */}
      <div className="relative px-4 py-3 border-b border-slate-700/50 bg-slate-800/30">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={onToggleSelection}
              className={cn(
                "flex items-center justify-center w-6 h-6 rounded-md border transition-all",
                isSelected 
                  ? "bg-blue-500 border-blue-400 text-white shadow-lg shadow-blue-500/30" 
                  : "border-slate-600 text-slate-500 hover:border-slate-500 hover:text-slate-400"
              )}
            >
              {isSelected ? (
                <CheckSquare className="w-4 h-4" />
              ) : (
                <Square className="w-4 h-4" />
              )}
            </button>
            <div>
              <div className="text-sm text-white truncate max-w-[180px]" style={{ fontFamily: "'Noto Sans TC', sans-serif" }}>
                {review.videoTitle}
              </div>
              <div className="flex items-center gap-2 mt-0.5">
                <Play className="w-3 h-3 text-sky-400" />
                <span className="text-xs font-mono text-sky-400 tabular-nums">
                  T+{formatTimestamp(review.timestamp)}
                </span>
                <span className="text-slate-600">|</span>
                <span className="text-[10px] font-mono text-slate-500 uppercase">
                  ID:{review.id.slice(-4)}
                </span>
              </div>
            </div>
          </div>
          <ConfidenceGauge confidence={review.confidence} size="sm" />
        </div>
      </div>

      {/* Face Comparison */}
      <div className="p-4">
        <div className="flex items-stretch gap-3">
          {/* Detected Face */}
          <div className="flex-1 text-center">
            <div className="flex items-center justify-center gap-1.5 text-[10px] font-mono text-slate-500 uppercase tracking-wider mb-2">
              <Crosshair className="w-3 h-3 text-sky-400" />
              DETECTED
            </div>
            <div className="relative mx-auto w-20 h-20">
              {/* Targeting frame */}
              <div className="absolute -inset-1 border border-dashed border-sky-500/40 rounded-lg" />
              <div className="absolute -top-2 left-1/2 -translate-x-1/2 w-2 h-2 border-t border-l border-sky-500/60 rotate-45" />
              <div className="absolute -bottom-2 left-1/2 -translate-x-1/2 w-2 h-2 border-b border-r border-sky-500/60 rotate-45" />
              <div className="w-full h-full bg-slate-800 rounded-lg flex items-center justify-center border border-slate-700">
                <User className="w-10 h-10 text-slate-600" />
              </div>
            </div>
          </div>

          {/* Analysis Arrow */}
          <div className="flex flex-col items-center justify-center gap-1 px-2">
            <div className={cn(
              "w-8 h-0.5 rounded-full",
              confidenceLevel === "low" ? "bg-red-500/50" : confidenceLevel === "medium" ? "bg-amber-500/50" : "bg-emerald-500/50"
            )} />
            <ArrowRight className={cn(
              "w-5 h-5",
              getConfidenceColor(review.confidence)
            )} />
            <div className="text-[8px] font-mono text-slate-600 uppercase">MATCH</div>
          </div>

          {/* Current Assignment */}
          <div className="flex-1 text-center">
            <div className="flex items-center justify-center gap-1.5 text-[10px] font-mono text-slate-500 uppercase tracking-wider mb-2">
              <Database className="w-3 h-3 text-blue-400" />
              ASSIGNED
            </div>
            {review.currentContestantId ? (
              <>
                <div className="relative mx-auto w-20 h-20">
                  <div className="absolute -inset-1 border border-blue-500/30 rounded-lg" />
                  <div className="w-full h-full bg-slate-800 rounded-lg flex items-center justify-center border border-slate-700">
                    <User className="w-10 h-10 text-slate-600" />
                  </div>
                </div>
                <div className="mt-2 space-y-0.5">
                  <div className="text-sm font-medium text-white" style={{ fontFamily: "'Noto Sans TC', sans-serif" }}>
                    {review.currentContestantName}
                  </div>
                  <div className="text-xs font-mono text-slate-500">@{review.currentContestantNickname}</div>
                </div>
              </>
            ) : (
              <>
                <div className="relative mx-auto w-20 h-20">
                  <div className="absolute -inset-1 border border-dashed border-amber-500/30 rounded-lg animate-pulse" />
                  <div className="w-full h-full bg-slate-800 rounded-lg flex items-center justify-center border border-dashed border-slate-600">
                    <UserX className="w-10 h-10 text-amber-500/50" />
                  </div>
                </div>
                <div className="mt-2">
                  <div className="text-xs font-mono text-amber-400">UNIDENTIFIED</div>
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="px-4 py-3 border-t border-slate-700/50 bg-slate-800/20">
        <div className="flex items-center gap-2">
          <button
            onClick={onFlagIncorrect}
            className="flex-1 flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg font-medium text-xs transition-all bg-gradient-to-r from-amber-600 to-orange-600 hover:from-amber-500 hover:to-orange-500 text-white shadow-lg shadow-amber-500/20 hover:shadow-amber-500/40"
            style={{ fontFamily: "'Noto Sans TC', sans-serif" }}
          >
            <Flag className="w-3.5 h-3.5" />
            標記錯誤
          </button>
          <button
            onClick={onMarkUnknown}
            className="flex-1 flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg font-medium text-xs transition-all bg-slate-700/80 hover:bg-slate-600/80 text-slate-200 border border-slate-600/50"
            style={{ fontFamily: "'Noto Sans TC', sans-serif" }}
          >
            <UserX className="w-3.5 h-3.5" />
            標記未知
          </button>
        </div>
      </div>
    </div>
  );
}

interface ContestantSelectorModalProps {
  isOpen: boolean;
  contestants: ContestantOption[];
  searchQuery: string;
  onSearch?: (query: string) => void;
  onSelect?: (contestantId: string | null) => void;
  onClose?: () => void;
}

function ContestantSelectorModal({
  isOpen,
  contestants,
  searchQuery,
  onSearch,
  onSelect,
  onClose,
}: ContestantSelectorModalProps) {
  if (!isOpen) return null;

  const filteredContestants = contestants.filter(
    (c) =>
      c.chineseName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.nickname.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm" onClick={onClose} />

      {/* Modal */}
      <div className="relative w-full max-w-lg overflow-hidden rounded-2xl border border-slate-700/50 bg-gradient-to-br from-slate-900 via-slate-800/95 to-slate-900 shadow-2xl shadow-black/50">
        {/* Corner decorations */}
        <div className="absolute top-0 left-0 w-16 h-16 border-l-2 border-t-2 border-blue-500/30 rounded-tl-2xl" />
        <div className="absolute top-0 right-0 w-16 h-16 border-r-2 border-t-2 border-blue-500/30 rounded-tr-2xl" />
        <div className="absolute bottom-0 left-0 w-16 h-16 border-l-2 border-b-2 border-blue-500/30 rounded-bl-2xl" />
        <div className="absolute bottom-0 right-0 w-16 h-16 border-r-2 border-b-2 border-blue-500/30 rounded-br-2xl" />

        {/* Header */}
        <div className="relative flex items-center justify-between px-6 py-4 border-b border-slate-700/50 bg-slate-800/30">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-blue-500/20 border border-blue-500/30">
              <Database className="w-5 h-5 text-blue-400" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white" style={{ fontFamily: "'Noto Sans TC', sans-serif" }}>
                身份資料庫
              </h2>
              <p className="text-[10px] font-mono text-slate-500 uppercase tracking-widest">
                IDENTITY DATABASE LOOKUP
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-white hover:bg-slate-700/50 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Search */}
        <div className="px-6 py-4 border-b border-slate-700/50 bg-slate-800/20">
          <div className="relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => onSearch?.(e.target.value)}
              placeholder="搜尋參賽者..."
              className="w-full pl-11 pr-4 py-3 bg-slate-800/80 border border-slate-600/50 rounded-xl text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/30 transition-all"
              style={{ fontFamily: "'Noto Sans TC', sans-serif" }}
            />
            <div className="absolute right-4 top-1/2 -translate-y-1/2 text-[10px] font-mono text-slate-600">
              {filteredContestants.length} FOUND
            </div>
          </div>
        </div>

        {/* Identity Grid */}
        <div className="max-h-80 overflow-y-auto p-4">
          {/* Mark as unknown option */}
          <button
            onClick={() => onSelect?.(null)}
            className="w-full flex items-center gap-4 p-4 mb-3 rounded-xl bg-gradient-to-r from-amber-500/10 to-orange-500/10 border border-dashed border-amber-500/30 hover:border-amber-500/50 hover:bg-amber-500/20 transition-all group"
          >
            <div className="flex items-center justify-center w-14 h-14 rounded-xl bg-amber-500/20 border border-amber-500/30 group-hover:scale-105 transition-transform">
              <UserX className="w-7 h-7 text-amber-400" />
            </div>
            <div className="text-left">
              <div className="text-sm font-semibold text-amber-300" style={{ fontFamily: "'Noto Sans TC', sans-serif" }}>
                標記為未知人物
              </div>
              <div className="text-xs font-mono text-amber-500/70 mt-0.5">
                NOT IN DATABASE
              </div>
            </div>
            <ChevronRight className="w-5 h-5 text-amber-500/50 ml-auto group-hover:translate-x-1 transition-transform" />
          </button>

          {/* Contestant Grid */}
          <div className="grid grid-cols-2 gap-3">
            {filteredContestants.map((contestant) => (
              <button
                key={contestant.id}
                onClick={() => onSelect?.(contestant.id)}
                className="group flex flex-col items-center p-4 rounded-xl bg-slate-800/50 border border-slate-700/50 hover:border-blue-500/50 hover:bg-slate-700/50 transition-all"
              >
                <div className="relative w-16 h-16 mb-3">
                  <div className="absolute -inset-1 rounded-xl border border-blue-500/0 group-hover:border-blue-500/30 transition-colors" />
                  <div className="w-full h-full bg-slate-700 rounded-xl flex items-center justify-center border border-slate-600 group-hover:border-blue-500/50 transition-colors">
                    <User className="w-8 h-8 text-slate-500 group-hover:text-blue-400 transition-colors" />
                  </div>
                </div>
                <div className="text-center">
                  <div className="text-sm font-medium text-white group-hover:text-blue-300 transition-colors" style={{ fontFamily: "'Noto Sans TC', sans-serif" }}>
                    {contestant.chineseName}
                  </div>
                  <div className="text-xs font-mono text-slate-500 mt-0.5">
                    @{contestant.nickname}
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-slate-700/50 bg-slate-800/20 flex justify-end">
          <button
            onClick={onClose}
            className="px-5 py-2.5 bg-slate-700/80 hover:bg-slate-600/80 text-white text-sm font-medium rounded-lg transition-colors border border-slate-600/50"
            style={{ fontFamily: "'Noto Sans TC', sans-serif" }}
          >
            取消
          </button>
        </div>
      </div>
    </div>
  );
}

interface BulkActionsBarProps {
  selectedCount: number;
  totalCount: number;
  onToggleSelectAll?: () => void;
  onBulkSubmit?: () => void;
}

function BulkActionsBar({ selectedCount, totalCount, onToggleSelectAll, onBulkSubmit }: BulkActionsBarProps) {
  const allSelected = selectedCount === totalCount && totalCount > 0;

  return (
    <div className="relative overflow-hidden rounded-xl border border-slate-700/50 bg-gradient-to-r from-slate-900/90 via-slate-800/80 to-slate-900/90 backdrop-blur-xl">
      {/* Glowing accent line */}
      <div className={cn(
        "absolute top-0 left-0 right-0 h-0.5 transition-colors",
        selectedCount > 0 ? "bg-gradient-to-r from-blue-500 via-sky-400 to-blue-500" : "bg-slate-700"
      )} />
      
      <div className="px-5 py-3 flex items-center justify-between">
        <div className="flex items-center gap-4">
          {/* Console indicator */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800/80 border border-slate-700/50">
            <Terminal className="w-4 h-4 text-sky-400" />
            <span className="text-[10px] font-mono text-slate-500 uppercase">COMMAND CONSOLE</span>
          </div>
          
          <button
            onClick={onToggleSelectAll}
            className="flex items-center gap-2.5 px-3 py-1.5 rounded-lg text-sm text-slate-300 hover:text-white hover:bg-slate-700/50 transition-all"
            style={{ fontFamily: "'Noto Sans TC', sans-serif" }}
          >
            <div className={cn(
              "flex items-center justify-center w-5 h-5 rounded border transition-all",
              allSelected 
                ? "bg-blue-500 border-blue-400 text-white" 
                : "border-slate-600 text-slate-500"
            )}>
              {allSelected ? <CheckSquare className="w-3.5 h-3.5" /> : <Square className="w-3.5 h-3.5" />}
            </div>
            {allSelected ? "取消全選" : "全選"}
          </button>
          
          {/* Selection counter */}
          <div className={cn(
            "flex items-center gap-2 px-3 py-1.5 rounded-lg border transition-all",
            selectedCount > 0 
              ? "bg-blue-500/10 border-blue-500/30" 
              : "bg-slate-800/50 border-slate-700/50"
          )}>
            <Zap className={cn(
              "w-3.5 h-3.5",
              selectedCount > 0 ? "text-blue-400" : "text-slate-600"
            )} />
            <span className="font-mono text-sm tabular-nums">
              <span className={selectedCount > 0 ? "text-blue-400" : "text-slate-600"}>
                {String(selectedCount).padStart(2, "0")}
              </span>
              <span className="text-slate-600">/</span>
              <span className="text-slate-500">{String(totalCount).padStart(2, "0")}</span>
            </span>
            <span className="text-[10px] font-mono text-slate-600 uppercase">SELECTED</span>
          </div>
        </div>

        {selectedCount > 0 && (
          <button
            onClick={onBulkSubmit}
            className="flex items-center gap-2.5 px-5 py-2.5 rounded-lg font-medium text-sm transition-all bg-gradient-to-r from-blue-600 to-sky-600 hover:from-blue-500 hover:to-sky-500 text-white shadow-lg shadow-blue-500/25 hover:shadow-blue-500/40"
            style={{ fontFamily: "'Noto Sans TC', sans-serif" }}
          >
            <Flag className="w-4 h-4" />
            批量修正
            <span className="ml-1 px-2 py-0.5 rounded bg-white/20 text-xs font-mono">
              {selectedCount}
            </span>
          </button>
        )}
      </div>
    </div>
  );
}

interface FlagStatusBadgeProps {
  status: FlagStatus;
}

function FlagStatusBadge({ status }: FlagStatusBadgeProps) {
  const config = {
    pending: {
      icon: Clock,
      label: "PENDING",
      labelCN: "待審核",
      className: "bg-amber-500/10 text-amber-400 border-amber-500/30",
    },
    accepted: {
      icon: CheckCircle2,
      label: "ACCEPTED",
      labelCN: "已接受",
      className: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
    },
    rejected: {
      icon: XCircle,
      label: "REJECTED",
      labelCN: "已拒絕",
      className: "bg-red-500/10 text-red-400 border-red-500/30",
    },
  };

  const { icon: Icon, label, className } = config[status];

  return (
    <span className={cn(
      "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[10px] font-mono uppercase tracking-wider border",
      className
    )}>
      <Icon className="w-3 h-3" />
      {label}
    </span>
  );
}

interface SubmissionHistoryProps {
  flags: SubmittedFlag[];
}

function SubmissionHistory({ flags }: SubmissionHistoryProps) {
  if (flags.length === 0) {
    return (
      <div className="relative overflow-hidden rounded-xl border border-slate-700/50 bg-gradient-to-br from-slate-900/90 via-slate-800/50 to-slate-900/90 p-12 text-center">
        <div className="absolute inset-0 bg-gradient-to-br from-slate-800/20 to-transparent" />
        <FileText className="w-16 h-16 text-slate-700 mx-auto mb-4" />
        <p className="text-slate-500 font-medium" style={{ fontFamily: "'Noto Sans TC', sans-serif" }}>
          尚無提交記錄
        </p>
        <p className="text-xs font-mono text-slate-600 mt-1 uppercase">NO AUDIT ENTRIES</p>
      </div>
    );
  }

  return (
    <div className="relative overflow-hidden rounded-xl border border-slate-700/50 bg-gradient-to-br from-slate-900/90 via-slate-800/50 to-slate-900/90">
      {/* Header */}
      <div className="px-5 py-3 bg-slate-800/50 border-b border-slate-700/50">
        <div className="flex items-center gap-3">
          <Terminal className="w-4 h-4 text-emerald-400" />
          <span className="text-xs font-mono text-emerald-400 uppercase tracking-wider">SYSTEM LOG // AUDIT TRAIL</span>
        </div>
      </div>
      
      {/* Table Header */}
      <div className="px-5 py-2.5 bg-slate-800/30 border-b border-slate-700/30">
        <div className="grid grid-cols-[1fr_100px_100px_90px_140px] gap-4 text-[10px] font-mono text-slate-500 uppercase tracking-wider">
          <span>SOURCE</span>
          <span>ORIGINAL</span>
          <span>CORRECTED</span>
          <span>STATUS</span>
          <span>TIMESTAMP</span>
        </div>
      </div>

      {/* Rows */}
      <div className="divide-y divide-slate-800/50">
        {flags.map((flag, index) => (
          <div 
            key={flag.id} 
            className="group px-5 py-3 hover:bg-slate-800/30 transition-colors"
          >
            <div className="grid grid-cols-[1fr_100px_100px_90px_140px] gap-4 items-center">
              {/* Source */}
              <div className="flex items-center gap-3">
                <span className="text-xs font-mono text-slate-600 tabular-nums">
                  [{String(index + 1).padStart(3, "0")}]
                </span>
                <span className="text-sm text-white truncate" style={{ fontFamily: "'Noto Sans TC', sans-serif" }}>
                  {flag.videoTitle}
                </span>
              </div>
              
              {/* Original */}
              <div className="text-sm font-mono">
                {flag.originalContestantName ? (
                  <span className="text-slate-400">{flag.originalContestantName}</span>
                ) : (
                  <span className="text-slate-600">NULL</span>
                )}
              </div>
              
              {/* Corrected */}
              <div className="text-sm font-mono">
                {flag.correctedContestantName ? (
                  <span className="text-sky-400">{flag.correctedContestantName}</span>
                ) : (
                  <span className="text-amber-400">UNKNOWN</span>
                )}
              </div>
              
              {/* Status */}
              <div>
                <FlagStatusBadge status={flag.status} />
              </div>
              
              {/* Timestamp */}
              <div className="text-xs font-mono text-slate-500 tabular-nums">
                {formatISOTimestamp(flag.submittedAt)}
              </div>
            </div>
            
            {flag.notes && (
              <div className="mt-2 ml-12 flex items-start gap-2">
                <span className="text-[10px] font-mono text-slate-600">NOTE:</span>
                <span className="text-xs text-slate-500 italic">{flag.notes}</span>
              </div>
            )}
          </div>
        ))}
      </div>
      
      {/* Footer */}
      <div className="px-5 py-2.5 bg-slate-800/30 border-t border-slate-700/30 flex items-center justify-between">
        <span className="text-[10px] font-mono text-slate-600">
          TOTAL ENTRIES: {flags.length}
        </span>
        <span className="text-[10px] font-mono text-slate-600">
          END OF LOG
        </span>
      </div>
    </div>
  );
}

// =============================================================================
// Main Component
// =============================================================================

export function FaceFlagging({
  pendingReviews,
  contestants,
  submittedFlags,
  videos,
  filterVideoId,
  filterContestantId,
  filterConfidenceThreshold,
  selectedReviewIds,
  searchQuery,
  onFlagIncorrect,
  onSelectCorrectContestant,
  onMarkUnknown,
  onSubmitCorrection,
  onBulkSubmit,
  onFilterVideo,
  onFilterContestant,
  onFilterConfidence,
  onToggleReviewSelection,
  onToggleSelectAll,
  onSearch,
}: FaceFlaggingProps) {
  const [showContestantSelector, setShowContestantSelector] = useState(false);
  const [activeReviewId, setActiveReviewId] = useState<string | null>(null);
  const [selectorSearchQuery, setSelectorSearchQuery] = useState("");

  // Filter reviews based on criteria
  const filteredReviews = pendingReviews.filter((review) => {
    // Filter by confidence threshold (show only those below threshold)
    if (review.confidence >= filterConfidenceThreshold) return false;

    // Filter by video
    if (filterVideoId && review.videoId !== filterVideoId) return false;

    // Filter by contestant
    if (filterContestantId && review.currentContestantId !== filterContestantId) return false;

    // Filter by search query
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      const matchesName = review.currentContestantName?.toLowerCase().includes(query);
      const matchesNickname = review.currentContestantNickname?.toLowerCase().includes(query);
      if (!matchesName && !matchesNickname) return false;
    }

    return true;
  });

  const handleFlagIncorrect = (reviewId: string) => {
    setActiveReviewId(reviewId);
    setSelectorSearchQuery("");
    setShowContestantSelector(true);
    onFlagIncorrect?.(reviewId);
  };

  const handleSelectContestant = (contestantId: string | null) => {
    if (activeReviewId) {
      onSelectCorrectContestant?.(activeReviewId, contestantId);
      onSubmitCorrection?.(activeReviewId, contestantId);
    }
    setShowContestantSelector(false);
    setActiveReviewId(null);
  };

  const handleBulkSubmit = () => {
    setSelectorSearchQuery("");
    setShowContestantSelector(true);
    setActiveReviewId(null); // null indicates bulk mode
  };

  const handleBulkSelectContestant = (contestantId: string | null) => {
    onBulkSubmit?.(selectedReviewIds, contestantId);
    setShowContestantSelector(false);
  };

  return (
    <div className="min-h-screen bg-slate-950">
      {/* Background effects */}
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute inset-0 bg-gradient-to-br from-blue-950/20 via-transparent to-sky-950/20" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-blue-500/5 via-transparent to-transparent" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_left,_var(--tw-gradient-stops))] from-sky-500/5 via-transparent to-transparent" />
        {/* Grid pattern */}
        <div className="absolute inset-0 opacity-[0.02]" style={{
          backgroundImage: `linear-gradient(rgba(148,163,184,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(148,163,184,0.1) 1px, transparent 1px)`,
          backgroundSize: '40px 40px'
        }} />
      </div>
      
      <div className="relative max-w-7xl mx-auto p-6">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-4 mb-2">
            <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-gradient-to-br from-amber-500/20 to-orange-500/20 border border-amber-500/30 shadow-lg shadow-amber-500/10">
              <Crosshair className="w-6 h-6 text-amber-400" />
            </div>
            <div>
              <h1 
                className="text-2xl font-bold text-white tracking-wide"
                style={{ fontFamily: "'Noto Sans TC', sans-serif" }}
              >
                人臉標記修正
              </h1>
              <p className="text-[11px] font-mono text-slate-500 uppercase tracking-widest mt-0.5">
                CORRECTION WORKSTATION // FACE RECOGNITION ERROR REVIEW
              </p>
            </div>
          </div>
          <p 
            className="text-slate-400 mt-3 max-w-2xl"
            style={{ fontFamily: "'Noto Sans TC', sans-serif" }}
          >
            審核並修正人臉辨識結果中的錯誤，提升系統識別準確度
          </p>
        </div>

        {/* Filters */}
        <div className="mb-6">
          <FilterControls
            videos={videos}
            contestants={contestants}
            filterVideoId={filterVideoId}
            filterContestantId={filterContestantId}
            filterConfidenceThreshold={filterConfidenceThreshold}
            searchQuery={searchQuery}
            onFilterVideo={onFilterVideo}
            onFilterContestant={onFilterContestant}
            onFilterConfidence={onFilterConfidence}
            onSearch={onSearch}
          />
        </div>

        {/* Bulk Actions */}
        <div className="mb-5">
          <BulkActionsBar
            selectedCount={selectedReviewIds.length}
            totalCount={filteredReviews.length}
            onToggleSelectAll={onToggleSelectAll}
            onBulkSubmit={handleBulkSubmit}
          />
        </div>

        {/* Pending Reviews Grid */}
        <div className="mb-10">
          <div className="flex items-center gap-3 mb-5">
            <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-amber-500/20 border border-amber-500/30">
              <AlertTriangle className="w-4 h-4 text-amber-400" />
            </div>
            <h2 
              className="text-lg font-semibold text-white"
              style={{ fontFamily: "'Noto Sans TC', sans-serif" }}
            >
              待審核
            </h2>
            {filteredReviews.length > 0 && (
              <span className="px-2.5 py-1 rounded-lg bg-amber-500/10 text-amber-400 text-xs font-mono border border-amber-500/30">
                {String(filteredReviews.length).padStart(2, "0")} ITEMS
              </span>
            )}
          </div>

          {filteredReviews.length === 0 ? (
            <div className="relative overflow-hidden rounded-xl border border-slate-700/50 bg-gradient-to-br from-slate-900/90 via-slate-800/50 to-slate-900/90 p-12 text-center">
              <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/5 to-transparent" />
              <CheckCircle2 className="w-16 h-16 text-emerald-500/50 mx-auto mb-4" />
              <p 
                className="text-emerald-400/80 font-medium"
                style={{ fontFamily: "'Noto Sans TC', sans-serif" }}
              >
                沒有需要審核的項目
              </p>
              <p className="text-xs font-mono text-slate-600 mt-2 uppercase">
                QUEUE EMPTY // ADJUST FILTERS OR AWAIT NEW DETECTIONS
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              {filteredReviews.map((review) => (
                <FaceComparisonCard
                  key={review.id}
                  review={review}
                  isSelected={selectedReviewIds.includes(review.id)}
                  onToggleSelection={() => onToggleReviewSelection?.(review.id)}
                  onFlagIncorrect={() => handleFlagIncorrect(review.id)}
                  onMarkUnknown={() => onMarkUnknown?.(review.id)}
                />
              ))}
            </div>
          )}
        </div>

        {/* Submission History */}
        <div>
          <div className="flex items-center gap-3 mb-5">
            <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-sky-500/20 border border-sky-500/30">
              <Clock className="w-4 h-4 text-sky-400" />
            </div>
            <h2 
              className="text-lg font-semibold text-white"
              style={{ fontFamily: "'Noto Sans TC', sans-serif" }}
            >
              提交記錄
            </h2>
            {submittedFlags.length > 0 && (
              <span className="px-2.5 py-1 rounded-lg bg-slate-700/50 text-slate-400 text-xs font-mono border border-slate-600/50">
                {String(submittedFlags.length).padStart(2, "0")} ENTRIES
              </span>
            )}
          </div>
          <SubmissionHistory flags={submittedFlags} />
        </div>

        {/* Contestant Selector Modal */}
        <ContestantSelectorModal
          isOpen={showContestantSelector}
          contestants={contestants}
          searchQuery={selectorSearchQuery}
          onSearch={setSelectorSearchQuery}
          onSelect={activeReviewId ? handleSelectContestant : handleBulkSelectContestant}
          onClose={() => {
            setShowContestantSelector(false);
            setActiveReviewId(null);
          }}
        />
      </div>
    </div>
  );
}

export default FaceFlagging;
