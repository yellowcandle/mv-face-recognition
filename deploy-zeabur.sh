#!/bin/bash
# Deployment script for Zeabur platform

echo "🚀 Deploying MV Face Recognition to Zeabur..."
echo ""

# Check if zeabur CLI is installed
if ! command -v zeabur &> /dev/null; then
    echo "❌ Zeabur CLI not found. Installing..."
    npm install -g @zeabur/cli
fi

# Check if user is logged in
if ! zeabur auth whoami &> /dev/null; then
    echo "🔐 Please log in to Zeabur:"
    zeabur auth login
fi

# Build and deploy backend
echo "🔧 Building and deploying backend..."
cd backend
zeabur deploy --service=backend --environment=production

# Build and deploy frontend
echo "🎨 Building and deploying frontend..."
cd ../frontend
zeabur deploy --service=frontend --environment=production

echo ""
echo "✅ Deployment completed!"
echo "🌐 Frontend: https://mv-face-recognition.zeabur.app"
echo "📡 Backend API: https://mv-face-recognition-api.zeabur.app"
echo "📊 API Docs: https://mv-face-recognition-api.zeabur.app/docs"
echo ""
echo "📝 Next steps:"
echo "1. Upload your video files to the mounted volume"
echo "2. Configure contestant photos in the admin panel"
echo "3. Start processing videos through the web interface"