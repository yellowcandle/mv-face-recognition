/**
 * The embedded-assets bundle has to fit in the Worker script limit.
 *
 * `worker/embedded-assets.js` ships the built viewer and admin inside the Worker, and the pair has
 * grown to 87% of the 1 MiB script limit (913,959 B on 2026-11-16). Nothing warned when it grew:
 * the next page or asset would have failed at deploy time, on the day someone was shipping
 * something else. This asserts the headroom instead, so the failure lands in `npm test`.
 *
 * If this fails: move the asset out of the bundle (stills and reels already live in R2), or split
 * the admin onto its own Worker. Raising the number without doing one of those just moves the
 * deploy failure back to deploy time.
 *
 * Run: node --test tests/*.test.mjs
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { statSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const BUNDLE = join(HERE, '..', 'embedded-assets.js');

/** The Workers script limit, and the fraction of it this project allows itself. */
const LIMIT = 1024 * 1024;
const BUDGET = 0.95;

test('the embedded-assets bundle stays inside its share of the Worker limit', () => {
  const { size } = statSync(BUNDLE);
  const share = size / LIMIT;
  assert.ok(
    size < LIMIT * BUDGET,
    `embedded-assets.js is ${size} B (${(share * 100).toFixed(1)}% of ${LIMIT}): over the ${(
      BUDGET * 100
    ).toFixed(0)}% budget. Move an asset to R2 or split the admin before adding more.`,
  );
});
