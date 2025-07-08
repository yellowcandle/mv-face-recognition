#!/usr/bin/env node

/**
 * Upload metadata to Cloudflare KV
 * Converts CSV and JSON files to KV store for the worker
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

async function main() {
  console.log('🚀 Uploading metadata to Cloudflare KV...');

  try {
    // 1. Convert contestant CSV to JSON
    console.log('📊 Converting contestant data...');
    const csvContent = fs.readFileSync('metadata/contestant_info.csv', 'utf8');
    const lines = csvContent.trim().split('\n');
    const headers = lines[0].split(',');
    
    const contestants = lines.slice(1).map(line => {
      const values = line.split(',');
      return {
        id: parseInt(values[0]),
        name: values[1],
        nickname: values[2],
        age: parseInt(values[3])
      };
    });

    // Upload contestants data
    execSync(`wrangler kv:key put --binding=METADATA_KV "contestants" '${JSON.stringify(contestants)}'`, { stdio: 'inherit' });

    // 2. Upload video metadata files
    console.log('🎬 Uploading video metadata...');
    const metadataFiles = fs.readdirSync('metadata').filter(f => f.endsWith('_metadata.json'));
    
    const videosList = [];
    
    for (const file of metadataFiles) {
      const metadata = JSON.parse(fs.readFileSync(path.join('metadata', file), 'utf8'));
      const videoId = file.replace('_metadata.json', '');
      
      // Upload individual video metadata
      execSync(`wrangler kv:key put --binding=METADATA_KV "video_metadata_${videoId}" '${JSON.stringify(metadata)}'`, { stdio: 'inherit' });
      
      // Add to videos list
      videosList.push({
        id: videoId,
        title: metadata.video_name || videoId,
        duration: metadata.video_duration,
        faces_detected: metadata.total_faces,
        contestants_found: metadata.unique_contestants?.length || 0,
        processed_at: metadata.processing_completed,
        file_path: `/videos/${videoId}_annotated.mp4`
      });
    }

    // Upload videos list
    execSync(`wrangler kv:key put --binding=METADATA_KV "videos_list" '${JSON.stringify(videosList)}'`, { stdio: 'inherit' });

    // 3. Upload processing report if it exists
    if (fs.existsSync('batch_processing_report.json')) {
      console.log('📋 Uploading processing report...');
      const report = fs.readFileSync('batch_processing_report.json', 'utf8');
      execSync(`wrangler kv:key put --binding=METADATA_KV "processing_report" '${report}'`, { stdio: 'inherit' });
    }

    // 4. Upload default settings
    console.log('⚙️ Uploading default settings...');
    const defaultSettings = {
      theme: 'auto',
      notifications: true,
      autoRefresh: true,
      refreshInterval: 30,
      maxConcurrentJobs: 3,
      videoQuality: 'medium',
      faceDetectionThreshold: 0.8
    };
    execSync(`wrangler kv:key put --binding=METADATA_KV "app_settings" '${JSON.stringify(defaultSettings)}'`, { stdio: 'inherit' });

    console.log('✅ Metadata upload completed!');
    console.log(`   📊 Uploaded ${contestants.length} contestants`);
    console.log(`   🎬 Uploaded ${videosList.length} videos`);
    console.log(`   📋 Uploaded processing report`);

  } catch (error) {
    console.error('❌ Error uploading metadata:', error.message);
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}

module.exports = { main };