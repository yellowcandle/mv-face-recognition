import type { FaceDetection } from '../../types';
import { bandFor } from '../../lib/bands';
import type { VideoRenderRect } from './useAnnotations';

interface FaceOverlayProps {
  faces: FaceDetection[];
  onFaceClick: (face: FaceDetection) => void;
  selectedFace: FaceDetection | null;
  batchMode: boolean;
  selectedFaces: Set<FaceDetection>;
  /** Flagging is an admin act; in the viewer a face is not a button. */
  canFlag: boolean;
  getVideoRenderRect: () => VideoRenderRect;
}

export function FaceOverlay({
  faces,
  onFaceClick,
  selectedFace,
  batchMode,
  selectedFaces,
  canFlag,
  getVideoRenderRect: getRenderRect,
}: FaceOverlayProps) {
  // Stored boxes are frame fractions: projecting one is `fraction × rendered size`,
  // with no width/height argument in between.
  const getBboxStyle = (bbox: [number, number, number, number]): React.CSSProperties => {
    if (!bbox || bbox.length < 4) return { display: 'none' };

    const [x1, y1, x2, y2] = bbox;
    const { offsetX, offsetY, renderW, renderH } = getRenderRect();

    return {
      position: 'absolute',
      left: `${offsetX + x1 * renderW}px`,
      top: `${offsetY + y1 * renderH}px`,
      width: `${(x2 - x1) * renderW}px`,
      height: `${(y2 - y1) * renderH}px`,
    };
  };

  return (
    <div className="absolute top-0 left-0 w-full h-full pointer-events-none z-[2]">
      {faces.map((face, i) => {
        const isSelected = selectedFace === face;
        const isBatchSelected = batchMode && selectedFaces.has(face);
        // The band is the headline; the raw cosine goes in the tooltip, never as a
        // percentage — and an unmatched detection has no contestant and no cosine, only
        // the detector's own score.
        const name = face.matched
          ? face.contestant_name || face.contestant_nickname || 'Unmatched'
          : 'Unmatched';
        const score =
          face.matched && face.match_score != null
            ? `${face.match_score.toFixed(2)} cosine (${bandFor(face.match_score)} band)`
            : `unmatched · detection score ${face.det_score.toFixed(2)}`;
        const action = !canFlag
          ? null
          : batchMode
            ? 'click to select/deselect'
            : 'click to flag this face';

        return (
          <button
            key={i}
            className={`
              pointer-events-auto cursor-pointer p-0 rounded-none
              border-2 transition-all duration-200
              ${isSelected
                ? 'border-stamp bg-stamp/20'
                : isBatchSelected
                  ? 'border-stamp bg-stamp/20'
                  : face.matched
                    ? 'border-carbon/60 bg-carbon/10 hover:border-carbon hover:bg-carbon/20'
                    : 'border-ledger/60 bg-ledger/10 hover:border-carbon hover:bg-carbon/20'}
            `}
            style={getBboxStyle(face.bbox)}
            onClick={() => onFaceClick(face)}
            title={action ? `${name} — ${score} — ${action}` : `${name} — ${score}`}
          >
            {batchMode && isBatchSelected && (
              <span className="absolute top-0.5 right-0.5 text-white text-xs bg-stamp rounded-full w-4 h-4 flex items-center justify-center">
                &#10003;
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
