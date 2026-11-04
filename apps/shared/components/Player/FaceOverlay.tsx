import { Check } from 'lucide-react';
import type { FaceDetection } from '../../types';
import { BAND_STAMP, bandFor } from '../../lib/bands';
import { faceName } from './faceView';
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

/** The clickable layer over each face. The canvas underneath draws the box and its label. */
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
    <div className="pointer-events-none absolute left-0 top-0 z-[2] h-full w-full">
      {faces.map((face, i) => {
        const isSelected = selectedFace === face;
        const isBatchSelected = batchMode && selectedFaces.has(face);
        // The band is the headline; the raw cosine goes in the tooltip, never as a
        // percentage — and an unmatched detection has no contestant and no cosine, only
        // the detector's own score.
        const name = faceName(face);
        const score =
          face.matched && face.match_score != null
            ? `${face.match_score.toFixed(2)} ${BAND_STAMP[bandFor(face.match_score)].word}`
            : `未認出 · 偵測分 ${face.det_score.toFixed(2)}`;
        const action = !canFlag ? null : batchMode ? '點選以選取或取消' : '點選以標記這張臉';

        return (
          <button
            key={i}
            className={`pointer-events-auto cursor-pointer p-0 transition-colors ${
              isSelected || isBatchSelected ? 'bg-stamp/20' : 'hover:bg-paper-light/15'
            }`}
            style={getBboxStyle(face.bbox)}
            onClick={() => onFaceClick(face)}
            title={action ? `${name} — ${score} — ${action}` : `${name} — ${score}`}
            aria-label={action ? `${name}，${action}` : name}
            aria-pressed={batchMode ? isBatchSelected : undefined}
          >
            {isBatchSelected && (
              <span className="absolute right-0.5 top-0.5 flex size-4 items-center justify-center rounded-xs bg-stamp text-paper-light">
                <Check size={12} aria-hidden />
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
