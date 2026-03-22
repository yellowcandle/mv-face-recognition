import { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { Card, Badge, Button } from '@mv/shared';

interface ProcessingJob {
  id: string;
  mode?: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  current_video?: string;
  videos_processed?: number;
  total_videos?: number;
  created_at?: string;
  started_at?: number;
  completed_at?: number;
  error?: string;
}

function getStatusVariant(status: string): 'success' | 'warning' | 'error' | 'neutral' {
  switch (status) {
    case 'completed': return 'success';
    case 'running': return 'warning';
    case 'failed': return 'error';
    default: return 'neutral';
  }
}

function getStatusColor(status: string): string {
  switch (status) {
    case 'completed': return 'bg-green-500';
    case 'running': return 'bg-blue-500';
    case 'failed': return 'bg-red-500';
    case 'cancelled': return 'bg-slate-500';
    default: return 'bg-amber-500';
  }
}

function formatDuration(start?: number, end?: number): string {
  if (!start) return '--';
  const endTime = end || Date.now();
  const diff = Math.floor((endTime - start) / 1000);
  const mins = Math.floor(diff / 60);
  const secs = diff % 60;
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function formatTimestamp(iso?: string): string {
  if (!iso) return '--';
  return new Date(iso).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function Processing() {
  const [jobs, setJobs] = useState<ProcessingJob[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const activeCount = useMemo(() => jobs.filter((j) => j.status === 'running' || j.status === 'queued').length, [jobs]);
  const completedCount = useMemo(() => jobs.filter((j) => j.status === 'completed').length, [jobs]);

  const fetchJobs = useCallback(async () => {
    try {
      const res = await fetch('/api/processing/jobs');
      if (!res.ok) return;
      const data = await res.json();
      const jobList = data.jobs || data || [];
      setJobs(Array.isArray(jobList) ? jobList : []);
    } catch (e) {
      console.error('Failed to fetch jobs:', e);
    }
  }, []);

  // Initial load + polling
  useEffect(() => {
    fetchJobs();
    pollingRef.current = setInterval(fetchJobs, 5000);
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, [fetchJobs]);

  async function startInitialProcessing() {
    setIsProcessing(true);
    setError(null);
    try {
      const res = await fetch('/api/processing/trigger', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mode: 'initial',
          similarity_threshold: 0.25,
          sync_from_hf: true,
          upload_results: true,
        }),
      });
      if (!res.ok) throw new Error('Failed to start processing');
      await fetchJobs();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to start processing');
    } finally {
      setIsProcessing(false);
    }
  }

  async function startEmbeddingUpdate() {
    setIsProcessing(true);
    setError(null);
    try {
      const res = await fetch('/api/processing/trigger', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mode: 'embedding-update',
          sync_from_hf: true,
        }),
      });
      if (!res.ok) throw new Error('Failed to update embeddings');
      await fetchJobs();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to update embeddings');
    } finally {
      setIsProcessing(false);
    }
  }

  async function cancelJob(jobId: string) {
    try {
      const res = await fetch(`/api/processing/cancel/${jobId}`, { method: 'POST' });
      if (!res.ok) throw new Error('Failed to cancel job');
      await fetchJobs();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to cancel job');
    }
  }

  async function clearCompleted() {
    try {
      const res = await fetch('/api/processing/clear-completed', { method: 'POST' });
      if (res.ok) {
        setJobs((prev) => prev.filter((j) => j.status !== 'completed'));
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to clear completed jobs');
    }
  }

  return (
    <div className="space-y-6 max-w-[1400px] mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Video Processing</h1>
        <p className="text-slate-400 text-sm mt-1">Manage cloud processing jobs for face recognition</p>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="bg-red-900/30 border border-red-800 text-red-400 px-4 py-3 rounded-lg text-sm font-medium">
          {error}
        </div>
      )}

      {/* Active Jobs Banner */}
      {activeCount > 0 && (
        <div className="bg-blue-900/20 border border-blue-800 text-blue-400 px-4 py-3 rounded-lg text-sm font-medium flex items-center gap-2">
          <div className="w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
          {activeCount} job{activeCount !== 1 ? 's' : ''} running
        </div>
      )}

      {/* Processing Action Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card padding="lg">
          <div className="flex justify-between items-center mb-3">
            <h2 className="text-base font-semibold text-slate-200">Initial Processing</h2>
            <span className="w-2 h-2 rounded-full bg-green-500" />
          </div>
          <p className="text-sm text-slate-400 mb-4 leading-relaxed">
            Process all videos using cloud GPUs for initial face detection and recognition
          </p>
          <Button
            variant="primary"
            onClick={startInitialProcessing}
            disabled={isProcessing}
            className="w-full mb-4"
          >
            {isProcessing ? 'Starting...' : 'Start Processing'}
          </Button>
          <ul className="space-y-1.5 text-xs text-slate-500">
            <li className="flex items-center gap-2"><span className="text-green-500">&#x2713;</span> Process all unprocessed videos</li>
            <li className="flex items-center gap-2"><span className="text-green-500">&#x2713;</span> Detect and recognize faces</li>
            <li className="flex items-center gap-2"><span className="text-green-500">&#x2713;</span> Cloud GPU acceleration</li>
            <li className="flex items-center gap-2"><span className="text-green-500">&#x2713;</span> Automatic HuggingFace sync</li>
          </ul>
        </Card>

        <Card padding="lg">
          <div className="flex justify-between items-center mb-3">
            <h2 className="text-base font-semibold text-slate-200">Embedding Update</h2>
            <span className="w-2 h-2 rounded-full bg-green-500" />
          </div>
          <p className="text-sm text-slate-400 mb-4 leading-relaxed">
            Improve recognition accuracy by incorporating user-flagged faces into embeddings
          </p>
          <Button
            variant="secondary"
            onClick={startEmbeddingUpdate}
            disabled={isProcessing}
            className="w-full mb-4"
          >
            {isProcessing ? 'Starting...' : 'Update Embeddings'}
          </Button>
          <ul className="space-y-1.5 text-xs text-slate-500">
            <li className="flex items-center gap-2"><span className="text-green-500">&#x2713;</span> Improve face recognition accuracy</li>
            <li className="flex items-center gap-2"><span className="text-green-500">&#x2713;</span> Incorporate user feedback</li>
            <li className="flex items-center gap-2"><span className="text-green-500">&#x2713;</span> Fast embedding recalculation</li>
            <li className="flex items-center gap-2"><span className="text-green-500">&#x2713;</span> Automatic database rebuild</li>
          </ul>
        </Card>
      </div>

      {/* Jobs List */}
      <Card padding="lg">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-base font-semibold text-slate-200">Processing Jobs</h2>
          <div className="flex items-center gap-2">
            <Badge variant="warning" size="sm">{activeCount} Active</Badge>
            <Badge variant="success" size="sm">{completedCount} Completed</Badge>
            {completedCount > 0 && (
              <Button variant="ghost" size="sm" onClick={clearCompleted}>
                Clear Completed
              </Button>
            )}
          </div>
        </div>

        {jobs.length === 0 ? (
          <div className="text-center py-10 text-slate-500">
            <p className="text-sm">No processing jobs yet</p>
            <p className="text-xs mt-1">Start a processing job to see it here</p>
          </div>
        ) : (
          <div className="space-y-3">
            {jobs.map((job) => (
              <div
                key={job.id}
                className="bg-slate-950 border border-slate-800 rounded-lg p-4 flex gap-4 hover:border-slate-700 transition-colors"
              >
                {/* Main Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3 mb-2">
                    <h3 className="text-sm font-semibold text-slate-200">
                      {job.mode ? job.mode.replace('-', ' ').toUpperCase() : 'Processing'}
                    </h3>
                    <Badge variant={getStatusVariant(job.status)} size="sm">
                      {job.status}
                    </Badge>
                  </div>

                  {job.current_video && (
                    <p className="text-xs text-slate-400 font-medium mb-1">{job.current_video}</p>
                  )}

                  {job.videos_processed !== undefined && job.total_videos && (
                    <p className="text-xs text-slate-300 font-medium mb-1">
                      {job.videos_processed} / {job.total_videos} videos
                    </p>
                  )}

                  {/* Progress bar */}
                  <div className="flex items-center gap-3 mt-2">
                    <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-300 ${getStatusColor(job.status)}`}
                        style={{ width: `${job.progress || 0}%` }}
                      />
                    </div>
                    <span className="text-xs font-semibold text-slate-300 min-w-[40px]">
                      {job.progress || 0}%
                    </span>
                  </div>

                  {job.error && (
                    <p className="text-xs text-red-400 mt-2">{job.error}</p>
                  )}
                </div>

                {/* Actions & Times */}
                <div className="flex flex-col items-end gap-2 shrink-0">
                  {(job.status === 'queued' || job.status === 'running') && (
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => cancelJob(job.id)}
                    >
                      Cancel
                    </Button>
                  )}
                  <div className="text-right space-y-0.5">
                    {job.created_at && (
                      <p className="text-[11px] text-slate-500">Created: {formatTimestamp(job.created_at)}</p>
                    )}
                    {job.started_at && (
                      <p className="text-[11px] text-slate-500">
                        Duration: {formatDuration(job.started_at, job.completed_at)}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
