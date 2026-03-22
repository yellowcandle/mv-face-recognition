import { useState, useMemo, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Card, Badge, Button } from '@mv/shared';
import { useFlaggedFaces, useContestants } from '@mv/shared';
import type { FlaggedFace, Contestant } from '@mv/shared';

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function getStatusVariant(status: string): 'warning' | 'success' | 'error' {
  switch (status) {
    case 'pending': return 'warning';
    case 'accepted': return 'success';
    case 'rejected': return 'error';
    default: return 'warning';
  }
}

function getConfidenceColor(confidence: number): string {
  if (confidence >= 0.8) return 'bg-green-500';
  if (confidence >= 0.6) return 'bg-amber-500';
  return 'bg-red-500';
}

export function Flagging() {
  const queryClient = useQueryClient();
  const { data: flaggedFaces = [], isLoading, error } = useFlaggedFaces();
  const { data: contestants = [] } = useContestants();

  const [statusFilter, setStatusFilter] = useState<'all' | 'pending' | 'accepted' | 'rejected'>('all');
  const [videoFilter, setVideoFilter] = useState('');
  const [contestantFilter, setContestantFilter] = useState('');
  const [confidenceThreshold, setConfidenceThreshold] = useState(0);
  const [selectedFaces, setSelectedFaces] = useState<Set<string>>(new Set());
  const [reassignModal, setReassignModal] = useState<FlaggedFace | null>(null);
  const [reassignContestantId, setReassignContestantId] = useState<string>('');

  const uniqueVideos = useMemo(
    () => [...new Set(flaggedFaces.map((f) => f.video_id))],
    [flaggedFaces],
  );

  const filteredFaces = useMemo(
    () =>
      flaggedFaces.filter((f) => {
        if (statusFilter !== 'all' && f.status !== statusFilter) return false;
        if (videoFilter && f.video_id !== videoFilter) return false;
        if (contestantFilter && String(f.contestant_id) !== contestantFilter) return false;
        if (f.confidence < confidenceThreshold) return false;
        return true;
      }),
    [flaggedFaces, statusFilter, videoFilter, contestantFilter, confidenceThreshold],
  );

  const getContestant = useCallback(
    (id: number): Contestant | undefined =>
      (contestants as Contestant[]).find((c) => Number(c.id) === id),
    [contestants],
  );

  async function updateFaceStatus(faceId: string, status: 'accepted' | 'rejected') {
    try {
      const res = await fetch(`/api/faces/flagged/${faceId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status }),
      });
      if (res.ok) queryClient.invalidateQueries({ queryKey: ['flaggedFaces'] });
    } catch (e) {
      console.error('Failed to update face status:', e);
    }
  }

  async function bulkUpdateStatus(status: 'accepted' | 'rejected') {
    for (const faceId of selectedFaces) {
      await updateFaceStatus(faceId, status);
    }
    setSelectedFaces(new Set());
  }

  async function reassignFace() {
    if (!reassignModal || !reassignContestantId) return;
    try {
      const res = await fetch('/api/faces/flag/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          face_id: reassignModal.id,
          contestant_id: Number(reassignContestantId),
        }),
      });
      if (res.ok) {
        queryClient.invalidateQueries({ queryKey: ['flaggedFaces'] });
        setReassignModal(null);
        setReassignContestantId('');
      }
    } catch (e) {
      console.error('Failed to reassign face:', e);
    }
  }

  function toggleSelection(faceId: string) {
    setSelectedFaces((prev) => {
      const next = new Set(prev);
      if (next.has(faceId)) next.delete(faceId);
      else next.add(faceId);
      return next;
    });
  }

  function selectAll() {
    setSelectedFaces(new Set(filteredFaces.map((f) => f.id)));
  }

  function clearSelection() {
    setSelectedFaces(new Set());
  }

  return (
    <div className="space-y-6 max-w-[1600px] mx-auto">
      {/* Header */}
      <div className="flex flex-wrap justify-between items-start gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Face Flagging</h1>
          <p className="text-slate-400 text-sm mt-1">
            Review and correct face identifications to improve recognition accuracy
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {selectedFaces.size > 0 && (
            <>
              <Badge variant="neutral" size="md">{selectedFaces.size} selected</Badge>
              <Button variant="secondary" size="sm" onClick={clearSelection}>Clear</Button>
              <Button variant="primary" size="sm" onClick={() => bulkUpdateStatus('accepted')}>Accept All</Button>
              <Button variant="destructive" size="sm" onClick={() => bulkUpdateStatus('rejected')}>Reject All</Button>
            </>
          )}
          <Button
            variant="secondary"
            size="sm"
            onClick={() => queryClient.invalidateQueries({ queryKey: ['flaggedFaces'] })}
          >
            Refresh
          </Button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-4 bg-slate-900 border border-slate-800 p-4 rounded-lg">
        <div className="flex items-center gap-2">
          <label className="text-xs text-slate-400 whitespace-nowrap">Status:</label>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as typeof statusFilter)}
            className="bg-slate-800 border border-slate-700 text-slate-200 text-xs rounded-lg px-2 py-1.5 focus:ring-orange-500 focus:outline-none"
          >
            <option value="all">All</option>
            <option value="pending">Pending</option>
            <option value="accepted">Accepted</option>
            <option value="rejected">Rejected</option>
          </select>
        </div>

        <div className="flex items-center gap-2">
          <label className="text-xs text-slate-400 whitespace-nowrap">Video:</label>
          <select
            value={videoFilter}
            onChange={(e) => setVideoFilter(e.target.value)}
            className="bg-slate-800 border border-slate-700 text-slate-200 text-xs rounded-lg px-2 py-1.5 focus:ring-orange-500 focus:outline-none"
          >
            <option value="">All Videos</option>
            {uniqueVideos.map((vid) => (
              <option key={vid} value={vid}>{vid}</option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-2">
          <label className="text-xs text-slate-400 whitespace-nowrap">Contestant:</label>
          <select
            value={contestantFilter}
            onChange={(e) => setContestantFilter(e.target.value)}
            className="bg-slate-800 border border-slate-700 text-slate-200 text-xs rounded-lg px-2 py-1.5 focus:ring-orange-500 focus:outline-none"
          >
            <option value="">All Contestants</option>
            {(contestants as Contestant[]).map((c) => (
              <option key={c.id} value={c.id}>#{c.id} - {c.nickname}</option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-2">
          <label className="text-xs text-slate-400 whitespace-nowrap">Min Confidence:</label>
          <input
            type="range"
            min="0"
            max="1"
            step="0.1"
            value={confidenceThreshold}
            onChange={(e) => setConfidenceThreshold(Number(e.target.value))}
            className="w-24 accent-orange-500"
          />
          <span className="text-xs text-slate-500 min-w-[40px]">
            {(confidenceThreshold * 100).toFixed(0)}%
          </span>
        </div>

        <Badge variant="neutral" size="md">{filteredFaces.length} flagged faces</Badge>

        {filteredFaces.length > 0 && (
          <Button variant="ghost" size="sm" onClick={selectAll}>Select All</Button>
        )}
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="flex flex-col items-center justify-center py-16 text-slate-400">
          <div className="w-10 h-10 border-3 border-slate-700 border-t-orange-500 rounded-full animate-spin mb-4" />
          <p>Loading flagged faces...</p>
        </div>
      ) : error ? (
        <div className="flex flex-col items-center justify-center py-16 text-slate-400">
          <p className="text-red-400 mb-4">Failed to load flagged faces</p>
          <Button
            variant="primary"
            onClick={() => queryClient.invalidateQueries({ queryKey: ['flaggedFaces'] })}
          >
            Retry
          </Button>
        </div>
      ) : filteredFaces.length === 0 ? (
        <Card padding="lg">
          <div className="text-center py-8">
            <span className="text-5xl block mb-4">&#x2705;</span>
            <h3 className="text-lg font-semibold text-slate-200 mb-2">No flagged faces</h3>
            <p className="text-slate-400">All faces have been reviewed or no corrections have been submitted yet.</p>
            <p className="text-slate-500 text-sm mt-4">You can flag faces from the Video Player while watching videos.</p>
          </div>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filteredFaces.map((face) => {
            const contestant = getContestant(face.contestant_id);
            return (
              <div
                key={face.id}
                onClick={() => toggleSelection(face.id)}
                className={`relative bg-slate-900 border-2 rounded-lg p-4 cursor-pointer transition-all hover:-translate-y-0.5 ${
                  selectedFaces.has(face.id)
                    ? 'border-orange-500 bg-orange-500/5'
                    : 'border-slate-800 hover:border-slate-600'
                }`}
              >
                {/* Checkbox */}
                <div className="absolute top-3 right-3 z-10">
                  <input
                    type="checkbox"
                    checked={selectedFaces.has(face.id)}
                    onChange={() => toggleSelection(face.id)}
                    onClick={(e) => e.stopPropagation()}
                    className="w-5 h-5 cursor-pointer accent-orange-500"
                  />
                </div>

                {/* Comparison View */}
                <div className="flex items-center justify-center gap-4 mb-4">
                  <div className="flex flex-col items-center gap-2">
                    <span className="text-[10px] text-slate-500 uppercase tracking-wider">Detected</span>
                    <div className="w-20 h-20 bg-slate-800 rounded-lg flex items-center justify-center overflow-hidden">
                      {face.thumbnail ? (
                        <img src={face.thumbnail} alt="Detected face" className="w-full h-full object-cover" />
                      ) : (
                        <span className="text-3xl text-slate-600">&#x1F464;</span>
                      )}
                    </div>
                  </div>

                  <span className="text-xl text-slate-600">&rarr;</span>

                  <div className="flex flex-col items-center gap-2">
                    <span className="text-[10px] text-slate-500 uppercase tracking-wider">Assigned</span>
                    <div className="w-20 h-20 bg-slate-800 rounded-lg flex items-center justify-center overflow-hidden relative">
                      <img
                        src={`/api/contestants/${face.contestant_id}/photo`}
                        alt="Contestant"
                        className="w-full h-full object-cover"
                        onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                      />
                      <span className="absolute text-sm text-slate-500">#{face.contestant_id}</span>
                    </div>
                  </div>
                </div>

                {/* Details */}
                <div>
                  <div className="flex justify-between items-center mb-2">
                    <span className="font-semibold text-slate-200 text-sm">
                      {contestant
                        ? <>{contestant.nickname} <span className="font-normal text-xs text-slate-500">({contestant.name})</span></>
                        : `Contestant #${face.contestant_id}`
                      }
                    </span>
                    <Badge variant={getStatusVariant(face.status)} size="sm">
                      {face.status}
                    </Badge>
                  </div>

                  {/* Confidence bar */}
                  <div className="h-2 bg-slate-800 rounded-full mb-3 relative overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${getConfidenceColor(face.confidence)}`}
                      style={{ width: `${face.confidence * 100}%` }}
                    />
                    <span className="absolute right-1 top-1/2 -translate-y-1/2 text-[10px] font-semibold text-slate-300">
                      {(face.confidence * 100).toFixed(1)}%
                    </span>
                  </div>

                  <div className="flex flex-wrap gap-3 text-xs text-slate-500 mb-2">
                    <span>{face.video_id}</span>
                    <span>{formatTime(face.timestamp)}</span>
                  </div>

                  {face.user_label && (
                    <p className="text-xs text-slate-400 bg-slate-800 rounded-md px-2 py-1.5 mb-3">
                      {face.user_label}
                    </p>
                  )}

                  {face.status === 'pending' && (
                    <div className="flex gap-2 mt-3">
                      <button
                        onClick={(e) => { e.stopPropagation(); updateFaceStatus(face.id, 'accepted'); }}
                        className="flex-1 py-1.5 px-3 bg-green-600 hover:bg-green-500 text-white text-xs font-medium rounded-lg transition-colors"
                      >
                        Accept
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); updateFaceStatus(face.id, 'rejected'); }}
                        className="flex-1 py-1.5 px-3 bg-slate-700 hover:bg-red-600 text-white text-xs font-medium rounded-lg transition-colors"
                      >
                        Reject
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setReassignModal(face);
                          setReassignContestantId(String(face.contestant_id));
                        }}
                        className="py-1.5 px-3 bg-slate-700 hover:bg-slate-600 text-slate-300 text-xs font-medium rounded-lg transition-colors"
                      >
                        Reassign
                      </button>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Info Card */}
      <Card padding="lg" className="mt-8">
        <h3 className="text-sm font-semibold text-slate-200 mb-3">How Face Flagging Works</h3>
        <ol className="list-decimal pl-5 text-sm text-slate-400 space-y-1.5">
          <li>While watching videos in the <span className="text-orange-400 font-medium">Video Player</span>, click on any detected face to flag it</li>
          <li>Select the correct contestant from the dropdown</li>
          <li>Optionally add notes about the correction</li>
          <li>Submit the flag for review</li>
          <li>Use this page to <span className="text-orange-400 font-medium">Accept</span> or <span className="text-orange-400 font-medium">Reject</span> flagged corrections</li>
          <li>Accepted corrections help improve future face recognition accuracy</li>
        </ol>
      </Card>

      {/* Reassignment Modal */}
      {reassignModal && (
        <div
          className="fixed inset-0 bg-black/70 flex items-center justify-center z-50"
          onClick={() => setReassignModal(null)}
        >
          <div
            className="bg-slate-900 border border-slate-700 rounded-lg w-full max-w-md mx-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex justify-between items-center p-4 border-b border-slate-800">
              <h3 className="text-lg font-semibold text-slate-100">Reassign Face</h3>
              <button
                onClick={() => setReassignModal(null)}
                className="text-slate-500 hover:text-slate-300 text-xl"
              >
                &times;
              </button>
            </div>

            <div className="p-4 space-y-4">
              {/* Side-by-side comparison */}
              <div className="flex items-center justify-center gap-4">
                <div className="flex flex-col items-center gap-2">
                  <span className="text-[10px] text-slate-500 uppercase tracking-wider">Detected</span>
                  <div className="w-24 h-24 bg-slate-800 rounded-lg flex items-center justify-center overflow-hidden">
                    {reassignModal.thumbnail ? (
                      <img src={reassignModal.thumbnail} alt="Detected" className="w-full h-full object-cover" />
                    ) : (
                      <span className="text-4xl text-slate-600">&#x1F464;</span>
                    )}
                  </div>
                </div>
                <span className="text-xl text-slate-600">&rarr;</span>
                <div className="flex flex-col items-center gap-2">
                  <span className="text-[10px] text-slate-500 uppercase tracking-wider">Reference</span>
                  <div className="w-24 h-24 bg-slate-800 rounded-lg flex items-center justify-center overflow-hidden">
                    <img
                      src={`/api/contestants/${reassignContestantId || reassignModal.contestant_id}/photo`}
                      alt="Reference"
                      className="w-full h-full object-cover"
                      onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                    />
                  </div>
                </div>
              </div>

              <div>
                <label className="block text-xs text-slate-400 mb-1.5">Assign to contestant:</label>
                <select
                  value={reassignContestantId}
                  onChange={(e) => setReassignContestantId(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 text-slate-200 text-sm rounded-lg px-3 py-2 focus:ring-orange-500 focus:outline-none"
                >
                  <option value="">Select contestant...</option>
                  {(contestants as Contestant[]).map((c) => (
                    <option key={c.id} value={c.id}>#{c.id} - {c.nickname} ({c.name})</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="flex justify-end gap-2 p-4 border-t border-slate-800">
              <Button variant="secondary" size="sm" onClick={() => setReassignModal(null)}>Cancel</Button>
              <Button
                variant="primary"
                size="sm"
                onClick={() => { reassignFace(); }}
                disabled={!reassignContestantId}
              >
                Accept &amp; Reassign
              </Button>
              <Button
                variant="destructive"
                size="sm"
                onClick={() => { updateFaceStatus(reassignModal.id, 'rejected'); setReassignModal(null); }}
              >
                Reject
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
