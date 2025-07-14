#!/usr/bin/env node

/**
 * Environment Setup Script
 * 
 * Helps users configure Cloudflare credentials and verify the environment
 * for the MV Face Recognition system.
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const readline = require('readline');

const ENV_FILE = path.join(__dirname, '..', '.env');
const ENV_EXAMPLE_FILE = path.join(__dirname, '..', '.env.example');

console.log('⚙️  MV Face Recognition - Environment Setup\n');

/**
 * Create readline interface for user input
 */
const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout
});

/**
 * Promisify readline question
 */
function question(query) {
  return new Promise(resolve => rl.question(query, resolve));
}

/**
 * Check if command exists
 */
function commandExists(command) {
  try {
    execSync(`which ${command}`, { stdio: 'pipe' });
    return true;
  } catch (error) {
    return false;
  }
}

/**
 * Check prerequisites
 */
function checkPrerequisites() {
  console.log('🔍 Checking prerequisites...\n');
  
  const checks = [
    { name: 'Node.js', command: 'node --version', required: true },
    { name: 'npm', command: 'npm --version', required: true },
    { name: 'Python', command: 'python --version', required: true },
    { name: 'pip', command: 'pip --version', required: true },
    { name: 'Wrangler CLI', command: 'wrangler --version', required: true },
    { name: 'Git', command: 'git --version', required: false },
    { name: 'FFmpeg', command: 'ffmpeg -version', required: false }
  ];
  
  let hasErrors = false;
  
  for (const check of checks) {
    try {
      const version = execSync(check.command, { stdio: 'pipe', encoding: 'utf8' });
      const shortVersion = version.split('\n')[0];
      console.log(`   ✅ ${check.name}: ${shortVersion}`);
    } catch (error) {
      if (check.required) {
        console.log(`   ❌ ${check.name}: Not found (REQUIRED)`);
        hasErrors = true;
      } else {
        console.log(`   ⚠️  ${check.name}: Not found (optional)`);
      }
    }
  }
  
  console.log('');
  
  if (hasErrors) {
    console.error('❌ Missing required dependencies. Please install them first:\n');
    console.error('   Node.js: https://nodejs.org/');
    console.error('   Python: https://python.org/');
    console.error('   Wrangler: npm install -g wrangler');
    console.error('');
    process.exit(1);
  }
  
  console.log('✅ All required dependencies found!\n');
}

/**
 * Setup Cloudflare credentials
 */
