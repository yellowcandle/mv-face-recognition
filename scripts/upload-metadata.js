#!/usr/bin/env node

/**
 * Upload metadata to Cloudflare KV
 * 
 * This script uploads processed metadata and configuration data to 
 * Cloudflare KV for fast edge access.
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// Configuration
const METADATA_DIR = path.join(__dirname, '..', 'metadata');
const CONTESTANT_INFO_FILE = path.join(__dirname, '..', 'source', 'contestant_info.csv');
const KV_NAMESPACE = 'METADATA_KV';

console.log('🗃️  Starting upload to Cloudflare KV...');

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
 * Upload a key-value pair to KV
 */
function uploadToKV(key, value) {
  try {
    // Write value to temporary file
    const tempFile = path.join(__dirname, 'temp_kv_value.json');
    fs.writeFileSync(tempFile, value);
    
    const command = `wrangler kv:key put "${key}" --path="${tempFile}" --binding=${KV_NAMESPACE}`;
    console.log(`📤 Uploading KV: ${key}`);
    execSync(command, { stdio: 'pipe' });
    
    // Clean up temp file
    fs.unlinkSync(tempFile);
    return true;
  } catch (error) {
    console.error(`❌ Failed to upload KV ${key}:`, error.message);
    return false;
  }
}

/**
 * Parse CSV file to JSON
 */
function parseCSVToJSON(csvPath) {
  if (!fs.existsSync(csvPath)) {
    console.warn(`⚠️  CSV file not found: ${csvPath}`);
    return null;
  }
  
  const csvContent = fs.readFileSync(csvPath, 'utf8');
  const lines = csvContent.trim().split('\n');
  
  if (lines.length < 2) {
    console.warn('⚠️  CSV file appears to be empty or invalid');
    return null;
  }
  
  // Parse header
  const header = lines[0].split(',').map(col => col.trim());
  
  // Parse data rows
  const contestants = [];
  for (let i = 1; i < lines.length; i++) {
    const values = lines[i].split(',').map(val => val.trim());
    const contestant = {};
    
    header.forEach((col, index) => {
      contestant[col] = values[index] || '';
    });
    
    contestants.push(contestant);
  }
  
  return contestants;
}

/**
 * Process and upload metadata files
 */
function uploadMetadataFiles() {
  if (!fs.existsSync(METADATA_DIR)) {
    console.log(`⚠️  Metadata directory not found: ${METADATA_DIR}`);
    return { uploaded: 0, failed: 0 };
  }
  
  const files = fs.readdirSync(METADATA_DIR);
  let uploaded = 0;
  let failed = 0;
  
  for (const file of files) {
    if (file.endsWith('.json')) {
      const filePath = path.join(METADATA_DIR, file);
      
      try {
        const content = fs.readFileSync(filePath, 'utf8');
        
        // Validate JSON
        JSON.parse(content);
        
        // Use filename (without extension) as key
        const key = file.replace('.json', '');
        
        if (uploadToKV(key, content)) {
          uploaded++;
        } else {
          failed++;
        }
      } catch (error) {
        console.error(`❌ Error processing ${file}:`, error.message);
        failed++;
      }
    }
  }
  
  return { uploaded, failed };
}

/**
 * Upload contestant information
 */
function uploadContestantInfo() {
  console.log('👥 Processing contestant information...');
  
  const contestants = parseCSVToJSON(CONTESTANT_INFO_FILE);
  if (!contestants) {
    console.log('⚠️  Skipping contestant info upload');
    return false;
  }
  
  console.log(`📊 Found ${contestants.length} contestants`);
  
  // Upload as JSON
  const contestantData = {
    contestants: contestants,
    updated_at: new Date().toISOString(),
    total_count: contestants.length
  };
  
  return uploadToKV('contestant_info', JSON.stringify(contestantData, null, 2));
}

/**
 * Upload system configuration
 */
