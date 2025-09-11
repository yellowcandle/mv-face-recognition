#!/bin/bash
# Startup script for MV Face Recognition Svelte Frontend

echo "🎨 Starting MV Face Recognition Svelte Frontend..."

# Change to frontend directory
cd "$(dirname "$0")/frontend"

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
fi

# Start the development server
echo "🌐 Frontend will be available at: http://localhost:5173"
echo "🔄 Press Ctrl+C to stop"
echo ""

npm run dev