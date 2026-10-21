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
    <div className="flex items-center gap-3 flex-wrap bg-paper-light/80 border border-paper-dark rounded-none px-4 py-2 text-sm">
      <button
        className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
          showAnnotations
            ? 'bg-stamp/20 text-stamp border border-stamp/40'
            : 'bg-paper-dark text-carbon-soft border border-paper-deep hover:text-carbon-deep'
        }`}
        onClick={onToggleAnnotations}
        title={showAnnotations ? 'Hide face annotations' : 'Show face annotations'}
      >
        {showAnnotations ? 'Boxes ON' : 'Boxes OFF'}
      </button>

      <span className="text-carbon-soft">
        Faces: <span className="text-carbon-deep font-medium">{faceCount}</span>
        {faceCount > 0 && (
          <span className="text-ledger">
            {' ('}
            <span className="text-carbon">{recognizedCount}</span> recognized,{' '}
            <span className="text-carbon">{faceCount - recognizedCount}</span> unmatched{')'}
          </span>
        )}
      </span>

      <span className="text-carbon-soft">
        Frame: <span className="text-carbon-deep font-mono">{frameNumber}</span>
      </span>

      {faceCount > 0 &&
        canFlag &&
        (batchMode ? (
          <span className="text-stamp font-medium">Selected: {selectedCount}</span>
        ) : (
          <span className="text-ledger text-xs italic">Click a face to flag it</span>
        ))}
    </div>
  );
}
