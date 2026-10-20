/**
 * Bands for **match scores** (raw cosine similarity between a detected face and a
 * contestant's reference set — see CONTEXT.md, "Match score").
 *
 * Where these numbers come from: a leave-one-out sweep over the reference cache —
 * 663 reference embeddings across 94 contestants, each reference's maximum cosine
 * against every *other* contestant's references. The seven worst impostor pairs
 * score 0.5846, 0.5846, 0.5014, 0.4616, 0.4616, 0.4509, 0.4509, then a step down to
 * 0.4446. So 7 of 663 pairs (1.06%) reach 0.451 and none reaches 0.585: those are
 * measured false-match boundaries, not a division of an observed distribution. The
 * pipeline's acceptance threshold (0.45) sits just under the medium boundary.
 *
 * These are **provisional**: they move as soon as ground-truth labels exist (ticket
 * 006 labels 30s of test-video-mv2). The pipeline stamps the cutoffs it applied into
 * `recognition_config.band_cutoffs` and marks them provisional; do not tune them
 * against a single video's scores.
 */

/** Measured false-match boundaries for a match score. */
export const BAND_CUTOFFS = { high: 0.585, medium: 0.451 } as const;

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
