#!/bin/bash
# Startup script for MV Face Recognition FastAPI Backend

echo "🚀 Starting MV Face Recognition FastAPI Backend..."

# Set environment variable to fix protobuf compatibility
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python

# Change to backend directory
cd "$(dirname "$0")/backend"

# Start the FastAPI server
echo "📡 Server will be available at: http://127.0.0.1:8000"
echo "📊 API documentation: http://127.0.0.1:8000/docs"
echo "🔄 Press Ctrl+C to stop"
echo ""

uvicorn main:app --reload --host 127.0.0.1 --port 8000