import { useState, useMemo, useCallback } from 'react';
import { useContestants } from '@mv/shared';
import { Badge } from '@mv/shared';
import type { Contestant } from '@mv/shared';

interface Appearance {
  video_id: string;
  video_name?: string;
  timestamp: number;
  confidence: number;
}

interface ContestantStats {
  total_appearances: number;
  screen_time_seconds: number;
  videos_appeared_in: number;
}

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function formatScreenTime(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  if (mins < 60) return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`;
  const hours = Math.floor(mins / 60);
  const remainingMins = mins % 60;
  return `${hours}h ${remainingMins}m`;
}

function getContestantInitials(contestant: Contestant): string {
  if (contestant.nickname && contestant.nickname.length <= 3) {
    return contestant.nickname;
  }
  return `#${contestant.id}`;
}

export function Contestants() {
  const { data: contestants = [], isLoading, error, refetch } = useContestants();
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedContestant, setSelectedContestant] = useState<Contestant | null>(null);
  const [appearances, setAppearances] = useState<Appearance[]>([]);
  const [stats, setStats] = useState<ContestantStats | null>(null);
  const [isLoadingAppearances, setIsLoadingAppearances] = useState(false);

  const filteredContestants = useMemo(() => {
    const query = searchQuery.toLowerCase().trim();
    if (!query) return contestants;
    return contestants.filter(
      (c: Contestant) =>
        c.name.toLowerCase().includes(query) ||
        c.nickname.toLowerCase().includes(query) ||
        String(c.id).includes(query),
    );
  }, [contestants, searchQuery]);

  const loadAppearances = useCallback(async (contestant: Contestant) => {
    setIsLoadingAppearances(true);
    try {
      const res = await fetch(`/api/recognition/results?contestant_id=${contestant.id}`);
      if (res.ok) {
        const data = await res.json();
        const results = data.results || data || [];
        setAppearances(
          results.map((r: Record<string, unknown>) => ({
            video_id: r.video_id,
            video_name: `Video ${r.video_id}`,
            timestamp: r.timestamp as number,
            confidence: r.confidence as number,
          })),
        );
        const uniqueVideos = new Set(results.map((r: Record<string, unknown>) => r.video_id));
        setStats({
          total_appearances: results.length,
          screen_time_seconds: results.length * 2,
          videos_appeared_in: uniqueVideos.size,
        });
      }
    } catch {
      setAppearances([]);
      setStats(null);
    } finally {
      setIsLoadingAppearances(false);
    }
  }, []);

  const openModal = useCallback(
    (contestant: Contestant) => {
      setSelectedContestant(contestant);
      setAppearances([]);
      setStats(null);
      loadAppearances(contestant);
    },
    [loadAppearances],
  );

  const closeModal = useCallback(() => {
    setSelectedContestant(null);
    setAppearances([]);
    setStats(null);
  }, []);

  return (
    <div className="p-6 max-w-[1400px] mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-100 mb-1">Contestant Directory</h1>
        <p className="text-slate-400 text-sm">Browse all 96 contestants and view their appearance history</p>
      </div>

      {/* Search bar */}
      <div className="flex gap-4 items-center mb-6 flex-wrap">
        <div className="relative flex-1 max-w-[400px] min-w-[200px]">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 text-sm">Search</span>
          <input
            type="text"
            className="w-full pl-16 pr-8 py-2.5 bg-slate-900 border border-slate-800 rounded-lg text-slate-200 text-sm placeholder:text-slate-600 focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500/30"
            placeholder="by name or nickname..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          {searchQuery && (
            <button
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-200"
              onClick={() => setSearchQuery('')}
            >
              x
            </button>
          )}
        </div>
        <Badge variant="neutral" size="md">
          {filteredContestants.length} of {contestants.length} contestants
        </Badge>
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="flex flex-col items-center justify-center py-12 text-slate-400">
          <div className="w-10 h-10 border-3 border-slate-700 border-t-orange-500 rounded-full animate-spin mb-4" />
          <p>Loading contestants...</p>
        </div>
      ) : error ? (
        <div className="flex flex-col items-center justify-center py-12 text-slate-400">
          <p className="text-red-400 mb-4">Failed to load contestants</p>
          <button
            className="px-4 py-2 bg-slate-800 text-slate-200 border border-slate-700 rounded-md hover:bg-orange-600 hover:border-orange-600 transition-colors"
            onClick={() => refetch()}
          >
            Retry
          </button>
        </div>
      ) : filteredContestants.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 text-slate-400">
          <p className="mb-4">No contestants found matching &quot;{searchQuery}&quot;</p>
          <button
            className="px-4 py-2 bg-slate-800 text-slate-200 border border-slate-700 rounded-md hover:bg-orange-600 hover:border-orange-600 transition-colors"
            onClick={() => setSearchQuery('')}
          >
            Clear search
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(180px,1fr))] gap-4">
          {filteredContestants.map((contestant: Contestant) => (
            <button
              key={contestant.id}
              className="flex flex-col bg-slate-900 border border-slate-800 rounded-lg overflow-hidden cursor-pointer transition-all text-left p-0 hover:border-orange-500 hover:-translate-y-1 hover:shadow-[0_8px_25px_rgba(0,0,0,0.3)]"
              onClick={() => openModal(contestant)}
            >
              <div className="aspect-square bg-gradient-to-br from-slate-800 to-slate-900 flex items-center justify-center relative">
                <span className="text-3xl font-bold text-white/90">{getContestantInitials(contestant)}</span>
                {contestant.has_embedding && (
                  <span
                    className="absolute bottom-2 right-2 bg-green-500 text-white w-5 h-5 rounded-full flex items-center justify-center text-xs"
                    title="Has face embedding"
                  >
                    &#10003;
                  </span>
                )}
              </div>
              <div className="p-3">
                <div className="font-semibold text-sm text-slate-200 truncate">{contestant.name}</div>
                <div className="text-xs text-slate-400 truncate">{contestant.nickname}</div>
                {contestant.age && <div className="text-xs text-slate-500 mt-0.5">{contestant.age} years old</div>}
              </div>
            </button>
          ))}
        </div>
      )}

      {/* Detail Modal */}
      {selectedContestant && (
        <div
          className="fixed inset-0 bg-black/85 flex items-center justify-center z-50 p-6 backdrop-blur-sm"
          onClick={closeModal}
          onKeyDown={(e) => e.key === 'Escape' && closeModal()}
          role="button"
          tabIndex={0}
        >
          <div
            className="bg-slate-900 rounded-xl max-w-[600px] w-full max-h-[85vh] overflow-y-auto relative border border-slate-800"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
          >
            {/* Close button */}
            <button
              className="absolute top-4 right-4 bg-slate-800 border-none text-slate-400 text-lg cursor-pointer z-10 w-8 h-8 rounded-full flex items-center justify-center hover:bg-red-500 hover:text-white transition-colors"
              onClick={closeModal}
              aria-label="Close modal"
            >
              x
            </button>

            <div className="p-6">
              {/* Modal Header */}
              <div className="flex gap-5 mb-6">
                <div className="w-[100px] h-[100px] shrink-0 bg-gradient-to-br from-slate-700 to-slate-800 rounded-lg flex items-center justify-center">
                  <span className="text-4xl font-bold text-white/90">
                    {getContestantInitials(selectedContestant)}
                  </span>
                </div>
                <div className="flex-1">
                  <h2 className="text-xl font-bold text-slate-100 mb-1">{selectedContestant.name}</h2>
                  <p className="text-base text-slate-400 mb-3">{selectedContestant.nickname}</p>
                  <div className="flex items-center gap-3 flex-wrap">
                    <Badge variant="neutral" size="sm">#{selectedContestant.id}</Badge>
                    {selectedContestant.age && (
                      <span className="text-xs text-slate-500">{selectedContestant.age} years old</span>
                    )}
                    {selectedContestant.has_embedding && (
                      <Badge variant="success" size="sm">Has Embedding</Badge>
                    )}
                  </div>
                </div>
              </div>

              {/* Stats */}
              <div className="grid grid-cols-3 gap-3 mb-6">
                {isLoadingAppearances ? (
                  <div className="col-span-3 text-center py-4 text-slate-500">Loading stats...</div>
                ) : stats ? (
                  <>
                    <div className="text-center p-4 bg-slate-800 rounded-lg">
                      <span className="block text-xl font-bold text-orange-400 leading-none mb-1">
                        {stats.total_appearances}
                      </span>
                      <span className="block text-[10px] text-slate-500 uppercase tracking-wider">Appearances</span>
                    </div>
                    <div className="text-center p-4 bg-slate-800 rounded-lg">
                      <span className="block text-xl font-bold text-orange-400 leading-none mb-1">
                        {formatScreenTime(stats.screen_time_seconds)}
                      </span>
                      <span className="block text-[10px] text-slate-500 uppercase tracking-wider">Screen Time</span>
                    </div>
                    <div className="text-center p-4 bg-slate-800 rounded-lg">
                      <span className="block text-xl font-bold text-orange-400 leading-none mb-1">
                        {stats.videos_appeared_in}
                      </span>
                      <span className="block text-[10px] text-slate-500 uppercase tracking-wider">Videos</span>
                    </div>
                  </>
                ) : (
                  <div className="col-span-3 text-center py-4 text-slate-500">No appearance data available</div>
                )}
              </div>

              {/* Appearances */}
              <div>
                <h3 className="text-sm font-semibold text-slate-200 mb-4">Appearance History</h3>
                {isLoadingAppearances ? (
                  <div className="flex items-center gap-3 py-4 text-slate-500">
                    <div className="w-5 h-5 border-2 border-slate-700 border-t-orange-500 rounded-full animate-spin" />
                    <span>Loading appearances...</span>
                  </div>
                ) : appearances.length === 0 ? (
                  <div className="text-center py-6 bg-slate-800 rounded-lg text-slate-400">
                    <p>No recorded appearances yet.</p>
                    <p className="text-xs text-slate-500 mt-2">
                      Appearances are recorded when videos are processed with face recognition.
                    </p>
                  </div>
                ) : (
                  <div className="flex flex-col gap-2 max-h-[250px] overflow-y-auto">
                    {appearances.map((appearance, idx) => (
                      <button
                        key={idx}
                        className="flex justify-between items-center px-4 py-3 bg-slate-800 border border-transparent rounded-md cursor-pointer transition-all text-left w-full hover:bg-slate-700 hover:border-orange-500 group"
                        onClick={() => {
                          window.location.href = `/player?video=${appearance.video_id}&t=${appearance.timestamp}`;
                        }}
                      >
                        <div className="flex flex-col gap-0.5">
                          <span className="font-medium text-slate-200 text-xs">
                            {appearance.video_name || `Video ${appearance.video_id}`}
                          </span>
                          <span className="text-[10px] text-slate-500">@ {formatTime(appearance.timestamp)}</span>
                        </div>
                        <div className="flex items-center gap-3">
                          <Badge
                            variant={
                              appearance.confidence > 0.85
                                ? 'success'
                                : appearance.confidence > 0.7
                                  ? 'warning'
                                  : 'neutral'
                            }
                            size="sm"
                          >
                            {(appearance.confidence * 100).toFixed(0)}%
                          </Badge>
                          <span className="text-slate-500 transition-transform group-hover:translate-x-1 group-hover:text-orange-400">
                            &rarr;
                          </span>
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
