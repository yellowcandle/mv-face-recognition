import {
  BarChart3,
  Users,
  TrendingUp,
  ChevronDown,
  ChevronUp,
  Clock,
  Check,
  Zap,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type {
  AnalyticsProps,
  LeaderboardEntry,
  CoAppearance,
  TrendDataPoint,
  VideoOption,
  ContestantOption,
  SortColumn,
  SortDirection,
} from "@product/sections/analytics/types";

// =============================================================================
// CSS Keyframes (injected via style tag for animations)
// =============================================================================

const styleSheet = `
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Noto+Sans+TC:wght@400;500;600;700&display=swap');

@keyframes fadeSlideIn {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes glowPulse {
  0%, 100% {
    filter: drop-shadow(0 0 4px currentColor);
  }
  50% {
    filter: drop-shadow(0 0 12px currentColor);
  }
}

@keyframes nodeGlow {
  0%, 100% {
    filter: drop-shadow(0 0 3px currentColor) drop-shadow(0 0 6px currentColor);
  }
  50% {
    filter: drop-shadow(0 0 6px currentColor) drop-shadow(0 0 12px currentColor);
  }
}

@keyframes medalShine {
  0% {
    background-position: -200% center;
  }
  100% {
    background-position: 200% center;
  }
}

@keyframes connectionPulse {
  0%, 100% {
    opacity: 0.3;
  }
  50% {
    opacity: 0.7;
  }
}

.cyber-grid-bg {
  background-image: 
    linear-gradient(rgba(59, 130, 246, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(59, 130, 246, 0.03) 1px, transparent 1px);
  background-size: 24px 24px;
}

.glass-panel {
  background: linear-gradient(135deg, rgba(15, 23, 42, 0.8) 0%, rgba(15, 23, 42, 0.6) 100%);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(59, 130, 246, 0.15);
}

.glass-panel-hover:hover {
  border-color: rgba(59, 130, 246, 0.35);
  box-shadow: 0 0 20px rgba(59, 130, 246, 0.1);
}

.medal-gold {
  background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 50%, #fbbf24 100%);
  background-size: 200% auto;
  animation: medalShine 3s linear infinite;
  box-shadow: 0 0 12px rgba(251, 191, 36, 0.5), 0 0 24px rgba(251, 191, 36, 0.3);
}

.medal-silver {
  background: linear-gradient(135deg, #e2e8f0 0%, #94a3b8 50%, #e2e8f0 100%);
  background-size: 200% auto;
  animation: medalShine 3s linear infinite;
  box-shadow: 0 0 10px rgba(148, 163, 184, 0.5), 0 0 20px rgba(148, 163, 184, 0.3);
}

.medal-bronze {
  background: linear-gradient(135deg, #f97316 0%, #ea580c 50%, #f97316 100%);
  background-size: 200% auto;
  animation: medalShine 3s linear infinite;
  box-shadow: 0 0 10px rgba(249, 115, 22, 0.5), 0 0 20px rgba(249, 115, 22, 0.3);
}

.font-mono-data {
  font-family: 'JetBrains Mono', ui-monospace, monospace;
}

.font-label {
  font-family: 'Noto Sans TC', system-ui, sans-serif;
}

.glow-line {
  filter: drop-shadow(0 0 3px currentColor);
}

.toggle-active {
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.3) 0%, rgba(14, 165, 233, 0.2) 100%);
  border-color: rgba(59, 130, 246, 0.6);
  box-shadow: 0 0 12px rgba(59, 130, 246, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.1);
}

.toggle-inactive {
  background: rgba(30, 41, 59, 0.5);
  border-color: rgba(71, 85, 105, 0.5);
}

.toggle-inactive:hover {
  background: rgba(51, 65, 85, 0.5);
  border-color: rgba(100, 116, 139, 0.5);
}
`;

// =============================================================================
// Helper Functions
// =============================================================================

function formatScreenTime(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  if (hours > 0) {
    return `${hours}小時 ${mins}分鐘`;
  }
  return `${mins}分鐘`;
}

function formatScreenTimeShort(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

// =============================================================================
// Sub-Components
// =============================================================================

interface VideoFilterProps {
  videos: VideoOption[];
  selectedVideoId: string | null;
  onSelect?: (videoId: string | null) => void;
}

function VideoFilter({ videos, selectedVideoId, onSelect }: VideoFilterProps) {
  return (
    <div className="relative group">
      <div className="absolute -inset-0.5 bg-gradient-to-r from-blue-500/20 to-sky-500/20 rounded-xl blur opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
      <select
        value={selectedVideoId ?? ""}
        onChange={(e) => onSelect?.(e.target.value || null)}
        className="font-label relative appearance-none w-full px-4 py-3 pr-10 glass-panel rounded-xl text-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50 cursor-pointer transition-all duration-200"
      >
        <option value="" className="bg-slate-900">所有影片</option>
        {videos.map((video) => (
          <option key={video.id} value={video.id} className="bg-slate-900">
            {video.title}
          </option>
        ))}
      </select>
      <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none">
        <ChevronDown className="w-4 h-4 text-blue-400" />
      </div>
    </div>
  );
}

interface SortHeaderProps {
  label: string;
  column: SortColumn;
  currentColumn: SortColumn;
  direction: SortDirection;
  onSort?: (column: SortColumn) => void;
}

function SortHeader({
  label,
  column,
  currentColumn,
  direction,
  onSort,
}: SortHeaderProps) {
  const isActive = column === currentColumn;
  return (
    <button
      onClick={() => onSort?.(column)}
      className={cn(
        "font-label flex items-center gap-1.5 text-xs font-medium transition-all duration-200 px-2 py-1 rounded-md",
        isActive
          ? "text-sky-400 bg-sky-500/10"
          : "text-slate-500 hover:text-slate-300 hover:bg-slate-800/50"
      )}
    >
      {label}
      {isActive && (
        <span className="text-sky-400">
          {direction === "desc" ? (
            <ChevronDown className="w-3.5 h-3.5" />
          ) : (
            <ChevronUp className="w-3.5 h-3.5" />
          )}
        </span>
      )}
    </button>
  );
}

interface RankBadgeProps {
  rank: number;
}

function RankBadge({ rank }: RankBadgeProps) {
  if (rank === 1) {
    return (
      <div className="medal-gold w-7 h-7 rounded-full flex items-center justify-center">
        <span className="font-mono-data text-xs font-bold text-slate-900">1</span>
      </div>
    );
  }
  if (rank === 2) {
    return (
      <div className="medal-silver w-7 h-7 rounded-full flex items-center justify-center">
        <span className="font-mono-data text-xs font-bold text-slate-900">2</span>
      </div>
    );
  }
  if (rank === 3) {
    return (
      <div className="medal-bronze w-7 h-7 rounded-full flex items-center justify-center">
        <span className="font-mono-data text-xs font-bold text-white">3</span>
      </div>
    );
  }
  return (
    <div className="w-7 h-7 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center">
      <span className="font-mono-data text-xs font-medium text-slate-400">{rank}</span>
    </div>
  );
}

interface LeaderboardTableProps {
  entries: LeaderboardEntry[];
  sortColumn: SortColumn;
  sortDirection: SortDirection;
  onSort?: (column: SortColumn) => void;
  onContestantClick?: (contestantId: string) => void;
}

function LeaderboardTable({
  entries,
  sortColumn,
  sortDirection,
  onSort,
  onContestantClick,
}: LeaderboardTableProps) {
  // Sort entries
  const sortedEntries = [...entries].sort((a, b) => {
    const aVal = a[sortColumn];
    const bVal = b[sortColumn];
    return sortDirection === "desc" ? bVal - aVal : aVal - bVal;
  });

  return (
    <div className="glass-panel rounded-2xl overflow-hidden">
      {/* Header */}
      <div className="grid grid-cols-[1fr_auto_auto_auto] gap-4 px-5 py-4 bg-slate-900/50 border-b border-slate-700/50">
        <div className="font-label text-xs font-medium text-slate-400 uppercase tracking-wider">參賽者</div>
        <SortHeader
          label="總時間"
          column="totalScreenTime"
          currentColumn={sortColumn}
          direction={sortDirection}
          onSort={onSort}
        />
        <SortHeader
          label="出現次數"
          column="appearanceCount"
          currentColumn={sortColumn}
          direction={sortDirection}
          onSort={onSort}
        />
        <SortHeader
          label="平均/集"
          column="avgPerVideo"
          currentColumn={sortColumn}
          direction={sortDirection}
          onSort={onSort}
        />
      </div>

      {/* Rows */}
      <div className="divide-y divide-slate-800/50">
        {sortedEntries.map((entry, index) => (
          <button
            key={entry.contestantId}
            onClick={() => onContestantClick?.(entry.contestantId)}
            className="w-full grid grid-cols-[1fr_auto_auto_auto] gap-4 px-5 py-4 hover:bg-blue-500/5 transition-all duration-200 text-left group"
            style={{
              animation: `fadeSlideIn 0.4s ease-out ${index * 0.05}s both`,
            }}
          >
            {/* Contestant */}
            <div className="flex items-center gap-3">
              <RankBadge rank={index + 1} />
              <div className="relative">
                <div className={cn(
                  "w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0 font-label",
                  index < 3
                    ? "bg-gradient-to-br from-blue-500 to-sky-400 text-white shadow-lg shadow-blue-500/30"
                    : "bg-gradient-to-br from-slate-700 to-slate-600 text-slate-300"
                )}>
                  {entry.chineseName.charAt(0)}
                </div>
                {index < 3 && (
                  <div className="absolute -inset-1 bg-blue-500/20 rounded-full blur-md -z-10" />
                )}
              </div>
              <div>
                <div className="font-label text-sm font-medium text-slate-100 group-hover:text-sky-300 transition-colors">
                  {entry.chineseName}
                </div>
                <div className="font-label text-xs text-slate-500">{entry.nickname}</div>
              </div>
            </div>

            {/* Total Screen Time */}
            <div className="flex items-center">
              <div className={cn(
                "font-mono-data text-sm tabular-nums",
                index < 3 ? "text-sky-400" : "text-slate-300"
              )}>
                {formatScreenTimeShort(entry.totalScreenTime)}
              </div>
            </div>

            {/* Appearance Count */}
            <div className="flex items-center">
              <div className={cn(
                "font-mono-data text-sm tabular-nums",
                index < 3 ? "text-blue-400" : "text-slate-300"
              )}>
                {entry.appearanceCount}
              </div>
            </div>

            {/* Avg Per Video */}
            <div className="flex items-center">
              <div className={cn(
                "font-mono-data text-sm tabular-nums",
                index < 3 ? "text-sky-400" : "text-slate-300"
              )}>
                {formatScreenTimeShort(entry.avgPerVideo)}
              </div>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

interface CoAppearanceCardProps {
  coAppearance: CoAppearance;
  onContestantClick?: (contestantId: string) => void;
  index: number;
}

function CoAppearanceCard({
  coAppearance,
  onContestantClick,
  index,
}: CoAppearanceCardProps) {
  return (
    <div
      className="glass-panel glass-panel-hover rounded-xl p-4 relative overflow-hidden group"
      style={{
        animation: `fadeSlideIn 0.4s ease-out ${index * 0.08}s both`,
      }}
    >
      {/* Connection line background effect */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <svg className="absolute inset-0 w-full h-full" preserveAspectRatio="none">
          <defs>
            <linearGradient id={`connection-${index}`} x1="0%" y1="50%" x2="100%" y2="50%">
              <stop offset="0%" stopColor="rgb(59, 130, 246)" stopOpacity="0.3" />
              <stop offset="50%" stopColor="rgb(14, 165, 233)" stopOpacity="0.5" />
              <stop offset="100%" stopColor="rgb(59, 130, 246)" stopOpacity="0.3" />
            </linearGradient>
          </defs>
          <line
            x1="15%"
            y1="35%"
            x2="85%"
            y2="35%"
            stroke={`url(#connection-${index})`}
            strokeWidth="1"
            strokeDasharray="4 4"
            className="opacity-50 group-hover:opacity-100 transition-opacity duration-300"
            style={{ animation: 'connectionPulse 2s ease-in-out infinite' }}
          />
        </svg>
      </div>

      <div className="flex items-center gap-3 relative z-10">
        {/* Contestant 1 */}
        <button
          onClick={() => onContestantClick?.(coAppearance.contestant1Id)}
          className="flex items-center gap-2 group/btn flex-1"
        >
          <div className="relative">
            <div className="w-11 h-11 rounded-full bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center text-sm font-bold text-white font-label shadow-lg shadow-blue-500/30">
              {coAppearance.contestant1Name.charAt(0)}
            </div>
            <div className="absolute -inset-0.5 bg-blue-500/30 rounded-full blur-sm -z-10 opacity-0 group-hover/btn:opacity-100 transition-opacity" />
          </div>
          <div className="text-left min-w-0">
            <div className="font-label text-sm font-medium text-slate-100 group-hover/btn:text-blue-300 transition-colors truncate">
              {coAppearance.contestant1Name}
            </div>
            <div className="font-label text-xs text-slate-500 truncate">
              {coAppearance.contestant1Nickname}
            </div>
          </div>
        </button>

        {/* Separator - Relational Node */}
        <div className="flex flex-col items-center justify-center px-2">
          <div className="relative">
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-sky-500/20 to-blue-500/20 border border-sky-500/30 flex items-center justify-center">
              <Zap className="w-4 h-4 text-sky-400" />
            </div>
            <div className="absolute -inset-1 bg-sky-500/10 rounded-full blur-md -z-10" />
          </div>
        </div>

        {/* Contestant 2 */}
        <button
          onClick={() => onContestantClick?.(coAppearance.contestant2Id)}
          className="flex items-center gap-2 group/btn flex-1 justify-end"
        >
          <div className="text-right min-w-0">
            <div className="font-label text-sm font-medium text-slate-100 group-hover/btn:text-sky-300 transition-colors truncate">
              {coAppearance.contestant2Name}
            </div>
            <div className="font-label text-xs text-slate-500 truncate">
              {coAppearance.contestant2Nickname}
            </div>
          </div>
          <div className="relative">
            <div className="w-11 h-11 rounded-full bg-gradient-to-br from-sky-500 to-sky-600 flex items-center justify-center text-sm font-bold text-white font-label shadow-lg shadow-sky-500/30">
              {coAppearance.contestant2Name.charAt(0)}
            </div>
            <div className="absolute -inset-0.5 bg-sky-500/30 rounded-full blur-sm -z-10 opacity-0 group-hover/btn:opacity-100 transition-opacity" />
          </div>
        </button>
      </div>

      {/* Shared time */}
      <div className="mt-4 pt-3 border-t border-slate-700/50 flex items-center justify-center gap-2">
        <Clock className="w-3.5 h-3.5 text-slate-500" />
        <span className="font-label text-xs text-slate-400">共同螢幕時間:</span>
        <span className="font-mono-data text-xs text-sky-400 font-medium">
          {formatScreenTime(coAppearance.sharedScreenTime)}
        </span>
      </div>
    </div>
  );
}

interface ContestantSelectorProps {
  contestants: ContestantOption[];
  selectedIds: string[];
  onSelect?: (ids: string[]) => void;
}

function ContestantSelector({
  contestants,
  selectedIds,
  onSelect,
}: ContestantSelectorProps) {
  const toggleContestant = (id: string) => {
    if (selectedIds.includes(id)) {
      onSelect?.(selectedIds.filter((i) => i !== id));
    } else if (selectedIds.length < 4) {
      onSelect?.([...selectedIds, id]);
    }
  };

  return (
    <div className="flex flex-wrap gap-2">
      {contestants.map((contestant, index) => {
        const isSelected = selectedIds.includes(contestant.id);
        return (
          <button
            key={contestant.id}
            onClick={() => toggleContestant(contestant.id)}
            className={cn(
              "font-label flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-medium transition-all duration-200 border",
              isSelected
                ? "toggle-active text-sky-300"
                : "toggle-inactive text-slate-400 hover:text-slate-300"
            )}
            style={{
              animation: `fadeSlideIn 0.3s ease-out ${index * 0.03}s both`,
            }}
          >
            {isSelected && <Check className="w-3.5 h-3.5 text-sky-400" />}
            {contestant.chineseName}
          </button>
        );
      })}
    </div>
  );
}

interface TrendChartProps {
  dataPoints: TrendDataPoint[];
  contestants: ContestantOption[];
  selectedIds: string[];
  onVideoClick?: (videoId: string) => void;
}

function TrendChart({
  dataPoints,
  contestants,
  selectedIds,
  onVideoClick,
}: TrendChartProps) {
  // Get unique videos (sorted by title)
  const videos = Array.from(new Set(dataPoints.map((d) => d.videoId)))
    .map((id) => {
      const point = dataPoints.find((d) => d.videoId === id);
      return { id, title: point?.videoTitle || "" };
    })
    .sort((a, b) => a.title.localeCompare(b.title));

  // Get max value for scaling
  const maxValue = Math.max(
    ...dataPoints
      .filter((d) => selectedIds.includes(d.contestantId))
      .map((d) => d.screenTime),
    1
  );

  // Colors for lines - using blue/sky spectrum
  const colors = [
    { stroke: "#3b82f6", fill: "rgba(59, 130, 246, 0.15)", glow: "rgba(59, 130, 246, 0.5)" },
    { stroke: "#0ea5e9", fill: "rgba(14, 165, 233, 0.15)", glow: "rgba(14, 165, 233, 0.5)" },
    { stroke: "#06b6d4", fill: "rgba(6, 182, 212, 0.15)", glow: "rgba(6, 182, 212, 0.5)" },
    { stroke: "#38bdf8", fill: "rgba(56, 189, 248, 0.15)", glow: "rgba(56, 189, 248, 0.5)" },
  ];

  const chartHeight = 220;
  const chartPadding = { top: 20, right: 20, bottom: 10, left: 50 };

  return (
    <div className="glass-panel rounded-2xl p-5 relative overflow-hidden">
      {/* Background grid pattern */}
      <div className="absolute inset-0 cyber-grid-bg opacity-50" />

      {/* Chart area */}
      <div className="relative" style={{ height: chartHeight }}>
        <svg
          className="absolute inset-0 w-full h-full overflow-visible"
          viewBox={`0 0 100 ${chartHeight}`}
          preserveAspectRatio="none"
        >
          <defs>
            {/* Gradient definitions for each line */}
            {selectedIds.map((_, index) => (
              <linearGradient
                key={`gradient-${index}`}
                id={`areaGradient-${index}`}
                x1="0%"
                y1="0%"
                x2="0%"
                y2="100%"
              >
                <stop offset="0%" stopColor={colors[index % colors.length].stroke} stopOpacity="0.4" />
                <stop offset="50%" stopColor={colors[index % colors.length].stroke} stopOpacity="0.1" />
                <stop offset="100%" stopColor={colors[index % colors.length].stroke} stopOpacity="0" />
              </linearGradient>
            ))}
            
            {/* Glow filter */}
            <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="2" result="coloredBlur" />
              <feMerge>
                <feMergeNode in="coloredBlur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Horizontal grid lines */}
          {[0, 25, 50, 75, 100].map((percent) => {
            const y = chartPadding.top + ((100 - percent) / 100) * (chartHeight - chartPadding.top - chartPadding.bottom);
            return (
              <line
                key={percent}
                x1="0"
                y1={y}
                x2="100"
                y2={y}
                stroke="rgba(59, 130, 246, 0.1)"
                strokeWidth="0.2"
                strokeDasharray="2 2"
              />
            );
          })}

          {/* Area fills and lines for selected contestants */}
          {selectedIds.map((contestantId, index) => {
            const points = videos.map((video, vIndex) => {
              const dataPoint = dataPoints.find(
                (d) => d.contestantId === contestantId && d.videoId === video.id
              );
              const value = dataPoint?.screenTime || 0;
              const x = videos.length > 1 
                ? (vIndex / (videos.length - 1)) * 100 
                : 50;
              const y = chartPadding.top + ((1 - value / maxValue) * (chartHeight - chartPadding.top - chartPadding.bottom));
              return { x, y, value };
            });

            const linePathD = points
              .map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`)
              .join(" ");

            const areaPathD = linePathD + 
              ` L ${points[points.length - 1].x} ${chartHeight - chartPadding.bottom} L ${points[0].x} ${chartHeight - chartPadding.bottom} Z`;

            return (
              <g key={contestantId}>
                {/* Area fill with gradient */}
                <path
                  d={areaPathD}
                  fill={`url(#areaGradient-${index})`}
                  className="transition-opacity duration-300"
                />
                
                {/* Line with glow */}
                <path
                  d={linePathD}
                  fill="none"
                  stroke={colors[index % colors.length].stroke}
                  strokeWidth="0.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  filter="url(#glow)"
                  className="glow-line"
                />
                
                {/* Data points with glow effect */}
                {points.map((p, i) => (
                  <g key={i}>
                    {/* Outer glow */}
                    <circle
                      cx={p.x}
                      cy={p.y}
                      r="1.5"
                      fill={colors[index % colors.length].stroke}
                      opacity="0.3"
                      style={{ animation: 'nodeGlow 2s ease-in-out infinite' }}
                    />
                    {/* Inner point */}
                    <circle
                      cx={p.x}
                      cy={p.y}
                      r="0.8"
                      fill={colors[index % colors.length].stroke}
                      stroke="rgba(255,255,255,0.8)"
                      strokeWidth="0.2"
                    />
                  </g>
                ))}
              </g>
            );
          })}
        </svg>

        {/* Y-axis labels */}
        <div className="absolute left-0 top-0 bottom-0 w-12 flex flex-col justify-between py-5 pointer-events-none">
          {[100, 75, 50, 25, 0].map((percent) => (
            <span
              key={percent}
              className="font-mono-data text-[10px] text-slate-500 text-right pr-2 tabular-nums"
            >
              {Math.round((maxValue * percent) / 100 / 60)}分
            </span>
          ))}
        </div>
      </div>

      {/* X-axis labels */}
      <div className="flex justify-between mt-3 pt-3 border-t border-slate-700/50 relative z-10">
        {videos.map((video) => (
          <button
            key={video.id}
            onClick={() => onVideoClick?.(video.id)}
            className="font-label text-[10px] text-slate-500 hover:text-sky-400 transition-colors px-1"
          >
            {video.title}
          </button>
        ))}
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-4 mt-4 pt-4 border-t border-slate-700/50 relative z-10">
        {selectedIds.map((id, index) => {
          const contestant = contestants.find((c) => c.id === id);
          return (
            <div key={id} className="flex items-center gap-2">
              <div
                className="w-3 h-3 rounded-full shadow-lg"
                style={{
                  backgroundColor: colors[index % colors.length].stroke,
                  boxShadow: `0 0 8px ${colors[index % colors.length].glow}`,
                }}
              />
              <span className="font-label text-xs text-slate-300">{contestant?.chineseName}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// =============================================================================
// Main Component
// =============================================================================

export function Analytics({
  leaderboardEntries,
  coAppearances,
  trendDataPoints,
  videos,
  contestants,
  filterVideoId,
  selectedContestantIds,
  sortColumn,
  sortDirection,
  onContestantClick,
  onVideoClick,
  onFilterVideo,
  onSelectContestantsForTrend,
  onSort,
}: AnalyticsProps) {
  return (
    <>
      {/* Inject custom styles */}
      <style>{styleSheet}</style>

      <div className="min-h-screen bg-slate-950 cyber-grid-bg p-4 sm:p-6 lg:p-8">
        <div className="max-w-7xl mx-auto">
          {/* Header */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
            <div className="flex items-center gap-4">
              <div className="relative">
                <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-blue-600 to-sky-500 flex items-center justify-center shadow-lg shadow-blue-500/30">
                  <BarChart3 className="w-6 h-6 text-white" />
                </div>
                <div className="absolute -inset-1 bg-blue-500/20 rounded-xl blur-md -z-10" />
              </div>
              <div>
                <h1 className="font-label text-2xl sm:text-3xl font-bold text-white tracking-tight">
                  數據分析
                </h1>
                <p className="font-label text-sm text-slate-400 mt-0.5">
                  螢幕時間統計與趨勢分析
                </p>
              </div>
            </div>

            {/* Video Filter */}
            <div className="w-full sm:w-72">
              <VideoFilter
                videos={videos}
                selectedVideoId={filterVideoId}
                onSelect={onFilterVideo}
              />
            </div>
          </div>

          {/* Main Grid - Responsive */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Leaderboard - spans 2 columns on desktop */}
            <div className="lg:col-span-2">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-8 h-8 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center">
                  <Clock className="w-4 h-4 text-blue-400" />
                </div>
                <h2 className="font-label text-lg font-semibold text-white">螢幕時間排行榜</h2>
              </div>
              <LeaderboardTable
                entries={leaderboardEntries}
                sortColumn={sortColumn}
                sortDirection={sortDirection}
                onSort={onSort}
                onContestantClick={onContestantClick}
              />
            </div>

            {/* Co-Appearances */}
            <div>
              <div className="flex items-center gap-3 mb-4">
                <div className="w-8 h-8 rounded-lg bg-sky-500/10 border border-sky-500/20 flex items-center justify-center">
                  <Users className="w-4 h-4 text-sky-400" />
                </div>
                <h2 className="font-label text-lg font-semibold text-white">最常同框組合</h2>
              </div>
              <div className="space-y-3">
                {coAppearances.slice(0, 5).map((coApp, index) => (
                  <CoAppearanceCard
                    key={`${coApp.contestant1Id}-${coApp.contestant2Id}`}
                    coAppearance={coApp}
                    onContestantClick={onContestantClick}
                    index={index}
                  />
                ))}
              </div>
            </div>
          </div>

          {/* Trend Chart */}
          <div className="mt-8">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-sky-500/10 border border-sky-500/20 flex items-center justify-center">
                  <TrendingUp className="w-4 h-4 text-sky-400" />
                </div>
                <h2 className="font-label text-lg font-semibold text-white">螢幕時間趨勢</h2>
              </div>
            </div>

            {/* Contestant selector */}
            <div className="mb-5">
              <p className="font-label text-xs text-slate-500 mb-3 uppercase tracking-wider">
                選擇參賽者比較 (最多4位)
              </p>
              <ContestantSelector
                contestants={contestants}
                selectedIds={selectedContestantIds}
                onSelect={onSelectContestantsForTrend}
              />
            </div>

            {/* Chart */}
            {selectedContestantIds.length > 0 ? (
              <TrendChart
                dataPoints={trendDataPoints}
                contestants={contestants}
                selectedIds={selectedContestantIds}
                onVideoClick={onVideoClick}
              />
            ) : (
              <div className="glass-panel rounded-2xl p-12 text-center relative overflow-hidden">
                <div className="absolute inset-0 cyber-grid-bg opacity-30" />
                <div className="relative z-10">
                  <div className="w-16 h-16 rounded-2xl bg-slate-800/50 border border-slate-700/50 flex items-center justify-center mx-auto mb-4">
                    <TrendingUp className="w-8 h-8 text-slate-600" />
                  </div>
                  <p className="font-label text-slate-500">請選擇參賽者以查看趨勢圖表</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}

export default Analytics;
