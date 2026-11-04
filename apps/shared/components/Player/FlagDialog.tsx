import { useEffect, useRef, useState } from 'react';
import type { FaceDetection } from '../../types';
import { bandFor } from '../../lib/bands';
import { AdminErrorNotice } from '../AdminErrorNotice';

interface FlagDialogProps {
  mode: 'single' | 'batch';
  face?: FaceDetection | null;
  selectedFaces?: FaceDetection[];
  contestants: Array<{ number: number; name: string; nickname: string }>;
  onSubmit: (contestantId: number, userLabel: string) => void;
  onClose: () => void;
  isSubmitting: boolean;
  /** Submit failure; the dialog stays open so the operator can retry. */
  error?: unknown;
}

export function FlagDialog({
  mode,
  face,
  selectedFaces = [],
  contestants,
  onSubmit,
  onClose,
  isSubmitting,
  error,
}: FlagDialogProps) {
  const [contestantId, setContestantId] = useState<number | null>(null);
  const [userLabel, setUserLabel] = useState('');
  const dialogRef = useRef<HTMLDivElement>(null);
  const contestantSelectRef = useRef<HTMLSelectElement>(null);

  // Opening the dialog lands the caret on the contestant picker: it is the only field
  // the operator came here to fill.
  useEffect(() => {
    contestantSelectRef.current?.focus();
  }, []);

  // The dialog is modal, so Tab stays inside it, and Escape is the Cancel button: it
  // closes only while there is nothing in flight.
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (!isSubmitting) onClose();
        return;
      }
      if (e.key !== 'Tab') return;
      const container = dialogRef.current;
      if (!container) return;
      const focusable = Array.from(
        container.querySelectorAll<HTMLElement>(
          'button, select, input, textarea, a[href], [tabindex]:not([tabindex="-1"])',
        ),
      ).filter((el) => !el.hasAttribute('disabled') && el.getClientRects().length > 0);
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement;
      const inside = active !== null && container.contains(active);
      if (e.shiftKey) {
        if (!inside || active === first) {
          e.preventDefault();
          last.focus();
        }
      } else if (!inside || active === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [isSubmitting, onClose]);

  const handleSubmit = () => {
    if (contestantId === null) return;
    onSubmit(contestantId, userLabel);
  };

  const title = mode === 'batch' ? `Batch Flag Faces (${selectedFaces.length})` : 'Flag Face';
  const submitLabel =
    mode === 'batch'
      ? isSubmitting
        ? 'Flagging...'
        : `Flag ${selectedFaces.length} Faces`
      : isSubmitting
        ? 'Flagging...'
        : 'Flag Face';

  return (
    <div
      className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
      onClick={() => {
        if (!isSubmitting) onClose();
      }}
    >
      <div
        ref={dialogRef}
        className="bg-paper-light border border-paper-deep rounded-none p-6 max-w-md w-full mx-4 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="flag-dialog-title"
      >
        <h3 id="flag-dialog-title" className="text-lg font-semibold text-carbon-deep mb-2">
          {title}
        </h3>
        <p className="text-carbon-soft text-sm mb-4">
          {mode === 'batch'
            ? 'Add all selected faces to the review queue for one human check.'
            : 'Add this face to the review queue for a human check.'}
        </p>

        <div className="space-y-4">
          {/* Show detected face info */}
          {mode === 'single' && face && (
            <div>
              <label className="block text-sm text-carbon-soft mb-1">Detected As:</label>
              <p className="text-carbon-deep">
                {face.matched
                  ? face.contestant_name || face.contestant_nickname || 'Unmatched'
                  : 'Unmatched'}{' '}
                (
                {face.matched && face.match_score != null
                  ? `${face.match_score.toFixed(2)} cosine (${bandFor(face.match_score)} band)`
                  : 'no match score'}
                )
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
                    {f.matched
                      ? f.contestant_name || f.contestant_nickname || 'Unmatched'
                      : 'Unmatched'}{' '}
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
              ref={contestantSelectRef}
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

        {error ? <AdminErrorNotice error={error} label="送出失敗" className="mt-4" /> : null}

        {/* Actions */}
        <div className="flex justify-end gap-3 mt-6">
          <button
            className="px-4 py-2 bg-paper-dark text-carbon border border-paper-deep rounded-none text-sm hover:bg-paper-deep disabled:opacity-45 disabled:cursor-not-allowed"
            onClick={onClose}
            disabled={isSubmitting}
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
