import { Button } from '../Button';

interface DetectionBarProps {
  faceCount: number;
  /** Of `faceCount`, how many were matched to a contestant; the rest are unmatched detections. */
  recognizedCount: number;
  frameNumber: number;
  showAnnotations: boolean;
  batchMode: boolean;
  selectedCount: number;
  /** Flagging is an admin act — the viewer must not be invited to click a face. */
  canFlag: boolean;
  onToggleAnnotations: () => void;
}

export function DetectionBar({
  faceCount,
  recognizedCount,
  frameNumber,
  showAnnotations,
  batchMode,
  selectedCount,
  canFlag,
  onToggleAnnotations,
}: DetectionBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-4 font-kai text-[13px]">
      <Button
        size="sm"
        className={showAnnotations ? 'bg-tint font-bold text-carbon-deep' : ''}
        aria-pressed={showAnnotations}
        onClick={onToggleAnnotations}
        title={showAnnotations ? '隱藏人臉方框' : '顯示人臉方框'}
      >
        {showAnnotations ? '方框 開' : '方框 關'}
      </Button>

      <span className="flex items-center gap-2 text-carbon-soft">
        人臉
        <span className="font-mono tabular-nums text-carbon-deep">{faceCount}</span>
        {faceCount > 0 && (
          <span className="text-ink-muted">
            認出 {recognizedCount} · 未認出 {faceCount - recognizedCount}
          </span>
        )}
      </span>

      <span className="flex items-center gap-2 text-carbon-soft">
        畫格
        <span className="font-mono tabular-nums text-carbon-deep">{frameNumber}</span>
      </span>

      {faceCount > 0 &&
        canFlag &&
        (batchMode ? (
          <span className="font-bold text-stamp">已選 {selectedCount}</span>
        ) : (
          <span className="text-[12px] text-ink-muted">點選人臉即可標記</span>
        ))}
    </div>
  );
}
