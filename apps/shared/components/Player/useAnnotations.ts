import { useCallback, useEffect, useRef } from 'react';
import type { FaceDetection } from '../../types';
import { BAND_STAMP, bandFor } from '../../lib/bands';
import { faceName } from './faceView';

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

  let renderW: number,
    renderH: number,
    offsetX = 0,
    offsetY = 0;

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
  isSelected?: (face: FaceDetection) => boolean,
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

    // Projection is exactly fractions × the rendered element's size. The video's own
    // videoWidth/videoHeight are not a scale factor for a stored box.
    const { offsetX, offsetY, renderW, renderH } = getVideoRenderRect(video, container);

    // Canvas cannot read Tailwind classes: take the same tokens from the stylesheet.
    const css = getComputedStyle(document.documentElement);
    const token = (name: string) => css.getPropertyValue(name).trim();
    const paper = token('--color-paper-light');
    const ink = token('--color-carbon-deep');
    const stamp = token('--color-stamp');
    const TEXT_H = 20;

    ctx.font = `12px ${token('--font-kai')}`;
    ctx.textBaseline = 'middle';

    for (const face of faces) {
      const [x1, y1, x2, y2] = face.bbox || [0, 0, 0, 0];
      if (x2 <= x1 || y2 <= y1) continue;

      const sx = offsetX + x1 * renderW;
      const sy = offsetY + y1 * renderH;
      const sw = (x2 - x1) * renderW;
      const sh = (y2 - y1) * renderH;
      const selected = isSelected?.(face) ?? false;

      ctx.strokeStyle = selected ? stamp : paper;
      ctx.lineWidth = 2;
      ctx.strokeRect(sx, sy, sw, sh);

      // Band, not a percentage: 0.51 is a cosine, and "51%" would read as certainty.
      // The raw cosine lives in the overlay button's tooltip.
      const name = faceName(face);
      const band = face.matched ? BAND_STAMP[bandFor(face.match_score)].word : '';
      const nameW = ctx.measureText(name).width;
      const textW = nameW + (band ? 4 + ctx.measureText(band).width : 0) + 8;
      // The label hangs under the box; at the foot of the frame it moves above.
      const below = sy + sh + 2;
      const labelY = below + TEXT_H > offsetY + renderH ? sy - TEXT_H - 2 : below;

      ctx.fillStyle = selected ? stamp : ink;
      ctx.fillRect(sx, labelY, textW, TEXT_H);

      ctx.fillStyle = paper;
      ctx.fillText(name, sx + 4, labelY + TEXT_H / 2);
      if (band) {
        ctx.globalAlpha = 0.8;
        ctx.fillText(band, sx + 8 + nameW, labelY + TEXT_H / 2);
        ctx.globalAlpha = 1;
      }
    }
  }, [canvasRef, videoRef, containerRef, faces, showAnnotations, isSelected]);

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
