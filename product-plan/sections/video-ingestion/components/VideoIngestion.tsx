import {
  Upload,
  Clock,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Loader2,
  RotateCcw,
  Trash2,
  Eye,
  X,
  Play,
  Film,
  Users,
  ExternalLink,
  Zap,
  Database,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type {
  VideoIngestionProps,
  ProcessingJob,
  ProcessedVideo,
  ProcessingLog,
  ProcessingStatus,
  LogLevel,
} from "@product/sections/video-ingestion/types";

const fontHeading = "font-['Noto_Sans_TC',sans-serif]";
const fontMono = "font-['JetBrains_Mono',monospace]";

function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  if (hours > 0) {
    return `${hours}:${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  }
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

function formatDateTime(isoString: string): string {
  const date = new Date(isoString);
  return date.toLocaleDateString("zh-HK", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatRelativeTime(isoString: string): string {
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 60) return `${diffMins}分鐘前`;
  if (diffHours < 24) return `${diffHours}小時前`;
  if (diffDays < 7) return `${diffDays}天前`;
  return formatDateTime(isoString);
}

function isValidYoutubeUrl(url: string): boolean {
  const pattern = /^(https?:\/\/)?(www\.)?(youtube\.com\/watch\?v=|youtu\.be\/)[a-zA-Z0-9_-]+/;
  return pattern.test(url);
}

interface UrlInputFormProps {
  value: string;
  onChange?: (value: string) => void;
  onSubmit?: (url: string) => void;
}

function UrlInputForm({ value, onChange, onSubmit }: UrlInputFormProps) {
  const isValid = value === "" || isValidYoutubeUrl(value);
  const canSubmit = value !== "" && isValid;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (canSubmit) {
      onSubmit?.(value);
    }
  };

  return (
    <form 
      onSubmit={handleSubmit} 
      className="relative bg-slate-900/80 backdrop-blur-xl border border-slate-700/50 rounded-lg overflow-hidden"
    >
      <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 via-transparent to-sky-500/5 pointer-events-none" />
      <div className="h-px bg-gradient-to-r from-transparent via-blue-500/50 to-transparent" />
      
      <div className="relative p-6">
        <div className="flex items-center gap-3 mb-5">
          <div className="relative">
            <div className="absolute inset-0 bg-blue-500/30 blur-lg rounded-full" />
            <div className="relative w-10 h-10 rounded-lg bg-slate-800/80 border border-slate-600/50 flex items-center justify-center">
              <Database className="w-5 h-5 text-blue-400" />
            </div>
          </div>
          <div>
            <h2 className={cn("text-lg font-semibold text-slate-100", fontHeading)}>
              資料入口
            </h2>
            <p className={cn("text-xs text-slate-500 uppercase tracking-widest", fontMono)}>
              DATA_ENTRY_PORT
            </p>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <span className="relative flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-sky-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-sky-500" />
            </span>
            <span className={cn("text-xs text-sky-400", fontMono)}>READY</span>
          </div>
        </div>

        <div className="flex flex-col sm:flex-row gap-3">
          <div className="flex-1 relative group">
            <div className="absolute inset-0 rounded-lg overflow-hidden pointer-events-none">
              <div className="absolute inset-0 opacity-0 group-focus-within:opacity-100 transition-opacity">
                <div className="absolute inset-x-0 h-px bg-gradient-to-r from-transparent via-blue-400 to-transparent animate-pulse" 
                     style={{ top: '50%', transform: 'translateY(-50%)' }} />
              </div>
            </div>
            
            <div className={cn(
              "relative rounded-lg transition-all duration-300",
              "before:absolute before:top-0 before:left-0 before:w-3 before:h-3 before:border-l-2 before:border-t-2 before:rounded-tl-lg",
              "after:absolute after:bottom-0 after:right-0 after:w-3 after:h-3 after:border-r-2 after:border-b-2 after:rounded-br-lg",
              !isValid 
                ? "before:border-red-500 after:border-red-500" 
                : "before:border-slate-600 after:border-slate-600 group-focus-within:before:border-blue-500 group-focus-within:after:border-blue-500"
            )}>
              <input
                type="text"
                value={value}
                onChange={(e) => onChange?.(e.target.value)}
                placeholder="https://youtube.com/watch?v=..."
                className={cn(
                  "w-full px-4 py-3.5 bg-slate-800/60 border rounded-lg text-slate-100 placeholder-slate-500 focus:outline-none transition-all duration-300",
                  fontMono,
                  "text-sm tracking-wide",
                  !isValid
                    ? "border-red-500/50 focus:border-red-500 focus:shadow-[0_0_20px_rgba(239,68,68,0.15)]"
                    : "border-slate-700/50 focus:border-blue-500/70 focus:shadow-[0_0_30px_rgba(59,130,246,0.15)]"
                )}
              />
            </div>
            
            {!isValid && (
              <p className={cn("absolute -bottom-6 left-0 text-xs text-red-400 flex items-center gap-1.5", fontMono)}>
                <XCircle className="w-3 h-3" />
                INVALID_URL_FORMAT
              </p>
            )}
          </div>
          
          <button
            type="submit"
            disabled={!canSubmit}
            className={cn(
              "relative flex items-center justify-center gap-2.5 px-6 py-3.5 rounded-lg font-medium transition-all duration-300 overflow-hidden",
              fontHeading,
              canSubmit
                ? "bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-500 hover:to-blue-400 text-white shadow-[0_0_20px_rgba(59,130,246,0.3)] hover:shadow-[0_0_30px_rgba(59,130,246,0.5)]"
                : "bg-slate-800/60 text-slate-500 cursor-not-allowed border border-slate-700/50"
            )}
          >
            {canSubmit && (
              <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent -translate-x-full animate-[shimmer_2s_infinite]" 
                   style={{ animationTimingFunction: 'ease-in-out' }} />
            )}
            <Zap className="w-4 h-4" />
            <span>提交處理</span>
          </button>
        </div>
      </div>
      
      <div className="h-px bg-gradient-to-r from-transparent via-slate-600/50 to-transparent" />
    </form>
  );
}

interface StatusBadgeProps {
  status: ProcessingStatus;
}

function StatusBadge({ status }: StatusBadgeProps) {
  const config = {
    pending: {
      icon: Clock,
      label: "PENDING",
      labelCn: "等待中",
      className: "bg-slate-800/80 text-slate-400 border-slate-600/50",
      glowColor: "",
    },
    processing: {
      icon: Loader2,
      label: "LIVE",
      labelCn: "處理中",
      className: "bg-blue-950/80 text-blue-400 border-blue-500/50",
      iconClassName: "animate-spin",
      glowColor: "shadow-[0_0_10px_rgba(59,130,246,0.4)]",
    },
    completed: {
      icon: CheckCircle2,
      label: "DONE",
      labelCn: "已完成",
      className: "bg-emerald-950/80 text-emerald-400 border-emerald-500/50",
      glowColor: "shadow-[0_0_10px_rgba(52,211,153,0.3)]",
    },
    failed: {
      icon: XCircle,
      label: "ERROR",
      labelCn: "失敗",
      className: "bg-red-950/80 text-red-400 border-red-500/50",
      glowColor: "shadow-[0_0_10px_rgba(239,68,68,0.3)]",
    },
  };

  const { icon: Icon, label, className, iconClassName, glowColor } = config[status] as {
    icon: typeof Clock;
    label: string;
    labelCn: string;
    className: string;
    iconClassName?: string;
    glowColor: string;
  };

  return (
    <span className={cn(
      "inline-flex items-center gap-2 px-3 py-1.5 rounded border text-xs backdrop-blur-sm",
      fontMono,
      className,
      glowColor
    )}>
      {status === "processing" && (
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500" />
        </span>
      )}
      <Icon className={cn("w-3.5 h-3.5", iconClassName)} />
      <span className="tracking-wider">{label}</span>
    </span>
  );
}

interface ProgressBarProps {
  progress: number;
  status: ProcessingStatus;
}

function ProgressBar({ progress, status }: ProgressBarProps) {
  const barConfig = {
    pending: { 
      barClass: "bg-slate-600",
      glowClass: "",
    },
    processing: { 
      barClass: "bg-gradient-to-r from-blue-600 via-sky-400 to-blue-600 bg-[length:200%_100%] animate-[shimmer_2s_linear_infinite]",
      glowClass: "shadow-[0_0_15px_rgba(59,130,246,0.5)]",
    },
    completed: { 
      barClass: "bg-gradient-to-r from-emerald-500 to-emerald-400",
      glowClass: "shadow-[0_0_10px_rgba(52,211,153,0.4)]",
    },
    failed: { 
      barClass: "bg-gradient-to-r from-red-600 to-red-500",
      glowClass: "",
    },
  };

  const { barClass, glowClass } = barConfig[status];

  return (
    <div className="w-full">
      <div className="flex items-center justify-between text-xs mb-1.5">
        <span className={cn("text-slate-500 uppercase tracking-wider text-[10px]", fontMono)}>PROGRESS</span>
        <span className={cn("text-slate-300 tabular-nums", fontMono)}>{progress}%</span>
      </div>
      <div className="h-1.5 bg-slate-800/80 rounded-full overflow-hidden border border-slate-700/50">
        <div
          className={cn("h-full rounded-full transition-all duration-500", barClass, glowClass)}
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
}

interface ProcessingQueueProps {
  jobs: ProcessingJob[];
  onRetry?: (jobId: string) => void;
  onViewDetails?: (jobId: string) => void;
}

function ProcessingQueue({ jobs, onRetry, onViewDetails }: ProcessingQueueProps) {
  if (jobs.length === 0) {
    return (
      <div className="relative bg-slate-900/80 backdrop-blur-xl border border-slate-700/50 rounded-lg p-10 text-center overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-slate-800/20 via-transparent to-slate-800/20 pointer-events-none" />
        <div className="absolute inset-0 opacity-30">
          <div className="absolute inset-0" style={{ 
            backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 50px, rgba(148,163,184,0.03) 50px, rgba(148,163,184,0.03) 51px)',
          }} />
        </div>
        <div className="relative">
          <div className="w-16 h-16 mx-auto mb-4 rounded-lg bg-slate-800/80 border border-slate-700/50 flex items-center justify-center">
            <Clock className="w-8 h-8 text-slate-600" />
          </div>
          <p className={cn("text-slate-400", fontHeading)}>處理佇列為空</p>
          <p className={cn("text-xs text-slate-600 mt-2 uppercase tracking-widest", fontMono)}>AWAITING_INPUT</p>
        </div>
      </div>
    );
  }

  return (
    <div className="relative bg-slate-900/80 backdrop-blur-xl border border-slate-700/50 rounded-lg overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-br from-blue-500/3 via-transparent to-sky-500/3 pointer-events-none" />
      <div className="h-px bg-gradient-to-r from-transparent via-blue-500/30 to-transparent" />
      
      <div className="hidden md:block relative px-5 py-3 bg-slate-800/40 border-b border-slate-700/50">
        <div className="grid grid-cols-[1fr_120px_140px_90px] gap-4 text-[10px] uppercase tracking-widest">
          <span className={cn("text-slate-500", fontMono)}>ASSET_ID</span>
          <span className={cn("text-slate-500", fontMono)}>STATUS</span>
          <span className={cn("text-slate-500", fontMono)}>PROGRESS</span>
          <span className={cn("text-slate-500", fontMono)}>ACTIONS</span>
        </div>
      </div>

      <div className="relative divide-y divide-slate-800/50">
        {jobs.map((job, index) => (
          <div 
            key={job.id} 
            className={cn(
              "px-5 py-4 transition-all duration-300 hover:bg-slate-800/30",
              job.status === "processing" && "bg-blue-950/10"
            )}
            style={{ animationDelay: `${index * 50}ms` }}
          >
            <div className="grid grid-cols-1 md:grid-cols-[1fr_120px_140px_90px] gap-4 items-center">
              <div className="min-w-0">
                <div className={cn("text-sm font-medium text-slate-100 truncate", fontHeading)}>
                  {job.title}
                </div>
                <div className={cn("text-xs text-slate-500 truncate mt-1", fontMono)}>
                  {job.youtubeUrl}
                </div>
                <div className={cn("text-[10px] text-slate-600 mt-1.5 uppercase tracking-wider", fontMono)}>
                  SUBMITTED: {formatRelativeTime(job.submittedAt)}
                </div>
              </div>

              <div className="flex md:justify-start">
                <StatusBadge status={job.status} />
              </div>

              <div>
                <ProgressBar progress={job.progress} status={job.status} />
              </div>

              <div className="flex items-center gap-1 justify-end md:justify-start">
                {job.status === "failed" && (
                  <button
                    onClick={() => onRetry?.(job.id)}
                    className="p-2 text-slate-500 hover:text-amber-400 hover:bg-amber-500/10 rounded-lg transition-all duration-200 border border-transparent hover:border-amber-500/30"
                    title="重試"
                  >
                    <RotateCcw className="w-4 h-4" />
                  </button>
                )}
                <button
                  onClick={() => onViewDetails?.(job.id)}
                  className="p-2 text-slate-500 hover:text-sky-400 hover:bg-sky-500/10 rounded-lg transition-all duration-200 border border-transparent hover:border-sky-500/30"
                  title="查看詳情"
                >
                  <Eye className="w-4 h-4" />
                </button>
              </div>
            </div>

            {job.status === "failed" && job.errorMessage && (
              <div className="mt-3 flex items-start gap-3 p-3 bg-red-950/30 border border-red-900/40 rounded-lg backdrop-blur-sm">
                <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
                <div>
                  <p className={cn("text-[10px] text-red-500 uppercase tracking-wider mb-1", fontMono)}>ERROR_LOG</p>
                  <p className={cn("text-xs text-red-300", fontMono)}>{job.errorMessage}</p>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
      
      <div className="h-px bg-gradient-to-r from-transparent via-slate-600/30 to-transparent" />
    </div>
  );
}

interface VideoLibraryProps {
  videos: ProcessedVideo[];
  onViewVideo?: (videoId: string) => void;
  onDeleteVideo?: (videoId: string) => void;
}

function VideoLibrary({ videos, onViewVideo, onDeleteVideo }: VideoLibraryProps) {
  if (videos.length === 0) {
    return (
      <div className="relative bg-slate-900/80 backdrop-blur-xl border border-slate-700/50 rounded-lg p-10 text-center overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-slate-800/20 via-transparent to-slate-800/20 pointer-events-none" />
        <div className="relative">
          <div className="w-16 h-16 mx-auto mb-4 rounded-lg bg-slate-800/80 border border-slate-700/50 flex items-center justify-center">
            <Film className="w-8 h-8 text-slate-600" />
          </div>
          <p className={cn("text-slate-400", fontHeading)}>尚無已處理影片</p>
          <p className={cn("text-xs text-slate-600 mt-2 uppercase tracking-widest", fontMono)}>LIBRARY_EMPTY</p>
        </div>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
      {videos.map((video, index) => (
        <div
          key={video.id}
          className="relative group"
          style={{ animationDelay: `${index * 100}ms` }}
        >
          <div className={cn(
            "relative bg-slate-900/80 backdrop-blur-xl border border-slate-700/50 rounded-lg overflow-hidden transition-all duration-300",
            "hover:border-blue-500/40 hover:shadow-[0_0_30px_rgba(59,130,246,0.15)]",
            "before:absolute before:top-0 before:left-0 before:w-4 before:h-4 before:border-l-2 before:border-t-2 before:border-transparent before:transition-colors before:duration-300 before:rounded-tl-lg before:z-10",
            "after:absolute after:bottom-0 after:right-0 after:w-4 after:h-4 after:border-r-2 after:border-b-2 after:border-transparent after:transition-colors after:duration-300 after:rounded-br-lg after:z-10",
            "hover:before:border-blue-500/60 hover:after:border-blue-500/60"
          )}>
            <div className="relative aspect-video bg-slate-800/60 overflow-hidden">
              <div className="absolute inset-0 bg-gradient-to-br from-slate-700/20 to-slate-900/40" />
              <div className="absolute inset-0 flex items-center justify-center">
                <Film className="w-10 h-10 text-slate-700" />
              </div>
              
              <button
                onClick={() => onViewVideo?.(video.id)}
                className="absolute inset-0 flex items-center justify-center bg-slate-950/60 backdrop-blur-sm opacity-0 group-hover:opacity-100 transition-all duration-300"
              >
                <div className="relative">
                  <div className="absolute inset-0 bg-blue-500/30 blur-xl rounded-full scale-150" />
                  <div className="relative w-14 h-14 rounded-full bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center shadow-[0_0_20px_rgba(59,130,246,0.5)] transition-transform duration-300 group-hover:scale-110">
                    <Play className="w-6 h-6 text-white ml-1" />
                  </div>
                </div>
              </button>
              
              <div className={cn(
                "absolute bottom-2 right-2 px-2 py-1 bg-slate-900/90 backdrop-blur-sm border border-slate-700/50 rounded text-xs text-slate-300 tabular-nums",
                fontMono
              )}>
                {formatDuration(video.duration)}
              </div>
              
              <div className="absolute top-2 left-2">
                <div className={cn(
                  "px-2 py-1 bg-slate-900/90 backdrop-blur-sm border border-slate-700/50 rounded text-[10px] text-slate-500 uppercase tracking-widest",
                  fontMono
                )}>
                  MANAGED
                </div>
              </div>
            </div>

            <div className="p-4 border-t border-slate-800/50">
              <h3 className={cn("text-sm font-medium text-slate-100 truncate", fontHeading)}>
                {video.title}
              </h3>
              <div className="flex items-center gap-4 mt-2.5">
                <span className={cn("flex items-center gap-1.5 text-xs text-sky-400", fontMono)}>
                  <Users className="w-3.5 h-3.5" />
                  <span>{video.faceCount}</span>
                  <span className="text-slate-600">FACES</span>
                </span>
                <span className={cn("text-[10px] text-slate-600 uppercase tracking-wider", fontMono)}>
                  {formatRelativeTime(video.processedAt)}
                </span>
              </div>

              <div className="flex items-center gap-2 mt-4 pt-3 border-t border-slate-800/50">
                <button
                  onClick={() => onViewVideo?.(video.id)}
                  className={cn(
                    "flex-1 flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg text-xs font-medium transition-all duration-300",
                    "bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-500 hover:to-blue-400 text-white",
                    "shadow-[0_0_15px_rgba(59,130,246,0.2)] hover:shadow-[0_0_20px_rgba(59,130,246,0.4)]",
                    fontHeading
                  )}
                >
                  <Play className="w-3.5 h-3.5" />
                  播放
                </button>
                <a
                  href={video.youtubeUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="p-2.5 text-slate-500 hover:text-sky-400 hover:bg-sky-500/10 border border-transparent hover:border-sky-500/30 rounded-lg transition-all duration-200"
                  title="開啟 YouTube"
                >
                  <ExternalLink className="w-4 h-4" />
                </a>
                <button
                  onClick={() => onDeleteVideo?.(video.id)}
                  className="p-2.5 text-slate-500 hover:text-red-400 hover:bg-red-500/10 border border-transparent hover:border-red-500/30 rounded-lg transition-all duration-200"
                  title="刪除"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

interface LogsModalProps {
  isOpen: boolean;
  job: ProcessingJob | null;
  logs: ProcessingLog[];
  onClose?: () => void;
}

function LogsModal({ isOpen, job, logs, onClose }: LogsModalProps) {
  if (!isOpen || !job) return null;

  const jobLogs = logs.filter((log) => log.jobId === job.id);

  const levelConfig: Record<LogLevel, { icon: typeof AlertCircle; className: string; labelClass: string; label: string }> = {
    info: { icon: AlertCircle, className: "text-sky-400", labelClass: "text-sky-500 bg-sky-500/10 border-sky-500/30", label: "INFO" },
    warning: { icon: AlertCircle, className: "text-amber-400", labelClass: "text-amber-500 bg-amber-500/10 border-amber-500/30", label: "WARN" },
    error: { icon: XCircle, className: "text-red-400", labelClass: "text-red-500 bg-red-500/10 border-red-500/30", label: "ERR" },
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-slate-950/90 backdrop-blur-sm" onClick={onClose} />

      <div className="relative w-full max-w-3xl bg-slate-900/95 backdrop-blur-xl border border-slate-700/50 rounded-lg overflow-hidden shadow-2xl">
        <div className="absolute inset-0 bg-gradient-to-br from-blue-500/3 via-transparent to-sky-500/3 pointer-events-none" />
        <div className="h-px bg-gradient-to-r from-transparent via-blue-500/50 to-transparent" />
        
        <div className="relative flex items-center justify-between px-5 py-4 border-b border-slate-700/50 bg-slate-800/30">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-3 rounded-full bg-red-500/80" />
              <div className="w-3 h-3 rounded-full bg-amber-500/80" />
              <div className="w-3 h-3 rounded-full bg-emerald-500/80" />
            </div>
            <div>
              <div className="flex items-center gap-3">
                <h2 className={cn("text-base font-semibold text-slate-100", fontHeading)}>系統控制台</h2>
                <span className={cn("text-[10px] text-slate-500 uppercase tracking-widest px-2 py-0.5 bg-slate-800/80 border border-slate-700/50 rounded", fontMono)}>
                  SYSTEM_CONSOLE
                </span>
              </div>
              <p className={cn("text-xs text-slate-500 mt-1 truncate max-w-md", fontMono)}>{job.title}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-slate-500 hover:text-slate-300 hover:bg-slate-800/50 border border-transparent hover:border-slate-700/50 rounded-lg transition-all duration-200"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="relative px-5 py-4 bg-slate-800/20 border-b border-slate-700/50">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <p className={cn("text-[10px] text-slate-600 uppercase tracking-widest mb-1.5", fontMono)}>STATUS</p>
              <StatusBadge status={job.status} />
            </div>
            <div>
              <p className={cn("text-[10px] text-slate-600 uppercase tracking-widest mb-1.5", fontMono)}>PROGRESS</p>
              <span className={cn("text-lg text-slate-200 tabular-nums", fontMono)}>{job.progress}%</span>
            </div>
            <div>
              <p className={cn("text-[10px] text-slate-600 uppercase tracking-widest mb-1.5", fontMono)}>SUBMITTED</p>
              <span className={cn("text-xs text-slate-400", fontMono)}>{formatDateTime(job.submittedAt)}</span>
            </div>
            {job.completedAt && (
              <div>
                <p className={cn("text-[10px] text-slate-600 uppercase tracking-widest mb-1.5", fontMono)}>COMPLETED</p>
                <span className={cn("text-xs text-slate-400", fontMono)}>{formatDateTime(job.completedAt)}</span>
              </div>
            )}
          </div>
        </div>

        <div className="relative max-h-80 overflow-y-auto bg-slate-950/50">
          <div className="absolute inset-0 opacity-20 pointer-events-none" style={{ 
            backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 23px, rgba(148,163,184,0.05) 23px, rgba(148,163,184,0.05) 24px)',
          }} />
          
          {jobLogs.length === 0 ? (
            <div className="relative p-10 text-center">
              <p className={cn("text-slate-500", fontHeading)}>尚無日誌記錄</p>
              <p className={cn("text-xs text-slate-600 mt-2 uppercase tracking-widest", fontMono)}>NO_LOGS_AVAILABLE</p>
            </div>
          ) : (
            <div className="relative divide-y divide-slate-800/30">
              {jobLogs.map((log, index) => {
                const { icon: Icon, className, labelClass, label } = levelConfig[log.level];
                return (
                  <div key={index} className="px-5 py-3 hover:bg-slate-800/20 transition-colors">
                    <div className="flex items-start gap-3">
                      <span className={cn("flex-shrink-0 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider border rounded", fontMono, labelClass)}>
                        {label}
                      </span>
                      <Icon className={cn("w-4 h-4 flex-shrink-0 mt-0.5", className)} />
                      <div className="flex-1 min-w-0">
                        <p className={cn("text-sm text-slate-300", fontMono)}>{log.message}</p>
                        <p className={cn("text-[10px] text-slate-600 mt-1.5 uppercase tracking-wider", fontMono)}>
                          {formatDateTime(log.timestamp)}
                        </p>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div className="relative px-5 py-4 border-t border-slate-700/50 bg-slate-800/20 flex items-center justify-between">
          <p className={cn("text-[10px] text-slate-600 uppercase tracking-widest", fontMono)}>
            {jobLogs.length} LOG_ENTRIES
          </p>
          <button
            onClick={onClose}
            className={cn(
              "px-4 py-2 bg-slate-800/80 hover:bg-slate-700/80 text-slate-300 text-sm font-medium rounded-lg transition-all duration-200",
              "border border-slate-700/50 hover:border-slate-600/50",
              fontHeading
            )}
          >
            關閉
          </button>
        </div>
        
        <div className="h-px bg-gradient-to-r from-transparent via-slate-600/30 to-transparent" />
      </div>
    </div>
  );
}

export function VideoIngestion({
  processingJobs,
  processedVideos,
  processingLogs,
  urlInput,
  selectedJobId,
  showLogsModal,
  onUrlInputChange,
  onSubmitUrl,
  onRetryJob,
  onDeleteVideo,
  onViewJobDetails,
  onCloseLogsModal,
  onViewVideo,
}: VideoIngestionProps) {
  const selectedJob = selectedJobId
    ? processingJobs.find((job) => job.id === selectedJobId) || null
    : null;

  const activeJobs = processingJobs.filter((job) => job.status !== "completed");

  return (
    <div className="min-h-screen bg-slate-950 relative overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-br from-blue-950/20 via-slate-950 to-sky-950/20 pointer-events-none" />
      <div className="absolute inset-0 opacity-30 pointer-events-none" style={{ 
        backgroundImage: `
          radial-gradient(circle at 20% 30%, rgba(59, 130, 246, 0.08) 0%, transparent 40%),
          radial-gradient(circle at 80% 70%, rgba(14, 165, 233, 0.06) 0%, transparent 40%)
        `,
      }} />
      <div className="absolute inset-0 opacity-[0.02] pointer-events-none" style={{ 
        backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 100px, rgba(148,163,184,0.1) 100px, rgba(148,163,184,0.1) 101px), repeating-linear-gradient(90deg, transparent, transparent 100px, rgba(148,163,184,0.1) 100px, rgba(148,163,184,0.1) 101px)',
      }} />
      
      <div className="relative p-4 sm:p-6 lg:p-8">
        <div className="max-w-6xl mx-auto">
          <div className="mb-8">
            <div className="flex items-center gap-4">
              <div className="relative">
                <div className="absolute inset-0 bg-blue-500/20 blur-xl rounded-full" />
                <div className="relative w-12 h-12 rounded-xl bg-slate-800/80 border border-slate-700/50 flex items-center justify-center backdrop-blur-sm">
                  <Upload className="w-6 h-6 text-blue-400" />
                </div>
              </div>
              <div>
                <h1 className={cn("text-2xl font-bold text-slate-100", fontHeading)}>
                  影片上傳系統
                </h1>
                <p className={cn("text-xs text-slate-500 mt-1 uppercase tracking-widest", fontMono)}>
                  VIDEO_INGESTION_SYSTEM v1.0
                </p>
              </div>
            </div>
          </div>

          <div className="mb-8">
            <UrlInputForm
              value={urlInput}
              onChange={onUrlInputChange}
              onSubmit={onSubmitUrl}
            />
          </div>

          <div className="mb-8">
            <div className="flex items-center gap-3 mb-5">
              <div className="w-8 h-8 rounded-lg bg-slate-800/80 border border-slate-700/50 flex items-center justify-center">
                <Loader2 className="w-4 h-4 text-blue-400" />
              </div>
              <h2 className={cn("text-lg font-semibold text-slate-100", fontHeading)}>處理佇列</h2>
              {activeJobs.length > 0 && (
                <span className={cn(
                  "flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-full border backdrop-blur-sm",
                  "bg-blue-500/10 text-blue-400 border-blue-500/30",
                  fontMono
                )}>
                  <span className="relative flex h-1.5 w-1.5">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
                    <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-blue-500" />
                  </span>
                  {activeJobs.length} ACTIVE
                </span>
              )}
            </div>
            <ProcessingQueue
              jobs={activeJobs}
              onRetry={onRetryJob}
              onViewDetails={onViewJobDetails}
            />
          </div>

          <div>
            <div className="flex items-center gap-3 mb-5">
              <div className="w-8 h-8 rounded-lg bg-slate-800/80 border border-slate-700/50 flex items-center justify-center">
                <Film className="w-4 h-4 text-sky-400" />
              </div>
              <h2 className={cn("text-lg font-semibold text-slate-100", fontHeading)}>資產庫</h2>
              {processedVideos.length > 0 && (
                <span className={cn(
                  "px-2.5 py-1 text-xs rounded-full border backdrop-blur-sm",
                  "bg-slate-800/50 text-slate-400 border-slate-700/50",
                  fontMono
                )}>
                  {processedVideos.length} ASSETS
                </span>
              )}
            </div>
            <VideoLibrary
              videos={processedVideos}
              onViewVideo={onViewVideo}
              onDeleteVideo={onDeleteVideo}
            />
          </div>

          <LogsModal
            isOpen={showLogsModal}
            job={selectedJob}
            logs={processingLogs}
            onClose={onCloseLogsModal}
          />
        </div>
      </div>
    </div>
  );
}

export default VideoIngestion;
