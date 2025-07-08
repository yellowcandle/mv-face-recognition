#!/bin/bash

set -e  # Exit on any error

echo "🚀 MV Face Recognition - Complete Deployment Script"
echo "=================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if wrangler is installed
if ! command -v npx &> /dev/null; then
    print_error "npx is not installed. Please install Node.js and npm."
    exit 1
fi

# Check if wrangler is available
if ! npx wrangler --version &> /dev/null; then
    print_error "Wrangler is not available. Please install with: npm install -g wrangler"
    exit 1
fi

print_status "Starting deployment process..."

# Step 1: Deploy Frontend (Pages)
print_status "Step 1: Deploying Frontend to Cloudflare Pages..."
if [ -d "frontend/build" ]; then
    npx wrangler pages deploy frontend/build --project-name=mv-face-recognition
    print_success "Frontend deployed successfully!"
else
    print_warning "Frontend build directory not found. Skipping frontend deployment."
    print_warning "Run 'npm run build' in the frontend directory first."
fi

# Step 2: Deploy Backend (Python Workers)
print_status "Step 2: Deploying Backend API..."
cd backend
if [ -f "wrangler.toml" ]; then
    npx wrangler deploy
    print_success "Backend API deployed successfully!"
    cd ..
else
    print_error "Backend wrangler.toml not found!"
    cd ..
    exit 1
fi

# Step 3: Upload Metadata to KV
print_status "Step 3: Uploading metadata to KV storage..."
if [ -f "scripts/upload_metadata_to_kv.js" ]; then
    node scripts/upload_metadata_to_kv.js
    print_success "Metadata uploaded to KV successfully!"
else
    print_error "Metadata upload script not found!"
    exit 1
fi

# Step 4: Ask about video upload (due to size)
print_status "Step 4: Video Upload Option"
echo
print_warning "The processed videos are very large (~3GB total)."
print_warning "Uploading them will take significant time and bandwidth."
echo
read -p "Do you want to upload processed videos to R2? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_status "Uploading videos to R2 storage..."
    node scripts/upload_videos_to_r2.js --confirm
    print_success "Videos uploaded to R2 successfully!"
else
    print_warning "Skipping video upload. You can run it later with:"
    print_warning "node scripts/upload_videos_to_r2.js --confirm"
fi

# Step 5: Display deployment summary
echo
print_success "🎉 Deployment completed!"
echo "=========================="
echo
print_status "Deployment Summary:"
echo "• Frontend: https://29374aab.mv-face-recognition.pages.dev"
echo "• Backend API: https://mv-face-recognition-api.your-subdomain.workers.dev"
echo "• Metadata: Uploaded to KV storage"
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "• Videos: Uploaded to R2 storage"
else
    echo "• Videos: Not uploaded (run manually if needed)"
fi
echo
print_status "Next Steps:"
echo "1. Update your frontend to use the new API endpoint"
echo "2. Test the deployed application"
echo "3. Configure custom domains if needed"
echo "4. Set up any additional environment variables"
echo
print_status "Useful commands:"
echo "• View KV data: npx wrangler kv key list --binding=METADATA_KV --preview false"
echo "• View R2 objects: npx wrangler r2 object list --bucket=mv-face-recognition-videos"
echo "• View logs: npx wrangler tail"
echo
print_success "Deployment script completed successfully! 🚀" 