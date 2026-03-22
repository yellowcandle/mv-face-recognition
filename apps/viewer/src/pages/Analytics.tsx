import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, Badge } from '@mv/shared';
import { useVideos } from '@mv/shared';
import type { VideoMetadata } from '@mv/shared';

interface ContestantStat {
  nickname: string;
  name: string;
  appearances: number;
  avgConfidence: number;
  maxConfidence: number;
  firstSeen: number;
  lastSeen: number;
}

export function Analytics() {
  const { data: videos = [] } = useVideos();
  const [selectedVideoId, setSelectedVideoId] = useState<string>('');
  const [sortBy, setSortBy] = useState<'appearances' | 'avgConfidence'>('appearances');

  const videoId = selectedVideoId || videos[0]?.id || '';
  const numericId = videoId.match(/^(\d+)/)?.[1] || videoId;

  const { data: metadata, isLoading } = useQuery<VideoMetadata>({
    queryKey: ['video-metadata', numericId],
    queryFn: async () => {
      const res = await fetch(`/api/videos/metadata/dense/${numericId}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    enabled: !!numericId,
    staleTime: 5 * 60 * 1000,
  });

  const stats = useMemo<ContestantStat[]>(() => {
    if (!metadata?.contestant_timeline) return [];
    return Object.entries(metadata.contestant_timeline)
      .map(([key, info]) => ({
        nickname: key,
        name: key,
        appearances: info.total_appearances,
        avgConfidence: info.avg_confidence,
        maxConfidence: info.max_confidence,
        firstSeen: info.first_appearance_time,
        lastSeen: info.last_appearance_time,
      }))
      .sort((a, b) =>
        sortBy === 'appearances'
          ? b.appearances - a.appearances
          : b.avgConfidence - a.avgConfidence
      );
  }, [metadata, sortBy]);

  const summary = metadata?.recognition_summary;

  return (
    <div className="max-w-5xl mx-auto px-6 py-10">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-bold text-slate-100">Analytics</h1>
        <select
          className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-orange-500"
          value={selectedVideoId}
          onChange={(e) => setSelectedVideoId(e.target.value)}
        >
          {videos.map((v) => (
            <option key={v.id} value={v.id}>
              {v.name}
            </option>
          ))}
        </select>
      </div>

      {/* Summary cards */}
      {summary && (
        <div className="grid grid-cols-4 gap-4 mb-8">
          {[
            { label: 'Frames', value: summary.total_frames_processed.toLocaleString() },
            { label: 'Faces Detected', value: summary.total_faces_detected.toLocaleString() },
            { label: 'Recognized', value: summary.total_faces_recognized.toLocaleString() },
            { label: 'Unique Contestants', value: summary.unique_contestants },
          ].map((s) => (
            <Card key={s.label}>
              <div className="text-2xl font-semibold text-slate-100">{s.value}</div>
              <div className="text-xs text-slate-500 mt-1">{s.label}</div>
            </Card>
          ))}
        </div>
      )}

      {/* Sort controls */}
      <div className="flex items-center gap-3 mb-4">
        <span className="text-sm text-slate-400">Sort by:</span>
        <button
          className={`px-3 py-1 rounded-full text-xs transition-colors ${
            sortBy === 'appearances' ? 'bg-orange-600 text-white' : 'bg-slate-800 text-slate-400 hover:text-slate-200'
          }`}
          onClick={() => setSortBy('appearances')}
        >
          Appearances
        </button>
        <button
          className={`px-3 py-1 rounded-full text-xs transition-colors ${
            sortBy === 'avgConfidence' ? 'bg-orange-600 text-white' : 'bg-slate-800 text-slate-400 hover:text-slate-200'
          }`}
          onClick={() => setSortBy('avgConfidence')}
        >
          Confidence
        </button>
      </div>

      {/* Contestant table */}
      {isLoading ? (
        <div className="text-center py-12 text-slate-500">Loading analytics...</div>
      ) : stats.length === 0 ? (
        <div className="text-center py-12 text-slate-500">No recognition data for this video.</div>
      ) : (
        <div className="bg-slate-900 border border-slate-800 rounded overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400 text-xs uppercase tracking-wider">
                <th className="text-left px-4 py-3">Contestant</th>
                <th className="text-right px-4 py-3">Appearances</th>
                <th className="text-right px-4 py-3">Avg Confidence</th>
                <th className="text-right px-4 py-3">Max Confidence</th>
                <th className="text-right px-4 py-3">Screen Time</th>
              </tr>
            </thead>
            <tbody>
              {stats.map((s) => (
                <tr key={s.nickname} className="border-b border-slate-800/50 hover:bg-slate-800/30">
                  <td className="px-4 py-3 font-medium text-slate-200">{s.nickname}</td>
                  <td className="px-4 py-3 text-right text-slate-300">{s.appearances}</td>
                  <td className="px-4 py-3 text-right">
                    <Badge variant={s.avgConfidence > 0.4 ? 'success' : s.avgConfidence > 0.25 ? 'warning' : 'error'}>
                      {(s.avgConfidence * 100).toFixed(0)}%
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-right text-slate-300">{(s.maxConfidence * 100).toFixed(0)}%</td>
                  <td className="px-4 py-3 text-right text-slate-400">
                    {formatTime(s.firstSeen)} – {formatTime(s.lastSeen)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}
