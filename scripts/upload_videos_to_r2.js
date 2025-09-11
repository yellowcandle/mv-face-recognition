#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const videosDir = path.join(__dirname, '..', 'processed_videos');
const bucketName = 'mv-face-recognition-videos';

// Get list of video files
const videoFiles = fs.readdirSync(videosDir).filter(file => 
    file.endsWith('.mp4') && !file.startsWith('.') // Ignore hidden files like .DS_Store
);

console.log(`Found ${videoFiles.length} processed videos to upload:`);
videoFiles.forEach((file, index) => {
    const filePath = path.join(videosDir, file);
    const stats = fs.statSync(filePath);
    const sizeInMB = (stats.size / (1024 * 1024)).toFixed(2);
    console.log(`  ${index + 1}. ${file} (${sizeInMB} MB)`);
});

const totalSize = videoFiles.reduce((total, file) => {
    const filePath = path.join(videosDir, file);
    const stats = fs.statSync(filePath);
    return total + stats.size;
}, 0);

console.log(`\nTotal size: ${(totalSize / (1024 * 1024 * 1024)).toFixed(2)} GB`);

async function uploadToR2() {
    console.log('\n🚀 Starting video upload to Cloudflare R2...\n');
    
    for (let i = 0; i < videoFiles.length; i++) {
        const file = videoFiles[i];
        const filePath = path.join(videosDir, file);
        const objectKey = `processed_videos/${file}`; // Organize in R2 with folder structure
        
        console.log(`\n[${i + 1}/${videoFiles.length}] Uploading ${file}...`);
        console.log(`  Source: ${filePath}`);
        console.log(`  Destination: ${bucketName}/${objectKey}`);
        
        try {
            const startTime = Date.now();
            
            // Upload using wrangler r2 object put
            execSync(`npx wrangler r2 object put "${bucketName}/${objectKey}" --file="${filePath}"`, {
                stdio: 'inherit'
            });
            
            const endTime = Date.now();
            const uploadTime = ((endTime - startTime) / 1000).toFixed(2);
            
            console.log(`  ✅ Successfully uploaded ${file} in ${uploadTime}s`);
            
        } catch (error) {
            console.error(`  ❌ Failed to upload ${file}:`, error.message);
        }
    }
    
    console.log('\n🎉 Video upload process completed!');
}

// Create a manifest file with video information
async function createVideoManifest() {
    console.log('\nCreating video manifest...');
    
    const manifest = {
        upload_date: new Date().toISOString(),
        total_videos: videoFiles.length,
        total_size_bytes: totalSize,
        total_size_gb: parseFloat((totalSize / (1024 * 1024 * 1024)).toFixed(2)),
        videos: videoFiles.map(file => {
            const filePath = path.join(videosDir, file);
            const stats = fs.statSync(filePath);
            return {
                filename: file,
                size_bytes: stats.size,
                size_mb: parseFloat((stats.size / (1024 * 1024)).toFixed(2)),
                r2_path: `processed_videos/${file}`,
                upload_date: new Date().toISOString()
            };
        })
    };
    
    try {
        const manifestFile = path.join(__dirname, 'temp_video_manifest.json');
        fs.writeFileSync(manifestFile, JSON.stringify(manifest, null, 2));
        
        // Upload manifest to R2
        execSync(`npx wrangler r2 object put "${bucketName}/manifest/processed_videos_manifest.json" --file="${manifestFile}"`, {
            stdio: 'inherit'
        });
        
        // Also upload to KV for easy access
        execSync(`npx wrangler kv key put "processed_videos_manifest" --path="${manifestFile}" --binding=METADATA_KV --preview false`, {
            stdio: 'inherit'
        });
        
        fs.unlinkSync(manifestFile);
        console.log('✅ Video manifest created and uploaded');
        
    } catch (error) {
        console.error('❌ Failed to create video manifest:', error.message);
    }
}

// Generate R2 public URLs (if needed)
async function generateAccessInfo() {
    console.log('\nGenerating access information...');
    
    const accessInfo = {
        bucket_name: bucketName,
        base_url: `https://${bucketName}.r2.cloudflarestorage.com`, // This might need to be configured
        videos: videoFiles.map(file => ({
            filename: file,
            r2_path: `processed_videos/${file}`,
            // Note: Actual public URLs would need R2 custom domain or presigned URLs
            estimated_url: `https://${bucketName}.r2.cloudflarestorage.com/processed_videos/${encodeURIComponent(file)}`
        })),
        note: "Actual access URLs depend on your R2 bucket configuration and custom domain setup"
    };
    
    try {
        const accessFile = path.join(__dirname, 'temp_access_info.json');
        fs.writeFileSync(accessFile, JSON.stringify(accessInfo, null, 2));
        
        execSync(`npx wrangler kv key put "r2_access_info" --path="${accessFile}" --binding=METADATA_KV --preview false`, {
            stdio: 'inherit'
        });
        
        fs.unlinkSync(accessFile);
        console.log('✅ Access information uploaded to KV');
        
    } catch (error) {
        console.error('❌ Failed to upload access information:', error.message);
    }
}

// Main execution
async function main() {
    if (videoFiles.length === 0) {
        console.log('❌ No video files found in processed_videos directory');
        return;
    }
    
    // Confirm upload due to large file sizes
    console.log('\n⚠️  WARNING: You are about to upload large video files to R2.');
    console.log(`Total data transfer: ${(totalSize / (1024 * 1024 * 1024)).toFixed(2)} GB`);
    console.log('This may take a significant amount of time and bandwidth.');
    console.log('\nTo proceed, run this script with --confirm flag:');
    console.log('node scripts/upload_videos_to_r2.js --confirm\n');
    
    if (!process.argv.includes('--confirm')) {
        console.log('Upload cancelled. Use --confirm to proceed.');
        return;
    }
    
    await uploadToR2();
    await createVideoManifest();
    await generateAccessInfo();
    
    console.log('\n📊 Upload summary:');
    console.log(`  • ${videoFiles.length} videos uploaded to R2`);
    console.log(`  • ${(totalSize / (1024 * 1024 * 1024)).toFixed(2)} GB transferred`);
    console.log(`  • Manifest and access info saved to KV`);
    console.log(`  • R2 bucket: ${bucketName}`);
}

main().catch(console.error); 