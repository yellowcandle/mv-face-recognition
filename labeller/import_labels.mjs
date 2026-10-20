#!/usr/bin/env node
/**
 * One-shot: print the `wrangler kv key put` commands that load a local labels/v1 file into the
 * labelling Worker's LABELS namespace. It PRINTS; it runs nothing and never writes the input.
 *
 *   node import_labels.mjs [path/to/<video_id>_labels.json] > load.sh   # review, then run from labeller/
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const HERE = dirname(fileURLToPath(import.meta.url));
const path = process.argv[2] ?? join(HERE, '..', 'local_output', 'labels', 'test-video-mv2_labels.json');
const file = JSON.parse(readFileSync(path, 'utf8'));

if (file.schema !== 'labels/v1') throw new Error(`Expected schema labels/v1, got ${file.schema}`);
if (!file.video_id || !file.labelled_at || !file.source?.processing_date) {
  throw new Error('File lacks video_id, labelled_at or source.processing_date');
}

const sh = (s) => `'${String(s).replace(/'/g, `'\\''`)}'`;

console.log(`# ${file.labels.length} labels for ${file.video_id} from ${path}`);
for (const l of file.labels) {
  if (!Number.isInteger(l.frame_number) || !Number.isInteger(l.detection_index)) {
    throw new Error(`Bad label ${JSON.stringify(l)}`);
  }
  const value = {
    verdict: l.verdict,
    ...(l.contestant_id ? { contestant_id: String(l.contestant_id) } : {}),
    labeller: 'import',
    labelled_at: file.labelled_at, // labels/v1 stamps the file, not each label
    source_processing_date: file.source.processing_date,
  };
  const key = `label:${file.video_id}:${l.frame_number}:${l.detection_index}`;
  console.log(`npx wrangler kv key put --binding=LABELS --remote ${sh(key)} ${sh(JSON.stringify(value))}`);
}
