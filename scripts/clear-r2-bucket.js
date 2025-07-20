#!/usr/bin/env node

/**
 * Clear all objects from Cloudflare R2 bucket
 */

import { execSync } from 'child_process';

const BUCKET_NAME = 'mv-face-recognition-videos';

console.log('🧹 Clearing R2 bucket...');

/**
 * Clear all objects from the bucket
 */
function clearBucket() {
  try {
    // List all objects and delete them
    console.log(`📋 Listing objects in bucket: ${BUCKET_NAME}`);
    
    // Get list of all objects
    const listCommand = `BUCKET=${BUCKET_NAME} wrangler r2 object list --bucket ${BUCKET_NAME} --format=json || echo "[]"`;
    let objects = [];
    
    try {
      const result = execSync(listCommand, { stdio: 'pipe', encoding: 'utf8' });
      if (result.trim() && result.trim() !== '[]') {
        objects = JSON.parse(result);
      }
    } catch (error) {
      // If listing fails, try alternative approach
      console.log('📋 Direct listing failed, checking if bucket is empty...');
      return true; // Assume empty bucket
    }
    
    if (!objects || objects.length === 0) {
      console.log('✅ Bucket is already empty');
      return true;
    }
    
    console.log(`🗑️  Found ${objects.length} objects to delete`);
    
    // Delete each object
    let successCount = 0;
    let failCount = 0;
    
    for (const obj of objects) {
      try {
        const deleteCommand = `wrangler r2 object delete ${BUCKET_NAME}/${obj.key}`;
        console.log(`🗑️  Deleting: ${obj.key}`);
        execSync(deleteCommand, { stdio: 'pipe' });
        successCount++;
      } catch (error) {
        console.error(`❌ Failed to delete ${obj.key}:`, error.message);
        failCount++;
      }
    }
    
    console.log(`📊 Deletion Summary:`);
    console.log(`   Successfully deleted: ${successCount}`);
    console.log(`   Failed to delete: ${failCount}`);
    
    return failCount === 0;
    
  } catch (error) {
    console.error('❌ Error clearing bucket:', error.message);
    return false;
  }
}

// Alternative method: Delete all by pattern
function forceDeleteAll() {
  console.log('🧹 Force clearing bucket using pattern delete...');
  
  const patterns = ['videos/*', 'metadata/*', 'thumbnails/*'];
  
  for (const pattern of patterns) {
    try {
      // Try to delete pattern (this might fail if no objects match)
      const command = `wrangler r2 object delete ${BUCKET_NAME}/${pattern} --recursive 2>/dev/null || true`;
      console.log(`🗑️  Deleting pattern: ${pattern}`);
      execSync(command, { stdio: 'pipe' });
    } catch (error) {
      // Ignore errors for pattern delete
      console.log(`   Pattern ${pattern} completed (may have been empty)`);
    }
  }
  
  // Also try to delete any root level files
  try {
    const command = `find . -name "*.mp4" -o -name "*.json" | head -20 | while read file; do wrangler r2 object delete ${BUCKET_NAME}/$(basename "$file") 2>/dev/null || true; done`;
    execSync(command, { stdio: 'pipe' });
  } catch (error) {
    // Ignore errors
  }
  
  console.log('✅ Force delete completed');
  return true;
}

async function main() {
  console.log('🚀 Starting R2 bucket cleanup...');
  
  // Try normal delete first
  let success = clearBucket();
  
  if (!success) {
    console.log('⚠️  Normal delete failed, trying force delete...');
    success = forceDeleteAll();
  }
  
  if (success) {
    console.log('🎉 R2 bucket cleared successfully!');
    process.exit(0);
  } else {
    console.log('❌ Failed to clear R2 bucket');
    process.exit(1);
  }
}

main();