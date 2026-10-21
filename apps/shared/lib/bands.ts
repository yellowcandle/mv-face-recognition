/**
 * Bands for **match scores** (raw cosine similarity between a detected face and a
 * contestant's reference set — see CONTEXT.md, "Match score").
 *
 * Where these numbers come from: a leave-one-out sweep over the curated reference
 * cache — 831 reference embeddings across 96 contestants (IG + historical photos),
 * each reference's maximum cosine against every *other* contestant's references.
 * The impostor p99 is 0.412 and the maximum 0.445; genuine pairs have p05 0.377.
 * Those are measured false-match boundaries, not a division of an observed
 * distribution. The pipeline's acceptance threshold (0.412) sits on the medium
 * boundary.
 *
 * These are **provisional**: they move as soon as ground-truth labels exist (ticket
 * 006 labels 30s of test-video-mv2). The pipeline stamps the cutoffs it applied into
 * `recognition_config.band_cutoffs` and marks them provisional; do not tune them
 * against a single video's scores.
 */

/** Measured false-match boundaries for a match score. */
export const BAND_CUTOFFS = { high: 0.445, medium: 0.412 } as const;

/**
 * A coarse quality tier for a recognition. `low` also covers "no candidate worth
 * calling": an unmatched detection carries no match score, so there is nothing to
 * compare against a cutoff.
 */
export type Band = 'high' | 'medium' | 'low';

/**
 * Classify a match score. Pass the raw cosine exactly as stored/served — never a
 * rescaled or percentage form. `null`/absent (an unmatched detection) is `low`.
 */
export function bandFor(matchScore: number | null | undefined): Band {
  if (matchScore == null) return 'low';
  if (matchScore >= BAND_CUTOFFS.high) return 'high';
  if (matchScore >= BAND_CUTOFFS.medium) return 'medium';
  return 'low';
}

/**
 * How a band is stamped: the word on the slip and its ink (text + border colour).
 * The single mapping — every surface that shows a band reads it from here.
 */
export const BAND_STAMP: Record<Band, { word: string; ink: string }> = {
  high: { word: '清楚', ink: 'text-carbon border-carbon' },
  medium: { word: '尚可', ink: 'text-stamp border-stamp' },
  low: { word: '存疑', ink: 'text-ledger border-ledger' },
};
