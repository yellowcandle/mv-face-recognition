interface DetectionBarProps {
  faceCount: number;
  frameNumber: number;
  showOriginalVideo: boolean;
  showAnnotations: boolean;
  batchMode: boolean;
  selectedCount: number;
  onToggleSource: () => void;
  onToggleAnnotations: () => void;
}

export function DetectionBar({
  faceCount,
  frameNumber,
  showOriginalVideo,
  showAnnotations,
  batchMode,
  selectedCount,
  onToggleSource,
  onToggleAnnotations,
}: DetectionBarProps) {
  return (
    <div className="flex items-center gap-3 flex-wrap bg-slate-900/80 border border-slate-800 rounded-lg px-4 py-2 text-sm">
      <button
        className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
          !showOriginalVideo
            ? 'bg-orange-500/20 text-orange-400 border border-orange-500/40'
            : 'bg-slate-800 text-slate-400 border border-slate-700 hover:text-slate-200'
        }`}
        onClick={onToggleSource}
        title={showOriginalVideo ? 'Switch to Annotated Video' : 'Switch to Original Video'}
      >
        {showOriginalVideo ? 'Original' : 'Annotated'}
      </button>

      <button
        className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
          showAnnotations
            ? 'bg-orange-500/20 text-orange-400 border border-orange-500/40'
            : 'bg-slate-800 text-slate-400 border border-slate-700 hover:text-slate-200'
        }`}
        onClick={onToggleAnnotations}
        title={showAnnotations ? 'Hide face annotations' : 'Show face annotations'}
      >
        {showAnnotations ? 'Boxes ON' : 'Boxes OFF'}
      </button>

      <span className="text-slate-400">
        Faces: <span className="text-slate-200 font-medium">{faceCount}</span>
      </span>

      <span className="text-slate-400">
        Frame: <span className="text-slate-200 font-mono">{frameNumber}</span>
      </span>

      {faceCount > 0 && (
        batchMode ? (
          <span className="text-orange-400 font-medium">
            Selected: {selectedCount}
          </span>
        ) : (
          <span className="text-slate-500 text-xs italic">Click a face to flag it</span>
        )
      )}
    </div>
  );
}
