import { Search, X, Clock, Film, Play, Users, Scan, Database, Activity } from "lucide-react";
import { useEffect, useRef } from "react";
import type {
  ContestantDirectoryProps,
  Contestant,
  Appearance,
} from "@product/sections/contestant-directory/types";

function injectStyles() {
  const styleId = "contestant-directory-animations";
  if (document.getElementById(styleId)) return;

  const style = document.createElement("style");
  style.id = styleId;
  style.textContent = `
    @keyframes avatar-pulse {
      0%, 100% { box-shadow: 0 0 20px rgba(56, 189, 248, 0.3), 0 0 40px rgba(56, 189, 248, 0.1); }
      50% { box-shadow: 0 0 30px rgba(56, 189, 248, 0.5), 0 0 60px rgba(56, 189, 248, 0.2); }
    }
    @keyframes card-enter {
      0% { opacity: 0; transform: translateY(20px) scale(0.95); }
      100% { opacity: 1; transform: translateY(0) scale(1); }
    }
    @keyframes scan-line {
      0% { transform: translateY(-100%); }
      100% { transform: translateY(400%); }
    }
    @keyframes glow-border {
      0%, 100% { opacity: 0.5; }
      50% { opacity: 1; }
    }
    @keyframes modal-enter {
      0% { opacity: 0; transform: translate(-50%, -48%) scale(0.96); }
      100% { opacity: 1; transform: translate(-50%, -50%) scale(1); }
    }
    @keyframes modal-backdrop {
      0% { opacity: 0; backdrop-filter: blur(0px); }
      100% { opacity: 1; backdrop-filter: blur(12px); }
    }
    @keyframes corner-frame {
      0%, 100% { opacity: 0.6; }
      50% { opacity: 1; }
    }
    @keyframes data-reveal {
      0% { opacity: 0; transform: translateX(-10px); }
      100% { opacity: 1; transform: translateX(0); }
    }
    @keyframes search-glow {
      0%, 100% { box-shadow: 0 0 0 1px rgba(59, 130, 246, 0.5), 0 0 20px rgba(59, 130, 246, 0.1); }
      50% { box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.8), 0 0 30px rgba(59, 130, 246, 0.2); }
    }
    .animate-avatar-pulse { animation: avatar-pulse 3s ease-in-out infinite; }
    .animate-card-enter { animation: card-enter 0.5s cubic-bezier(0.34, 1.56, 0.64, 1) forwards; opacity: 0; }
    .animate-scan-line { animation: scan-line 3s ease-in-out infinite; }
    .animate-glow-border { animation: glow-border 2s ease-in-out infinite; }
    .animate-modal-enter { animation: modal-enter 0.4s cubic-bezier(0.34, 1.56, 0.64, 1) forwards; }
    .animate-modal-backdrop { animation: modal-backdrop 0.3s ease-out forwards; }
    .animate-corner-frame { animation: corner-frame 2s ease-in-out infinite; }
    .animate-data-reveal { animation: data-reveal 0.4s ease-out forwards; opacity: 0; }
    .animate-search-glow { animation: search-glow 2s ease-in-out infinite; }
    
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');
    
    .font-display { font-family: 'Noto Sans TC', sans-serif; }
    .font-mono-tech { font-family: 'JetBrains Mono', monospace; }
  `;
  document.head.appendChild(style);
}

function formatScreenTime(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  if (hours > 0) {
    return `${hours}h ${mins}m`;
  }
  return `${mins}m`;
}

function formatTimestamp(seconds: number): string {
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
  const secs = seconds % 60;
  if (mins > 0) {
    return `${mins}m ${secs}s`;
  }
  return `${secs}s`;
}

interface SearchBarProps {
  value: string;
  onChange?: (query: string) => void;
}

