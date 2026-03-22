import type { FaceDetection } from '../../types';
import type { VideoRenderRect } from './useAnnotations';

interface FaceOverlayProps {
  faces: FaceDetection[];
  onFaceClick: (face: FaceDetection) => void;
  selectedFace: FaceDetection | null;
  batchMode: boolean;
  selectedFaces: Set<FaceDetection>;
  getVideoRenderRect: () => VideoRenderRect;
  videoWidth: number;
  videoHeight: number;
}

export function FaceOverlay({
  faces,
  onFaceClick,
  selectedFace,
  batchMode,
  selectedFaces,
  getVideoRenderRect: getRenderRect,
  videoWidth,
  videoHeight,
}: FaceOverlayProps) {
  const getBboxStyle = (bbox: [number, number, number, number]): React.CSSProperties => {
    if (!bbox || bbox.length < 4) return { display: 'none' };

    const [x1, y1, x2, y2] = bbox;
    const { offsetX, offsetY, renderW, renderH } = getRenderRect();
    const scaleX = renderW / (videoWidth || 1920);
    const scaleY = renderH / (videoHeight || 1080);

    return {
      position: 'absolute',
      left: `${offsetX + x1 * scaleX}px`,
      top: `${offsetY + y1 * scaleY}px`,
      width: `${(x2 - x1) * scaleX}px`,
      height: `${(y2 - y1) * scaleY}px`,
    };
  };

  return (
    <div className="absolute top-0 left-0 w-full h-full pointer-events-none z-[2]">
      {faces.map((face, i) => {
        const isSelected = selectedFace === face;
        const isBatchSelected = batchMode && selectedFaces.has(face);

        return (
          <button
            key={i}
            className={`
              pointer-events-auto cursor-pointer p-0 rounded-sm
              border-2 transition-all duration-200
              ${isSelected
                ? 'border-amber-500 bg-amber-500/20'
                : isBatchSelected
                  ? 'border-orange-500 bg-orange-500/20'
                  : 'border-green-500/60 bg-green-500/10 hover:border-blue-500 hover:bg-blue-500/20'}
            `}
            style={getBboxStyle(face.bbox)}
            onClick={() => onFaceClick(face)}
            title={batchMode ? 'Click to select/deselect' : 'Click to flag this face'}
          >
            {batchMode && isBatchSelected && (
              <span className="absolute top-0.5 right-0.5 text-white text-xs bg-orange-500 rounded-full w-4 h-4 flex items-center justify-center">
                &#10003;
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
