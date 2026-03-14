import { useCallback, useEffect, useRef } from 'react';
import type { FaceDetection } from '../../types';

const COLOR_PALETTE = [
  '#22c55e', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6',
  '#ec4899', '#14b8a6', '#f97316', '#06b6d4', '#84cc16',
];

export interface VideoRenderRect {
  offsetX: number;
  offsetY: number;
  renderW: number;
  renderH: number;
}

export function getVideoRenderRect(
  videoEl: HTMLVideoElement | null,
  containerEl: HTMLElement | null,
): VideoRenderRect {
  if (!videoEl || !containerEl) return { offsetX: 0, offsetY: 0, renderW: 0, renderH: 0 };

  const containerRect = containerEl.getBoundingClientRect();
  const containerW = containerRect.width;
  const containerH = containerRect.height;
  const videoW = videoEl.videoWidth || 1920;
  const videoH = videoEl.videoHeight || 1080;
  const videoAspect = videoW / videoH;
  const containerAspect = containerW / containerH;

  let renderW: number, renderH: number, offsetX = 0, offsetY = 0;

  if (videoAspect > containerAspect) {
    renderW = containerW;
    renderH = containerW / videoAspect;
    offsetY = (containerH - renderH) / 2;
  } else {
    renderH = containerH;
    renderW = containerH * videoAspect;
    offsetX = (containerW - renderW) / 2;
  }

  return { offsetX, offsetY, renderW, renderH };
}

export function useAnnotations(
  canvasRef: React.RefObject<HTMLCanvasElement | null>,
  videoRef: React.RefObject<HTMLVideoElement | null>,
  containerRef: React.RefObject<HTMLDivElement | null>,
  faces: FaceDetection[],
  showAnnotations: boolean,
) {
  const animFrameRef = useRef<number>(0);

  const drawAnnotations = useCallback(() => {
    const canvas = canvasRef.current;
    const video = videoRef.current;
    const container = containerRef.current;
    if (!canvas || !video || !container) return;

    const containerRect = container.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;

    canvas.width = containerRect.width * dpr;
    canvas.height = containerRect.height * dpr;
    canvas.style.width = `${containerRect.width}px`;
    canvas.style.height = `${containerRect.height}px`;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, containerRect.width, containerRect.height);

    if (!showAnnotations || faces.length === 0) return;

    const videoW = video.videoWidth || 1920;
    const videoH = video.videoHeight || 1080;
    const { offsetX, offsetY, renderW, renderH } = getVideoRenderRect(video, container);
    const scaleX = renderW / videoW;
    const scaleY = renderH / videoH;

    const colorMap = new Map<string, string>();

    for (const face of faces) {
      const [x1, y1, x2, y2] = face.bbox || [0, 0, 0, 0];
      if (x2 <= x1 || y2 <= y1) continue;

      const name = face.contestant_name || 'Unknown';
      if (!colorMap.has(name)) {
        colorMap.set(name, COLOR_PALETTE[colorMap.size % COLOR_PALETTE.length]);
      }
      const color = colorMap.get(name)!;
      const confidence = face.confidence ?? 0;

      const sx = offsetX + x1 * scaleX;
      const sy = offsetY + y1 * scaleY;
      const sw = (x2 - x1) * scaleX;
      const sh = (y2 - y1) * scaleY;

      // Bounding box
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.strokeRect(sx, sy, sw, sh);

      // Label
      const label = `${name}  ${(confidence * 100).toFixed(0)}%`;
      ctx.font = 'bold 13px system-ui, sans-serif';
      const textMetrics = ctx.measureText(label);
      const textH = 20;
      const textW = textMetrics.width + 10;
      const labelY = sy - textH - 2;
      const finalLabelY = labelY < offsetY ? sy : labelY;

      ctx.fillStyle = color;
      ctx.globalAlpha = 0.85;
      ctx.fillRect(sx, finalLabelY, textW, textH);
      ctx.globalAlpha = 1.0;

      ctx.fillStyle = '#ffffff';
      ctx.textBaseline = 'middle';
      ctx.fillText(label, sx + 5, finalLabelY + textH / 2);
    }
  }, [canvasRef, videoRef, containerRef, faces, showAnnotations]);

  // Redraw on faces/annotations change
  useEffect(() => {
    drawAnnotations();
  }, [drawAnnotations]);

  // Redraw on window resize
  useEffect(() => {
    const handleResize = () => {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = requestAnimationFrame(drawAnnotations);
    };
    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(animFrameRef.current);
    };
  }, [drawAnnotations]);

  return { drawAnnotations };
}
