#!/usr/bin/env node

/**
 * Full Pipeline Runner
 * 
 * Orchestrates the complete video processing and deployment pipeline:
 * 1. Process videos with MVP processor (Python)
 * 2. Upload videos to Cloudflare R2
 * 3. Upload metadata to Cloudflare KV
 * 4. Update and deploy Cloudflare Worker with embedded assets
 */

const fs = require('fs');
const path = require('path');
const { execSync, spawn } = require('child_process');

// Configuration
const PROCESSOR_DIR = path.join(__dirname, '..', 'mvp-processor');
const FRONTEND_DIR = path.join(__dirname, '..', 'apps', 'viewer');
const REPO_DIR = path.join(__dirname, '..');
const WORKER_DIR = path.join(__dirname, '..', 'worker');
const SOURCE_VIDEOS_DIR = path.join(__dirname, '..', 'source', 'videos');

console.log('🚀 Starting Full MV Face Recognition Pipeline...\n');

/**
 * Execute command with logging
 */
function executeCommand(command, cwd = process.cwd(), description = null) {
  if (description) {
    console.log(`🔧 ${description}`);
  }
  console.log(`   Running: ${command}`);
  
  try {
    const result = execSync(command, { 
      cwd: cwd, 
      stdio: 'inherit',
      encoding: 'utf8'
    });
    console.log('   ✅ Success\n');
    return result;
  } catch (error) {
    console.error(`   ❌ Failed: ${error.message}\n`);
    throw error;
  }
}

/**
 * Check prerequisites
 */
function checkPrerequisites() {
  console.log('🔍 Checking prerequisites...');
  
  // Check Python environment
  try {
    execSync('python --version', { stdio: 'pipe' });
    console.log('   ✅ Python found');
  } catch (error) {
    console.error('   ❌ Python not found');
    throw new Error('Python is required for video processing');
  }
  
  // Check Node.js dependencies
  try {
    execSync('npm --version', { stdio: 'pipe' });
    console.log('   ✅ Node.js/npm found');
  } catch (error) {
    console.error('   ❌ Node.js/npm not found');
    throw new Error('Node.js/npm is required for deployment');
  }
  
  // Check Wrangler CLI
  try {
    execSync('wrangler --version', { stdio: 'pipe' });
    console.log('   ✅ Wrangler CLI found');
  } catch (error) {
    console.error('   ❌ Wrangler CLI not found');
    throw new Error('Install with: npm install -g wrangler');
  }
  
  // Check source videos directory
  if (!fs.existsSync(SOURCE_VIDEOS_DIR)) {
    console.error(`   ❌ Source videos directory not found: ${SOURCE_VIDEOS_DIR}`);
    throw new Error('Create source/videos directory and add video files');
  }
  
  const videoFiles = fs.readdirSync(SOURCE_VIDEOS_DIR)
    .filter(f => f.toLowerCase().match(/\.(mp4|avi|mov|mkv)$/));
  
  if (videoFiles.length === 0) {
    console.error('   ❌ No video files found in source/videos');
    throw new Error('Add video files to source/videos directory');
  }
  
  console.log(`   ✅ Found ${videoFiles.length} video files`);
  console.log('');
  
  return videoFiles;
}

/**
 * Process videos with MVP processor
 */
function processVideos(videoFiles, options = {}) {
  console.log('🎬 Processing videos with face recognition...');
  
  const { skipUpload = false, rebuildDb = false, debugMode = false } = options;
  
  // Change to processor directory
  const processorConfigPath = path.join(PROCESSOR_DIR, 'config', 'processing_config.yaml');
  
  if (!fs.existsSync(processorConfigPath)) {
    throw new Error(`Configuration file not found: ${processorConfigPath}`);
  }
  
  console.log(`   Using config: ${processorConfigPath}`);
  console.log(`   Processing ${videoFiles.length} videos...\n`);
  
  for (const videoFile of videoFiles) {
    const videoPath = path.join(SOURCE_VIDEOS_DIR, videoFile);
    const outputName = path.basename(videoFile, path.extname(videoFile));
    
    console.log(`📹 Processing: ${videoFile}`);
    
    // Build Python command
    let command = `uv run python src/process_video.py --input "${videoPath}" --output-name "${outputName}"`;
    
    if (skipUpload) {
      command += ' --no-upload';
    }
    
    if (rebuildDb) {
      command += ' --rebuild-db';
      rebuildDb = false; // Only rebuild once
    }
    
    if (debugMode) {
      command += ' --debug';
    }
    
    // Execute processing
    executeCommand(command, PROCESSOR_DIR, `Processing ${videoFile}`);
  }
  
  console.log('✅ All videos processed successfully!\n');
}

/**
 * Build SvelteKit frontend
 */
function buildFrontend() {
  console.log('🏗️  Building the viewer...');

  // `apps/viewer` is the published frontend; pnpm installs the workspace once.
  executeCommand(
    'pnpm --filter @mv/viewer build',
    REPO_DIR,
    'Building apps/viewer'
  );

  const distDir = path.join(FRONTEND_DIR, 'dist');
  if (!fs.existsSync(path.join(distDir, 'index.html'))) {
    throw new Error(`Viewer build failed - ${distDir}/index.html not found`);
  }

  const buildFiles = fs.readdirSync(distDir, { recursive: true }).length;
  console.log(`   ✅ Build completed with ${buildFiles} assets\n`);
}

