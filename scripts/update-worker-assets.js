import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

function createLogger() {
  return {
    info: (msg, data) => console.log(`[INFO] ${msg}`, data ? JSON.stringify(data) : ''),
    debug: (msg, data) => console.log(`[DEBUG] ${msg}`, data ? JSON.stringify(data) : ''),
    warn: (msg, data) => console.warn(`[WARN] ${msg}`, data ? JSON.stringify(data) : ''),
    error: (msg, data) => console.error(`[ERROR] ${msg}`, data ? JSON.stringify(data) : ''),
  };
}

const logger = createLogger();

// Extensions safe to embed as UTF-8 text; everything else is base64-encoded
// and listed in BINARY_ASSETS so the worker knows to decode before serving.
const TEXT_EXTENSIONS = new Set([
  '.html', '.js', '.mjs', '.css', '.json', '.svg', '.txt', '.map',
  '.webmanifest', '.xml',
]);

function readDirectoryRecursively(dir, baseDir = '') {
  const assets = {};
  const binaryAssets = [];
  const items = fs.readdirSync(dir);

  for (const item of items) {
    const itemPath = path.join(dir, item);
    const relativePath = baseDir ? `${baseDir}/${item}` : item;

    if (fs.statSync(itemPath).isDirectory()) {
      const sub = readDirectoryRecursively(itemPath, relativePath);
      Object.assign(assets, sub.assets);
      binaryAssets.push(...sub.binaryAssets);
    } else {
      const ext = path.extname(item).toLowerCase();
      if (TEXT_EXTENSIONS.has(ext)) {
        assets[relativePath] = fs.readFileSync(itemPath, 'utf8');
      } else {
        assets[relativePath] = fs.readFileSync(itemPath).toString('base64');
        binaryAssets.push(relativePath);
      }
      logger.debug('Added asset file', { file: relativePath });
    }
  }

  return { assets, binaryAssets };
}

function main() {
  logger.info('Updating worker embedded assets');

  const buildDir = path.join(__dirname, '../apps/viewer/dist');
  const workerDir = path.join(__dirname, '../worker');
  const embeddedAssetsFile = path.join(workerDir, 'embedded-assets.js');

  if (!fs.existsSync(buildDir)) {
    logger.error('Viewer build directory not found — run `pnpm --filter @mv/viewer build` first', { buildDir });
    process.exit(1);
  }

  if (!fs.existsSync(path.join(buildDir, 'index.html'))) {
    logger.error('Viewer build has no index.html — incomplete build?', { buildDir });
    process.exit(1);
  }

  const { assets, binaryAssets } = readDirectoryRecursively(buildDir, '');

  logger.info('Assets collected from viewer dist/', {
    count: Object.keys(assets).length,
    binaryCount: binaryAssets.length,
    keys: Object.keys(assets).slice(0, 10),
  });

  const embeddedAssetsContent =
    `export const EMBEDDED_ASSETS = ${JSON.stringify(assets, null, 2)};\n\n` +
    `// Paths stored base64-encoded; the worker decodes these before serving.\n` +
    `/** @type {Set<string>} */\n` +
    `export const BINARY_ASSETS = new Set(${JSON.stringify(binaryAssets, null, 2)});\n`;

  fs.writeFileSync(embeddedAssetsFile, embeddedAssetsContent, 'utf8');

  logger.info('Embedded assets updated successfully', {
    assetCount: Object.keys(assets).length,
    outputFile: embeddedAssetsFile,
  });
}

if (process.argv[1] === __filename) {
  main();
}
