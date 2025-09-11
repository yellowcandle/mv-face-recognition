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
    const contestantsFile = path.join(__dirname, 'temp_contestants.json');
    fs.writeFileSync(contestantsFile, JSON.stringify(contestants, null, 2));
    execSync(`wrangler kv key put "contestants" --path="${contestantsFile}" --binding=METADATA_KV --preview false`, { stdio: 'inherit' });
    fs.unlinkSync(contestantsFile);

    // 2. Upload video metadata files
    console.log('🎬 Uploading video metadata...');
    const metadataFiles = fs.readdirSync('metadata').filter(f => f.endsWith('_metadata.json'));
    
    const videosList = [];
    
    for (const file of metadataFiles) {
      const metadata = JSON.parse(fs.readFileSync(path.join('metadata', file), 'utf8'));
      const videoId = file.replace('_metadata.json', '');
      
      // Upload individual video metadata
      const metadataFile = path.join(__dirname, `temp_metadata_${videoId}.json`);
      fs.writeFileSync(metadataFile, JSON.stringify(metadata, null, 2));
      execSync(`wrangler kv key put "video_metadata_${videoId}" --path="${metadataFile}" --binding=METADATA_KV --preview false`, { stdio: 'inherit' });
      fs.unlinkSync(metadataFile);
      
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
    const videosListFile = path.join(__dirname, 'temp_videos_list.json');
    fs.writeFileSync(videosListFile, JSON.stringify(videosList, null, 2));
    execSync(`wrangler kv key put "videos_list" --path="${videosListFile}" --binding=METADATA_KV --preview false`, { stdio: 'inherit' });
    fs.unlinkSync(videosListFile);

    // 3. Upload processing report if it exists
    if (fs.existsSync('batch_processing_report.json')) {
      console.log('📋 Uploading processing report...');
      execSync(`wrangler kv key put "processing_report" --path="batch_processing_report.json" --binding=METADATA_KV --preview false`, { stdio: 'inherit' });
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
    const settingsFile = path.join(__dirname, 'temp_settings.json');
    fs.writeFileSync(settingsFile, JSON.stringify(defaultSettings, null, 2));
    execSync(`wrangler kv key put "app_settings" --path="${settingsFile}" --binding=METADATA_KV --preview false`, { stdio: 'inherit' });
    fs.unlinkSync(settingsFile);

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