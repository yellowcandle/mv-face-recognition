const SIZES = [64, 128, 256, 512];
const DEPLOYED = 'mv.herballemon.dev';

/**
 * Portraits are 512px WebP; pages show them at 28-200px. On the deployed site (the only place
 * `/cdn-cgi/image` exists) ask Cloudflare for ~2x the display width, snapped to a few sizes so the
 * number of billed unique transformations stays small. Elsewhere, or for absolute urls, unchanged.
 */
export function portraitSrc(url: string | null | undefined, displayWidth: number): string | null {
  if (!url) return null;
  if (globalThis.location?.hostname !== DEPLOYED || !url.startsWith('/')) return url;
  const w = SIZES.find((s) => s >= displayWidth * 2) ?? SIZES[SIZES.length - 1];
  return `/cdn-cgi/image/width=${w},format=auto${url}`;
}
