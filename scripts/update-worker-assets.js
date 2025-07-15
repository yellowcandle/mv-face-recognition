#!/usr/bin/env node

/**
 * SvelteKit Asset Embedding Script for Cloudflare Workers
 * 
 * This script reads the SvelteKit build output and embeds all static assets
 * into the Cloudflare Worker for edge deployment.
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

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
    // Use JSON.stringify to properly escape the content
    const escapedContent = JSON.stringify(asset.content);
    
    entries.push(`  '${path}': {
    content: ${escapedContent},
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
  const workerLines = fs.readFileSync(WORKER_FILE, 'utf8').split('\n');
  
  // Find the STATIC_ASSETS object boundaries
  let startLine = -1;
  let endLine = -1;
  
  for (let i = 0; i < workerLines.length; i++) {
    // Look for the exact STATIC_ASSETS constant declaration
    if (workerLines[i].trim() === 'const STATIC_ASSETS = {};') {
      startLine = i;
      endLine = i; // Single line object, we'll replace this entire line
      break;
    }
  }
  
  if (startLine === -1 || endLine === -1) {
    console.error('❌ Could not find STATIC_ASSETS object boundaries in worker file');
    process.exit(1);
  }
  
  // Generate assets object
  const assetsObjectString = generateAssetsObject(assets);
  const newAssetsLine = `const STATIC_ASSETS = ${assetsObjectString};`;
  
  // Replace only the STATIC_ASSETS line
  const newWorkerLines = [
    ...workerLines.slice(0, startLine),
    newAssetsLine,
    ...workerLines.slice(endLine + 1)
  ];
  
  // Write updated worker file
  fs.writeFileSync(WORKER_FILE, newWorkerLines.join('\n'));
  
  console.log('✅ Updated existing STATIC_ASSETS object');
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