async function setupCloudflareCredentials() {
  console.log('☁️  Cloudflare Setup\n');
  
  console.log('📋 You need to gather the following from your Cloudflare dashboard:');
  console.log('   1. Account ID (found in the right sidebar)');
  console.log('   2. API Token (create one with Workers:Edit permissions)');
  console.log('   3. R2 Access Key (create in R2 > Manage R2 API tokens)');
  console.log('   4. R2 Secret Key (from the same R2 API token)');
  console.log('');
  
  const continueSetup = await question('Do you have these credentials ready? (y/n): ');
  if (continueSetup.toLowerCase() !== 'y') {
    console.log('\n📖 Setup Guide:');
    console.log('   1. Go to https://dash.cloudflare.com/');
    console.log('   2. Copy your Account ID from the right sidebar');
    console.log('   3. Go to "My Profile" > "API Tokens" > "Create Token"');
    console.log('   4. Use the "Workers:Edit" template');
    console.log('   5. Go to "R2 Object Storage" > "Manage R2 API tokens"');
    console.log('   6. Create a token with Read & Write permissions');
    console.log('');
    console.log('💡 Run this script again when you have the credentials ready.');
    rl.close();
    return;
  }
  
  console.log('');
  
  // Collect credentials
  const credentials = {};
  credentials.CLOUDFLARE_ACCOUNT_ID = await question('Enter your Cloudflare Account ID: ');
  credentials.CLOUDFLARE_API_TOKEN = await question('Enter your Cloudflare API Token: ');
  credentials.CLOUDFLARE_R2_ACCESS_KEY_ID = await question('Enter your R2 Access Key ID: ');
  credentials.CLOUDFLARE_R2_SECRET_ACCESS_KEY = await question('Enter your R2 Secret Access Key: ');
  
  // Validate credentials aren't empty
  for (const [key, value] of Object.entries(credentials)) {
    if (!value || value.trim().length === 0) {
      console.error(`❌ ${key} cannot be empty`);
      rl.close();
      return;
    }
  }
  
  // Write to .env file
  let envContent = '';\n  for (const [key, value] of Object.entries(credentials)) {\n    envContent += `${key}=\"${value.trim()}\"\\n`;\n  }\n  \n  fs.writeFileSync(ENV_FILE, envContent);\n  console.log(`\\n✅ Credentials saved to ${ENV_FILE}`);\n  \n  // Test credentials\n  console.log('\\n🧪 Testing credentials...');\n  try {\n    // Test Wrangler authentication\n    execSync('wrangler whoami', { stdio: 'pipe' });\n    console.log('   ✅ Wrangler authentication successful');\n  } catch (error) {\n    console.log('   ⚠️  Wrangler authentication failed - you may need to run \"wrangler login\"');\n  }\n  \n  console.log('');\n}\n\n/**\n * Setup project directories\n */\nfunction setupProjectDirectories() {\n  console.log('📁 Setting up project directories...\\n');\n  \n  const directories = [\n    'source/videos',\n    'source/photo/contestants',\n    'processed_videos',\n    'metadata',\n    'thumbnails',\n    'logs'\n  ];\n  \n  for (const dir of directories) {\n    const fullPath = path.join(__dirname, '..', dir);\n    if (!fs.existsSync(fullPath)) {\n      fs.mkdirSync(fullPath, { recursive: true });\n      console.log(`   📂 Created: ${dir}`);\n    } else {\n      console.log(`   ✅ Exists: ${dir}`);\n    }\n  }\n  \n  console.log('');\n}\n\n/**\n * Check critical files\n */\nfunction checkCriticalFiles() {\n  console.log('📋 Checking critical files...\\n');\n  \n  const criticalFiles = [\n    {\n      path: 'metadata/contestant_info.csv',\n      description: 'Contestant database (CRITICAL - do not delete)',\n      required: true\n    },\n    {\n      path: 'mvp-processor/config/processing_config.yaml',\n      description: 'Processing configuration',\n      required: true\n    },\n    {\n      path: 'worker/index.js',\n      description: 'Cloudflare Worker',\n      required: true\n    },\n    {\n      path: 'frontend/package.json',\n      description: 'Frontend dependencies',\n      required: true\n    }\n  ];\n  \n  let hasErrors = false;\n  \n  for (const file of criticalFiles) {\n    const fullPath = path.join(__dirname, '..', file.path);\n    if (fs.existsSync(fullPath)) {\n      console.log(`   ✅ ${file.path} - ${file.description}`);\n    } else {\n      if (file.required) {\n        console.log(`   ❌ ${file.path} - ${file.description} (MISSING)`);\n        hasErrors = true;\n      } else {\n        console.log(`   ⚠️  ${file.path} - ${file.description} (optional)`);\n      }\n    }\n  }\n  \n  console.log('');\n  \n  if (hasErrors) {\n    console.error('❌ Some critical files are missing. Check the repository integrity.');\n    process.exit(1);\n  }\n}\n\n/**\n * Install dependencies\n */\nasync function installDependencies() {\n  const installFrontend = await question('Install frontend dependencies? (y/n): ');\n  \n  if (installFrontend.toLowerCase() === 'y') {\n    console.log('\\n📦 Installing frontend dependencies...');\n    try {\n      execSync('npm install', { \n        cwd: path.join(__dirname, '..', 'frontend'),\n        stdio: 'inherit'\n      });\n      console.log('   ✅ Frontend dependencies installed');\n    } catch (error) {\n      console.error('   ❌ Frontend dependency installation failed');\n    }\n  }\n  \n  const installPython = await question('Install Python dependencies? (y/n): ');\n  \n  if (installPython.toLowerCase() === 'y') {\n    console.log('\\n🐍 Installing Python dependencies...');\n    try {\n      execSync('pip install -r requirements.txt', { \n        cwd: path.join(__dirname, '..', 'mvp-processor'),\n        stdio: 'inherit'\n      });\n      console.log('   ✅ Python dependencies installed');\n    } catch (error) {\n      console.error('   ❌ Python dependency installation failed');\n      console.error('   💡 You may need to create a virtual environment first');\n    }\n  }\n  \n  console.log('');\n}\n\n/**\n * Print next steps\n */\nfunction printNextSteps() {\n  console.log('🎉 Environment setup complete!\\n');\n  \n  console.log('🚀 Next steps:');\n  console.log('   1. Add video files to source/videos/');\n  console.log('   2. Verify contestant_info.csv has your contestant data');\n  console.log('   3. Run the full pipeline: node scripts/run-full-pipeline.js');\n  console.log('');\n  \n  console.log('📚 Useful commands:');\n  console.log('   🔧 Full pipeline: node scripts/run-full-pipeline.js');\n  console.log('   🎬 Process only: node scripts/run-full-pipeline.js --process-only');\n  console.log('   ☁️  Deploy only: node scripts/run-full-pipeline.js --skip-processing');\n  console.log('   🐛 Debug mode: node scripts/run-full-pipeline.js --debug');\n  console.log('');\n  \n  console.log('📖 Documentation:');\n  console.log('   📋 System design: DESIGN.md');\n  console.log('   ⚠️  Critical notes: CLAUDE.md');\n  console.log('');\n}\n\n/**\n * Main setup function\n */\nasync function runSetup() {\n  try {\n    checkPrerequisites();\n    setupProjectDirectories();\n    checkCriticalFiles();\n    await setupCloudflareCredentials();\n    await installDependencies();\n    printNextSteps();\n    \n  } catch (error) {\n    console.error('\\n❌ Setup failed:', error.message);\n    process.exit(1);\n  } finally {\n    rl.close();\n  }\n}\n\n// Handle command line arguments\nif (require.main === module) {\n  if (process.argv.includes('--help') || process.argv.includes('-h')) {\n    console.log(`\nMV Face Recognition - Environment Setup\n\nUsage: node setup-environment.js\n\nThis script will:\n- Check system prerequisites\n- Set up Cloudflare credentials\n- Create necessary directories\n- Install dependencies\n- Verify critical files\n\nOptions:\n  -h, --help    Show this help message\n`);\n    process.exit(0);\n  }\n  \n  runSetup();\n}\n\nmodule.exports = { runSetup };