function uploadSystemConfig() {
  console.log('⚙️  Uploading system configuration...');
  
  const config = {
    version: '1.0.0',
    updated_at: new Date().toISOString(),
    features: {
      video_streaming: true,
      face_recognition: true,
      metadata_storage: true,
      websocket: true
    },
    processing: {
      confidence_threshold: 0.7,
      max_faces_per_frame: 10,
      enable_tracking: true,
      processing_interval: 5,
      enable_interpolation: true
    },
    deployment: {
      environment: 'production',
      platform: 'cloudflare_workers',
      edge_locations: 300
    }
  };
  
  return uploadToKV('system_config', JSON.stringify(config, null, 2));
}

async function main() {
  // Check prerequisites
  if (!checkWrangler()) {
    process.exit(1);
  }
  
  console.log(`🎯 Target KV namespace: ${KV_NAMESPACE}`);
  console.log('');
  
  let totalUploaded = 0;
  let totalFailed = 0;
  
  // Upload metadata files
  console.log('📊 Uploading metadata files...');
  const metadataResults = uploadMetadataFiles();
  totalUploaded += metadataResults.uploaded;
  totalFailed += metadataResults.failed;
  
  console.log(`   ✅ ${metadataResults.uploaded} metadata files uploaded`);
  if (metadataResults.failed > 0) {
    console.log(`   ❌ ${metadataResults.failed} metadata files failed`);
  }
  console.log('');
  
  // Upload contestant information
  if (uploadContestantInfo()) {
    totalUploaded++;
    console.log('   ✅ Contestant info uploaded');
  } else {
    totalFailed++;
    console.log('   ❌ Contestant info failed');
  }
  console.log('');
  
  // Upload system configuration
  if (uploadSystemConfig()) {
    totalUploaded++;
    console.log('   ✅ System config uploaded');
  } else {
    totalFailed++;
    console.log('   ❌ System config failed');
  }
  console.log('');
  
  // Summary
  console.log('📈 Upload Summary:');
  console.log(`   Total KV entries uploaded: ${totalUploaded}`);
  console.log(`   Total KV entries failed: ${totalFailed}`);
  
  if (totalFailed === 0) {
    console.log('\n🎉 All KV uploads completed successfully!');
    console.log('🚀 Metadata is now available at the edge');
  } else {
    console.log(`\n⚠️  ${totalFailed} KV uploads failed. Check the errors above.`);
    process.exit(1);
  }
}

// Handle command line arguments
if (process.argv.includes('--help') || process.argv.includes('-h')) {
  console.log(`
Usage: node upload-metadata.js [options]

Upload metadata and configuration to Cloudflare KV

Options:
  -h, --help     Show this help message
  --list         List what would be uploaded without uploading
  
Environment:
  KV_NAMESPACE   Override the default KV namespace (default: ${KV_NAMESPACE})
  
Examples:
  node upload-metadata.js
  KV_NAMESPACE=MY_KV node upload-metadata.js
`);
  process.exit(0);
}

if (process.argv.includes('--list')) {
  console.log('🔍 Listing what would be uploaded to KV:');
  
  // List metadata files
  if (fs.existsSync(METADATA_DIR)) {
    const files = fs.readdirSync(METADATA_DIR)
      .filter(f => f.endsWith('.json'));
    
    console.log('\n📊 Metadata files:');
    files.forEach(file => {
      const key = file.replace('.json', '');
      console.log(`   🔑 ${key} (from ${file})`);
    });
  }
  
  // List other entries
  console.log('\n👥 Contestant info:');
  console.log('   🔑 contestant_info (from contestant_info.csv)');
  
  console.log('\n⚙️  System config:');
  console.log('   🔑 system_config (generated)');
  
  console.log('\n💡 Run without --list to actually upload to KV');
  process.exit(0);
}

// Run the main function
main().catch(error => {
  console.error('❌ KV upload failed:', error.message);
  process.exit(1);
});