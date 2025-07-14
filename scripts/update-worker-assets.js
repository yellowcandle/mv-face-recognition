#!/usr/bin/env node

/**
 * SvelteKit Asset Embedding Script for Cloudflare Workers
 * 
 * This script reads the SvelteKit build output and embeds all static assets
 * into the Cloudflare Worker for edge deployment.
 */

const fs = require('fs');
const path = require('path');

// Configuration
const FRONTEND_BUILD_DIR = path.join(__dirname, '..', 'frontend', 'build');
const WORKER_FILE = path.join(__dirname, '..', 'worker', 'index.js');
const BACKUP_FILE = path.join(__dirname, '..', 'worker', 'index.js.backup');

console.log('🚀 Starting SvelteKit asset embedding for Cloudflare Workers...');

// Check if build directory exists
if (!fs.existsSync(FRONTEND_BUILD_DIR)) {
  console.error('❌ Frontend build directory not found:', FRONTEND_BUILD_DIR);
  console.error('   Run "cd frontend && npm run build" first');
  process.exit(1);
}

// Check if worker file exists
if (!fs.existsSync(WORKER_FILE)) {
  console.error('❌ Worker file not found:', WORKER_FILE);
  process.exit(1);
}

/**
 * Recursively read all files in a directory
 */
function readDirectoryRecursively(dir, basePath = '') {
  const assets = {};
  const items = fs.readdirSync(dir);
  
  for (const item of items) {
    const fullPath = path.join(dir, item);
    const relativePath = basePath ? `${basePath}/${item}` : item;
    
    if (fs.statSync(fullPath).isDirectory()) {
      // Recursively process subdirectories
      Object.assign(assets, readDirectoryRecursively(fullPath, relativePath));
    } else {
      // Read file content
      try {
        const content = fs.readFileSync(fullPath, 'utf8');
        assets[relativePath] = {
          content: content,
          size: Buffer.byteLength(content, 'utf8')
        };
      } catch (error) {
        console.warn(`⚠️  Could not read file ${relativePath}:`, error.message);
      }
    }
  }
  
  return assets;
}

/**
 * Generate JavaScript object string from assets
 */
function generateAssetsObject(assets) {
  const entries = [];
  
  for (const [path, asset] of Object.entries(assets)) {
    // Escape the content for JavaScript string
    const escapedContent = asset.content
      .replace(/\\/g, '\\\\')
      .replace(/'/g, "\\'")
      .replace(/\n/g, '\\n')
      .replace(/\r/g, '\\r')
      .replace(/\t/g, '\\t');
    
    entries.push(`  '${path}': {
    content: '${escapedContent}',
    size: ${asset.size}
  }`);
  }
  
  return `{\n${entries.join(',\n')}\n}`;
}

try {
  // Create backup of original worker file
  console.log('📋 Creating backup of worker file...');
  fs.copyFileSync(WORKER_FILE, BACKUP_FILE);
  
  // Read all assets from SvelteKit build
  console.log('📂 Reading SvelteKit build assets...');
  const assets = readDirectoryRecursively(FRONTEND_BUILD_DIR);
  
  console.log(`📊 Found ${Object.keys(assets).length} assets:`);
  
  // Display asset summary
  const assetsByType = {};
  let totalSize = 0;
  
  for (const [path, asset] of Object.entries(assets)) {
    const ext = path.split('.').pop() || 'unknown';
    assetsByType[ext] = (assetsByType[ext] || 0) + 1;
    totalSize += asset.size;
    
    console.log(`   📄 ${path} (${(asset.size / 1024).toFixed(1)}KB)`);
  }
  
  console.log('\n📈 Asset Summary:');
  for (const [type, count] of Object.entries(assetsByType)) {
    console.log(`   ${type}: ${count} files`);
  }
  console.log(`   Total size: ${(totalSize / 1024).toFixed(1)}KB`);
  
  // Read worker file
  console.log('\n🔧 Updating worker file...');
  let workerContent = fs.readFileSync(WORKER_FILE, 'utf8');
  
  // Generate assets object
  const assetsObjectString = generateAssetsObject(assets);
  
  // Replace the STATIC_ASSETS object in the worker
  const assetsRegex = /const STATIC_ASSETS = \{[^}]*\};/s;
  const newAssetsDeclaration = `const STATIC_ASSETS = ${assetsObjectString};`;
  
  if (assetsRegex.test(workerContent)) {
    workerContent = workerContent.replace(assetsRegex, newAssetsDeclaration);
    console.log('✅ Updated existing STATIC_ASSETS object');
  } else {
    console.error('❌ Could not find STATIC_ASSETS object in worker file');
    console.error('   Make sure the worker file contains: const STATIC_ASSETS = {};');
    process.exit(1);
  }
  
  // Write updated worker file
  fs.writeFileSync(WORKER_FILE, workerContent);
  
  console.log('\n🎉 Asset embedding completed successfully!');
  console.log(`📦 Embedded ${Object.keys(assets).length} assets (${(totalSize / 1024).toFixed(1)}KB total)`);
  console.log('🚀 Worker is ready for deployment with "wrangler deploy"');
  
} catch (error) {
  console.error('\n❌ Asset embedding failed:', error.message);
  
  // Restore backup if it exists
  if (fs.existsSync(BACKUP_FILE)) {
    console.log('🔄 Restoring backup...');
    fs.copyFileSync(BACKUP_FILE, WORKER_FILE);
    fs.unlinkSync(BACKUP_FILE);
    console.log('✅ Backup restored');
  }
  
  process.exit(1);
}