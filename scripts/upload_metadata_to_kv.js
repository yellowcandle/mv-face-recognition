#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const metadataDir = path.join(__dirname, '..', 'metadata');
const namespace = 'METADATA_KV';

// Get list of metadata files
const metadataFiles = fs.readdirSync(metadataDir).filter(file => 
    file.endsWith('.json') || file.endsWith('.csv')
);

console.log(`Found ${metadataFiles.length} metadata files to upload:`);
metadataFiles.forEach(file => console.log(`  - ${file}`));

async function uploadToKV() {
    for (const file of metadataFiles) {
        const filePath = path.join(metadataDir, file);
        const keyName = file.replace(/\.(json|csv)$/, ''); // Remove extension for key name
        
        console.log(`\nUploading ${file} to KV with key: ${keyName}`);
        
        try {
            // For CSV files, we'll upload as text
            if (file.endsWith('.csv')) {
                const content = fs.readFileSync(filePath, 'utf8');
                const tempFile = path.join(__dirname, 'temp_upload.txt');
                fs.writeFileSync(tempFile, content);
                
                execSync(`npx wrangler kv key put "${keyName}" --path="${tempFile}" --binding=${namespace} --preview false`, {
                    stdio: 'inherit'
                });
                
                fs.unlinkSync(tempFile);
            } else {
                // For JSON files, upload directly
                execSync(`npx wrangler kv key put "${keyName}" --path="${filePath}" --binding=${namespace} --preview false`, {
                    stdio: 'inherit'
                });
            }
            
            console.log(`✅ Successfully uploaded ${file}`);
        } catch (error) {
            console.error(`❌ Failed to upload ${file}:`, error.message);
        }
    }
    
    console.log('\n🎉 Metadata upload process completed!');
}

// Special handling for video metadata - create organized structure
async function uploadVideoMetadata() {
    console.log('\nCreating organized video metadata structure...');
    
    const videoMetadata = {};
    const annotatedMetadata = {};
    
    metadataFiles.forEach(file => {
        if (file.includes('_metadata.json') && !file.includes('annotated')) {
            const videoName = file.replace('_metadata.json', '');
            const filePath = path.join(metadataDir, file);
            try {
                const content = JSON.parse(fs.readFileSync(filePath, 'utf8'));
                videoMetadata[videoName] = content;
            } catch (error) {
                console.error(`Failed to parse ${file}:`, error.message);
            }
        } else if (file.includes('_annotated_dense_metadata.json')) {
            const videoName = file.replace('_annotated_dense_metadata.json', '');
            const filePath = path.join(metadataDir, file);
            try {
                const content = JSON.parse(fs.readFileSync(filePath, 'utf8'));
                annotatedMetadata[videoName] = content;
            } catch (error) {
                console.error(`Failed to parse ${file}:`, error.message);
            }
        }
    });
    
    // Upload organized structures
    try {
        const videoMetadataFile = path.join(__dirname, 'temp_video_metadata.json');
        fs.writeFileSync(videoMetadataFile, JSON.stringify(videoMetadata, null, 2));
        execSync(`npx wrangler kv key put "video_metadata_collection" --path="${videoMetadataFile}" --binding=${namespace} --preview false`, {
            stdio: 'inherit'
        });
        fs.unlinkSync(videoMetadataFile);
        console.log('✅ Uploaded organized video metadata collection');
        
        const annotatedMetadataFile = path.join(__dirname, 'temp_annotated_metadata.json');
        fs.writeFileSync(annotatedMetadataFile, JSON.stringify(annotatedMetadata, null, 2));
        execSync(`npx wrangler kv key put "annotated_metadata_collection" --path="${annotatedMetadataFile}" --binding=${namespace} --preview false`, {
            stdio: 'inherit'
        });
        fs.unlinkSync(annotatedMetadataFile);
        console.log('✅ Uploaded organized annotated metadata collection');
        
    } catch (error) {
        console.error('❌ Failed to upload organized metadata:', error.message);
    }
}

// Upload contestant info as structured data
async function uploadContestantInfo() {
    const csvFile = path.join(metadataDir, 'contestant_info.csv');
    if (!fs.existsSync(csvFile)) {
        console.log('No contestant_info.csv found, skipping...');
        return;
    }
    
    console.log('\nProcessing contestant info...');
    
    try {
        const csvContent = fs.readFileSync(csvFile, 'utf8');
        const lines = csvContent.trim().split('\n');
        const headers = lines[0].split(',');
        
        const contestants = lines.slice(1).map(line => {
            const values = line.split(',');
            const contestant = {};
            headers.forEach((header, index) => {
                contestant[header.trim()] = values[index]?.trim() || '';
            });
            return contestant;
        });
        
        const contestantsFile = path.join(__dirname, 'temp_contestants.json');
        fs.writeFileSync(contestantsFile, JSON.stringify(contestants, null, 2));
        
        execSync(`npx wrangler kv key put "contestants_structured" --path="${contestantsFile}" --binding=${namespace} --preview false`, {
            stdio: 'inherit'
        });
        
        fs.unlinkSync(contestantsFile);
        console.log('✅ Uploaded structured contestant data');
        
    } catch (error) {
        console.error('❌ Failed to process contestant info:', error.message);
    }
}

// Main execution
async function main() {
    console.log('🚀 Starting metadata upload to Cloudflare KV...\n');
    
    await uploadToKV();
    await uploadVideoMetadata();
    await uploadContestantInfo();
    
    console.log('\n📊 Upload summary completed. Check KV namespace for all uploaded data.');
}

main().catch(console.error); 