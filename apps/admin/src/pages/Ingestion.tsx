import { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { Card, Badge, Button } from '@mv/shared';
import { useVideos } from '@mv/shared';

interface ProcessingJob {
  id: string;
  youtubeUrl: string;
  title: string;
  status: 'pending' | 'downloading' | 'processing' | 'completed' | 'failed';
  progress: number;
  startTime?: string;
  endTime?: string;
  facesDetected?: number;
  facesRecognized?: number;
  duration?: number;
  error?: string;
  logs: string[];
}

const youtubeRegex = /^(https?:\/\/)?(www\.)?(youtube\.com\/(watch\?v=|embed\/|v\/)|youtu\.be\/)[\w-]{11}$/;

function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function getStatusVariant(status: string): 'success' | 'warning' | 'error' | 'neutral' {
  switch (status) {
    case 'completed': return 'success';
    case 'processing':
    case 'downloading': return 'warning';
    case 'failed': return 'error';
    default: return 'neutral';
  }
}

export function Ingestion() {
  const { data: videos = [], isLoading: videosLoading } = useVideos();

  const [activeTab, setActiveTab] = useState<'queue' | 'library'>('queue');
  const [youtubeUrl, setYoutubeUrl] = useState('');
  const [urlError, setUrlError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [queue, setQueue] = useState<ProcessingJob[]>([]);
  const [logModal, setLogModal] = useState<ProcessingJob | null>(null);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const pendingCount = useMemo(() => queue.filter((j) => j.status === 'pending').length, [queue]);
  const processingCount = useMemo(() => queue.filter((j) => j.status === 'processing' || j.status === 'downloading').length, [queue]);
  const completedCount = useMemo(() => queue.filter((j) => j.status === 'completed').length, [queue]);
  const failedCount = useMemo(() => queue.filter((j) => j.status === 'failed').length, [queue]);

  const refreshJobs = useCallback(async () => {
    try {
      const res = await fetch('/api/ingestion/jobs');
      if (!res.ok) return;
      const jobs = await res.json();
      setQueue(
        jobs.map((job: any) => ({
          id: job.id,
          youtubeUrl: job.url,
          title: job.url,
          status: job.status,
          progress: job.progress || 0,
          startTime: job.created_at,
          endTime: job.updated_at,
          facesDetected: job.faces_detected,
          facesRecognized: job.faces_recognized,
          error: job.error,
          logs: [],
        })),
      );
    } catch (e) {
      console.error('Failed to refresh jobs:', e);
    }
  }, []);

  const startPolling = useCallback(() => {
    if (pollingRef.current) return;
    pollingRef.current = setInterval(refreshJobs, 3000);
  }, [refreshJobs]);

  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  // Initial load + polling management
  useEffect(() => {
    refreshJobs();
    return () => stopPolling();
  }, [refreshJobs, stopPolling]);

  // Start/stop polling based on active jobs
  useEffect(() => {
    const hasActive = queue.some((j) => j.status === 'pending' || j.status === 'downloading' || j.status === 'processing');
    if (hasActive) startPolling();
    else stopPolling();
  }, [queue, startPolling, stopPolling]);

  function validateUrl(url: string): boolean {
    if (!url.trim()) { setUrlError('Please enter a YouTube URL'); return false; }
    if (!youtubeRegex.test(url)) { setUrlError('Please enter a valid YouTube URL'); return false; }
    setUrlError('');
    return true;
  }

  async function submitUrl(e: React.FormEvent) {
    e.preventDefault();
    if (!validateUrl(youtubeUrl)) return;

    setIsSubmitting(true);
    try {
      const res = await fetch('/api/ingestion/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: youtubeUrl }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || err.error || 'Failed to submit');
      }
      const result = await res.json();
      setQueue((prev) => [
        {
          id: result.id,
          youtubeUrl: result.url,
          title: result.url,
          status: result.status,
          progress: result.progress || 0,
          logs: [],
        },
        ...prev,
      ]);
      setYoutubeUrl('');
      startPolling();
    } catch (e) {
      setUrlError(e instanceof Error ? e.message : 'Failed to submit URL. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  }

  async function retryJob(job: ProcessingJob) {
    try {
      const res = await fetch('/api/ingestion/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: job.youtubeUrl }),
      });
      if (res.ok) {
        await refreshJobs();
        startPolling();
      }
    } catch (e) {
      console.error('Failed to retry job:', e);
    }
  }

  function removeFromQueue(jobId: string) {
    setQueue((prev) => prev.filter((j) => j.id !== jobId));
  }

  const stats = [
    { icon: '\u23F3', value: pendingCount, label: 'Pending', accent: '' },
    { icon: '\u26A1', value: processingCount, label: 'Processing', accent: 'border-orange-500/30 bg-orange-500/5' },
    { icon: '\u2705', value: completedCount, label: 'Completed', accent: 'border-green-500/30 bg-green-500/5' },
    { icon: '\u274C', value: failedCount, label: 'Failed', accent: 'border-red-500/30 bg-red-500/5' },
  ];

  return (
    <div className="space-y-6 max-w-[1200px] mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Video Ingestion</h1>
        <p className="text-slate-400 text-sm mt-1">Submit YouTube videos for face recognition processing</p>
      </div>

      {/* URL Form */}
      <Card padding="lg">
        <h2 className="text-base font-semibold text-slate-200 mb-4">Add New Video</h2>
        <form onSubmit={submitUrl} className="flex gap-3 items-start">
          <div className="flex-1 space-y-1">
            <div className={`flex items-center bg-slate-800 border-2 rounded-lg px-4 transition-colors focus-within:border-orange-500 ${urlError ? 'border-red-500' : 'border-slate-700'}`}>
              <span className="text-lg mr-3">{'\uD83D\uDD17'}</span>
              <input
                type="text"
                value={youtubeUrl}
                onChange={(e) => { setYoutubeUrl(e.target.value); if (urlError) validateUrl(e.target.value); }}
                placeholder="Paste YouTube URL (e.g., https://youtube.com/watch?v=...)"
                className="flex-1 bg-transparent border-none py-3 text-slate-200 text-sm placeholder-slate-500 outline-none"
              />
            </div>
            {urlError && <span className="text-xs text-red-400">{urlError}</span>}
          </div>
          <Button type="submit" variant="primary" size="lg" disabled={isSubmitting}>
            {isSubmitting ? 'Submitting...' : 'Start Processing'}
          </Button>
        </form>
        <p className="text-xs text-slate-500 mt-3">Videos will be downloaded and processed for face detection and recognition.</p>
      </Card>

      {/* Stats Row */}
      <div className="grid grid-cols-4 gap-4">
        {stats.map((s) => (
          <div key={s.label} className={`flex flex-col items-center p-4 bg-slate-900 border border-slate-800 rounded-lg ${s.accent}`}>
            <span className="text-2xl mb-2">{s.icon}</span>
            <span className="text-2xl font-bold text-slate-100">{s.value}</span>
            <span className="text-xs text-slate-400">{s.label}</span>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-slate-800">
        <button
          onClick={() => setActiveTab('queue')}
          className={`px-5 py-3 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'queue'
              ? 'text-orange-500 border-orange-500'
              : 'text-slate-400 border-transparent hover:text-slate-200'
          }`}
        >
          Processing Queue ({queue.length})
        </button>
        <button
          onClick={() => setActiveTab('library')}
          className={`px-5 py-3 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'library'
              ? 'text-orange-500 border-orange-500'
              : 'text-slate-400 border-transparent hover:text-slate-200'
          }`}
        >
          Video Library ({videos.length})
        </button>
      </div>

      {/* Tab Content */}
      {activeTab === 'queue' ? (
        <Card padding="lg">
          {queue.length === 0 ? (
            <div className="text-center py-10 text-slate-400">
              <span className="text-5xl block mb-4">{'\uD83D\uDCED'}</span>
              <h3 className="text-lg font-semibold text-slate-200 mb-2">No videos in queue</h3>
              <p className="text-sm">Submit a YouTube URL above to start processing.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {queue.map((job) => (
                <div
                  key={job.id}
                  className={`p-4 bg-slate-950 rounded-lg border-2 transition-colors ${
                    job.status === 'processing' || job.status === 'downloading'
                      ? 'border-orange-500'
                      : 'border-transparent'
                  }`}
                >
                  <div className="flex justify-between items-start mb-3">
                    <div className="min-w-0 flex-1">
                      <h4 className="text-sm font-semibold text-slate-200 truncate">{job.title}</h4>
                      <p className="text-xs text-slate-500 break-all mt-0.5">{job.youtubeUrl}</p>
                    </div>
                    <Badge variant={getStatusVariant(job.status)} size="md">
                      {job.status.toUpperCase()}
                    </Badge>
                  </div>

                  {(job.status === 'processing' || job.status === 'downloading') && (
                    <div className="flex items-center gap-3 mb-3">
                      <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-orange-500 rounded-full transition-all"
                          style={{ width: `${job.progress}%` }}
                        />
                      </div>
                      <span className="text-xs font-semibold text-slate-300 min-w-[40px]">{Math.round(job.progress)}%</span>
                    </div>
                  )}

                  {job.status === 'completed' && (
                    <div className="flex flex-wrap gap-4 mb-3 text-xs text-slate-400">
                      <span>{job.facesDetected} detected</span>
                      <span>{job.facesRecognized} recognized</span>
                      <span>{formatDuration(job.duration || 0)}</span>
                    </div>
                  )}

                  {job.error && (
                    <p className="text-xs text-red-400 mb-3">{job.error}</p>
                  )}

                  <div className="flex gap-2">
                    <Button variant="secondary" size="sm" onClick={() => setLogModal(job)}>
                      Logs
                    </Button>
                    {job.status === 'failed' && (
                      <Button variant="primary" size="sm" onClick={() => retryJob(job)}>
                        Retry
                      </Button>
                    )}
                    {(job.status === 'completed' || job.status === 'failed') && (
                      <Button variant="ghost" size="sm" onClick={() => removeFromQueue(job.id)}>
                        Remove
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      ) : (
        <Card padding="lg">
          {videosLoading ? (
            <div className="flex flex-col items-center py-10 text-slate-400">
              <div className="w-10 h-10 border-3 border-slate-700 border-t-orange-500 rounded-full animate-spin mb-4" />
              <p>Loading video library...</p>
            </div>
          ) : videos.length === 0 ? (
            <div className="text-center py-10 text-slate-400">
              <span className="text-5xl block mb-4">{'\uD83C\uDFAC'}</span>
              <h3 className="text-lg font-semibold text-slate-200 mb-2">No videos in library</h3>
              <p className="text-sm">Processed videos will appear here.</p>
            </div>
          ) : (
            <div>
              {/* Table Header */}
              <div className="hidden md:grid grid-cols-[2fr_100px_120px_150px_120px] gap-4 px-4 py-3 bg-slate-950 rounded-lg text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
                <span>Title</span>
                <span>Duration</span>
                <span>Faces</span>
                <span>Added</span>
                <span>Actions</span>
              </div>
              {/* Rows */}
              {videos.map((video) => (
                <div
                  key={video.id}
                  className="grid grid-cols-1 md:grid-cols-[2fr_100px_120px_150px_120px] gap-2 md:gap-4 px-4 py-3 items-center border-b border-slate-800/50 hover:bg-slate-950/50 transition-colors"
                >
                  <span className="text-sm text-slate-200 flex items-center gap-2 truncate">
                    <span className="text-lg">{'\uD83D\uDCF9'}</span>
                    {video.name}
                  </span>
                  <span className="text-xs text-slate-400">--</span>
                  <span className="text-xs text-slate-400">--</span>
                  <span className="text-xs text-slate-400">--</span>
                  <span className="flex gap-2">
                    <a href={`/player?video=${video.id}`}>
                      <Button variant="secondary" size="sm">Play</Button>
                    </a>
                  </span>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* Log Modal */}
      {logModal && (
        <div
          className="fixed inset-0 bg-black/70 flex items-center justify-center z-50"
          onClick={() => setLogModal(null)}
        >
          <div
            className="bg-slate-900 border border-slate-700 rounded-lg w-full max-w-2xl mx-4 flex flex-col max-h-[80vh]"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex justify-between items-center p-4 border-b border-slate-800">
              <h3 className="text-lg font-semibold text-slate-100">Processing Logs</h3>
              <button onClick={() => setLogModal(null)} className="text-slate-500 hover:text-slate-300 text-xl">&times;</button>
            </div>
            <div className="p-4 overflow-y-auto flex-1">
              <div className="flex items-center gap-3 mb-4">
                <Badge variant={getStatusVariant(logModal.status)} size="md">{logModal.status.toUpperCase()}</Badge>
                <span className="text-sm text-slate-300 font-medium">{logModal.title}</span>
              </div>
              <div className="bg-slate-950 rounded-lg p-4 font-mono text-xs text-slate-400 max-h-96 overflow-y-auto">
                {logModal.logs.length > 0
                  ? logModal.logs.map((line, i) => <div key={i} className="py-0.5 break-all">{line}</div>)
                  : <p className="text-slate-600">No logs available.</p>
                }
              </div>
            </div>
            <div className="flex justify-end p-4 border-t border-slate-800">
              <Button variant="secondary" size="sm" onClick={() => setLogModal(null)}>Close</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
