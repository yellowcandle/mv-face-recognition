#!/usr/bin/env node

/**
 * Guard against the silent Tailwind failure we shipped once.
 *
 * Tailwind 4 discovers sources from the Vite root, which is each app. Utilities used only inside
 * `apps/shared` therefore do not exist unless that directory is declared with `@source`. The
 * failure is invisible: the class is simply absent, and the component renders in its default
 * state — a disabled button that looks enabled, a masthead with no gap.
 *
 * The apps build before this runs. These two sentinels are the ones that already bit us; add to
 * the list when another shared-only utility matters.
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const REPO = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const ASSETS = process.argv[2] ? path.resolve(process.argv[2]) : path.join(REPO, 'apps/admin/dist/assets');

const SENTINELS = [
  { css: 'disabled\\:opacity-45:disabled', why: 'Button disabled state (apps/shared/components/Button.tsx)' },
  { css: '.gap-3\\.5', why: 'Masthead title/latin gap (apps/shared/components/Masthead.tsx)' },
];

if (!fs.existsSync(ASSETS)) {
  console.error(`[check-shared-css] no built assets at ${ASSETS} — run the admin build first`);
  process.exit(1);
}

const css = fs
  .readdirSync(ASSETS)
  .filter((file) => file.endsWith('.css'))
  .map((file) => fs.readFileSync(path.join(ASSETS, file), 'utf8'))
  .join('\n');

const missing = SENTINELS.filter((sentinel) => !css.includes(sentinel.css));
if (missing.length > 0) {
  for (const sentinel of missing) {
    console.error(`[check-shared-css] missing ${sentinel.css} — ${sentinel.why}`);
  }
  console.error(
    '[check-shared-css] is `@source \'../../shared\'` still in apps/admin/src/app.css?',
  );
  process.exit(1);
}

console.log(`[check-shared-css] ${SENTINELS.length} shared utilities present`);
