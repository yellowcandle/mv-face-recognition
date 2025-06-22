#!/bin/bash
# Zeabur Build Script for MV Face Recognition System

set -e

echo "🚀 Starting Zeabur build process..."

# Install Python dependencies
echo "📦 Installing dependencies..."
pip install --no-cache-dir -r requirements.txt

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p cache output source/videos source/photo/contestants fonts

# Build the package
echo "🔨 Building package..."
pip install --no-cache-dir -e .

# Run any build-time setup
echo "⚙️ Running setup..."
python -c "print('Build completed successfully!')"

echo "✅ Build process completed!"