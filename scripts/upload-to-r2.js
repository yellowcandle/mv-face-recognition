#!/usr/bin/env node

/**
 * Upload processed videos to Cloudflare R2
 * 
 * This script uploads processed video files and metadata to Cloudflare R2
 * for serving via the Workers deployment.
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// Configuration
const PROCESSED_VIDEOS_DIR = path.join(__dirname, '..', 'processed_videos');
const METADATA_DIR = path.join(__dirname, '..', 'metadata');
const BUCKET_NAME = 'mv-face-recognition-videos';

console.log('☁️  Starting upload to Cloudflare R2...');

/**
 * Check if wrangler is available
 */
function checkWrangler() {
  try {
    execSync('wrangler --version', { stdio: 'pipe' });
    console.log('✅ Wrangler CLI found');
    return true;
  } catch (error) {
    console.error('❌ Wrangler CLI not found. Install with: npm install -g wrangler');
    return false;
  }
}

/**
 * Upload a file to R2
 */
function uploadFile(localPath, remotePath) {
  try {
    const command = `wrangler r2 object put ${BUCKET_NAME}/${remotePath} --file="${localPath}"`;
    console.log(`📤 Uploading: ${remotePath}`);
    execSync(command, { stdio: 'pipe' });
    return true;
  } catch (error) {
    console.error(`❌ Failed to upload ${remotePath}:`, error.message);
    return false;
  }
}

/**
 * Get file size in MB
 */
function getFileSizeMB(filePath) {
  const stats = fs.statSync(filePath);
  return (stats.size / (1024 * 1024)).toFixed(2);
}

/**
 * Upload all files in a directory
 */
function uploadDirectory(localDir, remotePrefix) {
  if (!fs.existsSync(localDir)) {
    console.log(`⚠️  Directory not found: ${localDir}`);
    return { uploaded: 0, failed: 0, totalSize: 0 };
  }
  
  const files = fs.readdirSync(localDir);
  let uploaded = 0;
  let failed = 0;
  let totalSize = 0;
  
  for (const file of files) {
    const localPath = path.join(localDir, file);
    const remotePath = `${remotePrefix}${file}`;
    
    if (fs.statSync(localPath).isFile()) {
      const sizeMB = parseFloat(getFileSizeMB(localPath));
      totalSize += sizeMB;
      
      console.log(`📁 ${file} (${sizeMB}MB)`);
      
      if (uploadFile(localPath, remotePath)) {
        uploaded++;
      } else {
        failed++;
      }
    }
  }
  
  return { uploaded, failed, totalSize };
}

async function main() {
  // Check prerequisites
  if (!checkWrangler()) {
    process.exit(1);
  }
  
  console.log(`🎯 Target bucket: ${BUCKET_NAME}`);
  console.log('');
  
  let totalUploaded = 0;
  let totalFailed = 0;
  let totalSizeMB = 0;
  
  // Upload processed videos
  console.log('🎬 Uploading processed videos...');
  const videoResults = uploadDirectory(PROCESSED_VIDEOS_DIR, 'videos/');
  totalUploaded += videoResults.uploaded;
  totalFailed += videoResults.failed;
  totalSizeMB += videoResults.totalSize;
  
  console.log(`   ✅ ${videoResults.uploaded} videos uploaded`);
  if (videoResults.failed > 0) {
    console.log(`   ❌ ${videoResults.failed} videos failed`);
  }
  console.log('');
  
  // Upload metadata
  console.log('📊 Uploading metadata files...');
  const metadataResults = uploadDirectory(METADATA_DIR, 'metadata/');
  totalUploaded += metadataResults.uploaded;
  totalFailed += metadataResults.failed;
  totalSizeMB += metadataResults.totalSize;
  
  console.log(`   ✅ ${metadataResults.uploaded} metadata files uploaded`);
  if (metadataResults.failed > 0) {
    console.log(`   ❌ ${metadataResults.failed} metadata files failed`);
  }
  console.log('');
  
  // Summary
  console.log('📈 Upload Summary:');
  console.log(`   Total files uploaded: ${totalUploaded}`);
  console.log(`   Total files failed: ${totalFailed}`);
  console.log(`   Total size uploaded: ${totalSizeMB.toFixed(2)}MB`);
  
  if (totalFailed === 0) {
    console.log('\n🎉 All uploads completed successfully!');
    console.log('🚀 Videos are now available via Cloudflare Workers');
  } else {
    console.log(`\n⚠️  ${totalFailed} uploads failed. Check the errors above.`);
    process.exit(1);
  }
}

// Handle command line arguments
if (process.argv.includes('--help') || process.argv.includes('-h')) {
  console.log(`
Usage: node upload-to-r2.js [options]

Upload processed videos and metadata to Cloudflare R2

Options:
  -h, --help     Show this help message
  --dry-run      Show what would be uploaded without actually uploading
  
Environment:
  BUCKET_NAME    Override the default bucket name (default: ${BUCKET_NAME})
  
Examples:
  node upload-to-r2.js
  BUCKET_NAME=my-custom-bucket node upload-to-r2.js
`);
  process.exit(0);
}

if (process.argv.includes('--dry-run')) {
  console.log('🔍 Dry run mode - showing what would be uploaded:');
  
  // Just list files without uploading
  function listDirectory(dir, prefix) {
    if (!fs.existsSync(dir)) {
      console.log(`⚠️  Directory not found: ${dir}`);
      return;
    }
    
    const files = fs.readdirSync(dir);
    console.log(`\n📁 ${prefix}:`);
    
    for (const file of files) {
      const localPath = path.join(dir, file);
      if (fs.statSync(localPath).isFile()) {
        const sizeMB = getFileSizeMB(localPath);
        console.log(`   📄 ${file} (${sizeMB}MB)`);
      }
    }
  }
  
  listDirectory(PROCESSED_VIDEOS_DIR, 'Videos');
  listDirectory(METADATA_DIR, 'Metadata');
  
  console.log('\n💡 Run without --dry-run to actually upload files');
  process.exit(0);
}

// Run the main function
main().catch(error => {
  console.error('❌ Upload failed:', error.message);
  process.exit(1);
});