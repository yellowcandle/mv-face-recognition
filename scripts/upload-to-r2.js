#!/usr/bin/env node

/**
 * Upload the published video encodes to Cloudflare R2.
 *
 * The settled layout (wayfinder ticket 007) is `processed_videos/<stem>_1080p.mp4`
 * and `_720p.mp4` inside the `mv-face-recognition-videos` bucket — the Worker serves
 * whatever key `stream_url` names, and those two are the only encodes the publish
 * step may reference. `_annotated.mp4` is never published.
 *
 * `scripts/package.json` declares `"type": "module"`, so this file is ESM.
 * Pass --dry-run to print the objects without touching R2.
 */

import fs from 'fs';
import path from 'path';
import { execSync } from 'child_process';
import { fileURLToPath } from 'url';

const BUCKET = 'mv-face-recognition-videos';
const PREFIX = 'processed_videos';
const VARIANTS = ['_1080p.mp4', '_720p.mp4'];
const REPO = path.dirname(path.dirname(fileURLToPath(import.meta.url)));

function main() {
  const dryRun = process.argv.includes('--dry-run');
  console.log('🎥 Uploading published encodes to Cloudflare R2...');

  const videosDir = path.join(REPO, 'local_output', 'processed_videos');
  if (!fs.existsSync(videosDir)) {
    console.error(`❌ ${videosDir} not found — run the pipeline first.`);
    process.exit(1);
  }

  const files = fs
    .readdirSync(videosDir)
    .filter((f) => VARIANTS.some((suffix) => f.endsWith(suffix)));

  if (files.length === 0) {
    console.error(`❌ No ${VARIANTS.join(' / ')} files in ${videosDir}.`);
    process.exit(1);
  }

  console.log(`📹 Found ${files.length} encodes to upload...`);

  for (const file of files) {
    const filePath = path.join(videosDir, file);
    const key = `${BUCKET}/${PREFIX}/${file}`;
    const sizeMB = (fs.statSync(filePath).size / 1024 / 1024).toFixed(1);
    console.log(`⬆️  ${key} (${sizeMB} MB)`);
    if (dryRun) continue;
    try {
      execSync(`wrangler r2 object put "${key}" --file="${filePath}" --remote`, {
        stdio: 'pipe',
      });
      console.log(`✅ Uploaded ${file}`);
    } catch (error) {
      console.error(`❌ Failed to upload ${file}:`, error.message);
      process.exitCode = 1;
    }
  }

  console.log(dryRun ? 'Dry run: nothing written.' : '🎉 Video upload completed.');
}

main();
