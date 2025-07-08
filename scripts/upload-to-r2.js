#!/usr/bin/env node

/**
 * Upload processed videos to Cloudflare R2
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

async function main() {
  console.log('🎥 Uploading videos to Cloudflare R2...');

  try {
    const videosDir = 'processed_videos';
    
    if (!fs.existsSync(videosDir)) {
      console.log('❌ No processed_videos directory found. Please run video processing first.');
      process.exit(1);
    }

    const videoFiles = fs.readdirSync(videosDir).filter(f => f.endsWith('.mp4'));
    
    if (videoFiles.length === 0) {
      console.log('❌ No video files found in processed_videos directory.');
      process.exit(1);
    }

    console.log(`📹 Found ${videoFiles.length} videos to upload...`);

    for (const video of videoFiles) {
      const filePath = path.join(videosDir, video);
      const fileSize = fs.statSync(filePath).size;
      const sizeMB = (fileSize / 1024 / 1024).toFixed(1);
      
      console.log(`⬆️  Uploading ${video} (${sizeMB} MB)...`);
      
      try {
        // Upload to R2 using wrangler
        execSync(`wrangler r2 object put mv-face-recognition-videos/${video} --file=${filePath}`, { 
          stdio: 'pipe' // Reduce noise, only show errors
        });
        console.log(`✅ Uploaded ${video}`);
      } catch (error) {
        console.error(`❌ Failed to upload ${video}:`, error.message);
      }
    }

    console.log('🎉 Video upload completed!');
    console.log(`   📹 Total videos: ${videoFiles.length}`);
    console.log(`   🌐 Available at: https://your-worker.your-domain.com/videos/[filename]`);

  } catch (error) {
    console.error('❌ Error uploading videos:', error.message);
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}

module.exports = { main };