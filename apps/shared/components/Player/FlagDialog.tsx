import { useEffect, useRef, useState } from 'react';
import type { FaceDetection } from '../../types';
import { bandFor } from '../../lib/bands';
import { AdminErrorNotice } from '../AdminErrorNotice';
import { Button } from '../Button';
import { Stamp } from '../Stamp';
import { FrameFace } from './FrameFace';
import { faceName } from './faceView';

interface FlagDialogProps {
  mode: 'single' | 'batch';
  face?: FaceDetection | null;
  selectedFaces?: FaceDetection[];
  contestants: Array<{ number: number; name: string; nickname: string }>;
  /** The video element, to draw the detected face from. */
  video?: HTMLVideoElement | null;
  /** Where this frame sits, e.g. `00:51 · 首部曲`. */
  where?: string;
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
  video = null,
  where,
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

  const batch = mode === 'batch';
  const title = batch ? `批次標記人臉（${selectedFaces.length}）` : '標記人臉';
  const submitLabel = isSubmitting
    ? '標記中…'
    : batch
      ? `標記 ${selectedFaces.length} 張臉`
      : '標記此臉';

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-carbon-deep/47"
      onClick={() => {
        if (!isSubmitting) onClose();
      }}
    >
      <div
        ref={dialogRef}
        className="mx-4 flex w-full max-w-[448px] flex-col gap-5 rounded-md border border-carbon-deep/33 bg-ground p-6"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="flag-dialog-title"
      >
        <div className="flex flex-col gap-1">
          <h3 id="flag-dialog-title" className="font-kai text-[18px] font-normal text-carbon-deep">
            {title}
          </h3>
          <p className="font-kai text-[14px] text-carbon-soft">
            {batch
              ? '把所選的臉全部指定給同一位參賽者，送入待核，由人覆核。'
              : '把這張偵測到的臉指定給參賽者，送入待核，由人覆核。'}
          </p>
        </div>

        {!batch && face && (
          <div className="flex items-center gap-3 border-b border-carbon-deep/13 pb-5">
            <FrameFace video={video} bbox={face.bbox} size={64} alt={faceName(face)} />
            <div className="flex min-w-0 flex-1 flex-col gap-1">
              <span className="font-kai text-[12px] text-ink-muted">偵測為</span>
              <span className="truncate font-kai text-[15px] text-carbon-deep">
                {faceName(face)}
              </span>
              {where ? (
                <span className="truncate font-mono text-[12px] text-ink-muted">{where}</span>
              ) : null}
            </div>
            {face.matched && face.match_score != null ? (
              <div className="flex items-center gap-2">
                <span className="font-mono text-[14px] tabular-nums text-carbon">
                  {face.match_score.toFixed(3)}
                </span>
                <Stamp band={bandFor(face.match_score)} />
              </div>
            ) : (
              <span className="font-mono text-[12px] tabular-nums text-ink-muted">
                偵測分 {face.det_score.toFixed(2)}
              </span>
            )}
          </div>
        )}

        {batch && selectedFaces.length > 0 && (
          <div className="flex flex-wrap gap-3 border-b border-carbon-deep/13 pb-5">
            {selectedFaces.map((f, i) => (
              <div key={i} className="flex items-center gap-2">
                <FrameFace video={video} bbox={f.bbox} size={32} alt={faceName(f)} />
                <span className="font-kai text-[13px] text-carbon-deep">{faceName(f)}</span>
              </div>
            ))}
          </div>
        )}

        <div className="flex flex-col gap-2">
          <label htmlFor="flag-contestant-select" className="font-kai text-[13px] text-carbon-soft">
            {batch ? '全部指定給' : '正確參賽者'}
          </label>
          <select
            id="flag-contestant-select"
            ref={contestantSelectRef}
            className="field field-select h-10 w-full text-[14px] text-carbon-deep"
            value={contestantId ?? ''}
            onChange={(e) => setContestantId(e.target.value ? parseInt(e.target.value, 10) : null)}
          >
            <option value="">請選擇參賽者</option>
            {contestants.map((c) => (
              <option key={c.number} value={c.number}>
                #{c.number} · {c.nickname}（{c.name}）
              </option>
            ))}
          </select>
        </div>

        {!batch && (
          <div className="flex flex-col gap-2">
            <label htmlFor="flag-user-label" className="font-kai text-[13px] text-carbon-soft">
              備註（選填）
            </label>
            <input
              id="flag-user-label"
              type="text"
              className="field h-10 w-full text-[14px] text-carbon-deep placeholder:text-ink-muted"
              placeholder="例如：正面清晰"
              value={userLabel}
              onChange={(e) => setUserLabel(e.target.value)}
            />
          </div>
        )}

        {error ? <AdminErrorNotice error={error} label="送出失敗" /> : null}

        <div className="flex items-center justify-end gap-2">
          <Button onClick={onClose} disabled={isSubmitting}>
            取消
          </Button>
          <Button
            variant="primary"
            onClick={handleSubmit}
            disabled={contestantId === null || isSubmitting}
          >
            {submitLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
