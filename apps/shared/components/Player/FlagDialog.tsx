import { useState } from 'react';
import type { FaceDetection } from '../../types';
import { bandFor } from '../../lib/bands';

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
        className="bg-paper-light border border-paper-deep rounded-none p-6 max-w-md w-full mx-4 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <h3 className="text-lg font-semibold text-carbon-deep mb-2">{title}</h3>
        <p className="text-carbon-soft text-sm mb-4">
          {mode === 'batch'
            ? 'Assign all selected faces to a single contestant.'
            : 'Assign this detected face to a contestant to improve recognition accuracy.'}
        </p>

        <div className="space-y-4">
          {/* Show detected face info */}
          {mode === 'single' && face && (
            <div>
              <label className="block text-sm text-carbon-soft mb-1">Detected As:</label>
              <p className="text-carbon-deep">
                {face.matched ? face.contestant_name || face.contestant_nickname || 'Unmatched' : 'Unmatched'}{' '}
                ({face.matched && face.match_score != null
                  ? `${face.match_score.toFixed(2)} cosine (${bandFor(face.match_score)} band)`
                  : 'no match score'})
              </p>
            </div>
          )}

          {mode === 'batch' && selectedFaces.length > 0 && (
            <div>
              <label className="block text-sm text-carbon-soft mb-1">Selected Faces:</label>
              <div className="flex flex-wrap gap-1.5">
                {selectedFaces.map((f, i) => (
                  <span
                    key={i}
                    className="bg-paper-dark text-carbon text-xs px-2 py-1 rounded-full border border-paper-deep"
                  >
                    {f.matched ? f.contestant_name || f.contestant_nickname || 'Unmatched' : 'Unmatched'}{' '}
                    ({f.matched ? bandFor(f.match_score) : 'unmatched'})
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Contestant select */}
          <div>
            <label htmlFor="flag-contestant-select" className="block text-sm text-carbon-soft mb-1">
              {mode === 'batch' ? 'Assign All to Contestant:' : 'Correct Contestant:'}
            </label>
            <select
              id="flag-contestant-select"
              className="w-full bg-paper-dark text-carbon-deep border border-paper-deep rounded-none px-3 py-2 text-sm"
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
              <label htmlFor="flag-user-label" className="block text-sm text-carbon-soft mb-1">
                Note (optional):
              </label>
              <input
                id="flag-user-label"
                type="text"
                className="w-full bg-paper-dark text-carbon-deep border border-paper-deep rounded-none px-3 py-2 text-sm"
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
            className="px-4 py-2 bg-paper-dark text-carbon border border-paper-deep rounded-none text-sm hover:bg-paper-deep"
            onClick={onClose}
          >
            Cancel
          </button>
          <button
            className="px-4 py-2 bg-stamp text-white rounded-none text-sm font-medium hover:bg-stamp disabled:opacity-50 disabled:cursor-not-allowed"
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
