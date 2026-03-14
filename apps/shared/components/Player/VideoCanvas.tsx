import { useRef, useEffect, forwardRef, useImperativeHandle } from 'react';
import type { FaceDetection } from '../../types';
import { useAnnotations } from './useAnnotations';

interface VideoCanvasProps {
  videoSrc: string;
  faces: FaceDetection[];
  showAnnotations: boolean;
  containerRef: React.RefObject<HTMLDivElement | null>;
  onTimeUpdate?: (time: number) => void;
  onLoadedMetadata?: (duration: number) => void;
  onPlay?: () => void;
  onPause?: () => void;
  onEnded?: () => void;
}

export interface VideoCanvasHandle {
  video: HTMLVideoElement | null;
}

export const VideoCanvas = forwardRef<VideoCanvasHandle, VideoCanvasProps>(
  function VideoCanvas(
    { videoSrc, faces, showAnnotations, containerRef, onTimeUpdate, onLoadedMetadata, onPlay, onPause, onEnded },
    ref,
  ) {
    const videoRef = useRef<HTMLVideoElement>(null);
    const canvasRef = useRef<HTMLCanvasElement>(null);

    useImperativeHandle(ref, () => ({
      get video() {
        return videoRef.current;
      },
    }));

    useAnnotations(canvasRef, videoRef, containerRef, faces, showAnnotations);

    // Sync video src changes while preserving position
    const prevSrcRef = useRef(videoSrc);
    useEffect(() => {
      const video = videoRef.current;
      if (!video || videoSrc === prevSrcRef.current) {
        prevSrcRef.current = videoSrc;
        return;
      }
      prevSrcRef.current = videoSrc;
      // src change handled by React re-render; the key prop on <video> or
      // the src attribute change will trigger loadedmetadata
    }, [videoSrc]);

    return (
      <>
        <video
          ref={videoRef}
          src={videoSrc}
          className="w-full h-full object-contain"
          crossOrigin="anonymous"
          onTimeUpdate={() => {
            if (videoRef.current) onTimeUpdate?.(videoRef.current.currentTime);
          }}
          onLoadedMetadata={() => {
            if (videoRef.current) onLoadedMetadata?.(videoRef.current.duration);
          }}
          onPlay={onPlay}
          onPause={onPause}
          onEnded={onEnded}
        />
        <canvas
          ref={canvasRef}
          className="absolute top-0 left-0 w-full h-full pointer-events-none z-[1]"
        />
      </>
    );
  },
);
