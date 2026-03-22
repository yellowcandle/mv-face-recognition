import { useState } from 'react';
import type { FaceDetection } from '../../types';

interface FlagDialogProps {
  mode: 'single' | 'batch';
  face?: FaceDetection | null;
  selectedFaces?: FaceDetection[];
  contestants: Array<{ number: number; name: string; nickname: string }>;
  onSubmit: (contestantId: number, userLabel: string) => void;
  onClose: () => void;
  isSubmitting: boolean;
}

export function FlagDialog({
  mode,
  face,
  selectedFaces = [],
  contestants,
  onSubmit,
  onClose,
  isSubmitting,
}: FlagDialogProps) {
  const [contestantId, setContestantId] = useState<number | null>(null);
  const [userLabel, setUserLabel] = useState('');

  const handleSubmit = () => {
    if (contestantId === null) return;
    onSubmit(contestantId, userLabel);
  };

  const facesToShow = mode === 'batch' ? selectedFaces : face ? [face] : [];
  const title = mode === 'batch' ? `Batch Flag Faces (${selectedFaces.length})` : 'Flag Face';
  const submitLabel = mode === 'batch'
    ? isSubmitting ? 'Flagging...' : `Flag ${selectedFaces.length} Faces`
    : isSubmitting ? 'Flagging...' : 'Flag Face';

  return (
    <div
      className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
      onClick={onClose}
    >
      <div
        className="bg-slate-900 border border-slate-700 rounded-xl p-6 max-w-md w-full mx-4 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <h3 className="text-lg font-semibold text-slate-100 mb-2">{title}</h3>
        <p className="text-slate-400 text-sm mb-4">
          {mode === 'batch'
            ? 'Assign all selected faces to a single contestant.'
            : 'Assign this detected face to a contestant to improve recognition accuracy.'}
        </p>

        <div className="space-y-4">
          {/* Show detected face info */}
          {mode === 'single' && face && (
            <div>
              <label className="block text-sm text-slate-400 mb-1">Detected As:</label>
              <p className="text-slate-200">
                {face.contestant_name || 'Unknown'}{' '}
                ({((face.confidence ?? 0) * 100).toFixed(1)}% confidence)
              </p>
            </div>
          )}

          {mode === 'batch' && selectedFaces.length > 0 && (
            <div>
              <label className="block text-sm text-slate-400 mb-1">Selected Faces:</label>
              <div className="flex flex-wrap gap-1.5">
                {selectedFaces.map((f, i) => (
                  <span
                    key={i}
                    className="bg-slate-800 text-slate-300 text-xs px-2 py-1 rounded-full border border-slate-700"
                  >
                    {f.contestant_name || 'Unknown'} ({((f.confidence ?? 0) * 100).toFixed(0)}%)
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Contestant select */}
          <div>
            <label htmlFor="flag-contestant-select" className="block text-sm text-slate-400 mb-1">
              {mode === 'batch' ? 'Assign All to Contestant:' : 'Correct Contestant:'}
            </label>
            <select
              id="flag-contestant-select"
              className="w-full bg-slate-800 text-slate-200 border border-slate-700 rounded-lg px-3 py-2 text-sm"
              value={contestantId ?? ''}
              onChange={(e) =>
                setContestantId(e.target.value ? parseInt(e.target.value, 10) : null)
              }
            >
              <option value="">-- Select Contestant --</option>
              {contestants.map((c) => (
                <option key={c.number} value={c.number}>
                  #{c.number} - {c.nickname} ({c.name})
                </option>
              ))}
            </select>
          </div>

          {/* User label (single mode only) */}
          {mode === 'single' && (
            <div>
              <label htmlFor="flag-user-label" className="block text-sm text-slate-400 mb-1">
                Note (optional):
              </label>
              <input
                id="flag-user-label"
                type="text"
                className="w-full bg-slate-800 text-slate-200 border border-slate-700 rounded-lg px-3 py-2 text-sm"
                placeholder="e.g., Clear frontal view"
                value={userLabel}
                onChange={(e) => setUserLabel(e.target.value)}
              />
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-3 mt-6">
          <button
            className="px-4 py-2 bg-slate-800 text-slate-300 border border-slate-700 rounded-lg text-sm hover:bg-slate-700"
            onClick={onClose}
          >
            Cancel
          </button>
          <button
            className="px-4 py-2 bg-orange-500 text-white rounded-lg text-sm font-medium hover:bg-orange-400 disabled:opacity-50 disabled:cursor-not-allowed"
            onClick={handleSubmit}
            disabled={contestantId === null || isSubmitting}
          >
            {submitLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