function SearchBar({ value, onChange }: SearchBarProps) {
  return (
    <div className="relative group">
      <div className="absolute -inset-0.5 bg-gradient-to-r from-blue-500/20 via-sky-500/20 to-blue-500/20 rounded-2xl blur-sm opacity-0 group-focus-within:opacity-100 group-focus-within:animate-search-glow transition-opacity duration-300" />
      
      <div className="relative bg-slate-900/80 backdrop-blur-xl border border-slate-700/50 rounded-xl overflow-hidden">
        <div className="absolute inset-0 overflow-hidden pointer-events-none opacity-0 group-focus-within:opacity-100 transition-opacity">
          <div className="absolute inset-x-0 h-px bg-gradient-to-r from-transparent via-sky-400/50 to-transparent animate-scan-line" />
        </div>
        
        <div className="absolute top-0 left-0 w-3 h-3 border-l-2 border-t-2 border-blue-500/50 rounded-tl-lg" />
        <div className="absolute top-0 right-0 w-3 h-3 border-r-2 border-t-2 border-blue-500/50 rounded-tr-lg" />
        <div className="absolute bottom-0 left-0 w-3 h-3 border-l-2 border-b-2 border-blue-500/50 rounded-bl-lg" />
        <div className="absolute bottom-0 right-0 w-3 h-3 border-r-2 border-b-2 border-blue-500/50 rounded-br-lg" />
        
        <div className="relative flex items-center">
          <div className="pl-4 pr-2">
            <Scan className="w-5 h-5 text-sky-400/70 group-focus-within:text-sky-400 transition-colors" />
          </div>
          <input
            type="text"
            value={value}
            onChange={(e) => onChange?.(e.target.value)}
            placeholder="輸入識別碼或名稱進行搜尋..."
            className="font-display w-full py-3.5 pr-10 bg-transparent text-slate-100 placeholder-slate-500 focus:outline-none text-sm tracking-wide"
          />
          {value && (
            <button
              onClick={() => onChange?.("")}
              className="absolute right-3 top-1/2 -translate-y-1/2 p-1.5 rounded-lg text-slate-500 hover:text-sky-400 hover:bg-slate-800/50 transition-all"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

interface ContestantCardProps {
  contestant: Contestant;
  index: number;
  onClick?: () => void;
}

function ContestantCard({ contestant, index, onClick }: ContestantCardProps) {
  return (
    <button
      onClick={onClick}
      className="animate-card-enter group relative text-left"
      style={{ animationDelay: `${index * 60}ms` }}
    >
      <div className="absolute -inset-0.5 bg-gradient-to-br from-blue-500/0 via-sky-500/0 to-blue-500/0 group-hover:from-blue-500/20 group-hover:via-sky-500/10 group-hover:to-blue-500/20 rounded-2xl blur-md transition-all duration-500" />
      
      <div className="relative bg-slate-900/60 backdrop-blur-xl border border-slate-700/40 group-hover:border-sky-500/40 rounded-2xl overflow-hidden transition-all duration-300 group-hover:bg-slate-900/80">
        <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
          <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-sky-400/60 to-transparent" />
          <div className="absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-transparent via-blue-400/40 to-transparent" />
        </div>
        
        <div className="aspect-[3/4] relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-br from-slate-800 via-slate-900 to-slate-950" />
          <div className="absolute inset-0 bg-gradient-to-t from-blue-950/40 via-transparent to-sky-900/20" />
          
          <div 
            className="absolute inset-0 opacity-10"
            style={{
              backgroundImage: `linear-gradient(rgba(56, 189, 248, 0.1) 1px, transparent 1px), 
                               linear-gradient(90deg, rgba(56, 189, 248, 0.1) 1px, transparent 1px)`,
              backgroundSize: '20px 20px'
            }}
          />
          
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="relative">
              <div className="absolute -inset-3 rounded-full bg-gradient-to-br from-blue-500/20 to-sky-500/20 blur-xl group-hover:from-blue-500/30 group-hover:to-sky-500/30 transition-all duration-500" />
              
              <div className="relative w-20 h-20 md:w-24 md:h-24 rounded-full bg-gradient-to-br from-blue-600 via-blue-500 to-sky-400 flex items-center justify-center animate-avatar-pulse">
                <span className="font-display text-2xl md:text-3xl font-bold text-white drop-shadow-lg">
                  {contestant.chineseName.charAt(0)}
                </span>
              </div>
              
              <div className="absolute -inset-1 rounded-full border border-sky-400/30 group-hover:border-sky-400/50 transition-colors" 
                   style={{ animation: 'spin 20s linear infinite' }} />
            </div>
          </div>
          
          <div className="absolute inset-0 overflow-hidden opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none">
            <div className="absolute inset-x-0 h-8 bg-gradient-to-b from-sky-400/10 via-sky-400/5 to-transparent animate-scan-line" />
          </div>
          
          <div className="absolute top-2 left-2 w-4 h-4 border-l-2 border-t-2 border-sky-500/40 animate-corner-frame" />
          <div className="absolute top-2 right-2 w-4 h-4 border-r-2 border-t-2 border-sky-500/40 animate-corner-frame" style={{ animationDelay: '0.5s' }} />
          <div className="absolute bottom-2 left-2 w-4 h-4 border-l-2 border-b-2 border-sky-500/40 animate-corner-frame" style={{ animationDelay: '1s' }} />
          <div className="absolute bottom-2 right-2 w-4 h-4 border-r-2 border-b-2 border-sky-500/40 animate-corner-frame" style={{ animationDelay: '1.5s' }} />
          
          <div className="absolute top-3 right-3 font-mono-tech bg-slate-950/80 backdrop-blur-sm px-2 py-1 rounded border border-slate-700/50 text-[10px] text-sky-400/80 tracking-wider">
            ID:{contestant.id.slice(-4).toUpperCase()}
          </div>
          
          <div className="absolute bottom-3 left-3 font-mono-tech bg-slate-950/80 backdrop-blur-sm px-2 py-1 rounded border border-slate-700/50 text-[10px] text-slate-400">
            AGE:<span className="text-sky-400 ml-1">{contestant.age}</span>
          </div>
          
          <div className="absolute bottom-3 right-3 opacity-0 group-hover:opacity-100 transform translate-y-2 group-hover:translate-y-0 transition-all duration-300">
            <div className="font-mono-tech bg-slate-950/90 backdrop-blur-sm px-2 py-1 rounded border border-blue-500/30 text-[9px] text-blue-400 flex items-center gap-1">
              <Activity className="w-3 h-3" />
              ACTIVE
            </div>
          </div>
        </div>

        <div className="p-4 relative">
          <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-slate-700/50 to-transparent" />
          
          <h3 className="font-display text-base md:text-lg font-semibold text-slate-100 group-hover:text-sky-300 transition-colors truncate">
            {contestant.chineseName}
          </h3>
          <p className="font-display text-sm text-slate-500 mt-0.5 truncate">{contestant.nickname}</p>

          <div className="mt-3 pt-3 border-t border-slate-800/60 flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-slate-500">
              <Clock className="w-3.5 h-3.5 text-sky-500/60" />
              <span className="font-mono-tech text-xs text-sky-400/80">{formatScreenTime(contestant.totalScreenTime)}</span>
            </div>
            <div className="flex items-center gap-1.5 text-slate-500">
              <Film className="w-3.5 h-3.5 text-blue-500/60" />
              <span className="font-mono-tech text-xs text-blue-400/80">{contestant.appearanceCount}</span>
            </div>
          </div>
        </div>
      </div>
    </button>
  );
}

interface ContestantModalProps {
  contestant: Contestant;
  appearances: Appearance[];
  onClose?: () => void;
  onPlayAppearance?: (videoId: string, timestamp: number) => void;
}

function ContestantModal({
  contestant,
  appearances,
  onClose,
  onPlayAppearance,
}: ContestantModalProps) {
  const contestantAppearances = appearances.filter(
    (a) => a.contestantId === contestant.id
  );

  return (
    <>
      <div
        className="fixed inset-0 bg-slate-950/80 z-40 animate-modal-backdrop"
        onClick={onClose}
      />

      <div className="fixed inset-4 md:inset-auto md:left-1/2 md:top-1/2 md:-translate-x-1/2 md:-translate-y-1/2 md:w-full md:max-w-3xl md:max-h-[85vh] z-50 flex flex-col md:animate-modal-enter">
        <div className="relative h-full bg-slate-900/90 backdrop-blur-2xl border border-slate-700/50 rounded-2xl overflow-hidden shadow-2xl shadow-blue-500/10 flex flex-col">
          <div className="absolute inset-0 pointer-events-none">
            <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-sky-400/50 to-transparent animate-glow-border" />
            <div className="absolute inset-y-0 left-0 w-px bg-gradient-to-b from-transparent via-blue-400/30 to-transparent animate-glow-border" style={{ animationDelay: '1s' }} />
            <div className="absolute inset-y-0 right-0 w-px bg-gradient-to-b from-transparent via-blue-400/30 to-transparent animate-glow-border" style={{ animationDelay: '1s' }} />
            <div className="absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-transparent via-sky-400/30 to-transparent animate-glow-border" />
          </div>

          <div className="relative p-6 border-b border-slate-800/60">
            <div 
              className="absolute inset-0 opacity-5"
              style={{
                backgroundImage: `linear-gradient(rgba(56, 189, 248, 0.3) 1px, transparent 1px), 
                                 linear-gradient(90deg, rgba(56, 189, 248, 0.3) 1px, transparent 1px)`,
                backgroundSize: '30px 30px'
              }}
            />
            
            <div className="relative flex flex-col md:flex-row items-start gap-6">
              <div className="w-full md:w-40 h-52 md:h-56 rounded-xl relative overflow-hidden flex-shrink-0 self-center md:self-start">
                <div className="absolute inset-0 bg-gradient-to-br from-slate-800 via-slate-900 to-slate-950" />
                <div className="absolute inset-0 bg-gradient-to-t from-blue-950/60 via-transparent to-sky-900/30" />
                
                <div 
                  className="absolute inset-0 opacity-15"
                  style={{
                    backgroundImage: `linear-gradient(rgba(56, 189, 248, 0.2) 1px, transparent 1px), 
                                     linear-gradient(90deg, rgba(56, 189, 248, 0.2) 1px, transparent 1px)`,
                    backgroundSize: '15px 15px'
                  }}
                />
                
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="relative">
                    <div className="absolute -inset-4 rounded-full bg-gradient-to-br from-blue-500/30 to-sky-500/20 blur-2xl" />
                    <div className="relative w-24 h-24 rounded-full bg-gradient-to-br from-blue-600 via-blue-500 to-sky-400 flex items-center justify-center animate-avatar-pulse">
                      <span className="font-display text-4xl font-bold text-white drop-shadow-lg">
                        {contestant.chineseName.charAt(0)}
                      </span>
                    </div>
                  </div>
                </div>
                
                <div className="absolute inset-0 pointer-events-none">
                  <div className="absolute top-3 left-3 w-6 h-6 border-l-2 border-t-2 border-sky-400/70 animate-corner-frame" />
                  <div className="absolute top-3 right-3 w-6 h-6 border-r-2 border-t-2 border-sky-400/70 animate-corner-frame" style={{ animationDelay: '0.5s' }} />
                  <div className="absolute bottom-3 left-3 w-6 h-6 border-l-2 border-b-2 border-sky-400/70 animate-corner-frame" style={{ animationDelay: '1s' }} />
                  <div className="absolute bottom-3 right-3 w-6 h-6 border-r-2 border-b-2 border-sky-400/70 animate-corner-frame" style={{ animationDelay: '1.5s' }} />
                </div>
                
                <div className="absolute bottom-4 inset-x-4 font-mono-tech text-center bg-slate-950/80 backdrop-blur-sm py-1.5 rounded border border-slate-700/50">
                  <span className="text-[10px] text-slate-500 tracking-wider">SUBJECT ID </span>
                  <span className="text-xs text-sky-400">{contestant.id.slice(-6).toUpperCase()}</span>
                </div>
              </div>

              <div className="flex-1 min-w-0 w-full">
                <div className="flex items-start justify-between">
                  <div className="animate-data-reveal">
                    <div className="font-mono-tech text-[10px] text-sky-500/70 tracking-widest mb-1">DESIGNATED NAME</div>
                    <h2 className="font-display text-2xl md:text-3xl font-bold text-slate-100">
                      {contestant.chineseName}
                    </h2>
                    <p className="font-display text-lg text-slate-400 mt-1">{contestant.nickname}</p>
                    <div className="font-mono-tech text-sm text-slate-500 mt-2">
                      AGE: <span className="text-sky-400">{contestant.age}</span>
                    </div>
                  </div>
                  <button
                    onClick={onClose}
                    className="p-2 rounded-lg text-slate-500 hover:text-sky-400 hover:bg-slate-800/50 transition-all border border-transparent hover:border-sky-500/30"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>

                <div className="mt-6 grid grid-cols-2 gap-3 animate-data-reveal" style={{ animationDelay: '100ms' }}>
                  <div className="bg-slate-800/40 backdrop-blur-sm rounded-xl p-4 border border-slate-700/30 hover:border-sky-500/30 transition-colors">
                    <div className="flex items-center gap-2 mb-2">
                      <div className="w-6 h-6 rounded bg-sky-500/20 flex items-center justify-center">
                        <Clock className="w-3.5 h-3.5 text-sky-400" />
                      </div>
                      <span className="font-mono-tech text-[10px] text-slate-500 tracking-wider">SCREEN TIME</span>
                    </div>
                    <div className="font-mono-tech text-2xl font-semibold text-sky-400">
                      {formatScreenTime(contestant.totalScreenTime)}
                    </div>
                  </div>
                  <div className="bg-slate-800/40 backdrop-blur-sm rounded-xl p-4 border border-slate-700/30 hover:border-blue-500/30 transition-colors">
                    <div className="flex items-center gap-2 mb-2">
                      <div className="w-6 h-6 rounded bg-blue-500/20 flex items-center justify-center">
                        <Film className="w-3.5 h-3.5 text-blue-400" />
                      </div>
                      <span className="font-mono-tech text-[10px] text-slate-500 tracking-wider">APPEARANCES</span>
                    </div>
                    <div className="font-mono-tech text-2xl font-semibold text-blue-400">
                      {contestant.appearanceCount}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-6">
            <div className="flex items-center gap-3 mb-4 animate-data-reveal" style={{ animationDelay: '200ms' }}>
              <div className="w-7 h-7 rounded-lg bg-slate-800/60 border border-slate-700/50 flex items-center justify-center">
                <Database className="w-4 h-4 text-sky-400/70" />
              </div>
              <div>
                <h3 className="font-display text-sm font-medium text-slate-300">活動紀錄</h3>
                <p className="font-mono-tech text-[10px] text-slate-600 tracking-wider">ACTIVITY LOG • {contestantAppearances.length} ENTRIES</p>
              </div>
            </div>

            {contestantAppearances.length === 0 ? (
              <div className="text-center py-12 animate-data-reveal" style={{ animationDelay: '300ms' }}>
                <div className="w-16 h-16 mx-auto mb-4 rounded-xl bg-slate-800/40 border border-slate-700/30 flex items-center justify-center">
                  <Database className="w-8 h-8 text-slate-600" />
                </div>
                <p className="font-display text-slate-500">暫無活動紀錄</p>
                <p className="font-mono-tech text-[10px] text-slate-600 mt-1 tracking-wider">NO ENTRIES FOUND</p>
              </div>
            ) : (
              <div className="space-y-2">
                {contestantAppearances.map((appearance, index) => (
                  <button
                    key={appearance.id}
                    onClick={() =>
                      onPlayAppearance?.(appearance.videoId, appearance.timestamp)
                    }
                    className="animate-data-reveal w-full flex items-center gap-4 p-3 bg-slate-800/30 hover:bg-slate-800/50 border border-slate-700/30 hover:border-sky-500/30 rounded-xl transition-all duration-200 group"
                    style={{ animationDelay: `${300 + index * 50}ms` }}
                  >
                    <div className="w-10 h-10 rounded-lg bg-blue-500/10 border border-blue-500/20 group-hover:bg-blue-500/20 group-hover:border-blue-500/40 flex items-center justify-center flex-shrink-0 transition-all">
                      <Play className="w-4 h-4 text-blue-400 group-hover:text-blue-300 transition-colors" />
                    </div>

                    <div className="flex-1 min-w-0 text-left">
                      <div className="font-display text-sm font-medium text-slate-200 group-hover:text-sky-300 truncate transition-colors">
                        {appearance.videoTitle}
                      </div>
                      <div className="font-mono-tech text-[11px] text-slate-500 mt-0.5 flex items-center gap-2">
                        <span className="text-sky-400/70">{formatTimestamp(appearance.timestamp)}</span>
                        <span className="text-slate-600">•</span>
                        <span>{formatDuration(appearance.duration)}</span>
                      </div>
                    </div>

                    <div className="text-slate-600 group-hover:text-sky-400 transition-colors transform group-hover:translate-x-1 duration-200">
                      <Play className="w-4 h-4" />
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}

export function ContestantDirectory({
  contestants,
  appearances,
  searchQuery,
  selectedContestantId,
  onSearch,
  onSelectContestant,
  onCloseModal,
  onPlayAppearance,
}: ContestantDirectoryProps) {
  const hasInjected = useRef(false);
  useEffect(() => {
    if (!hasInjected.current) {
      injectStyles();
      hasInjected.current = true;
    }
  }, []);

  const filteredContestants = contestants.filter((c) => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      c.chineseName.toLowerCase().includes(query) ||
      c.nickname.toLowerCase().includes(query)
    );
  });

  const selectedContestant = contestants.find(
    (c) => c.id === selectedContestantId
  );

  return (
    <div className="min-h-screen bg-slate-950 relative overflow-hidden">
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-blue-500/5 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-0 w-80 h-80 bg-sky-500/5 rounded-full blur-3xl" />
        
        <div 
          className="absolute inset-0 opacity-[0.02]"
          style={{
            backgroundImage: `linear-gradient(rgba(56, 189, 248, 0.5) 1px, transparent 1px), 
                             linear-gradient(90deg, rgba(56, 189, 248, 0.5) 1px, transparent 1px)`,
            backgroundSize: '60px 60px'
          }}
        />
        
        <div className="absolute inset-0 bg-gradient-to-b from-slate-950 via-transparent to-slate-950" />
      </div>

      <div className="relative p-4 md:p-6">
        <div className="max-w-7xl mx-auto">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
            <div className="animate-data-reveal">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500/20 to-sky-500/10 border border-sky-500/30 flex items-center justify-center">
                  <Users className="w-5 h-5 text-sky-400" />
                </div>
                <div>
                  <h1 className="font-display text-xl md:text-2xl font-bold text-slate-100 tracking-tight">
                    參賽者檔案庫
                  </h1>
                  <p className="font-mono-tech text-[11px] text-slate-500 tracking-widest">
                    CONTESTANT ARCHIVE • <span className="text-sky-400">{contestants.length}</span> SUBJECTS
                  </p>
                </div>
              </div>
            </div>
          </div>

          <div className="mb-8 max-w-lg animate-data-reveal" style={{ animationDelay: '100ms' }}>
            <SearchBar value={searchQuery} onChange={onSearch} />
          </div>

          {filteredContestants.length === 0 ? (
            <div className="text-center py-20">
              <div className="w-20 h-20 mx-auto mb-6 rounded-2xl bg-slate-800/40 border border-slate-700/30 flex items-center justify-center">
                <Search className="w-10 h-10 text-slate-600" />
              </div>
              <p className="font-display text-slate-400 text-lg">
                找不到符合「<span className="text-sky-400">{searchQuery}</span>」的參賽者
              </p>
              <p className="font-mono-tech text-[11px] text-slate-600 mt-2 tracking-wider">
                NO MATCHING SUBJECTS FOUND
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3 md:gap-4">
              {filteredContestants.map((contestant, index) => (
                <ContestantCard
                  key={contestant.id}
                  contestant={contestant}
                  index={index}
                  onClick={() => onSelectContestant?.(contestant.id)}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {selectedContestant && (
        <ContestantModal
          contestant={selectedContestant}
          appearances={appearances}
          onClose={onCloseModal}
          onPlayAppearance={onPlayAppearance}
        />
      )}
    </div>
  );
}

export default ContestantDirectory;
