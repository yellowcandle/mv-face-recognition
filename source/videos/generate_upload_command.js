
const fs = require('fs');
const path = require('path');

const videosDir = 'source/videos';
const bucketName = 'mv-face-recognition-videos';

try {
    const videoFiles = fs.readdirSync(videosDir).filter(file => 
        file.endsWith('.mp4') && !file.includes('-original')
    );

    console.log('Compressed videos ready for upload:');
    videoFiles.forEach(file => {
        const stats = fs.statSync(path.join(videosDir, file));
        const sizeMB = (stats.size / (1024 * 1024)).toFixed(1);
        console.log(`  ${file} (${sizeMB}M)`);
    });

    const testFile = videoFiles[0];
    console.log('\nTo test upload the first video, run:');
    console.log(`npx wrangler r2 object put "${bucketName}/${testFile}" --file="${videosDir}/${testFile}"`);

} catch (error) {
    console.error('Error reading video directory:', error.message);
}
