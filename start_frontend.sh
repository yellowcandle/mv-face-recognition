#!/bin/bash
# Startup script for MV Face Recognition SvelteKit Frontend

echo "🎨 Starting MV Face Recognition SvelteKit Frontend..."

# Change to mvp-processor directory (primary frontend)
cd "$(dirname "$0")/mvp-processor"

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
fi

# Start the development server
echo "🌐 Frontend will be available at: http://localhost:3000"
echo "🔄 Press Ctrl+C to stop"
echo ""

npm run dev