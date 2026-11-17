/**
 * The deployed Worker script has to fit in Cloudflare's limit.
 *
 * The limit is 64 MiB uncompressed, on both the Free and Paid plans, and Cloudflare applies no
 * compressed limit (developers.cloudflare.com/workers/platform/limits, checked 2026-11-17).
 * An earlier version of this test asserted 1 MiB against `embedded-assets.js` — an intermediate
 * file, not the upload. It passed while the real bundle was already 1,040,923 B, so it could not
 * have caught the growth it described.
 *
 * This measures the artifact Cloudflare actually receives: `wrangler deploy --dry-run` reports
 * `Total Upload`. It stays a deploy-time guard, not a byte-for-byte budget: at ~1 MiB the Worker
 * sits at 1.6% of the limit, so the assertion only fires when something is genuinely wrong.
 *
 * If this fails: move an asset out of the bundle (stills and reels already live in R2) or split
 * the admin onto its own Worker.
 *
 * Run: node --test tests/*.test.mjs
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const WORKER = join(HERE, '..');
const WRANGLER = join(WORKER, 'node_modules', 'wrangler', 'bin', 'wrangler.js');

/** Cloudflare's uncompressed script limit, and the fraction of it this project allows itself. */
const LIMIT = 64 * 1024 * 1024;
const BUDGET = 0.95;

test('the deployed Worker bundle stays inside the platform script limit', () => {
  const outdir = mkdtempSync(join(tmpdir(), 'worker-bundle-'));
  try {
    const stdout = execFileSync(
      process.execPath,
      [WRANGLER, 'deploy', '--dry-run', '--outdir', outdir],
      { cwd: WORKER, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] },
    );
    const reported = stdout.match(/Total Upload: ([\d.]+) KiB/);
    assert.ok(reported, 'wrangler did not report an upload size');

    const size = Math.round(Number(reported[1]) * 1024);
    const share = (size / LIMIT) * 100;
    assert.ok(
      size < LIMIT * BUDGET,
      `the Worker uploads ${size} B (${share.toFixed(1)}% of ${LIMIT}): over the ${(
        BUDGET * 100
      ).toFixed(0)}% budget. Move an asset to R2 or split the admin before adding more.`,
    );
  } finally {
    rmSync(outdir, { recursive: true, force: true });
  }
});
