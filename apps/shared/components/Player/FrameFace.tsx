import { useEffect, useRef } from 'react';
import { squareCrop } from './faceView';

interface FrameFaceProps {
  video: HTMLVideoElement | null;
  bbox: [number, number, number, number];
  /** Rendered size in CSS pixels. */
  size: number;
  alt: string;
}

/** A detection's face, drawn straight from the video's current frame. */
export function FrameFace({ video, bbox, size, alt }: FrameFaceProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const key = bbox.join(',');

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !ctx || !video) return;
    const draw = () => {
      const crop = squareCrop(bbox, video.videoWidth, video.videoHeight);
      if (!crop) return;
      const pixels = Math.round(size * (window.devicePixelRatio || 1));
      canvas.width = pixels;
      canvas.height = pixels;
      ctx.drawImage(video, crop.x, crop.y, crop.size, crop.size, 0, 0, pixels, pixels);
    };
    draw();
    // The faces arrive before a seek lands: redraw once the frame they belong to is on screen.
    video.addEventListener('seeked', draw);
    return () => video.removeEventListener('seeked', draw);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [video, key, size]);

  return (
    <canvas
      ref={canvasRef}
      role="img"
      aria-label={alt}
      className="shrink-0 rounded bg-tint"
      style={{ width: size, height: size }}
    />
  );
}