/**
 * Upload content to Cloudflare
 */
function uploadToCloudflare(skipVideoUpload = false) {
  console.log('☁️  Uploading content to Cloudflare...');
  
  if (!skipVideoUpload) {
    // Upload videos to R2
    executeCommand(
      'node scripts/upload-to-r2.js', 
      REPO_DIR, 
      'Uploading published encodes to R2'
    );
  } else {
    console.log('   ⏭️  Skipping video upload (already processed)');
  }
  
  // Publish the validated read model to KV (scripts/publish owns KV)
  executeCommand(
    'uv run --no-project python scripts/publish/build_read_model.py --publish', 
    REPO_DIR, 
    'Publishing metadata to KV'
  );
  
  console.log('✅ Cloudflare upload completed!\n');
}

/**
 * Deploy Cloudflare Worker
 */
function deployWorker() {
  console.log('🌐 Deploying Cloudflare Worker...');
  
  // Update worker with embedded assets
  executeCommand(
    'node scripts/update-worker-assets.js', 
    REPO_DIR, 
    'Embedding viewer assets in the worker'
  );
  
  // Deploy worker
  executeCommand(
    'wrangler deploy', 
    WORKER_DIR, 
    'Deploying worker to Cloudflare'
  );
  
  console.log('✅ Worker deployment completed!\n');
}

/**
 * Print pipeline summary
 */
function printSummary(videoFiles, options) {
  console.log('🎉 Pipeline completed successfully!\n');
  
  console.log('📊 Summary:');
  console.log(`   Videos processed: ${videoFiles.length}`);
  console.log(`   Frontend: apps/viewer built and embedded in the Worker`);
  console.log(`   Backend: Cloudflare Worker deployed`);
  console.log(`   Storage: R2 (encodes) + KV (read model)`);
  console.log('');
  
  console.log('🌐 Access your application:');
  console.log('   🔗 https://mv-face-recognition-api.herballemon.workers.dev/');
  console.log('');
  console.log('🛠️  Development commands:');
  console.log('   📹 Process new video: uv run python mvp-processor/src/process_video.py -i path/to/video.mp4 --local-only');
  console.log('   🏗️  Rebuild viewer: pnpm --filter @mv/viewer build && node scripts/update-worker-assets.js');
  console.log('   ☁️  Redeploy worker: cd worker && wrangler deploy');
  console.log('');
}

/**
 * Main pipeline function
 */
async function runPipeline(options = {}) {
  const {
    skipProcessing = false,
    skipVideoUpload = false,
    skipDeploy = false,
    rebuildDb = false,
    debugMode = false,
    processOnly = false
  } = options;
  
  try {
    // Check prerequisites
    const videoFiles = checkPrerequisites();
    
    // Step 1: Process videos (unless skipped)
    if (!skipProcessing) {
      processVideos(videoFiles, { 
        skipUpload: true, // We handle upload separately
        rebuildDb, 
        debugMode 
      });
    } else {
      console.log('⏭️  Skipping video processing\n');
    }
    
    // Early exit for process-only mode
    if (processOnly) {
      console.log('✅ Processing completed (process-only mode)\n');
      return;
    }
    
    // Step 2: Build frontend
    buildFrontend();
    
    // Step 3: Upload to Cloudflare
    uploadToCloudflare(skipVideoUpload);
    
    // Step 4: Deploy worker (unless skipped)
    if (!skipDeploy) {
      deployWorker();
    } else {
      console.log('⏭️  Skipping worker deployment\n');
    }
    
    // Print summary
    printSummary(videoFiles, options);
    
  } catch (error) {
    console.error('\n❌ Pipeline failed:', error.message);
    console.error('\n🔧 Troubleshooting:');
    console.error('   1. Check that all prerequisites are installed');
    console.error('   2. Verify Cloudflare credentials are set');
    console.error('   3. Ensure source videos are in source/videos/');
    console.error('   4. Check CLAUDE.md for configuration requirements');
    process.exit(1);
  }
}

// Handle command line arguments
if (require.main === module) {
  const args = process.argv.slice(2);
  
  if (args.includes('--help') || args.includes('-h')) {
    console.log(`
MV Face Recognition - Full Pipeline Runner

Usage: node scripts/run-full-pipeline.cjs [options]

Options:
  -h, --help           Show this help message
  --skip-processing    Skip video processing (use existing processed videos)
  --skip-upload        Skip video upload to R2 (use existing R2 content)
  --skip-deploy        Skip worker deployment
  --process-only       Only run video processing, skip deployment
  --rebuild-db         Force rebuild of contestant database
  --debug              Enable debug logging
  
Examples:
  node run-full-pipeline.js                          # Run complete pipeline
  node run-full-pipeline.js --skip-processing        # Deploy existing processed videos
  node run-full-pipeline.js --process-only           # Only process videos
  node run-full-pipeline.js --debug --rebuild-db     # Debug mode with database rebuild
`);
    process.exit(0);
  }
  
  const options = {
    skipProcessing: args.includes('--skip-processing'),
    skipVideoUpload: args.includes('--skip-upload'),
    skipDeploy: args.includes('--skip-deploy'),
    processOnly: args.includes('--process-only'),
    rebuildDb: args.includes('--rebuild-db'),
    debugMode: args.includes('--debug')
  };
  
  runPipeline(options);
}

module.exports = { runPipeline };