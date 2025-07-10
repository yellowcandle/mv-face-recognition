#!/usr/bin/env node

/**
 * Update embedded assets in the Cloudflare Worker from frontend build
 */

const fs = require('fs');
const path = require('path');

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
        console.log(`✅ Added ${relativePath}`);
      } catch (err) {
        console.warn(`⚠️ Could not read ${relativePath} as text:`, err.message);
      }
    }
  }

  return assets;
}

function main() {
  console.log('🔄 Updating worker embedded assets...');

  const buildDir = path.join(__dirname, '../frontend/build');
  const workerDir = path.join(__dirname, '../worker');
  const embeddedAssetsFile = path.join(workerDir, 'embedded-assets.js');

  if (!fs.existsSync(buildDir)) {
    console.error('❌ Frontend build directory not found. Please run "npm run build" in the frontend directory first.');
    process.exit(1);
  }

  const assets = {};

  // Read HTML file
  const indexHtmlPath = path.join(buildDir, 'index.html');
  if (fs.existsSync(indexHtmlPath)) {
    assets['index.html'] = fs.readFileSync(indexHtmlPath, 'utf8');
    console.log('✅ Added index.html');
  }

  // Read favicon
  const faviconPath = path.join(buildDir, 'favicon.ico');
  if (fs.existsSync(faviconPath)) {
    // For favicon, we'll skip it as it's binary and we can serve it separately
    console.log('ℹ️ Skipping favicon.ico (binary file)');
  }

  // Read _app directory (SvelteKit structure)
  const appDir = path.join(buildDir, '_app');
  if (fs.existsSync(appDir)) {
    const appAssets = readDirectoryRecursively(appDir, '_app');
    Object.assign(assets, appAssets);
  }

  // Also check for legacy assets directory (old Vite structure)
  const assetsDir = path.join(buildDir, 'assets');
  if (fs.existsSync(assetsDir)) {
    const legacyAssets = readDirectoryRecursively(assetsDir, 'assets');
    Object.assign(assets, legacyAssets);
  }

  // Generate embedded-assets.js
  const embeddedAssetsContent = `export const EMBEDDED_ASSETS = ${JSON.stringify(assets, null, 2)};`;
  
  fs.writeFileSync(embeddedAssetsFile, embeddedAssetsContent, 'utf8');
  
  console.log('🎉 Embedded assets updated successfully!');
  console.log(`📄 Generated ${Object.keys(assets).length} embedded assets`);
  console.log(`📁 Saved to: ${embeddedAssetsFile}`);
}

if (require.main === module) {
  main();
}

module.exports = { main }; 