import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

function logger(prefix = 'update-worker-assets') {
  return {
    info: (msg, data) => console.log(`[INFO] ${msg}`, data ? JSON.stringify(data) : ''),
    debug: (msg, data) => console.log(`[DEBUG] ${msg}`, data ? JSON.stringify(data) : ''),
    warn: (msg, data) => console.warn(`[WARN] ${msg}`, data ? JSON.stringify(data) : ''),
    error: (msg, data) => console.error(`[ERROR] ${msg}`, data ? JSON.stringify(data) : ''),
  };
}

const { info, debug, warn, error } = logger();

function readDirectoryRecursively(dir, baseDir = '') {
  const assets = {};
  const items = fs.readdirSync(dir);

  for (const item of items) {
    const itemPath = path.join(dir, item);
    const relativePath = baseDir ? `${baseDir}/${item}` : item;
    
    if (fs.statSync(itemPath).isDirectory()) {
      // Recursively read subdirectories
      const subAssets = readDirectoryRecursively(itemPath, relativePath);
      Object.assign(assets, subAssets);
    } else {
      // Read file content
      try {
        const content = fs.readFileSync(itemPath, 'utf8');
        assets[relativePath] = content;
        logger.debug(`Added asset file`, { file: relativePath });
      } catch (err) {
        logger.warn(`Could not read asset file as text`, { file: relativePath, error: err.message });
      }
    }
  }

  return assets;
}

function main() {
  logger.info('Updating worker embedded assets');

  const buildDir = path.join(__dirname, '../mvp-processor/build');
  const workerDir = path.join(__dirname, '../worker');
  const embeddedAssetsFile = path.join(workerDir, 'embedded-assets.js');

  if (!fs.existsSync(buildDir)) {
    logger.error('Frontend build directory not found', { buildDir });
    process.exit(1);
  }

  const assets = readDirectoryRecursively(buildDir, '');

  // Skip favicon if present
  delete assets['favicon.ico'];

  logger.info('Assets collected from entire build/', { count: Object.keys(assets).length, keys: Object.keys(assets).slice(0, 10) });

  // Generate embedded-assets.js
  const embeddedAssetsContent = `export const EMBEDDED_ASSETS = ${JSON.stringify(assets, null, 2)};`;
  
  fs.writeFileSync(embeddedAssetsFile, embeddedAssetsContent, 'utf8');

  logger.info('Embedded assets updated successfully', {
    assetCount: Object.keys(assets).length,
    outputFile: embeddedAssetsFile
  });
}

if (process.argv[1] === import.meta.url) {
  main();
} 